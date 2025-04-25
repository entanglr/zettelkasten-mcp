"""MCP server implementation for the Zettelkasten."""
import logging
import os
import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import exc as sqlalchemy_exc
from mcp.server.fastmcp import FastMCP
from zettelkasten_mcp.config import config
from zettelkasten_mcp.models.schema import LinkType, NoteType
from zettelkasten_mcp.services.search_service import SearchService
from zettelkasten_mcp.services.zettel_service import ZettelService
from zettelkasten_mcp.services.export_service import ExportService

logger = logging.getLogger(__name__)

class ZettelkastenMcpServer:
    """MCP server for Zettelkasten."""
    def __init__(self):
        """Initialize the MCP server."""
        self.mcp = FastMCP(
            config.server_name,
            version=config.server_version
        )
        # Services
        self.zettel_service = ZettelService()
        self.search_service = SearchService(self.zettel_service)
        self.export_service = ExportService(self.zettel_service)
        # Initialize services
        self.initialize()
        # Register tools
        self._register_tools()
        self._register_resources()
        self._register_prompts()

    def initialize(self) -> None:
        """Initialize services."""
        self.zettel_service.initialize()
        self.search_service.initialize()
        logger.info("Zettelkasten MCP server initialized")

    def format_error_response(self, error: Exception) -> str:
        """Format an error response in a consistent way.
        
        Args:
            error: The exception that occurred
            
        Returns:
            Formatted error message with appropriate level of detail
        """
        # Generate a unique error ID for traceability in logs
        error_id = str(uuid.uuid4())[:8]
        
        if isinstance(error, ValueError):
            # Domain validation errors - typically safe to show to users
            logger.error(f"Validation error [{error_id}]: {str(error)}")
            return f"Error: {str(error)}"
        elif isinstance(error, (IOError, OSError)):
            # File system errors - don't expose paths or detailed error messages
            logger.error(f"File system error [{error_id}]: {str(error)}", exc_info=True)
            # return f"Unable to access the requested resource. Error ID: {error_id}"
            return f"Error: {str(error)}"
        else:
            # Unexpected errors - log with full stack trace but return generic message
            logger.error(f"Unexpected error [{error_id}]: {str(error)}", exc_info=True)
            # return f"An unexpected error occurred. Error ID: {error_id}"
            return f"Error: {str(error)}"

    def _register_tools(self) -> None:
        """Register MCP tools."""
        # Create a new note
        @self.mcp.tool(name="zk_create_note")
        def zk_create_note(
            title: str, 
            content: str, 
            note_type: str = "permanent",
            tags: Optional[str] = None
        ) -> str:
            """Create a new Zettelkasten note.
            Args:
                title: The title of the note
                content: The main content of the note
                note_type: Type of note (fleeting, literature, permanent, structure, hub)
                tags: Comma-separated list of tags (optional)
            """
            try:
                # Convert note_type string to enum
                try:
                    note_type_enum = NoteType(note_type.lower())
                except ValueError:
                    return f"Invalid note type: {note_type}. Valid types are: {', '.join(t.value for t in NoteType)}"
                
                # Convert tags string to list
                tag_list = []
                if tags:
                    tag_list = [t.strip() for t in tags.split(",") if t.strip()]
                
                # Create the note
                note = self.zettel_service.create_note(
                    title=title,
                    content=content,
                    note_type=note_type_enum,
                    tags=tag_list,
                )
                return f"Note created successfully with ID: {note.id}"
            except Exception as e:
                return self.format_error_response(e)

        # Get a note by ID or title
        @self.mcp.tool(name="zk_get_note")
        def zk_get_note(identifier: str) -> str:
            """Retrieve a note by ID or title.
            Args:
                identifier: The ID or title of the note
            """
            try:
                identifier = str(identifier)
                # Try to get by ID first
                note = self.zettel_service.get_note(identifier)
                # If not found, try by title
                if not note:
                    note = self.zettel_service.get_note_by_title(identifier)
                if not note:
                    return f"Note not found: {identifier}"
                
                # Format the note
                result = f"# {note.title}\n"
                result += f"ID: {note.id}\n"
                result += f"Type: {note.note_type.value}\n"
                result += f"Created: {note.created_at.isoformat()}\n"
                result += f"Updated: {note.updated_at.isoformat()}\n"
                if note.tags:
                    result += f"Tags: {', '.join(tag.name for tag in note.tags)}\n"
                # Add note content, including the Links section added by _note_to_markdown()
                result += f"\n{note.content}\n"
                return result
            except Exception as e:
                return self.format_error_response(e)

        # Update a note
        @self.mcp.tool(name="zk_update_note")
        def zk_update_note(
            note_id: str,
            title: Optional[str] = None,
            content: Optional[str] = None,
            note_type: Optional[str] = None,
            tags: Optional[str] = None
        ) -> str:
            """Update an existing note.
            Args:
                note_id: The ID of the note to update
                title: New title (optional)
                content: New content (optional)
                note_type: New note type (optional)
                tags: New comma-separated list of tags (optional)
            """
            try:
                # Get the note
                note = self.zettel_service.get_note(str(note_id))
                if not note:
                    return f"Note not found: {note_id}"
                
                # Convert note_type string to enum if provided
                note_type_enum = None
                if note_type:
                    try:
                        note_type_enum = NoteType(note_type.lower())
                    except ValueError:
                        return f"Invalid note type: {note_type}. Valid types are: {', '.join(t.value for t in NoteType)}"
                
                # Convert tags string to list if provided
                tag_list = None
                if tags is not None:  # Allow empty string to clear tags
                    tag_list = [t.strip() for t in tags.split(",") if t.strip()]
                
                # Update the note
                updated_note = self.zettel_service.update_note(
                    note_id=note_id,
                    title=title,
                    content=content,
                    note_type=note_type_enum,
                    tags=tag_list
                )
                return f"Note updated successfully: {updated_note.id}"
            except Exception as e:
                return self.format_error_response(e)

        # Delete a note
        @self.mcp.tool(name="zk_delete_note")
        def zk_delete_note(note_id: str) -> str:
            """Delete a note.
            Args:
                note_id: The ID of the note to delete
            """
            try:
                # Check if note exists
                note = self.zettel_service.get_note(note_id)
                if not note:
                    return f"Note not found: {note_id}"
                
                # Delete the note
                self.zettel_service.delete_note(str(note_id))
                return f"Note deleted successfully: {note_id}"
            except Exception as e:
                return self.format_error_response(e)

        # Add a link between notes
        @self.mcp.tool(name="zk_create_link")
        def zk_create_link(
            source_id: str,
            target_id: str,
            link_type: str = "reference",
            description: Optional[str] = None,
            bidirectional: bool = False
        ) -> str:
            """Create a link between two notes.
            Args:
                source_id: ID of the source note
                target_id: ID of the target note
                link_type: Type of link (reference, extends, refines, contradicts, questions, supports, related)
                description: Optional description of the link
                bidirectional: Whether to create a link in both directions
            """
            try:
                # Convert link_type string to enum
                try:
                    source_id_str = str(source_id)
                    target_id_str = str(target_id)
                    link_type_enum = LinkType(link_type.lower())
                except ValueError:
                    return f"Invalid link type: {link_type}. Valid types are: {', '.join(t.value for t in LinkType)}"
                
                # Create the link
                source_note, target_note = self.zettel_service.create_link(
                    source_id=source_id,
                    target_id=target_id,
                    link_type=link_type_enum,
                    description=description,
                    bidirectional=bidirectional
                )
                if bidirectional:
                    return f"Bidirectional link created between {source_id} and {target_id}"
                else:
                    return f"Link created from {source_id} to {target_id}"
            except (Exception, sqlalchemy_exc.IntegrityError) as e:
                if "UNIQUE constraint failed" in str(e):
                    return f"A link of this type already exists between these notes. Try a different link type."
                return self.format_error_response(e)
        self.zk_create_link = zk_create_link

        # Remove a link between notes
        @self.mcp.tool(name="zk_remove_link")
        def zk_remove_link(
            source_id: str,
            target_id: str,
            bidirectional: bool = False
        ) -> str:
            """Remove a link between two notes.
            Args:
                source_id: ID of the source note
                target_id: ID of the target note
                bidirectional: Whether to remove the link in both directions
            """
            try:
                # Remove the link
                source_note, target_note = self.zettel_service.remove_link(
                    source_id=str(source_id),
                    target_id=str(target_id),
                    bidirectional=bidirectional
                )
                if bidirectional:
                    return f"Bidirectional link removed between {source_id} and {target_id}"
                else:
                    return f"Link removed from {source_id} to {target_id}"
            except Exception as e:
                return self.format_error_response(e)

        # Search for notes
        @self.mcp.tool(name="zk_search_notes")
        def zk_search_notes(
            query: Optional[str] = None,
            tags: Optional[str] = None,
            note_type: Optional[str] = None,
            limit: int = 10
        ) -> str:
            """Search for notes by text, tags, or type.
            Args:
                query: Text to search for in titles and content
                tags: Comma-separated list of tags to filter by
                note_type: Type of note to filter by
                limit: Maximum number of results to return
            """
            try:
                # Convert tags string to list if provided
                tag_list = None
                if tags:
                    tag_list = [t.strip() for t in tags.split(",") if t.strip()]
                
                # Convert note_type string to enum if provided
                note_type_enum = None
                if note_type:
                    try:
                        note_type_enum = NoteType(note_type.lower())
                    except ValueError:
                        return f"Invalid note type: {note_type}. Valid types are: {', '.join(t.value for t in NoteType)}"
                
                # Perform search
                results = self.search_service.search_combined(
                    text=query,
                    tags=tag_list,
                    note_type=note_type_enum
                )
                
                # Limit results
                results = results[:limit]
                if not results:
                    return "No matching notes found."
                
                # Format results
                output = f"Found {len(results)} matching notes:\n\n"
                for i, result in enumerate(results, 1):
                    note = result.note
                    output += f"{i}. {note.title} (ID: {note.id})\n"
                    if note.tags:
                        output += f"   Tags: {', '.join(tag.name for tag in note.tags)}\n"
                    output += f"   Created: {note.created_at.strftime('%Y-%m-%d')}\n"
                    # Add a snippet of content (first 150 chars)
                    content_preview = note.content[:150].replace("\n", " ")
                    if len(note.content) > 150:
                        content_preview += "..."
                    output += f"   Preview: {content_preview}\n\n"
                return output
            except Exception as e:
                return self.format_error_response(e)

        # Get linked notes
        @self.mcp.tool(name="zk_get_linked_notes")
        def zk_get_linked_notes(
            note_id: str,
            direction: str = "both"
        ) -> str:
            """Get notes linked to/from a note.
            Args:
                note_id: ID of the note
                direction: Direction of links (outgoing, incoming, both)
            """
            try:
                if direction not in ["outgoing", "incoming", "both"]:
                    return f"Invalid direction: {direction}. Use 'outgoing', 'incoming', or 'both'."
                # Get linked notes
                linked_notes = self.zettel_service.get_linked_notes(str(note_id), direction)
                if not linked_notes:
                    return f"No {direction} links found for note {note_id}."
                # Format results
                output = f"Found {len(linked_notes)} {direction} linked notes for {note_id}:\n\n"
                for i, note in enumerate(linked_notes, 1):
                    output += f"{i}. {note.title} (ID: {note.id})\n"
                    if note.tags:
                        output += f"   Tags: {', '.join(tag.name for tag in note.tags)}\n"
                    # Try to determine link type
                    if direction in ["outgoing", "both"]:
                        # Check source note's outgoing links
                        source_note = self.zettel_service.get_note(str(note_id))
                        if source_note:
                            for link in source_note.links:
                                if str(link.target_id) == str(note.id):  # Explicit string conversion for comparison
                                    output += f"   Link type: {link.link_type.value}\n"
                                    if link.description:
                                        output += f"   Description: {link.description}\n"
                                    break
                    if direction in ["incoming", "both"]:
                        # Check target note's outgoing links
                        for link in note.links:
                            if str(link.target_id) == str(note_id):  # Explicit string conversion for comparison
                                output += f"   Incoming link type: {link.link_type.value}\n"
                                if link.description:
                                    output += f"   Description: {link.description}\n"
                                break
                    output += "\n"
                return output
            except Exception as e:
                return self.format_error_response(e)
        self.zk_get_linked_notes = zk_get_linked_notes

        # Get all tags
        @self.mcp.tool(name="zk_get_all_tags")
        def zk_get_all_tags() -> str:
            """Get all tags in the Zettelkasten."""
            try:
                tags = self.zettel_service.get_all_tags()
                if not tags:
                    return "No tags found in the Zettelkasten."
                
                # Format results
                output = f"Found {len(tags)} tags:\n\n"
                # Sort alphabetically
                tags.sort(key=lambda t: t.name.lower())
                for i, tag in enumerate(tags, 1):
                    output += f"{i}. {tag.name}\n"
                return output
            except Exception as e:
                return self.format_error_response(e)

        # Find similar notes
        @self.mcp.tool(name="zk_find_similar_notes")
        def zk_find_similar_notes(
            note_id: str,
            threshold: float = 0.3,
            limit: int = 5
        ) -> str:
            """Find notes similar to a given note.
            Args:
                note_id: ID of the reference note
                threshold: Similarity threshold (0.0-1.0)
                limit: Maximum number of results to return
            """
            try:
                # Get similar notes
                similar_notes = self.zettel_service.find_similar_notes(str(note_id), threshold)
                # Limit results
                similar_notes = similar_notes[:limit]
                if not similar_notes:
                    return f"No similar notes found for {note_id} with threshold {threshold}."
                
                # Format results
                output = f"Found {len(similar_notes)} similar notes for {note_id}:\n\n"
                for i, (note, similarity) in enumerate(similar_notes, 1):
                    output += f"{i}. {note.title} (ID: {note.id})\n"
                    output += f"   Similarity: {similarity:.2f}\n"
                    if note.tags:
                        output += f"   Tags: {', '.join(tag.name for tag in note.tags)}\n"
                    # Add a snippet of content (first 100 chars)
                    content_preview = note.content[:100].replace("\n", " ")
                    if len(note.content) > 100:
                        content_preview += "..."
                    output += f"   Preview: {content_preview}\n\n"
                return output
            except Exception as e:
                return self.format_error_response(e)

        # Find central notes
        @self.mcp.tool(name="zk_find_central_notes")
        def zk_find_central_notes(limit: int = 10) -> str:
            """Find notes with the most connections (incoming + outgoing links).
            Notes are ranked by their total number of connections, determining
            their centrality in the knowledge network. Due to database constraints,
            only one link of each type is counted between any pair of notes.

            Args:
                limit: Maximum number of results to return (default: 10)
            """
            try:
                # Get central notes
                central_notes = self.search_service.find_central_notes(limit)
                if not central_notes:
                    return "No notes found with connections."
                
                # Format results
                output = "Central notes in the Zettelkasten (most connected):\n\n"
                for i, (note, connection_count) in enumerate(central_notes, 1):
                    output += f"{i}. {note.title} (ID: {note.id})\n"
                    output += f"   Connections: {connection_count}\n"
                    if note.tags:
                        output += f"   Tags: {', '.join(tag.name for tag in note.tags)}\n"
                    # Add a snippet of content (first 100 chars)
                    content_preview = note.content[:100].replace("\n", " ")
                    if len(note.content) > 100:
                        content_preview += "..."
                    output += f"   Preview: {content_preview}\n\n"
                return output
            except Exception as e:
                return self.format_error_response(e)

        # Find orphaned notes
        @self.mcp.tool(name="zk_find_orphaned_notes")
        def zk_find_orphaned_notes() -> str:
            """Find notes with no connections to other notes."""
            try:
                # Get orphaned notes
                orphans = self.search_service.find_orphaned_notes()
                if not orphans:
                    return "No orphaned notes found."
                
                # Format results
                output = f"Found {len(orphans)} orphaned notes:\n\n"
                for i, note in enumerate(orphans, 1):
                    output += f"{i}. {note.title} (ID: {note.id})\n"
                    if note.tags:
                        output += f"   Tags: {', '.join(tag.name for tag in note.tags)}\n"
                    # Add a snippet of content (first 100 chars)
                    content_preview = note.content[:100].replace("\n", " ")
                    if len(note.content) > 100:
                        content_preview += "..."
                    output += f"   Preview: {content_preview}\n\n"
                return output
            except Exception as e:
                return self.format_error_response(e)

        # List notes by date range
        @self.mcp.tool(name="zk_list_notes_by_date")
        def zk_list_notes_by_date(
            start_date: Optional[str] = None,
            end_date: Optional[str] = None,
            use_updated: bool = False,
            limit: int = 10
        ) -> str:
            """List notes created or updated within a date range.
            Args:
                start_date: Start date in ISO format (YYYY-MM-DD)
                end_date: End date in ISO format (YYYY-MM-DD)
                use_updated: Whether to use updated_at instead of created_at
                limit: Maximum number of results to return
            """
            try:
                # Parse dates
                start_datetime = None
                if start_date:
                    start_datetime = datetime.fromisoformat(f"{start_date}T00:00:00")
                end_datetime = None
                if end_date:
                    end_datetime = datetime.fromisoformat(f"{end_date}T23:59:59")
                
                # Get notes
                notes = self.search_service.find_notes_by_date_range(
                    start_date=start_datetime,
                    end_date=end_datetime,
                    use_updated=use_updated
                )
                
                # Limit results
                notes = notes[:limit]
                if not notes:
                    date_type = "updated" if use_updated else "created"
                    date_range = ""
                    if start_date and end_date:
                        date_range = f" between {start_date} and {end_date}"
                    elif start_date:
                        date_range = f" after {start_date}"
                    elif end_date:
                        date_range = f" before {end_date}"
                    return f"No notes found {date_type}{date_range}."
                
                # Format results
                date_type = "updated" if use_updated else "created"
                output = f"Notes {date_type}"
                if start_date or end_date:
                    if start_date and end_date:
                        output += f" between {start_date} and {end_date}"
                    elif start_date:
                        output += f" after {start_date}"
                    elif end_date:
                        output += f" before {end_date}"
                output += f" (showing {len(notes)} results):\n\n"
                for i, note in enumerate(notes, 1):
                    date = note.updated_at if use_updated else note.created_at
                    output += f"{i}. {note.title} (ID: {note.id})\n"
                    output += f"   {date_type.capitalize()}: {date.strftime('%Y-%m-%d %H:%M')}\n"
                    if note.tags:
                        output += f"   Tags: {', '.join(tag.name for tag in note.tags)}\n"
                    # Add a snippet of content (first 100 chars)
                    content_preview = note.content[:100].replace("\n", " ")
                    if len(note.content) > 100:
                        content_preview += "..."
                    output += f"   Preview: {content_preview}\n\n"
                return output
            except ValueError as e:
                # Special handling for date parsing errors
                logger.error(f"Date parsing error: {str(e)}")
                return f"Error parsing date: {str(e)}"
            except Exception as e:
                return self.format_error_response(e)

        # Rebuild the index
        @self.mcp.tool(name="zk_rebuild_index")
        def zk_rebuild_index() -> str:
            """Rebuild the database index from files."""
            try:
                # Get count before rebuild
                note_count_before = len(self.zettel_service.get_all_notes())
                
                # Perform the rebuild
                self.zettel_service.rebuild_index()
                
                # Get count after rebuild
                note_count_after = len(self.zettel_service.get_all_notes())
                
                # Return a detailed success message
                return (
                    f"Database index rebuilt successfully.\n"
                    f"Notes processed: {note_count_after}\n"
                    f"Change in note count: {note_count_after - note_count_before}"
                )
            except Exception as e:
                # Provide a detailed error message
                logger.error(f"Failed to rebuild index: {e}", exc_info=True)
                return self.format_error_response(e)
        
        # Batch create notes
        @self.mcp.tool(name="zk_batch_create_notes")
        def zk_batch_create_notes(
            notes: list
        ) -> str:
            """Create multiple notes in a batch operation.
            Args:
                notes: List of note objects, each with keys:
                    - title (required): Note title
                    - content (required): Note content
                    - note_type (optional): Type of note (default: "permanent")
                    - tags (optional): Comma-separated list of tags
            
            Example:
                [
                    {"title": "Note 1", "content": "Content 1", "note_type": "permanent", "tags": "tag1,tag2"},
                    {"title": "Note 2", "content": "Content 2"}
                ]
            """
            try:
                # Log the input for debugging
                logger.info(f"batch_create_notes received: {notes}")
                
                # Check that notes is actually a list
                if not isinstance(notes, list):
                    return "Error: 'notes' must be a list of note objects"
                
                # Process each note
                processed_notes = []
                for note_data in notes:
                    # Extract required fields
                    title = note_data.get("title")
                    content = note_data.get("content")
                    if not title or not content:
                        processed_notes.append({
                            "success": False,
                            "error": "Title and content are required"
                        })
                        continue
                    
                    # Extract optional fields
                    note_type_str = note_data.get("note_type", "permanent")
                    tags_str = note_data.get("tags", "")
                    
                    # Convert note_type
                    try:
                        note_type_enum = NoteType(note_type_str.lower())
                    except ValueError:
                        processed_notes.append({
                            "success": False,
                            "error": f"Invalid note type: {note_type_str}"
                        })
                        continue
                    
                    # Convert tags
                    tag_list = []
                    if tags_str:
                        tag_list = [t.strip() for t in tags_str.split(",") if t.strip()]
                    
                    # Create the note
                    try:
                        note = self.zettel_service.create_note(
                            title=title,
                            content=content,
                            note_type=note_type_enum,
                            tags=tag_list
                        )
                        processed_notes.append({
                            "success": True,
                            "id": note.id,
                            "title": note.title
                        })
                    except Exception as e:
                        processed_notes.append({
                            "success": False,
                            "error": str(e)
                        })
                
                # Format response
                success_count = sum(1 for n in processed_notes if n.get("success", False))
                result = f"Batch note creation completed: {success_count}/{len(notes)} successful\n\n"
                
                for i, note_result in enumerate(processed_notes, 1):
                    if note_result.get("success"):
                        result += f"{i}. Created: '{note_result['title']}' (ID: {note_result['id']})\n"
                    else:
                        result += f"{i}. Failed: {note_result.get('error', 'Unknown error')}\n"
                
                return result
            except Exception as e:
                logger.error(f"Error in batch_create_notes: {e}", exc_info=True)
                return self.format_error_response(e)

        # Batch update notes
        @self.mcp.tool(name="zk_batch_update_notes")
        def zk_batch_update_notes(
            updates: list
        ) -> str:
            """Update multiple notes in a batch operation.
            Args:
                updates: List of note update objects, each with:
                    - note_id: ID of the note to update (required)
                    - title: New title (optional)
                    - content: New content (optional)
                    - note_type: New note type (optional)
                    - tags: New comma-separated list of tags (optional)
                    
            Example:
                [
                    {"note_id": "20230101120000", "title": "Updated Title"},
                    {"note_id": "20230102120000", "content": "Updated content", "tags": "new_tag,another_tag"}
                ]
            """
            try:
                # Process each update
                processed_updates = []
                for update in updates:
                    # Extract required fields
                    note_id = update.get("note_id")
                    if not note_id:
                        processed_updates.append({
                            "success": False,
                            "error": "note_id is required"
                        })
                        continue
                    
                    # Extract optional fields
                    title = update.get("title")
                    content = update.get("content")
                    note_type_str = update.get("note_type")
                    tags_str = update.get("tags")
                    
                    # Validate note exists
                    note = self.zettel_service.get_note(str(note_id))
                    if not note:
                        processed_updates.append({
                            "success": False,
                            "id": note_id,
                            "error": f"Note not found: {note_id}"
                        })
                        continue
                    
                    # Convert note_type if provided
                    note_type_enum = None
                    if note_type_str:
                        try:
                            note_type_enum = NoteType(note_type_str.lower())
                        except ValueError:
                            processed_updates.append({
                                "success": False,
                                "id": note_id,
                                "error": f"Invalid note type: {note_type_str}"
                            })
                            continue
                    
                    # Convert tags if provided
                    tag_list = None
                    if tags_str is not None:  # Allow empty string to clear tags
                        tag_list = [t.strip() for t in tags_str.split(",") if t.strip()]
                    
                    # Update the note
                    try:
                        updated_note = self.zettel_service.update_note(
                            note_id=note_id,
                            title=title,
                            content=content,
                            note_type=note_type_enum,
                            tags=tag_list
                        )
                        processed_updates.append({
                            "success": True,
                            "id": updated_note.id,
                            "title": updated_note.title
                        })
                    except Exception as e:
                        processed_updates.append({
                            "success": False,
                            "id": note_id,
                            "error": str(e)
                        })
                
                # Format response
                success_count = sum(1 for u in processed_updates if u.get("success", False))
                result = f"Batch note update completed: {success_count}/{len(updates)} successful\n\n"
                
                for i, update_result in enumerate(processed_updates, 1):
                    if update_result.get("success"):
                        result += f"{i}. Updated: ID {update_result['id']} - '{update_result['title']}'\n"
                    else:
                        result += f"{i}. Failed: ID {update_result.get('id', 'unknown')} - {update_result.get('error', 'Unknown error')}\n"
                
                return result
            except Exception as e:
                return self.format_error_response(e)

        # Batch delete notes
        @self.mcp.tool(name="zk_batch_delete_notes")
        def zk_batch_delete_notes(
            note_ids: list
        ) -> str:
            """Delete multiple notes in a batch operation.
            Args:
                note_ids: List of note IDs to delete
                
            Example:
                ["20230101120000", "20230102120000"]
            """
            try:
                # Process each deletion
                results = []
                for note_id in note_ids:
                    try:
                        # Check if note exists
                        note = self.zettel_service.get_note(str(note_id))
                        if not note:
                            results.append({
                                "success": False,
                                "id": note_id,
                                "error": f"Note not found: {note_id}"
                            })
                            continue
                            
                        # Store title for reporting
                        title = note.title
                        
                        # Delete the note
                        self.zettel_service.delete_note(str(note_id))
                        results.append({
                            "success": True,
                            "id": note_id,
                            "title": title
                        })
                    except Exception as e:
                        results.append({
                            "success": False,
                            "id": note_id,
                            "error": str(e)
                        })
                
                # Format response
                success_count = sum(1 for r in results if r.get("success", False))
                result = f"Batch note deletion completed: {success_count}/{len(note_ids)} successful\n\n"
                
                for i, del_result in enumerate(results, 1):
                    if del_result.get("success"):
                        result += f"{i}. Deleted: ID {del_result['id']} - '{del_result['title']}'\n"
                    else:
                        result += f"{i}. Failed: ID {del_result['id']} - {del_result.get('error', 'Unknown error')}\n"
                
                return result
            except Exception as e:
                return self.format_error_response(e)

        # Batch create links
        @self.mcp.tool(name="zk_batch_create_links")
        def zk_batch_create_links(
            links: list
        ) -> str:
            """Create multiple links between notes in a batch operation.
            Args:
                links: List of link objects, each with:
                    - source_id: ID of source note (required)
                    - target_id: ID of target note (required)
                    - link_type: Type of link (optional, default: "reference")
                    - description: Link description (optional)
                    - bidirectional: Whether to create a reciprocal link (optional, default: false)
                    
            Example:
                [
                    {"source_id": "20230101120000", "target_id": "20230102120000"},
                    {"source_id": "20230103120000", "target_id": "20230104120000", "link_type": "refines", "description": "Refines the concept", "bidirectional": true}
                ]
            """
            try:
                # Process each link
                results = []
                for link_data in links:
                    # Extract required fields
                    source_id = link_data.get("source_id")
                    target_id = link_data.get("target_id")
                    
                    if not source_id or not target_id:
                        results.append({
                            "success": False,
                            "error": "source_id and target_id are required"
                        })
                        continue
                    
                    # Extract optional fields
                    link_type_str = link_data.get("link_type", "reference")
                    description = link_data.get("description")
                    bidirectional = link_data.get("bidirectional", False)
                    
                    # Convert link_type
                    try:
                        link_type_enum = LinkType(link_type_str.lower())
                    except ValueError:
                        results.append({
                            "success": False,
                            "source": source_id,
                            "target": target_id,
                            "error": f"Invalid link type: {link_type_str}"
                        })
                        continue
                    
                    # Create the link
                    try:
                        source_note, target_note = self.zettel_service.create_link(
                            source_id=source_id,
                            target_id=target_id,
                            link_type=link_type_enum,
                            description=description,
                            bidirectional=bidirectional
                        )
                        
                        # If unidirectional, the target note does not get returned as it was not updated
                        if target_note is None:
                            target_note = self.zettel_service.get_note(str(target_id))

                        results.append({
                            "success": True,
                            "source": source_id,
                            "source_title": source_note.title,
                            "target": target_id,
                            "target_title": target_note.title,
                            "link_type": link_type_str,
                            "bidirectional": bidirectional
                        })
                    except Exception as e:
                        results.append({
                            "success": False,
                            "source": source_id,
                            "target": target_id,
                            "error": str(e)
                        })
                
                # Format response
                success_count = sum(1 for r in results if r.get("success", False))
                result = f"Batch link creation completed: {success_count}/{len(links)} successful\n\n"
                
                for i, link_result in enumerate(results, 1):
                    if link_result.get("success"):
                        link_desc = f"{link_result['link_type']}" + (" (bidirectional)" if link_result.get("bidirectional") else "")
                        result += f"{i}. Created: {link_result['source_title']} -> {link_result['target_title']} [{link_desc}]\n"
                    else:
                        source = link_result.get('source', 'unknown')
                        target = link_result.get('target', 'unknown')
                        result += f"{i}. Failed: {source} -> {target} - {link_result.get('error', 'Unknown error')}\n"
                
                return result
            except Exception as e:
                return self.format_error_response(e)
                
        # Batch search by text
        @self.mcp.tool(name="zk_batch_search_by_text")
        def zk_batch_search_by_text(queries_data: str) -> str:
            """Perform multiple text searches in a batch operation.
            Args:
                queries_data: JSON string containing an array of search queries, or
                              a JSON object with queries array and options
                
            Example array format:
                ["search term 1", "search term 2"]
                
            Example object format:
                {
                    "queries": ["search term 1", "search term 2"],
                    "include_content": true,
                    "include_title": true,
                    "limit": 5
                }
            """
            try:
                # Import JSON if not already imported
                import json
                
                # Parse the JSON input
                try:
                    data = json.loads(queries_data)
                    
                    # Handle both array and object formats
                    queries = data
                    include_content = True
                    include_title = True
                    limit = 5
                    
                    if isinstance(data, dict):
                        queries = data.get("queries", [])
                        include_content = data.get("include_content", True)
                        include_title = data.get("include_title", True)
                        limit = data.get("limit", 5)
                    
                    if not isinstance(queries, list):
                        return "Error: Input must contain an array of search queries"
                    
                except json.JSONDecodeError:
                    return "Error: Invalid JSON format"
                
                # Process each query
                results = []
                for query in queries:
                    try:
                        search_results = self.search_service.search_by_text(
                            query=query,
                            include_content=include_content,
                            include_title=include_title
                        )
                        
                        # Limit results per query
                        search_results = search_results[:limit]
                        
                        results.append({
                            "success": True,
                            "query": query,
                            "count": len(search_results),
                            "results": search_results
                        })
                    except Exception as e:
                        results.append({
                            "success": False,
                            "query": query,
                            "error": str(e)
                        })
                
                # Format response
                output = f"Batch search completed for {len(queries)} queries\n\n"
                
                for i, query_result in enumerate(results, 1):
                    if query_result.get("success"):
                        output += f"{i}. Query: \"{query_result['query']}\"\n"
                        output += f"   Found: {query_result['count']} results\n"
                        
                        # List the results for this query
                        if query_result['results']:
                            for j, result in enumerate(query_result['results'], 1):
                                note = result.note
                                output += f"   {j}. {note.title} (ID: {note.id})\n"
                                if note.tags:
                                    output += f"      Tags: {', '.join(tag.name for tag in note.tags)}\n"
                                
                                # Show the score and matched terms
                                output += f"      Score: {result.score:.2f}\n"
                                if result.matched_terms:
                                    output += f"      Matched terms: {', '.join(result.matched_terms)}\n"
                                
                                # Add context snippet if available
                                if result.matched_context:
                                    output += f"      Context: \"{result.matched_context}\"\n"
                        else:
                            output += "   No matches found\n"
                    else:
                        output += f"{i}. Query: \"{query_result['query']}\" - Failed: {query_result.get('error', 'Unknown error')}\n"
                    
                    output += "\n"
                
                return output
            except Exception as e:
                return self.format_error_response(e)

        @self.mcp.tool(name="zk_export_knowledge_base")
        def zk_export_knowledge_base(export_dir: Optional[str] = None, clean_dir: bool = True) -> str:
            """Export the entire knowledge base to a directory of markdown files.
            
            This creates a well-formatted, well-linked, markdown collection with human readable
            filenames and an obvious entrypoint (index.md). The collection is organized by note
            type (hub, structure, permanent, literature, fleeting) and includes proper cross-links.
            The output is suitable for uploading as documentation website.
            
            Args:
                export_dir: Directory path to export to (optional, defaults to 'data/export' next to notes directory)
                clean_dir: Whether to clean the directory before export (default: True)
            """
            try:
                # Export the knowledge base
                export_path = self.export_service.export_to_markdown(
                    export_dir=export_dir,
                    clean_dir=clean_dir
                )
                
                # Count files in the export directory
                total_files = 0
                for root, _, files in os.walk(export_path):
                    total_files += len([f for f in files if f.endswith('.md')])
                
                # Return a success message
                result = f"Knowledge base exported successfully to: {export_path}\n"
                result += f"Total markdown files created: {total_files}\n\n"
                result += "Export structure:\n"
                result += "- index.md (main entry point)\n"
                result += "- hub_notes/ (entry points into the knowledge base)\n"
                result += "- structure_notes/ (organizing notes)\n"
                result += "- permanent_notes/ (well-formulated, evergreen notes)\n"
                result += "- literature_notes/ (notes from reading material)\n"
                result += "- fleeting_notes/ (quick, temporary notes)\n\n"
                result += "You can now upload this directory to any service that hosts markdown files as a website."
                return result
            except Exception as e:
                return self.format_error_response(e)

    def _register_resources(self) -> None:
        """Register MCP resources."""
        # Currently, we don't define resources for the Zettelkasten server
        pass

    def _register_prompts(self) -> None:
        """Register MCP prompts."""
        # Currently, we don't define prompts for the Zettelkasten server
        pass

    def run(self) -> None:
        """Run the MCP server."""
        self.mcp.run()
