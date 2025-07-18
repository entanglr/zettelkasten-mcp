"""Import utilities for restoring notes from markdown files to SQLite."""
import datetime
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Set

import frontmatter
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.prompt import Confirm

from zettelkasten_mcp.models.schema import Note, Tag, Link, LinkType, NoteType
from zettelkasten_mcp.storage.sqlite_repository import SQLiteNoteRepository

console = Console()
logger = logging.getLogger(__name__)

class MarkdownImporter:
    """Import notes from markdown files to SQLite database."""
    
    def __init__(self, repository: SQLiteNoteRepository):
        """Initialize importer with repository."""
        self.repository = repository
        self.import_stats = {
            "total_files": 0,
            "imported": 0,
            "updated": 0,
            "skipped": 0,
            "failed": 0,
            "warnings": []
        }
    
    def parse_note_from_markdown(self, file_path: Path) -> Optional[Note]:
        """Parse a note from markdown file."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            
            # Parse frontmatter
            post = frontmatter.loads(content)
            metadata = post.metadata
            
            # Extract required fields
            note_id = metadata.get("id")
            if not note_id:
                self.import_stats["warnings"].append(f"No ID in {file_path}, skipping")
                return None
            
            title = metadata.get("title", f"Untitled Note {note_id}")
            
            # Extract note type
            note_type_str = metadata.get("type", NoteType.PERMANENT.value)
            try:
                note_type = NoteType(note_type_str)
            except ValueError:
                note_type = NoteType.PERMANENT
                self.import_stats["warnings"].append(
                    f"Invalid note type '{note_type_str}' in {file_path}, using PERMANENT"
                )
            
            # Extract tags
            tags_data = metadata.get("tags", "")
            if isinstance(tags_data, str):
                tag_names = [t.strip() for t in tags_data.split(",") if t.strip()]
            elif isinstance(tags_data, list):
                tag_names = [str(t).strip() for t in tags_data if str(t).strip()]
            else:
                tag_names = []
            tags = [Tag(name=name) for name in tag_names]
            
            # Extract links from content
            links = self._extract_links_from_content(note_id, post.content)
            
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
            
            # Extract metadata
            extra_metadata = {
                k: v for k, v in metadata.items()
                if k not in ["id", "title", "type", "tags", "created", "updated"]
            }
            
            return Note(
                id=note_id,
                title=title,
                content=post.content,
                note_type=note_type,
                tags=tags,
                links=links,
                created_at=created_at,
                updated_at=updated_at,
                metadata=extra_metadata
            )
            
        except Exception as e:
            logger.error(f"Error parsing {file_path}: {e}")
            self.import_stats["warnings"].append(f"Failed to parse {file_path}: {str(e)}")
            return None
    
    def _extract_links_from_content(self, source_id: str, content: str) -> List[Link]:
        """Extract links from note content."""
        links = []
        links_section = False
        
        for line in content.split("\n"):
            line = line.strip()
            
            if line.startswith("## Links"):
                links_section = True
                continue
            if links_section and line.startswith("## "):
                links_section = False
                continue
            
            if links_section and line.startswith("- "):
                try:
                    if "[[" in line and "]]" in line:
                        parts = line.split("[[", 1)
                        link_type_str = parts[0].strip()
                        if link_type_str.startswith("- "):
                            link_type_str = link_type_str[2:].strip()
                        
                        id_and_desc = parts[1].split("]]", 1)
                        target_id = id_and_desc[0].strip()
                        description = None
                        if len(id_and_desc) > 1:
                            description = id_and_desc[1].strip()
                        
                        try:
                            link_type = LinkType(link_type_str)
                        except ValueError:
                            link_type = LinkType.REFERENCE
                        
                        links.append(
                            Link(
                                source_id=source_id,
                                target_id=target_id,
                                link_type=link_type,
                                description=description,
                                created_at=datetime.datetime.now()
                            )
                        )
                except Exception as e:
                    logger.error(f"Error parsing link: {line} - {e}")
        
        return links
    
    def import_single_file(self, file_path: Path, update_existing: bool = False) -> bool:
        """Import a single markdown file."""
        try:
            # Parse note
            note = self.parse_note_from_markdown(file_path)
            if not note:
                self.import_stats["failed"] += 1
                return False
            
            # Check if note exists
            existing = self.repository.read(note.id)
            
            if existing:
                if update_existing:
                    self.repository.update(note)
                    self.import_stats["updated"] += 1
                    logger.info(f"Updated note {note.id}")
                else:
                    self.import_stats["skipped"] += 1
                    logger.info(f"Skipped existing note {note.id}")
            else:
                self.repository.create(note)
                self.import_stats["imported"] += 1
                logger.info(f"Imported note {note.id}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error importing {file_path}: {e}")
            self.import_stats["failed"] += 1
            self.import_stats["warnings"].append(f"Failed to import {file_path}: {str(e)}")
            return False
    
    def import_directory(self, import_dir: Path, update_existing: bool = False,
                        batch_size: int = 50) -> Dict[str, any]:
        """Import all markdown files from a directory."""
        if not import_dir.exists():
            raise ValueError(f"Import directory {import_dir} does not exist")
        
        # Get all markdown files
        md_files = list(import_dir.glob("*.md"))
        # Exclude metadata files
        md_files = [f for f in md_files if not f.name.startswith("_")]
        
        self.import_stats["total_files"] = len(md_files)
        
        console.print(f"[bold]Importing {len(md_files)} markdown files from {import_dir}[/bold]\n")
        
        # Import in batches for better transaction management
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console
        ) as progress:
            task = progress.add_task("Importing notes...", total=len(md_files))
            
            for i in range(0, len(md_files), batch_size):
                batch = md_files[i:i + batch_size]
                
                for file_path in batch:
                    progress.update(task, advance=1, description=f"Importing {file_path.name}")
                    self.import_single_file(file_path, update_existing)
        
        # Display summary
        console.print(f"\n[green]✓ Import completed![/green]")
        console.print(f"  • Imported: {self.import_stats['imported']}")
        console.print(f"  • Updated: {self.import_stats['updated']}")
        console.print(f"  • Skipped: {self.import_stats['skipped']}")
        console.print(f"  • Failed: {self.import_stats['failed']}")
        
        if self.import_stats["warnings"]:
            console.print(f"\n[yellow]Warnings ({len(self.import_stats['warnings'])}):[/yellow]")
            for warning in self.import_stats["warnings"][:5]:
                console.print(f"  • {warning}")
            if len(self.import_stats["warnings"]) > 5:
                console.print(f"  ... and {len(self.import_stats['warnings']) - 5} more")
        
        return self.import_stats
    
    def validate_links(self) -> Dict[str, List[str]]:
        """Validate all links in the database."""
        console.print("\nValidating links...")
        
        broken_links = {}
        all_notes = self.repository.list(limit=10000)
        note_ids = {note.id for note in all_notes}
        
        with Progress() as progress:
            task = progress.add_task("Checking links...", total=len(all_notes))
            
            for note in all_notes:
                progress.update(task, advance=1)
                
                broken = []
                for link in note.links:
                    if link.target_id not in note_ids:
                        broken.append(link.target_id)
                
                if broken:
                    broken_links[note.id] = broken
        
        if broken_links:
            console.print(f"\n[yellow]Found {len(broken_links)} notes with broken links[/yellow]")
            for note_id, targets in list(broken_links.items())[:5]:
                console.print(f"  • {note_id} → {', '.join(targets)}")
            if len(broken_links) > 5:
                console.print(f"  ... and {len(broken_links) - 5} more")
        else:
            console.print("\n[green]✓ All links are valid[/green]")
        
        return broken_links

class BulkImporter:
    """Handle bulk import operations."""
    
    def __init__(self, repository: SQLiteNoteRepository):
        """Initialize bulk importer."""
        self.repository = repository
        self.importer = MarkdownImporter(repository)
    
    def restore_from_export(self, export_dir: Path, clear_existing: bool = False) -> bool:
        """Restore notes from a previous export."""
        if not export_dir.exists():
            console.print(f"[red]Export directory {export_dir} does not exist[/red]")
            return False
        
        # Check for export metadata
        metadata_path = export_dir / "_export_metadata.json"
        if metadata_path.exists():
            with open(metadata_path, "r", encoding="utf-8") as f:
                metadata = json.load(f)
            
            console.print(f"[bold]Restoring from export dated {metadata['export_date']}[/bold]")
            console.print(f"Export contains {metadata['statistics']['total_notes']} notes\n")
        
        # Confirm action
        if clear_existing:
            if not Confirm.ask("[red]This will DELETE all existing notes. Continue?[/red]"):
                console.print("Restore cancelled")
                return False
            
            # Clear database
            console.print("Clearing existing notes...")
            all_notes = self.repository.list(limit=10000)
            for note in all_notes:
                try:
                    self.repository.delete(note.id)
                except ValueError:
                    pass  # Note might already be deleted
            console.print("✓ Database cleared\n")
        
        # Import notes
        stats = self.importer.import_directory(export_dir, update_existing=not clear_existing)
        
        # Validate links
        self.importer.validate_links()
        
        success = stats["failed"] == 0
        if success:
            console.print("\n[green]✓ Restore completed successfully![/green]")
        else:
            console.print(f"\n[red]Restore completed with {stats['failed']} errors[/red]")
        
        return success
    
    def merge_imports(self, import_dirs: List[Path], strategy: str = "newest") -> Dict[str, any]:
        """Merge imports from multiple directories."""
        all_notes = {}
        total_files = 0
        
        # Collect all notes from all directories
        for import_dir in import_dirs:
            if not import_dir.exists():
                console.print(f"[yellow]Skipping non-existent directory: {import_dir}[/yellow]")
                continue
            
            md_files = [f for f in import_dir.glob("*.md") if not f.name.startswith("_")]
            total_files += len(md_files)
            
            console.print(f"Reading {len(md_files)} files from {import_dir}")
            
            for file_path in md_files:
                note = self.importer.parse_note_from_markdown(file_path)
                if note:
                    if note.id not in all_notes:
                        all_notes[note.id] = []
                    all_notes[note.id].append((note, file_path))
        
        # Resolve conflicts based on strategy
        console.print(f"\nResolving conflicts using '{strategy}' strategy...")
        
        notes_to_import = []
        conflicts = 0
        
        for note_id, versions in all_notes.items():
            if len(versions) == 1:
                notes_to_import.append(versions[0][0])
            else:
                conflicts += 1
                # Apply merge strategy
                if strategy == "newest":
                    # Choose version with latest updated_at
                    selected = max(versions, key=lambda x: x[0].updated_at)
                elif strategy == "oldest":
                    # Choose version with earliest updated_at
                    selected = min(versions, key=lambda x: x[0].updated_at)
                elif strategy == "largest":
                    # Choose version with most content
                    selected = max(versions, key=lambda x: len(x[0].content))
                else:
                    # Default to first found
                    selected = versions[0]
                
                notes_to_import.append(selected[0])
        
        if conflicts:
            console.print(f"Resolved {conflicts} conflicts")
        
        # Import merged notes
        console.print(f"\nImporting {len(notes_to_import)} unique notes...")
        
        imported = 0
        failed = 0
        
        with Progress() as progress:
            task = progress.add_task("Importing merged notes...", total=len(notes_to_import))
            
            for note in notes_to_import:
                progress.update(task, advance=1)
                
                try:
                    existing = self.repository.read(note.id)
                    if existing:
                        self.repository.update(note)
                    else:
                        self.repository.create(note)
                    imported += 1
                except Exception as e:
                    logger.error(f"Error importing note {note.id}: {e}")
                    failed += 1
        
        console.print(f"\n✓ Merge import completed: {imported} imported, {failed} failed")
        
        return {
            "total_files": total_files,
            "unique_notes": len(all_notes),
            "conflicts": conflicts,
            "imported": imported,
            "failed": failed
        }