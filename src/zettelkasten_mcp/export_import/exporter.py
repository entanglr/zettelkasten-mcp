"""Export utilities for backing up notes from SQLite to markdown files."""
import datetime
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

import frontmatter
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

from zettelkasten_mcp.models.schema import Note, LinkType
from zettelkasten_mcp.storage.sqlite_repository import SQLiteNoteRepository

console = Console()
logger = logging.getLogger(__name__)

class MarkdownExporter:
    """Export notes from SQLite database to markdown files."""
    
    def __init__(self, repository: SQLiteNoteRepository):
        """Initialize exporter with repository."""
        self.repository = repository
        self.export_stats = {
            "total_notes": 0,
            "exported": 0,
            "failed": 0,
            "warnings": []
        }
    
    def export_note_to_markdown(self, note: Note) -> str:
        """Convert a note to markdown format with frontmatter."""
        # Prepare frontmatter
        metadata = {
            "id": note.id,
            "title": note.title,
            "type": note.note_type.value,
            "tags": ", ".join(tag.name for tag in note.tags),
            "created": note.created_at.isoformat(),
            "updated": note.updated_at.isoformat()
        }
        
        # Add any extra metadata
        if note.metadata:
            for key, value in note.metadata.items():
                if key not in metadata and key not in ["migrated_from", "migration_date"]:
                    metadata[key] = value
        
        # Create content with links section
        content_parts = [note.content.strip()]
        
        # Only add links section if not already in content
        if note.links and "## Links" not in note.content:
            content_parts.append("\n## Links")
            for link in note.links:
                link_line = f"- {link.link_type.value} [[{link.target_id}]]"
                if link.description:
                    link_line += f" {link.description}"
                content_parts.append(link_line)
        
        # Combine frontmatter and content
        post = frontmatter.Post("\n".join(content_parts), **metadata)
        return frontmatter.dumps(post)
    
    def export_single_note(self, note_id: str, export_dir: Path) -> bool:
        """Export a single note to markdown file."""
        try:
            # Read note from database
            note = self.repository.read(note_id)
            if not note:
                logger.error(f"Note {note_id} not found")
                return False
            
            # Convert to markdown
            markdown_content = self.export_note_to_markdown(note)
            
            # Write to file
            file_path = export_dir / f"{note.id}.md"
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(markdown_content)
            
            logger.info(f"Exported note {note_id} to {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error exporting note {note_id}: {e}")
            return False
    
    def export_all_notes(self, export_dir: Path, batch_size: int = 100) -> Dict[str, any]:
        """Export all notes from database to markdown files."""
        # Ensure export directory exists
        export_dir.mkdir(parents=True, exist_ok=True)
        
        # Get total count
        stats = self.repository.get_statistics()
        self.export_stats["total_notes"] = stats["total_notes"]
        
        console.print(f"[bold]Exporting {self.export_stats['total_notes']} notes to {export_dir}[/bold]\n")
        
        # Export notes in batches
        offset = 0
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console
        ) as progress:
            task = progress.add_task("Exporting notes...", total=self.export_stats["total_notes"])
            
            while offset < self.export_stats["total_notes"]:
                # Get batch of notes
                notes = self.repository.list(limit=batch_size, offset=offset)
                
                for note in notes:
                    progress.update(task, advance=1, description=f"Exporting {note.id}")
                    
                    try:
                        # Convert to markdown
                        markdown_content = self.export_note_to_markdown(note)
                        
                        # Write to file
                        file_path = export_dir / f"{note.id}.md"
                        with open(file_path, "w", encoding="utf-8") as f:
                            f.write(markdown_content)
                        
                        self.export_stats["exported"] += 1
                        
                    except Exception as e:
                        logger.error(f"Error exporting note {note.id}: {e}")
                        self.export_stats["failed"] += 1
                        self.export_stats["warnings"].append(f"Failed to export {note.id}: {str(e)}")
                
                offset += batch_size
        
        # Save export metadata
        metadata_path = export_dir / "_export_metadata.json"
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump({
                "export_date": datetime.datetime.now().isoformat(),
                "statistics": self.export_stats,
                "database_stats": stats
            }, f, indent=2)
        
        # Display summary
        console.print(f"\n[green]✓ Export completed![/green]")
        console.print(f"  • Exported: {self.export_stats['exported']}")
        console.print(f"  • Failed: {self.export_stats['failed']}")
        if self.export_stats["warnings"]:
            console.print(f"  • Warnings: {len(self.export_stats['warnings'])}")
        
        return self.export_stats
    
    def export_by_criteria(self, export_dir: Path, **criteria) -> Dict[str, any]:
        """Export notes matching specific criteria."""
        export_dir.mkdir(parents=True, exist_ok=True)
        
        # Supported criteria: tag, note_type, search_query
        notes = []
        
        if "tag" in criteria:
            notes = self.repository.find_by_tag(criteria["tag"])
            console.print(f"Exporting notes with tag '{criteria['tag']}'")
        elif "note_type" in criteria:
            notes = self.repository.list(note_type=criteria["note_type"])
            console.print(f"Exporting notes of type '{criteria['note_type']}'")
        elif "search_query" in criteria:
            notes = self.repository.search(criteria["search_query"])
            console.print(f"Exporting notes matching '{criteria['search_query']}'")
        else:
            console.print("[red]No valid criteria provided[/red]")
            return {"error": "No valid criteria"}
        
        self.export_stats["total_notes"] = len(notes)
        
        # Export notes
        with Progress() as progress:
            task = progress.add_task("Exporting notes...", total=len(notes))
            
            for note in notes:
                progress.update(task, advance=1)
                
                try:
                    markdown_content = self.export_note_to_markdown(note)
                    file_path = export_dir / f"{note.id}.md"
                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write(markdown_content)
                    self.export_stats["exported"] += 1
                except Exception as e:
                    logger.error(f"Error exporting note {note.id}: {e}")
                    self.export_stats["failed"] += 1
        
        console.print(f"\n✓ Exported {self.export_stats['exported']} notes")
        return self.export_stats

class BulkExporter:
    """Handle bulk export operations with progress tracking."""
    
    def __init__(self, repository: SQLiteNoteRepository):
        """Initialize bulk exporter."""
        self.repository = repository
        self.exporter = MarkdownExporter(repository)
    
    def create_timestamped_export(self, base_dir: Path, prefix: str = "export") -> Path:
        """Create a timestamped export of all notes."""
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        export_dir = base_dir / f"{prefix}_{timestamp}"
        
        # Export all notes
        stats = self.exporter.export_all_notes(export_dir)
        
        # Create export summary
        summary_path = export_dir / "_export_summary.txt"
        with open(summary_path, "w", encoding="utf-8") as f:
            f.write(f"Zettelkasten Export Summary\n")
            f.write(f"==========================\n\n")
            f.write(f"Export Date: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Total Notes: {stats['total_notes']}\n")
            f.write(f"Successfully Exported: {stats['exported']}\n")
            f.write(f"Failed: {stats['failed']}\n\n")
            
            if stats['warnings']:
                f.write("Warnings:\n")
                for warning in stats['warnings']:
                    f.write(f"  - {warning}\n")
        
        return export_dir
    
    def create_incremental_export(self, base_dir: Path, since: datetime.datetime) -> Path:
        """Create an incremental export of notes modified since a given date."""
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        export_dir = base_dir / f"incremental_{timestamp}"
        export_dir.mkdir(parents=True, exist_ok=True)
        
        # Get all notes and filter by update date
        all_notes = self.repository.list(limit=10000)  # Adjust limit as needed
        notes_to_export = [n for n in all_notes if n.updated_at >= since]
        
        console.print(f"Found {len(notes_to_export)} notes modified since {since}")
        
        # Export filtered notes
        exported = 0
        failed = 0
        
        with Progress() as progress:
            task = progress.add_task("Exporting modified notes...", total=len(notes_to_export))
            
            for note in notes_to_export:
                progress.update(task, advance=1)
                
                try:
                    markdown_content = self.exporter.export_note_to_markdown(note)
                    file_path = export_dir / f"{note.id}.md"
                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write(markdown_content)
                    exported += 1
                except Exception as e:
                    logger.error(f"Error exporting note {note.id}: {e}")
                    failed += 1
        
        # Save incremental metadata
        metadata_path = export_dir / "_incremental_metadata.json"
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump({
                "export_date": datetime.datetime.now().isoformat(),
                "since_date": since.isoformat(),
                "notes_exported": exported,
                "failed": failed,
                "note_ids": [n.id for n in notes_to_export]
            }, f, indent=2)
        
        console.print(f"\n✓ Incremental export completed: {exported} notes")
        return export_dir