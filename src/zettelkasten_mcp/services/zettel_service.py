"""Service layer for Zettelkasten operations."""
import datetime
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from zettelkasten_mcp.models.schema import (
    BatchOperationResult, BatchResult, LinkType, 
    Note, NoteType, Tag, NoteData, NoteUpdateData, TagOperationData, LinkData
)

from zettelkasten_mcp.storage.note_repository import NoteRepository

logger = logging.getLogger(__name__)

class ZettelService:
    """Service for managing Zettelkasten notes."""
    
    def __init__(self, repository: Optional[NoteRepository] = None):
        """Initialize the service."""
        self.repository = repository or NoteRepository()
    
    def initialize(self) -> None:
        """Initialize the service and dependencies."""
        # Nothing to do here for synchronous implementation
        # The repository is initialized in its constructor
        pass
    
    def create_note(
        self,
        title: str,
        content: str,
        note_type: NoteType = NoteType.PERMANENT,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Note:
        """Create a new note."""
        if not title:
            raise ValueError("Title is required")
        if not content:
            raise ValueError("Content is required")
        
        # Create note object
        note = Note(
            title=title,
            content=content,
            note_type=note_type,
            tags=[Tag(name=tag) for tag in (tags or [])],
            metadata=metadata or {}
        )
        
        # Save to repository
        return self.repository.create(note)
    
    def get_note(self, note_id: str) -> Optional[Note]:
        """Retrieve a note by ID."""
        return self.repository.get(note_id)
    
    def get_note_by_title(self, title: str) -> Optional[Note]:
        """Retrieve a note by title."""
        return self.repository.get_by_title(title)
    
    def update_note(
        self,
        note_id: str,
        title: Optional[str] = None,
        content: Optional[str] = None,
        note_type: Optional[NoteType] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Note:
        """Update an existing note."""
        note = self.repository.get(note_id)
        if not note:
            raise ValueError(f"Note with ID {note_id} not found")
        
        # Update fields
        if title is not None:
            note.title = title
        if content is not None:
            note.content = content
        if note_type is not None:
            note.note_type = note_type
        if tags is not None:
            note.tags = [Tag(name=tag) for tag in tags]
        if metadata is not None:
            note.metadata = metadata
        
        note.updated_at = datetime.datetime.now()
        
        # Save to repository
        return self.repository.update(note)
    
    def delete_note(self, note_id: str) -> None:
        """Delete a note."""
        self.repository.delete(note_id)
    
    def get_all_notes(self) -> List[Note]:
        """Get all notes."""
        return self.repository.get_all()
    
    def search_notes(self, **kwargs: Any) -> List[Note]:
        """Search for notes based on criteria."""
        return self.repository.search(**kwargs)
    
    def get_notes_by_tag(self, tag: str) -> List[Note]:
        """Get notes by tag."""
        return self.repository.find_by_tag(tag)
    
    def add_tag_to_note(self, note_id: str, tag: str) -> Note:
        """Add a tag to a note."""
        note = self.repository.get(note_id)
        if not note:
            raise ValueError(f"Note with ID {note_id} not found")
        note.add_tag(tag)
        return self.repository.update(note)
    
    def remove_tag_from_note(self, note_id: str, tag: str) -> Note:
        """Remove a tag from a note."""
        note = self.repository.get(note_id)
        if not note:
            raise ValueError(f"Note with ID {note_id} not found")
        note.remove_tag(tag)
        return self.repository.update(note)
    
    def get_all_tags(self) -> List[Tag]:
        """Get all tags in the system."""
        return self.repository.get_all_tags()
    
    def create_link(
        self,
        source_id: str,
        target_id: str,
        link_type: LinkType = LinkType.REFERENCE,
        description: Optional[str] = None,
        bidirectional: bool = False,
        bidirectional_type: Optional[LinkType] = None
    ) -> Tuple[Note, Optional[Note]]:
        """Create a link between notes with proper bidirectional semantics.
        
        Args:
            source_id: ID of the source note
            target_id: ID of the target note
            link_type: Type of link from source to target
            description: Optional description of the link
            bidirectional: Whether to create a link in both directions
            bidirectional_type: Optional custom link type for the reverse direction
                If not provided, an appropriate inverse relation will be used
        
        Returns:
            Tuple of (source_note, target_note or None)
        """
        source_note = self.repository.get(source_id)
        if not source_note:
            raise ValueError(f"Source note with ID {source_id} not found")
        target_note = self.repository.get(target_id)
        if not target_note:
            raise ValueError(f"Target note with ID {target_id} not found")
        
        # Check if this link already exists before attempting to add it
        for link in source_note.links:
            if link.target_id == target_id and link.link_type == link_type:
                # Link already exists, no need to add it again
                if not bidirectional:
                    return source_note, None
                break
        else:
            # Only add the link if it doesn't exist
            source_note.add_link(target_id, link_type, description)
            source_note = self.repository.update(source_note)
        
        # If bidirectional, add link from target to source with appropriate semantics
        reverse_note = None
        if bidirectional:
            # If no explicit bidirectional type is provided, determine appropriate inverse
            if bidirectional_type is None:
                # Map link types to their semantic inverses
                inverse_map = {
                    LinkType.REFERENCE: LinkType.REFERENCE,
                    LinkType.EXTENDS: LinkType.EXTENDED_BY,
                    LinkType.EXTENDED_BY: LinkType.EXTENDS,
                    LinkType.REFINES: LinkType.REFINED_BY,
                    LinkType.REFINED_BY: LinkType.REFINES,
                    LinkType.CONTRADICTS: LinkType.CONTRADICTED_BY,
                    LinkType.CONTRADICTED_BY: LinkType.CONTRADICTS,
                    LinkType.QUESTIONS: LinkType.QUESTIONED_BY,
                    LinkType.QUESTIONED_BY: LinkType.QUESTIONS,
                    LinkType.SUPPORTS: LinkType.SUPPORTED_BY,
                    LinkType.SUPPORTED_BY: LinkType.SUPPORTS,
                    LinkType.RELATED: LinkType.RELATED
                }
                bidirectional_type = inverse_map.get(link_type, link_type)
            
            # Check if the reverse link already exists before adding it
            for link in target_note.links:
                if link.target_id == source_id and link.link_type == bidirectional_type:
                    # Reverse link already exists, no need to add it again
                    return source_note, target_note
                    
            # Only add the reverse link if it doesn't exist
            target_note.add_link(source_id, bidirectional_type, description)
            reverse_note = self.repository.update(target_note)
        
        return source_note, reverse_note
    
    def remove_link(
        self,
        source_id: str,
        target_id: str,
        link_type: Optional[LinkType] = None,
        bidirectional: bool = False
    ) -> Tuple[Note, Optional[Note]]:
        """Remove a link between notes."""
        source_note = self.repository.get(source_id)
        if not source_note:
            raise ValueError(f"Source note with ID {source_id} not found")
        
        # Remove link from source to target
        source_note.remove_link(target_id, link_type)
        source_note = self.repository.update(source_note)
        
        # If bidirectional, remove link from target to source
        reverse_note = None
        if bidirectional:
            target_note = self.repository.get(target_id)
            if target_note:
                target_note.remove_link(source_id, link_type)
                reverse_note = self.repository.update(target_note)
        
        return source_note, reverse_note
    
    def get_linked_notes(
        self, note_id: str, direction: str = "outgoing"
    ) -> List[Note]:
        """Get notes linked to/from a note."""
        note = self.repository.get(note_id)
        if not note:
            raise ValueError(f"Note with ID {note_id} not found")
        return self.repository.find_linked_notes(note_id, direction)
    
    def rebuild_index(self) -> None:
        """Rebuild the database index from files."""
        self.repository.rebuild_index()
    
    def export_note(self, note_id: str, format: str = "markdown") -> str:
        """Export a note in the specified format."""
        note = self.repository.get(note_id)
        if not note:
            raise ValueError(f"Note with ID {note_id} not found")
        
        if format.lower() == "markdown":
            return note.to_markdown()
        else:
            raise ValueError(f"Unsupported export format: {format}")
    
    def find_similar_notes(self, note_id: str, threshold: float = 0.5) -> List[Tuple[Note, float]]:
        """Find notes similar to the given note based on shared tags and links."""
        note = self.repository.get(note_id)
        if not note:
            raise ValueError(f"Note with ID {note_id} not found")
        
        # Get all notes
        all_notes = self.repository.get_all()
        results = []
        
        # Set of this note's tags and links
        note_tags = {tag.name for tag in note.tags}
        note_links = {link.target_id for link in note.links}
        
        # Add notes linked to this note
        incoming_notes = self.repository.find_linked_notes(note_id, "incoming")
        note_incoming = {n.id for n in incoming_notes}
        
        # For each note, calculate similarity
        for other_note in all_notes:
            if other_note.id == note_id:
                continue
            
            # Calculate tag overlap
            other_tags = {tag.name for tag in other_note.tags}
            tag_overlap = len(note_tags.intersection(other_tags))
            
            # Calculate link overlap (outgoing)
            other_links = {link.target_id for link in other_note.links}
            link_overlap = len(note_links.intersection(other_links))
            
            # Check if other note links to this note
            incoming_overlap = 1 if other_note.id in note_incoming else 0
            
            # Check if this note links to other note
            outgoing_overlap = 1 if other_note.id in note_links else 0
            
            # Calculate similarity score
            # Weight: 40% tags, 20% outgoing links, 20% incoming links, 20% direct connections
            total_possible = (
                max(len(note_tags), len(other_tags)) * 0.4 +
                max(len(note_links), len(other_links)) * 0.2 +
                1 * 0.2 +  # Possible incoming link
                1 * 0.2    # Possible outgoing link
            )
            
            # Avoid division by zero
            if total_possible == 0:
                similarity = 0.0
            else:
                similarity = (
                    (tag_overlap * 0.4) +
                    (link_overlap * 0.2) +
                    (incoming_overlap * 0.2) +
                    (outgoing_overlap * 0.2)
                ) / total_possible
            
            if similarity >= threshold:
                results.append((other_note, similarity))
        
        # Sort by similarity (descending)
        results.sort(key=lambda x: x[1], reverse=True)
        return results

    def batch_create_notes(
        self, 
        notes_data: List[NoteData]
    ) -> BatchResult[Note, str]:
        """Create multiple notes in a batch operation.
        
        Args:
            notes_data: List of dictionaries containing note data with keys:
                - title: Note title (required)
                - content: Note content (required)
                - note_type: Type of note (optional, string)
                - tags: Comma-separated list of tags (optional, string)
                - metadata: Dict of metadata (optional)
        
        Returns:
            BatchResult with success/failure counts and individual results
        """
        results = []
        
        for i, note_data in enumerate(notes_data):
            try:
                # Extract required fields
                title = note_data.get('title')
                content = note_data.get('content')
                
                if not title:
                    raise ValueError("Title is required")
                if not content:
                    raise ValueError("Content is required")
                
                # Extract optional fields
                note_type = note_data.get('note_type', NoteType.PERMANENT)
                tags = note_data.get('tags', [])
                metadata = note_data.get('metadata', {})
                
                # Create the note
                note = self.create_note(
                    title=title,
                    content=content,
                    note_type=note_type,
                    tags=tags,
                    metadata=metadata
                )
                
                results.append(
                    BatchOperationResult(
                        success=True,
                        item_id=note.id,
                        result=note
                    )
                )
            except Exception as e:
                results.append(
                    BatchOperationResult(
                        success=False,
                        item_id=f"item_{i}",  # Use position as ID for failed items
                        error=str(e)
                    )
                )
        
        # Calculate summary statistics
        success_count = sum(1 for r in results if r.success)
        
        return BatchResult(
            total_count=len(results),
            success_count=success_count,
            failure_count=len(results) - success_count,
            results=results
        )
    
    def batch_update_notes(
        self, 
        updates: List[NoteUpdateData]
    ) -> BatchResult[Note, str]:
        """Update multiple notes in a batch operation.
        
        Args:
            updates: List of dictionaries containing note updates with keys:
                - note_id: ID of the note to update (required)
                - title: New title (optional)
                - content: New content (optional)
                - note_type: New note type (optional, string)
                - tags: New comma-separated list of tags (optional, string)
                - metadata: New metadata dict (optional)
        
        Returns:
            BatchResult with success/failure counts and individual results
        """
        results = []
        
        for update_data in updates:
            try:
                # Extract note_id (required)
                note_id = update_data.get('note_id')
                if not note_id:
                    raise ValueError("note_id is required for updates")
                
                # Extract optional fields
                title = update_data.get('title')
                content = update_data.get('content')
                note_type = update_data.get('note_type')
                tags = update_data.get('tags')
                metadata = update_data.get('metadata')
                
                # Update the note
                updated_note = self.update_note(
                    note_id=note_id,
                    title=title,
                    content=content,
                    note_type=note_type,
                    tags=tags,
                    metadata=metadata
                )
                
                results.append(
                    BatchOperationResult(
                        success=True,
                        item_id=note_id,
                        result=updated_note
                    )
                )
            except Exception as e:
                results.append(
                    BatchOperationResult(
                        success=False,
                        item_id=note_id if 'note_id' in update_data else "unknown",
                        error=str(e)
                    )
                )
        
        # Calculate summary statistics
        success_count = sum(1 for r in results if r.success)
        
        return BatchResult(
            total_count=len(results),
            success_count=success_count,
            failure_count=len(results) - success_count,
            results=results
        )
    
    def batch_delete_notes(self, note_ids: List[str]) -> BatchResult[None, str]:
        """Delete multiple notes in a batch operation.
        
        Args:
            note_ids: List of note IDs to delete
            
        Returns:
            BatchResult with success/failure counts
        """
        results = []
        
        for note_id in note_ids:
            try:
                self.delete_note(note_id)
                results.append(
                    BatchOperationResult(
                        success=True,
                        item_id=note_id,
                        result=None
                    )
                )
            except Exception as e:
                results.append(
                    BatchOperationResult(
                        success=False,
                        item_id=note_id,
                        error=str(e)
                    )
                )
        
        # Calculate summary statistics
        success_count = sum(1 for r in results if r.success)
        
        return BatchResult(
            total_count=len(results),
            success_count=success_count,
            failure_count=len(results) - success_count,
            results=results
        )
    
    def batch_add_tags(
        self, 
        tag_operations: List[TagOperationData]
    ) -> BatchResult[Note, str]:
        """Add tags to multiple notes in a batch operation.
        
        Args:
            tag_operations: List of dicts containing:
                - note_id: ID of the note (required)
                - tags: Comma-separated list of tags to add (required)
                
        Returns:
            BatchResult with success/failure counts and updated notes
        """
        results = []
        
        for op in tag_operations:
            try:
                note_id = op.get('note_id')
                tags = op.get('tags', [])
                
                if not note_id:
                    raise ValueError("note_id is required")
                if not tags:
                    raise ValueError("tags list is required")
                
                # Get the note
                note = self.repository.get(note_id)
                if not note:
                    raise ValueError(f"Note with ID {note_id} not found")
                
                # Add each tag
                for tag in tags:
                    note.add_tag(tag)
                
                # Save the updated note
                updated_note = self.repository.update(note)
                
                results.append(
                    BatchOperationResult(
                        success=True,
                        item_id=note_id,
                        result=updated_note
                    )
                )
            except Exception as e:
                results.append(
                    BatchOperationResult(
                        success=False,
                        item_id=op.get('note_id', "unknown"),
                        error=str(e)
                    )
                )
        
        # Calculate summary statistics
        success_count = sum(1 for r in results if r.success)
        
        return BatchResult(
            total_count=len(results),
            success_count=success_count,
            failure_count=len(results) - success_count,
            results=results
        )
    
    def batch_create_links(
        self, 
        link_operations: List[LinkData]
    ) -> BatchResult[Tuple[Note, Optional[Note]], str]:
        """Create links between notes in a batch operation.
        
        Args:
            link_operations: List of dicts containing:
                - source_id: ID of source note (required)
                - target_id: ID of target note (required)
                - link_type: Type of link (optional, string)
                - description: Link description (optional)
                - bidirectional: Whether to create bidirectional link (optional)
                - bidirectional_type: Type for reverse link (optional, string)
                
        Returns:
            BatchResult with success/failure counts and link results
        """
        results = []
        
        for i, op in enumerate(link_operations):
            try:
                source_id = op.get('source_id')
                target_id = op.get('target_id')
                
                if not source_id:
                    raise ValueError("source_id is required")
                if not target_id:
                    raise ValueError("target_id is required")
                
                # Extract optional parameters
                link_type = op.get('link_type', LinkType.REFERENCE)
                description = op.get('description')
                bidirectional = op.get('bidirectional', False)
                bidirectional_type = op.get('bidirectional_type')
                
                # Verify both notes exist before attempting to link
                source_note = self.repository.get(source_id)
                if not source_note:
                    raise ValueError(f"Source note with ID {source_id} not found")
                
                target_note = self.repository.get(target_id)
                if not target_note:
                    raise ValueError(f"Target note with ID {target_id} not found")
                
                # Create the link
                updated_source, updated_target = self.create_link(
                    source_id=source_id,
                    target_id=target_id,
                    link_type=link_type,
                    description=description,
                    bidirectional=bidirectional,
                    bidirectional_type=bidirectional_type
                )
                
                # Create a description of what was done
                link_description = f"{source_note.title} -> {target_note.title}"
                if bidirectional:
                    if updated_target:
                        link_description += f" [{link_type} (bidirectional)]"
                    else:
                        link_description += f" [{link_type} (bidirectional link already existed)]"
                else:
                    link_description += f" [{link_type}]"
                
                results.append(
                    BatchOperationResult(
                        success=True,
                        item_id=f"{source_id}-{target_id}",
                        result=(updated_source, updated_target),
                        error=None
                    )
                )
            except Exception as e:
                # Create an identifier for the failed operation
                item_id = f"{op.get('source_id', 'unknown')}-{op.get('target_id', 'unknown')}"
                
                results.append(
                    BatchOperationResult(
                        success=False,
                        item_id=item_id,
                        error=str(e)
                    )
                )
        
        # Calculate summary statistics
        success_count = sum(1 for r in results if r.success)
        
        return BatchResult(
            total_count=len(results),
            success_count=success_count,
            failure_count=len(results) - success_count,
            results=results
        )

