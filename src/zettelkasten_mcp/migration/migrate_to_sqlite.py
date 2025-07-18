#!/usr/bin/env python3
"""Migration script to convert markdown files to SQLite-only storage."""
import argparse
import datetime
import json
import logging
import shutil
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import frontmatter
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.table import Table

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from zettelkasten_mcp.config import config
from zettelkasten_mcp.models.schema import Note, Tag, Link, LinkType, NoteType
from zettelkasten_mcp.storage.note_repository import NoteRepository
from zettelkasten_mcp.storage.sqlite_repository import SQLiteNoteRepository

console = Console()
logger = logging.getLogger(__name__)

class MigrationReport:
    """Track migration statistics and issues."""
    
    def __init__(self):
        self.total_files = 0
        self.successful_migrations = 0
        self.failed_migrations = 0
        self.warnings = []
        self.errors = []
        self.notes_migrated = []
        self.start_time = datetime.datetime.now()
    
    def add_success(self, note_id: str, title: str):
        """Record successful migration."""
        self.successful_migrations += 1
        self.notes_migrated.append({"id": note_id, "title": title})
    
    def add_error(self, file_path: str, error: str):
        """Record migration error."""
        self.failed_migrations += 1
        self.errors.append({"file": str(file_path), "error": str(error)})
    
    def add_warning(self, message: str):
        """Record migration warning."""
        self.warnings.append(message)
    
    def get_duration(self) -> float:
        """Get migration duration in seconds."""
        return (datetime.datetime.now() - self.start_time).total_seconds()
    
    def save_report(self, report_path: Path):
        """Save migration report to JSON file."""
        report_data = {
            "migration_date": self.start_time.isoformat(),
            "duration_seconds": self.get_duration(),
            "statistics": {
                "total_files": self.total_files,
                "successful": self.successful_migrations,
                "failed": self.failed_migrations,
                "success_rate": (self.successful_migrations / self.total_files * 100) 
                                if self.total_files > 0 else 0
            },
            "notes_migrated": self.notes_migrated,
            "warnings": self.warnings,
            "errors": self.errors
        }
        
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report_data, f, indent=2)
    
    def display_summary(self):
        """Display migration summary to console."""
        console.print("\n[bold]Migration Summary[/bold]")
        
        # Statistics table
        table = Table(title="Statistics")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")
        
        table.add_row("Total Files", str(self.total_files))
        table.add_row("Successful", str(self.successful_migrations))
        table.add_row("Failed", str(self.failed_migrations))
        table.add_row("Success Rate", 
                     f"{(self.successful_migrations / self.total_files * 100):.1f}%" 
                     if self.total_files > 0 else "N/A")
        table.add_row("Duration", f"{self.get_duration():.2f} seconds")
        
        console.print(table)
        
        # Warnings
        if self.warnings:
            console.print(f"\n[yellow]Warnings ({len(self.warnings)}):[/yellow]")
            for warning in self.warnings[:5]:
                console.print(f"  • {warning}")
            if len(self.warnings) > 5:
                console.print(f"  ... and {len(self.warnings) - 5} more")
        
        # Errors
        if self.errors:
            console.print(f"\n[red]Errors ({len(self.errors)}):[/red]")
            for error in self.errors[:5]:
                console.print(f"  • {error['file']}: {error['error']}")
            if len(self.errors) > 5:
                console.print(f"  ... and {len(self.errors) - 5} more")

class MarkdownToSQLiteMigrator:
    """Migrate Zettelkasten from markdown files to SQLite-only storage."""
    
    def __init__(self, notes_dir: Path, db_path: Path, backup_dir: Optional[Path] = None):
        """Initialize migrator."""
        self.notes_dir = notes_dir
        self.db_path = db_path
        self.backup_dir = backup_dir or notes_dir.parent / "backups"
        self.report = MigrationReport()
        
        # Create SQLite repository
        self.sqlite_repo = SQLiteNoteRepository(db_path)
    
    def create_backup(self) -> Path:
        """Create backup of current notes directory."""
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = self.backup_dir / f"notes_backup_{timestamp}"
        
        console.print(f"Creating backup at {backup_path}...")
        shutil.copytree(self.notes_dir, backup_path)
        
        # Also backup existing database if it exists
        if self.db_path.exists():
            db_backup = self.backup_dir / f"database_backup_{timestamp}.db"
            shutil.copy2(self.db_path, db_backup)
        
        return backup_path
    
    def parse_note_from_markdown(self, file_path: Path) -> Optional[Note]:
        """Parse a note from markdown file."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            
            # Parse frontmatter
            post = frontmatter.loads(content)
            metadata = post.metadata
            
            # Extract note ID
            note_id = metadata.get("id")
            if not note_id:
                # Try to generate from filename
                note_id = file_path.stem
                self.report.add_warning(f"No ID in frontmatter for {file_path}, using filename: {note_id}")
            
            # Extract title
            title = metadata.get("title", "")
            if not title:
                # Try to extract from first heading
                lines = post.content.strip().split("\n")
                for line in lines:
                    if line.startswith("# "):
                        title = line[2:].strip()
                        break
                if not title:
                    title = f"Untitled Note {note_id}"
                    self.report.add_warning(f"No title found for {file_path}, using: {title}")
            
            # Extract note type
            note_type_str = metadata.get("type", NoteType.PERMANENT.value)
            try:
                note_type = NoteType(note_type_str)
            except ValueError:
                note_type = NoteType.PERMANENT
                self.report.add_warning(f"Invalid note type '{note_type_str}' for {file_path}, defaulting to PERMANENT")
            
            # Extract tags
            tags_data = metadata.get("tags", "")
            if isinstance(tags_data, str):
                tag_names = [t.strip() for t in tags_data.split(",") if t.strip()]
            elif isinstance(tags_data, list):
                tag_names = [str(t).strip() for t in tags_data if str(t).strip()]
            else:
                tag_names = []
            tags = [Tag(name=name) for name in tag_names]
            
            # Extract links
            links = self._extract_links_from_content(note_id, post.content)
            
            # Extract timestamps
            created_str = metadata.get("created")
            created_at = (
                datetime.datetime.fromisoformat(created_str)
                if created_str
                else datetime.datetime.fromtimestamp(file_path.stat().st_ctime)
            )
            
            updated_str = metadata.get("updated")
            updated_at = (
                datetime.datetime.fromisoformat(updated_str)
                if updated_str
                else datetime.datetime.fromtimestamp(file_path.stat().st_mtime)
            )
            
            # Store any extra metadata
            extra_metadata = {
                k: v for k, v in metadata.items() 
                if k not in ["id", "title", "type", "tags", "created", "updated"]
            }
            
            # Add migration info
            extra_metadata["migrated_from"] = str(file_path)
            extra_metadata["migration_date"] = datetime.datetime.now().isoformat()
            
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
            return None
    
    def _extract_links_from_content(self, source_id: str, content: str) -> List[Link]:
        """Extract links from note content."""
        links = []
        links_section = False
        
        for line in content.split("\n"):
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
                    if "[[" in line and "]]" in line:
                        # Split the line at the [[ delimiter
                        parts = line.split("[[", 1)
                        # Extract the link type from before [[
                        link_type_str = parts[0].strip()
                        if link_type_str.startswith("- "):
                            link_type_str = link_type_str[2:].strip()
                        
                        # Extract target ID and description
                        id_and_desc = parts[1].split("]]", 1)
                        target_id = id_and_desc[0].strip()
                        description = None
                        if len(id_and_desc) > 1:
                            description = id_and_desc[1].strip()
                        
                        # Validate link type
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
    
    def migrate_note(self, file_path: Path) -> bool:
        """Migrate a single note file."""
        try:
            # Parse note from markdown
            note = self.parse_note_from_markdown(file_path)
            if not note:
                self.report.add_error(file_path, "Failed to parse note")
                return False
            
            # Create note in SQLite
            self.sqlite_repo.create(note)
            
            self.report.add_success(note.id, note.title)
            return True
            
        except Exception as e:
            self.report.add_error(file_path, str(e))
            logger.error(f"Error migrating {file_path}: {e}")
            return False
    
    def verify_migration(self) -> Tuple[bool, List[str]]:
        """Verify that all notes were migrated correctly."""
        issues = []
        
        # Get all markdown files
        md_files = list(self.notes_dir.glob("*.md"))
        md_count = len(md_files)
        
        # Get statistics from SQLite
        stats = self.sqlite_repo.get_statistics()
        db_count = stats["total_notes"]
        
        # Check counts
        if md_count != db_count:
            issues.append(f"Count mismatch: {md_count} files vs {db_count} in database")
        
        # Verify each note
        with Progress() as progress:
            task = progress.add_task("Verifying notes...", total=md_count)
            
            for md_file in md_files:
                progress.update(task, advance=1)
                
                # Parse note from file
                file_note = self.parse_note_from_markdown(md_file)
                if not file_note:
                    issues.append(f"Could not parse {md_file} for verification")
                    continue
                
                # Read note from database
                db_note = self.sqlite_repo.read(file_note.id)
                if not db_note:
                    issues.append(f"Note {file_note.id} not found in database")
                    continue
                
                # Compare content
                if file_note.title != db_note.title:
                    issues.append(f"Title mismatch for {file_note.id}")
                if file_note.content != db_note.content:
                    issues.append(f"Content mismatch for {file_note.id}")
                if file_note.note_type != db_note.note_type:
                    issues.append(f"Type mismatch for {file_note.id}")
                
                # Compare tags (order doesn't matter)
                file_tags = set(t.name for t in file_note.tags)
                db_tags = set(t.name for t in db_note.tags)
                if file_tags != db_tags:
                    issues.append(f"Tags mismatch for {file_note.id}")
        
        return len(issues) == 0, issues
    
    def run_migration(self, skip_backup: bool = False, verify: bool = True) -> bool:
        """Run the complete migration process."""
        console.print("[bold]Starting Zettelkasten Migration to SQLite[/bold]\n")
        
        # Step 1: Create backup
        if not skip_backup:
            backup_path = self.create_backup()
            console.print(f"✓ Backup created at {backup_path}\n")
        
        # Step 2: Count files
        md_files = list(self.notes_dir.glob("*.md"))
        self.report.total_files = len(md_files)
        console.print(f"Found {self.report.total_files} markdown files to migrate\n")
        
        # Step 3: Migrate notes
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console
        ) as progress:
            task = progress.add_task("Migrating notes...", total=self.report.total_files)
            
            for md_file in md_files:
                progress.update(task, advance=1, description=f"Migrating {md_file.name}")
                self.migrate_note(md_file)
        
        # Step 4: Verify migration
        if verify:
            console.print("\nVerifying migration...")
            is_valid, issues = self.verify_migration()
            
            if is_valid:
                console.print("✓ Migration verification passed\n")
            else:
                console.print(f"[red]✗ Migration verification found {len(issues)} issues[/red]")
                for issue in issues[:10]:
                    console.print(f"  • {issue}")
                if len(issues) > 10:
                    console.print(f"  ... and {len(issues) - 10} more")
                self.report.add_warning(f"Verification found {len(issues)} issues")
        
        # Step 5: Optimize database
        console.print("Optimizing database...")
        self.sqlite_repo.optimize()
        console.print("✓ Database optimized\n")
        
        # Step 6: Display summary
        self.report.display_summary()
        
        # Step 7: Save report
        report_path = self.backup_dir / f"migration_report_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        self.report.save_report(report_path)
        console.print(f"\n✓ Migration report saved to {report_path}")
        
        success = self.report.failed_migrations == 0
        if success:
            console.print("\n[green]✓ Migration completed successfully![/green]")
        else:
            console.print(f"\n[red]✗ Migration completed with {self.report.failed_migrations} errors[/red]")
        
        return success

def main():
    """Main entry point for migration script."""
    parser = argparse.ArgumentParser(
        description="Migrate Zettelkasten from markdown files to SQLite-only storage"
    )
    parser.add_argument(
        "--notes-dir",
        type=Path,
        help="Directory containing markdown notes (default: from config)"
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        help="Path for SQLite database (default: from config)"
    )
    parser.add_argument(
        "--backup-dir",
        type=Path,
        help="Directory for backups (default: notes_dir/../backups)"
    )
    parser.add_argument(
        "--skip-backup",
        action="store_true",
        help="Skip creating backup (not recommended)"
    )
    parser.add_argument(
        "--skip-verify",
        action="store_true",
        help="Skip migration verification"
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level"
    )
    
    args = parser.parse_args()
    
    # Configure logging
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    # Set paths
    notes_dir = args.notes_dir or config.get_absolute_path(config.notes_dir)
    db_path = args.db_path or Path(config.get_db_url().replace("sqlite:///", ""))
    
    # Create migrator
    migrator = MarkdownToSQLiteMigrator(
        notes_dir=notes_dir,
        db_path=db_path,
        backup_dir=args.backup_dir
    )
    
    # Run migration
    success = migrator.run_migration(
        skip_backup=args.skip_backup,
        verify=not args.skip_verify
    )
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()