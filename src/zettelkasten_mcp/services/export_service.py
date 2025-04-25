"""Service for exporting Zettelkasten knowledge base to various formats."""
import logging
import re
import shutil
from pathlib import Path
from typing import Dict, List, Optional

from zettelkasten_mcp.config import config
from zettelkasten_mcp.models.schema import Note, NoteType
from zettelkasten_mcp.services.zettel_service import ZettelService

logger = logging.getLogger(__name__)

class ExportService:
    """Service for exporting the Zettelkasten knowledge base."""
    
    def __init__(self, zettel_service: Optional[ZettelService] = None):
        """Initialize the service.
        
        Args:
            zettel_service: ZettelService instance to use (creates new one if None)
        """
        self.zettel_service = zettel_service or ZettelService()
        
    def export_to_markdown(self, export_dir: Optional[Path], clean_dir: bool = True) -> Path:
        """Export the entire knowledge base to a directory of markdown files.
        
        Args:
            export_dir: Directory to export to
            clean_dir: Whether to clean the directory before export
            
        Returns:
            Path to the export directory
        """

        export_dir = (
            config.get_absolute_path(export_dir)
            if export_dir
            else config.get_absolute_path(config.export_dir)
        )
        
        # Create directory if it doesn't exist
        export_dir.mkdir(parents=True, exist_ok=True)
        
        # Clean directory if specified
        if clean_dir and export_dir.exists():
            for item in export_dir.iterdir():
                if item.is_file():
                    item.unlink()
                elif item.is_dir():
                    shutil.rmtree(item)
        
        # Get all notes
        notes = self.zettel_service.get_all_notes()
        logger.info(f"Exporting {len(notes)} notes to {export_dir}")
        
        # Create structure for arranging notes
        hub_notes = []
        structure_notes = []
        permanent_notes = []
        literature_notes = []
        fleeting_notes = []
        
        # Dictionary to map note IDs to filenames
        id_to_filename = {}
        
        # First pass: categorize notes and create filename mappings
        for note in notes:
            # Create a sanitized filename from the title
            base_filename = self._sanitize_filename(note.title)
            
            # Add note ID prefix for uniqueness
            filename = f"{note.id}_{base_filename}.md"
            id_to_filename[note.id] = filename
            
            # Categorize notes by type
            if note.note_type == NoteType.HUB:
                hub_notes.append(note)
            elif note.note_type == NoteType.STRUCTURE:
                structure_notes.append(note)
            elif note.note_type == NoteType.PERMANENT:
                permanent_notes.append(note)
            elif note.note_type == NoteType.LITERATURE:
                literature_notes.append(note)
            elif note.note_type == NoteType.FLEETING:
                fleeting_notes.append(note)
        
        # Create directories for different note types if there are notes of that type
        if hub_notes:
            (export_dir / "hub_notes").mkdir(exist_ok=True)
        if structure_notes:
            (export_dir / "structure_notes").mkdir(exist_ok=True)
        if permanent_notes:
            (export_dir / "permanent_notes").mkdir(exist_ok=True)
        if literature_notes:
            (export_dir / "literature_notes").mkdir(exist_ok=True)
        if fleeting_notes:
            (export_dir / "fleeting_notes").mkdir(exist_ok=True)
        
        # Second pass: Export all notes with proper links
        for note in notes:
            # Determine subdirectory based on note type
            if note.note_type == NoteType.HUB:
                subdir = "hub_notes"
            elif note.note_type == NoteType.STRUCTURE:
                subdir = "structure_notes"
            elif note.note_type == NoteType.PERMANENT:
                subdir = "permanent_notes"
            elif note.note_type == NoteType.LITERATURE:
                subdir = "literature_notes"
            elif note.note_type == NoteType.FLEETING:
                subdir = "fleeting_notes"
            else:
                subdir = "other"
            
            # Get filename for this note
            filename = id_to_filename[note.id]
            
            # Create file path
            file_path = export_dir / subdir / filename
            
            # Export note with updated links
            self._export_note_with_links(note, file_path, id_to_filename)
        
        # Create index.md file
        self._create_index_file(export_dir, notes, id_to_filename)
        
        return export_dir
    
    def _sanitize_filename(self, title: str) -> str:
        """Sanitize a title to use as a filename.
        
        Args:
            title: The title to sanitize
            
        Returns:
            A sanitized version of the title suitable for use as a filename
        """
        # Replace non-alphanumeric characters with underscores
        sanitized = re.sub(r'[^\w\s.-]', '_', title)
        # Replace spaces with hyphens
        sanitized = re.sub(r'\s+', '-', sanitized)
        # Ensure it's not too long
        if len(sanitized) > 100:
            sanitized = sanitized[:100]
        return sanitized
    
    def _export_note_with_links(
        self, note: Note, file_path: Path, id_to_filename: Dict[str, str]
    ) -> None:
        """Export a note to a file with updated links.
        
        Args:
            note: The note to export
            file_path: Path to export to
            id_to_filename: Dictionary mapping note IDs to filenames
        """
        # Start with the content of the note
        content_lines = note.content.split("\n")
        
        # Process content to update links
        processed_content = []
        for line in content_lines:
            # Skip existing link sections as we'll regenerate them
            if line.strip() == "## Links":
                break
            processed_content.append(line)
        
        # Join processed content
        content = "\n".join(processed_content)
        
        # Add frontmatter
        frontmatter = "---\n"
        frontmatter += f"id: {note.id}\n"
        frontmatter += f"title: \"{note.title}\"\n"
        frontmatter += f"type: {note.note_type.value}\n"
        
        if note.tags:
            tag_names = [tag.name for tag in note.tags]
            frontmatter += f"tags: [{', '.join(f'\"{tag}\"' for tag in tag_names)}]\n"
        else:
            frontmatter += "tags: []\n"
            
        frontmatter += f"created: {note.created_at.isoformat()}\n"
        frontmatter += f"updated: {note.updated_at.isoformat()}\n"
        
        # Add any custom metadata
        for key, value in note.metadata.items():
            frontmatter += f"{key}: {value}\n"
            
        frontmatter += "---\n\n"
        
        # Add title as heading if not already present
        if not content.strip().startswith(f"# {note.title}"):
            content = f"# {note.title}\n\n{content}"
        
        # Add links section if there are links
        if note.links:
            content += "\n\n## Links\n"
            
            # Group links by type
            links_by_type = {}
            for link in note.links:
                if link.link_type not in links_by_type:
                    links_by_type[link.link_type] = []
                links_by_type[link.link_type].append(link)
                
            # Add links by type
            for link_type, links in links_by_type.items():
                content += f"\n### {link_type.value.capitalize()} Links\n\n"
                
                for link in links:
                    target_id = link.target_id
                    
                    # Get the path to the linked note
                    if target_id in id_to_filename:
                        # Determine the directory for the target note
                        target_note = self.zettel_service.get_note(target_id)
                        if target_note:
                            if target_note.note_type == NoteType.HUB:
                                target_dir = "hub_notes"
                            elif target_note.note_type == NoteType.STRUCTURE:
                                target_dir = "structure_notes"
                            elif target_note.note_type == NoteType.PERMANENT:
                                target_dir = "permanent_notes"
                            elif target_note.note_type == NoteType.LITERATURE:
                                target_dir = "literature_notes"
                            elif target_note.note_type == NoteType.FLEETING:
                                target_dir = "fleeting_notes"
                            else:
                                target_dir = "other"
                                
                            target_filename = id_to_filename[target_id]
                            target_path = f"../{target_dir}/{target_filename}" if target_dir != file_path.parent.name else f"{target_filename}"
                            
                            # Add the link
                            if link.description:
                                content += f"- [{target_note.title}]({target_path}) - {link.description}\n"
                            else:
                                content += f"- [{target_note.title}]({target_path})\n"
        
        # Write to file
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(frontmatter + content)
    
    def _create_index_file(
        self, export_dir: Path, notes: List[Note], id_to_filename: Dict[str, str]
    ) -> None:
        """Create an index.md file as the entry point.
        
        Args:
            export_dir: Path to the export directory
            notes: List of all notes
            id_to_filename: Dictionary mapping note IDs to filenames
        """
        # Start with a title and introduction
        content = "# Zettelkasten Knowledge Base\n\n"
        content += "This is an exported collection of knowledge from a Zettelkasten system.\n\n"
        
        # Add sections for different note types
        
        # Hub notes section
        hub_notes = [n for n in notes if n.note_type == NoteType.HUB]
        if hub_notes:
            content += "## Hub Notes\n\n"
            content += "Hub notes serve as entry points into the knowledge base for broad areas of interest.\n\n"
            
            for note in sorted(hub_notes, key=lambda n: n.title):
                filename = id_to_filename[note.id]
                content += f"- [{note.title}](hub_notes/{filename})\n"
            
            content += "\n"
        
        # Structure notes section
        structure_notes = [n for n in notes if n.note_type == NoteType.STRUCTURE]
        if structure_notes:
            content += "## Structure Notes\n\n"
            content += "Structure notes organize groups of notes on particular topics.\n\n"
            
            for note in sorted(structure_notes, key=lambda n: n.title):
                filename = id_to_filename[note.id]
                content += f"- [{note.title}](structure_notes/{filename})\n"
            
            content += "\n"
        
        # Tags section
        all_tags = self.zettel_service.get_all_tags()
        if all_tags:
            content += "## Browse by Tag\n\n"
            
            # Create a tag index
            tag_to_notes = {}
            for tag in all_tags:
                tag_notes = self.zettel_service.get_notes_by_tag(tag.name)
                tag_to_notes[tag.name] = tag_notes
            
            # Sort tags by name
            sorted_tags = sorted(all_tags, key=lambda t: t.name)
            
            # List tags
            for tag in sorted_tags:
                tag_notes = tag_to_notes[tag.name]
                if tag_notes:
                    content += f"### {tag.name} ({len(tag_notes)})\n\n"
                    
                    for note in sorted(tag_notes, key=lambda n: n.title):
                        filename = id_to_filename[note.id]
                        
                        # Determine the directory for the note
                        if note.note_type == NoteType.HUB:
                            note_dir = "hub_notes"
                        elif note.note_type == NoteType.STRUCTURE:
                            note_dir = "structure_notes"
                        elif note.note_type == NoteType.PERMANENT:
                            note_dir = "permanent_notes"
                        elif note.note_type == NoteType.LITERATURE:
                            note_dir = "literature_notes"
                        elif note.note_type == NoteType.FLEETING:
                            note_dir = "fleeting_notes"
                        else:
                            note_dir = "other"
                            
                        content += f"- [{note.title}]({note_dir}/{filename})\n"
                    
                    content += "\n"
        
        # Stats section
        content += "## Statistics\n\n"
        content += f"- Total notes: {len(notes)}\n"
        content += f"- Hub notes: {len([n for n in notes if n.note_type == NoteType.HUB])}\n"
        content += f"- Structure notes: {len([n for n in notes if n.note_type == NoteType.STRUCTURE])}\n"
        content += f"- Permanent notes: {len([n for n in notes if n.note_type == NoteType.PERMANENT])}\n"
        content += f"- Literature notes: {len([n for n in notes if n.note_type == NoteType.LITERATURE])}\n"
        content += f"- Fleeting notes: {len([n for n in notes if n.note_type == NoteType.FLEETING])}\n"
        content += f"- Total tags: {len(all_tags)}\n"
        
        # Write to file
        index_path = export_dir / "index.md"
        with open(index_path, "w", encoding="utf-8") as f:
            f.write(content)