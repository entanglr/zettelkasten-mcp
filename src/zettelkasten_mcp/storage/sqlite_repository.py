"""SQLite-only repository for note storage and retrieval."""
import datetime
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union

from sqlalchemy import and_, create_engine, func, or_, select, text
from sqlalchemy.orm import Session, joinedload

from zettelkasten_mcp.config import config
from zettelkasten_mcp.models.db_models_sqlite import (
    Base, DBLink, DBNote, DBTag, get_session_factory, init_db
)
from zettelkasten_mcp.models.schema import Link, LinkType, Note, NoteType, Tag
from zettelkasten_mcp.storage.base import Repository

logger = logging.getLogger(__name__)

class SQLiteNoteRepository(Repository[Note]):
    """SQLite-only repository for note storage and retrieval.
    
    This implementation stores all note data directly in SQLite, eliminating
    the need for separate markdown files. All note content, metadata, and
    relationships are stored in the database for better scalability and
    performance.
    """
    
    def __init__(self, db_path: Optional[Path] = None):
        """Initialize the repository with SQLite backend."""
        # Use provided path or default from config
        if db_path:
            self.db_path = db_path
            db_url = f"sqlite:///{db_path}"
        else:
            db_url = config.get_db_url()
            self.db_path = Path(db_url.replace("sqlite:///", ""))
        
        # Ensure database directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize database
        self.engine = init_db(db_url)
        self.session_factory = get_session_factory(self.engine)
        
        logger.info(f"Initialized SQLite repository at {self.db_path}")
    
    def create(self, item: Note) -> Note:
        """Create a new note in the database."""
        with self.session_factory() as session:
            # Check if note already exists
            existing = session.scalar(select(DBNote).where(DBNote.id == item.id))
            if existing:
                raise ValueError(f"Note with ID {item.id} already exists")
            
            # Create database note
            db_note = DBNote(
                id=item.id,
                title=item.title,
                content=item.content,
                note_type=item.note_type.value,
                created_at=item.created_at,
                updated_at=item.updated_at,
                extra_metadata=item.metadata if item.metadata else {}
            )
            session.add(db_note)
            session.flush()
            
            # Add tags
            for tag in item.tags:
                db_tag = session.scalar(select(DBTag).where(DBTag.name == tag.name))
                if not db_tag:
                    db_tag = DBTag(name=tag.name)
                    session.add(db_tag)
                    session.flush()
                db_note.tags.append(db_tag)
            
            # Add links
            for link in item.links:
                # Verify target exists
                target_exists = session.scalar(
                    select(DBNote).where(DBNote.id == link.target_id)
                )
                if target_exists:
                    db_link = DBLink(
                        source_id=item.id,
                        target_id=link.target_id,
                        link_type=link.link_type.value,
                        description=link.description,
                        created_at=link.created_at or datetime.datetime.now()
                    )
                    session.add(db_link)
            
            session.commit()
            
            # Return the created note
            return self._db_note_to_note(db_note)
    
    def read(self, id: str) -> Optional[Note]:
        """Read a note from the database by ID."""
        with self.session_factory() as session:
            db_note = session.scalar(
                select(DBNote)
                .options(
                    joinedload(DBNote.tags),
                    joinedload(DBNote.outgoing_links).joinedload(DBLink.target),
                    joinedload(DBNote.incoming_links).joinedload(DBLink.source)
                )
                .where(DBNote.id == id)
            )
            
            if not db_note:
                return None
            
            return self._db_note_to_note(db_note)
    
    def get(self, id: str) -> Optional[Note]:
        """Get a note by ID (alias for read)."""
        return self.read(id)
    
    def update(self, item: Note) -> Note:
        """Update an existing note in the database."""
        with self.session_factory() as session:
            db_note = session.scalar(select(DBNote).where(DBNote.id == item.id))
            if not db_note:
                raise ValueError(f"Note with ID {item.id} not found")
            
            # Update core fields
            db_note.title = item.title
            db_note.content = item.content
            db_note.note_type = item.note_type.value
            db_note.updated_at = datetime.datetime.now()
            db_note.extra_metadata = item.metadata if item.metadata else {}
            
            # Update tags
            # Clear existing tags
            db_note.tags.clear()
            # Add new tags
            for tag in item.tags:
                db_tag = session.scalar(select(DBTag).where(DBTag.name == tag.name))
                if not db_tag:
                    db_tag = DBTag(name=tag.name)
                    session.add(db_tag)
                    session.flush()
                db_note.tags.append(db_tag)
            
            # Update links
            # Remove existing outgoing links
            session.query(DBLink).filter_by(source_id=item.id).delete()
            # Add new links
            for link in item.links:
                # Verify target exists
                target_exists = session.scalar(
                    select(DBNote).where(DBNote.id == link.target_id)
                )
                if target_exists:
                    db_link = DBLink(
                        source_id=item.id,
                        target_id=link.target_id,
                        link_type=link.link_type.value,
                        description=link.description,
                        created_at=link.created_at or datetime.datetime.now()
                    )
                    session.add(db_link)
            
            session.commit()
            
            # Reload and return the updated note
            session.refresh(db_note)
            return self._db_note_to_note(db_note)
    
    def delete(self, id: str) -> None:
        """Delete a note from the database."""
        with self.session_factory() as session:
            db_note = session.scalar(select(DBNote).where(DBNote.id == id))
            if not db_note:
                raise ValueError(f"Note with ID {id} does not exist")
            
            session.delete(db_note)
            session.commit()
    
    def get_all(self) -> List[Note]:
        """Get all notes from the database."""
        return self.list(limit=10000)  # Large limit to get all notes
    
    def list(self, **kwargs) -> List[Note]:
        """List notes from the database with optional filtering."""
        limit = kwargs.get("limit", 100)
        offset = kwargs.get("offset", 0)
        note_type = kwargs.get("note_type")
        tag = kwargs.get("tag")
        
        with self.session_factory() as session:
            query = select(DBNote).options(
                joinedload(DBNote.tags),
                joinedload(DBNote.outgoing_links)
            )
            
            # Apply filters
            if note_type:
                query = query.where(DBNote.note_type == note_type)
            
            if tag:
                query = query.join(DBNote.tags).where(DBTag.name == tag)
            
            # Apply pagination
            query = query.order_by(DBNote.updated_at.desc())
            query = query.limit(limit).offset(offset)
            
            db_notes = session.scalars(query).unique().all()
            
            return [self._db_note_to_note(db_note) for db_note in db_notes]
    
    def search(self, query: str, **kwargs) -> List[Note]:
        """Search for notes matching the query."""
        limit = kwargs.get("limit", 50)
        search_title = kwargs.get("search_title", True)
        search_content = kwargs.get("search_content", True)
        search_tags = kwargs.get("search_tags", True)
        
        with self.session_factory() as session:
            # Build search conditions
            conditions = []
            
            if search_title:
                conditions.append(DBNote.title.ilike(f"%{query}%"))
            
            if search_content:
                conditions.append(DBNote.content.ilike(f"%{query}%"))
            
            if search_tags:
                # Subquery for tag search
                tag_subquery = (
                    select(DBNote.id)
                    .join(DBNote.tags)
                    .where(DBTag.name.ilike(f"%{query}%"))
                )
                conditions.append(DBNote.id.in_(tag_subquery))
            
            if not conditions:
                return []
            
            # Execute search
            search_query = (
                select(DBNote)
                .options(
                    joinedload(DBNote.tags),
                    joinedload(DBNote.outgoing_links)
                )
                .where(or_(*conditions))
                .order_by(DBNote.updated_at.desc())
                .limit(limit)
            )
            
            db_notes = session.scalars(search_query).unique().all()
            
            return [self._db_note_to_note(db_note) for db_note in db_notes]
    
    def find_by_tag(self, tag_name: str) -> List[Note]:
        """Find all notes with a specific tag."""
        with self.session_factory() as session:
            db_notes = session.scalars(
                select(DBNote)
                .options(
                    joinedload(DBNote.tags),
                    joinedload(DBNote.outgoing_links)
                )
                .join(DBNote.tags)
                .where(DBTag.name == tag_name)
                .order_by(DBNote.updated_at.desc())
            ).unique().all()
            
            return [self._db_note_to_note(db_note) for db_note in db_notes]
    
    def find_linked_notes(self, note_id: str, direction: str = "both") -> List[Note]:
        """Find notes linked to/from a specific note."""
        with self.session_factory() as session:
            linked_ids = set()
            
            # Get outgoing links
            if direction in ["outgoing", "both"]:
                outgoing = session.scalars(
                    select(DBLink.target_id)
                    .where(DBLink.source_id == note_id)
                ).all()
                linked_ids.update(outgoing)
            
            # Get incoming links
            if direction in ["incoming", "both"]:
                incoming = session.scalars(
                    select(DBLink.source_id)
                    .where(DBLink.target_id == note_id)
                ).all()
                linked_ids.update(incoming)
            
            if not linked_ids:
                return []
            
            # Fetch the linked notes
            db_notes = session.scalars(
                select(DBNote)
                .options(
                    joinedload(DBNote.tags),
                    joinedload(DBNote.outgoing_links)
                )
                .where(DBNote.id.in_(linked_ids))
                .order_by(DBNote.updated_at.desc())
            ).unique().all()
            
            return [self._db_note_to_note(db_note) for db_note in db_notes]
    
    def get_tags(self) -> List[Dict[str, Any]]:
        """Get all tags with note counts."""
        with self.session_factory() as session:
            results = session.execute(
                select(
                    DBTag.name,
                    func.count(DBNote.id).label("count")
                )
                .select_from(DBTag)
                .join(DBTag.notes)
                .group_by(DBTag.name)
                .order_by(func.count(DBNote.id).desc())
            ).all()
            
            return [{"name": name, "count": count} for name, count in results]
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get repository statistics."""
        with self.session_factory() as session:
            total_notes = session.scalar(select(func.count(DBNote.id)))
            total_tags = session.scalar(select(func.count(DBTag.id)))
            total_links = session.scalar(select(func.count(DBLink.id)))
            
            # Notes by type
            type_counts = session.execute(
                select(
                    DBNote.note_type,
                    func.count(DBNote.id).label("count")
                )
                .group_by(DBNote.note_type)
            ).all()
            
            notes_by_type = {note_type: count for note_type, count in type_counts}
            
            return {
                "total_notes": total_notes or 0,
                "total_tags": total_tags or 0,
                "total_links": total_links or 0,
                "notes_by_type": notes_by_type,
                "storage_type": "sqlite"
            }
    
    def backup(self, backup_path: Path) -> None:
        """Create a backup of the SQLite database."""
        import shutil
        
        # Ensure backup directory exists
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Use SQLite backup API for consistency
        with self.engine.connect() as conn:
            conn.execute(text("VACUUM"))  # Optimize before backup
            
        # Copy the database file
        shutil.copy2(self.db_path, backup_path)
        logger.info(f"Database backed up to {backup_path}")
    
    def restore(self, backup_path: Path) -> None:
        """Restore the SQLite database from a backup."""
        import shutil
        
        if not backup_path.exists():
            raise ValueError(f"Backup file {backup_path} does not exist")
        
        # Close all connections
        self.engine.dispose()
        
        # Replace the database file
        shutil.copy2(backup_path, self.db_path)
        
        # Reinitialize connection
        self.engine = init_db(f"sqlite:///{self.db_path}")
        self.session_factory = get_session_factory(self.engine)
        
        logger.info(f"Database restored from {backup_path}")
    
    def _db_note_to_note(self, db_note: DBNote) -> Note:
        """Convert a database note to a domain note."""
        # Convert tags
        tags = [Tag(name=db_tag.name) for db_tag in db_note.tags]
        
        # Convert links
        links = []
        for db_link in db_note.outgoing_links:
            links.append(
                Link(
                    source_id=db_link.source_id,
                    target_id=db_link.target_id,
                    link_type=LinkType(db_link.link_type),
                    description=db_link.description,
                    created_at=db_link.created_at
                )
            )
        
        # Create note
        return Note(
            id=db_note.id,
            title=db_note.title,
            content=db_note.content,
            note_type=NoteType(db_note.note_type),
            tags=tags,
            links=links,
            created_at=db_note.created_at,
            updated_at=db_note.updated_at,
            metadata=db_note.extra_metadata or {}
        )
    
    def optimize(self) -> None:
        """Optimize the SQLite database."""
        with self.engine.connect() as conn:
            # Run VACUUM to reclaim space and defragment
            conn.execute(text("VACUUM"))
            # Analyze to update query planner statistics
            conn.execute(text("ANALYZE"))
            logger.info("Database optimized")
    
    def verify_integrity(self) -> bool:
        """Verify database integrity."""
        with self.engine.connect() as conn:
            result = conn.execute(text("PRAGMA integrity_check")).scalar()
            is_ok = result == "ok"
            if is_ok:
                logger.info("Database integrity check passed")
            else:
                logger.error(f"Database integrity check failed: {result}")
            return is_ok