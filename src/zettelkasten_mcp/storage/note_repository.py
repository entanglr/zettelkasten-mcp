"""Repository for note storage and retrieval."""
import datetime
import logging
import os
import threading
from pathlib import Path
from typing import Any, List, Optional, Union

import frontmatter
from sqlalchemy import and_, func, or_, select, text
from sqlalchemy.orm import joinedload

from zettelkasten_mcp.config import config
from zettelkasten_mcp.models.db_models import (DBLink, DBNote, DBTag,
                                            get_session_factory, init_db)
from zettelkasten_mcp.models.schema import Link, LinkType, Note, NoteType, Tag
from zettelkasten_mcp.storage.base import Repository

logger = logging.getLogger(__name__)

class NoteRepository(Repository[Note]):
    """Repository for note storage and retrieval.
    This implements a dual storage approach:
    1. Notes are stored as Markdown files on disk for human readability and editing
    2. MySQL database is used for indexing and efficient querying
    The file system is the source of truth - database is rebuilt from files if needed.
    """
    
    def __init__(self, notes_dir: Optional[Path] = None):
        """Initialize the repository."""
        self.notes_dir = (
            config.get_absolute_path(notes_dir)
            if notes_dir
            else config.get_absolute_path(config.notes_dir)
        )
        
        # Ensure directories exist
        self.notes_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize database
        self.engine = init_db()
        self.session_factory = get_session_factory(self.engine)
        
        # File access lock
        self.file_lock = threading.RLock()
        
        # Initialize by rebuilding index if needed
        self.rebuild_index_if_needed()
    
    def rebuild_index_if_needed(self) -> None:
        """Rebuild the database index from files if needed."""
        # Count notes in database
        with self.session_factory() as session:
            db_count = session.scalar(select(text("COUNT(*)")).select_from(DBNote))
        
        # Count note files
        file_count = len(list(self.notes_dir.glob("*.md")))
        
        # Rebuild if counts don't match
        if db_count != file_count:
            self.rebuild_index()
    
    def rebuild_index(self) -> None:
        """Rebuild the database index from all markdown files."""
        # Clear the database first
        with self.session_factory() as session:
            # Delete all records from link table
            session.execute(text("DELETE FROM links"))
            # Delete all records from note_tags table
            session.execute(text("DELETE FROM note_tags"))
            # Delete all records from notes table
            session.execute(text("DELETE FROM notes"))
            # Commit changes
            session.commit()
        
        # Read all markdown files
        note_files = list(self.notes_dir.glob("*.md"))
        
        # Process files in batches to avoid memory issues with large Zettelkasten systems
        batch_size = 100
        for i in range(0, len(note_files), batch_size):
            batch = note_files[i:i + batch_size]
            notes = []
            
            # Read files
            for file_path in batch:
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    note = self._parse_note_from_markdown(content)
                    notes.append(note)
                except Exception as e:
                    logger.error(f"Error processing file {file_path}: {e}")
            
            # Index notes
            for note in notes:
                self._index_note(note)
    
    def _parse_note_from_markdown(self, content: str) -> Note:
        """Parse a note from markdown content."""
        # Parse frontmatter
        post = frontmatter.loads(content)
        metadata = post.metadata
        
        # Extract ID from metadata or filename
        note_id = metadata.get("id")
        if not note_id:
            raise ValueError("Note ID missing from frontmatter")
        
        # Extract title from metadata or first heading
        title = metadata.get("title")
        if not title:
            # Try to extract from content
            lines = post.content.strip().split("\n")
            for line in lines:
                if line.startswith("# "):
                    title = line[2:].strip()
                    break
        if not title:
            raise ValueError("Note title missing from frontmatter or content")
        
        # Extract note type
        note_type_str = metadata.get("type", NoteType.PERMANENT.value)
        try:
            note_type = NoteType(note_type_str)
        except ValueError:
            note_type = NoteType.PERMANENT
        
        # Extract tags
        tags_str = metadata.get("tags", "")
        if isinstance(tags_str, str):
            tag_names = [t.strip() for t in tags_str.split(",") if t.strip()]
        elif isinstance(tags_str, list):
            tag_names = [str(t).strip() for t in tags_str if str(t).strip()]
        else:
            tag_names = []
        tags = [Tag(name=name) for name in tag_names]
        
        # Extract links
        links = []
        links_section = False
        for line in post.content.split("\n"):
            line = line.strip()
            # Check if we're in the links section
            if line.startswith("## Links"):
                links_section = True
                continue
            if links_section and line.startswith("## "):
                # We've reached the next section
                links_section = False
                continue
            if links_section and line.startswith("- "):
                # Parse link line
                try:
                    # Example format: - reference [[202101010000]] Optional description
                    line_content = line.strip()
                    if "[[" in line_content and "]]" in line_content:
                        # Split the line at the [[ delimiter
                        parts = line_content.split("[[", 1)
                        # Extract the link type from before [[
                        link_type_str = parts[0].strip()
                        # Remove the leading "- " from the link type string
                        if link_type_str.startswith("- "):
                            link_type_str = link_type_str[2:].strip()
                        # Extract target ID and description
                        id_and_description = parts[1].split("]]", 1)
                        target_id = id_and_description[0].strip()
                        description = None
                        if len(id_and_description) > 1:
                            description = id_and_description[1].strip()
                        # Validate link type
                        try:
                            link_type = LinkType(link_type_str)
                        except ValueError:
                            # If not a valid type, default to reference
                            link_type = LinkType.REFERENCE
                        links.append(
                            Link(
                                source_id=note_id,
                                target_id=target_id,
                                link_type=link_type,
                                description=description,
                                created_at=datetime.datetime.now()
                            )
                        )
                except Exception as e:
                    logger.error(f"Error parsing link: {line} - {e}")
        
        # Extract timestamps
        created_str = metadata.get("created")
        created_at = (
            datetime.datetime.fromisoformat(created_str)
            if created_str
            else datetime.datetime.now()
        )
        updated_str = metadata.get("updated")
        updated_at = (
            datetime.datetime.fromisoformat(updated_str)
            if updated_str
            else created_at
        )
        
        # Create note object
        return Note(
            id=note_id,
            title=title,
            content=post.content,
            note_type=note_type,
            tags=tags,
            links=links,
            created_at=created_at,
            updated_at=updated_at,
            metadata={k: v for k, v in metadata.items() 
                     if k not in ["id", "title", "type", "tags", "created", "updated"]}
        )
    
    def _index_note(self, note: Note) -> None:
        """Index a note in the database."""
        with self.session_factory() as session:
            # Create or update note
            db_note = session.scalar(select(DBNote).where(DBNote.id == note.id))
            if db_note:
                # Update existing note
                db_note.title = note.title
                db_note.content = note.content
                db_note.note_type = note.note_type.value
                db_note.updated_at = note.updated_at
                # Clear existing links and tags to rebuild them
                session.execute(text(f"DELETE FROM links WHERE source_id = '{note.id}'"))
                session.execute(text(f"DELETE FROM note_tags WHERE note_id = '{note.id}'"))
            else:
                # Create new note
                db_note = DBNote(
                    id=note.id,
                    title=note.title,
                    content=note.content,
                    note_type=note.note_type.value,
                    created_at=note.created_at,
                    updated_at=note.updated_at
                )
                session.add(db_note)
                
            session.flush()  # Flush to get the note ID
            
            # Add tags
            for tag in note.tags:
                # Check if tag exists
                db_tag = session.scalar(
                    select(DBTag).where(DBTag.name == tag.name)
                )
                if not db_tag:
                    db_tag = DBTag(name=tag.name)
                    session.add(db_tag)
                    session.flush()  # Flush to get the tag ID
                db_note.tags.append(db_tag)
            
            # Add links
            for link in note.links:
                # Check if this link already exists in the database
                existing_link = session.scalar(
                    select(DBLink).where(
                        (DBLink.source_id == link.source_id) &
                        (DBLink.target_id == link.target_id) &
                        (DBLink.link_type == link.link_type.value)
                    )
                )
                
                if not existing_link:
                    db_link = DBLink(
                        source_id=link.source_id,
                        target_id=link.target_id,
                        link_type=link.link_type.value,
                        description=link.description,
                        created_at=link.created_at
                    )
                    session.add(db_link)
            
            # Commit changes
            session.commit()

    def _note_to_markdown(self, note: Note) -> str:
        """Convert a note to markdown with frontmatter."""
        # Create frontmatter
        metadata = {
            "id": note.id,
            "title": note.title,
            "type": note.note_type.value,
            "tags": [tag.name for tag in note.tags],
            "created": note.created_at.isoformat(),
            "updated": note.updated_at.isoformat()
        }
        # Add any custom metadata
        metadata.update(note.metadata)
        
        # Check if content already starts with the title
        title_heading = f"# {note.title}"
        if note.content.strip().startswith(title_heading):
            content = note.content
        else:
            content = f"{title_heading}\n\n{note.content}"
        
        # Remove existing Links section(s)
        content_parts = []
        skip_section = False
        for line in content.split("\n"):
            if line.strip() == "## Links":
                skip_section = True
                continue
            elif skip_section and line.startswith("## "):
                skip_section = False
            
            if not skip_section:
                content_parts.append(line)
        
        # Reconstruct the content without the Links sections
        content = "\n".join(content_parts).rstrip()
        
        # Add links section (with deduplication)
        if note.links:
            unique_links = {}  # Use dict to deduplicate
            for link in note.links:
                key = f"{link.target_id}:{link.link_type.value}"
                unique_links[key] = link
            content += "\n\n## Links\n"
            for link in unique_links.values():
                desc = f" {link.description}" if link.description else ""
                content += f"- {link.link_type.value} [[{link.target_id}]]{desc}\n"
        
        # Create markdown with frontmatter
        post = frontmatter.Post(content, **metadata)
        return frontmatter.dumps(post)

    def create(self, note: Note) -> Note:
        """Create a new note."""
        # Ensure the note has an ID
        if not note.id:
            from zettelkasten_mcp.models.schema import generate_id
            note.id = generate_id()
        
        # Convert note to markdown
        markdown = self._note_to_markdown(note)
        
        # Write to file
        file_path = self.notes_dir / f"{note.id}.md"
        try:
            with self.file_lock:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(markdown)
        except IOError as e:
            raise IOError(f"Failed to write note to {file_path}: {e}")
        
        # Index in database
        self._index_note(note)
        return note
    
    def get(self, id: str) -> Optional[Note]:
        """Get a note by ID.
        
        Args:
            id: The ISO 8601 formatted identifier of the note
            
        Returns:
            Note object if found, None otherwise
        """
        file_path = self.notes_dir / f"{id}.md"
        if not file_path.exists():
            return None
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            return self._parse_note_from_markdown(content)
        except Exception as e:
            raise IOError(f"Failed to read note {id}: {e}")
    
    def get_by_title(self, title: str) -> Optional[Note]:
        """Get a note by title."""
        with self.session_factory() as session:
            db_note = session.scalar(
                select(DBNote).where(DBNote.title == title)
            )
            if not db_note:
                return None
            return self.get(db_note.id)
    
    def get_all(self) -> List[Note]:
        """Get all notes."""
        with self.session_factory() as session:
            # Get all notes with eager loading of tags and links
            query = select(DBNote).options(
                joinedload(DBNote.tags),
                joinedload(DBNote.outgoing_links),
                joinedload(DBNote.incoming_links)
            )
            result = session.execute(query)
            # Apply unique() to handle the duplicate rows from eager loading
            db_notes = result.unique().scalars().all()
            
            # Process notes in batches to reduce memory usage
            batch_size = 50
            all_notes = []
            # Create batches of note IDs
            note_ids = [note.id for note in db_notes]
            for i in range(0, len(note_ids), batch_size):
                batch_ids = note_ids[i:i + batch_size]
                note_batch = []
                # Process each note in the batch
                for note_id in batch_ids:
                    try:
                        note = self.get(note_id)
                        if note:
                            note_batch.append(note)
                    except Exception as e:
                        logger.error(f"Error loading note {note_id}: {e}")
                all_notes.extend(note_batch)
            return all_notes
    
    def update(self, note: Note) -> Note:
        """Update a note."""
        # Check if note exists
        existing_note = self.get(note.id)
        if not existing_note:
            raise ValueError(f"Note with ID {note.id} does not exist")
        
        # Update timestamp
        note.updated_at = datetime.datetime.now()
        
        # Convert note to markdown
        markdown = self._note_to_markdown(note)
        
        # Write to file
        file_path = self.notes_dir / f"{note.id}.md"
        try:
            with self.file_lock:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(markdown)
        except IOError as e:
            raise IOError(f"Failed to write note to {file_path}: {e}")
        
        try:
            # Re-index in database
            with self.session_factory() as session:
                # Get the existing note from the database
                db_note = session.scalar(select(DBNote).where(DBNote.id == note.id))
                if db_note:
                    # Update the note fields
                    db_note.title = note.title
                    db_note.content = note.content
                    db_note.note_type = note.note_type.value
                    db_note.updated_at = note.updated_at
                    
                    # Clear existing tags
                    db_note.tags = []
                    
                    # Add tags
                    for tag in note.tags:
                        # Check if tag exists
                        db_tag = session.scalar(
                            select(DBTag).where(DBTag.name == tag.name)
                        )
                        if not db_tag:
                            db_tag = DBTag(name=tag.name)
                            session.add(db_tag)
                            session.flush()
                        db_note.tags.append(db_tag)
                    
                    # For links, we'll delete existing links and add the new ones
                    session.execute(text(f"DELETE FROM links WHERE source_id = '{note.id}'"))
                    
                    # Add new links
                    for link in note.links:
                        db_link = DBLink(
                            source_id=link.source_id,
                            target_id=link.target_id,
                            link_type=link.link_type.value,
                            description=link.description,
                            created_at=link.created_at
                        )
                        session.add(db_link)
                    
                    session.commit()
                else:
                    # This would be unusual, but handle it by creating a new database record
                    self._index_note(note)
        except Exception as e:
            # Log and re-raise the exception
            logger.error(f"Failed to update note in database: {e}")
            raise
        
        return note
    
    def delete(self, id: str) -> None:
        """Delete a note by ID."""
        # Check if note exists
        file_path = self.notes_dir / f"{id}.md"
        if not file_path.exists():
            raise ValueError(f"Note with ID {id} does not exist")
        
        # Delete from file system
        try:
            with self.file_lock:
                os.remove(file_path)
        except IOError as e:
            raise IOError(f"Failed to delete note {id}: {e}")
        
        # Delete from database
        with self.session_factory() as session:
            # Delete note and its relationships
            session.execute(text(f"DELETE FROM links WHERE source_id = '{id}' OR target_id = '{id}'"))
            session.execute(text(f"DELETE FROM note_tags WHERE note_id = '{id}'"))
            session.execute(text(f"DELETE FROM notes WHERE id = '{id}'"))
            session.commit()
    
    def search(self, **kwargs: Any) -> List[Note]:
        """Search for notes based on criteria."""
        with self.session_factory() as session:
            query = select(DBNote).options(
                joinedload(DBNote.tags),
                joinedload(DBNote.outgoing_links),
                joinedload(DBNote.incoming_links)
            )
            # Process search criteria
            if "content" in kwargs:
                search_term = kwargs['content']
                # Search in both content and title since content might include the title
                query = query.where(
                    or_(
                        DBNote.content.like(f"%{search_term}%"),
                        DBNote.title.like(f"%{search_term}%")
                    )
                )
            if "title" in kwargs:
                search_title = kwargs['title']
                # query = query.where(DBNote.title.like(f"%{search_title}%"))
                # Use case-insensitive search with func.lower()
                query = query.where(func.lower(DBNote.title).like(f"%{search_title.lower()}%"))
            if "note_type" in kwargs:
                note_type = (
                    kwargs["note_type"].value
                    if isinstance(kwargs["note_type"], NoteType)
                    else kwargs["note_type"]
                )
                query = query.where(DBNote.note_type == note_type)
            if "tag" in kwargs:
                tag_name = kwargs["tag"]
                query = query.join(DBNote.tags).where(DBTag.name == tag_name)
            if "tags" in kwargs:
                tag_names = kwargs["tags"]
                if isinstance(tag_names, list):
                    query = query.join(DBNote.tags).where(DBTag.name.in_(tag_names))
            if "linked_to" in kwargs:
                target_id = kwargs["linked_to"]
                query = query.join(DBNote.outgoing_links).where(DBLink.target_id == target_id)
            if "linked_from" in kwargs:
                source_id = kwargs["linked_from"]
                query = query.join(DBNote.incoming_links).where(DBLink.source_id == source_id)
            if "created_after" in kwargs:
                query = query.where(DBNote.created_at >= kwargs["created_after"])
            if "created_before" in kwargs:
                query = query.where(DBNote.created_at <= kwargs["created_before"])
            if "updated_after" in kwargs:
                query = query.where(DBNote.updated_at >= kwargs["updated_after"])
            if "updated_before" in kwargs:
                query = query.where(DBNote.updated_at <= kwargs["updated_before"])
            # Execute query and apply unique() to handle duplicates from joins
            result = session.execute(query)
            db_notes = result.unique().scalars().all()
        # Load notes from file system
        notes = []
        for db_note in db_notes:
            note = self.get(db_note.id)
            if note:
                notes.append(note)
        return notes
    
    def find_by_tag(self, tag: Union[str, Tag]) -> List[Note]:
        """Find notes by tag."""
        tag_name = tag.name if isinstance(tag, Tag) else tag
        return self.search(tag=tag_name)
    
    def find_linked_notes(self, note_id: str, direction: str = "outgoing") -> List[Note]:
        """Find notes linked to/from this note."""
        with self.session_factory() as session:
            if direction == "outgoing":
                # Find notes that this note links to
                query = (
                    select(DBNote)
                    .join(DBLink, DBNote.id == DBLink.target_id)
                    .where(DBLink.source_id == note_id)
                    .options(
                        joinedload(DBNote.tags),
                        joinedload(DBNote.outgoing_links),
                        joinedload(DBNote.incoming_links)
                    )
                )
            elif direction == "incoming":
                # Find notes that link to this note
                query = (
                    select(DBNote)
                    .join(DBLink, DBNote.id == DBLink.source_id)
                    .where(DBLink.target_id == note_id)
                    .options(
                        joinedload(DBNote.tags),
                        joinedload(DBNote.outgoing_links),
                        joinedload(DBNote.incoming_links)
                    )
                )
            elif direction == "both":
                # Find both directions
                query = (
                    select(DBNote)
                    .join(
                        DBLink,
                        or_(
                            and_(DBNote.id == DBLink.target_id, DBLink.source_id == note_id),
                            and_(DBNote.id == DBLink.source_id, DBLink.target_id == note_id)
                        )
                    )
                    .options(
                        joinedload(DBNote.tags),
                        joinedload(DBNote.outgoing_links),
                        joinedload(DBNote.incoming_links)
                    )
                )
            else:
                raise ValueError(f"Invalid direction: {direction}. Use 'outgoing', 'incoming', or 'both'")
            
            result = session.execute(query)
            # Apply unique() to handle the duplicate rows from eager loading
            db_notes = result.unique().scalars().all()
            
            # Convert to model Notes
            notes = []
            for db_note in db_notes:
                note = self.get(db_note.id)
                if note:
                    notes.append(note)
            return notes
    
    def get_all_tags(self) -> List[Tag]:
        """Get all tags in the system."""
        with self.session_factory() as session:
            result = session.execute(select(DBTag))
            db_tags = result.scalars().all()
        return [Tag(name=tag.name) for tag in db_tags]
