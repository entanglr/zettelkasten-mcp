"""Tests for markdown to SQLite migration."""
import datetime
import tempfile
from pathlib import Path
import pytest

from zettelkasten_mcp.migration.migrate_to_sqlite import (
    MarkdownToSQLiteMigrator, MigrationReport
)
from zettelkasten_mcp.models.schema import Note, NoteType, Tag, Link, LinkType
from zettelkasten_mcp.storage.sqlite_repository import SQLiteNoteRepository

@pytest.fixture
def temp_notes_dir():
    """Create a temporary directory for test notes."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)

@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)
    yield db_path
    # Cleanup
    if db_path.exists():
        db_path.unlink()

@pytest.fixture
def sample_markdown_note():
    """Sample markdown note content."""
    return """---
id: 20240101000000000000000
title: Test Note
type: permanent
tags: test, sample, migration
created: 2024-01-01T00:00:00
updated: 2024-01-01T12:00:00
custom_field: custom_value
---

# Test Note

This is a test note for migration testing.

## Content

Some interesting content here.

## Links

- reference [[20240102000000000000000]] Related note
- contrast [[20240103000000000000000]] Different perspective
"""

@pytest.fixture
def sample_markdown_note_without_id():
    """Sample markdown note without ID in frontmatter."""
    return """---
title: Note Without ID
type: literature
tags: test
created: 2024-01-02T00:00:00
---

# Note Without ID

This note doesn't have an ID in frontmatter.
"""

@pytest.fixture
def sample_markdown_note_minimal():
    """Minimal markdown note."""
    return """# Minimal Note

Just some content without frontmatter.

## Links

- reference [[20240102000000000000000]]
"""

class TestMigrationReport:
    """Test migration report functionality."""
    
    def test_report_initialization(self):
        """Test report initialization."""
        report = MigrationReport()
        assert report.total_files == 0
        assert report.successful_migrations == 0
        assert report.failed_migrations == 0
        assert len(report.warnings) == 0
        assert len(report.errors) == 0
    
    def test_add_success(self):
        """Test adding successful migration."""
        report = MigrationReport()
        report.add_success("note1", "Test Note")
        
        assert report.successful_migrations == 1
        assert len(report.notes_migrated) == 1
        assert report.notes_migrated[0]["id"] == "note1"
        assert report.notes_migrated[0]["title"] == "Test Note"
    
    def test_add_error(self):
        """Test adding migration error."""
        report = MigrationReport()
        report.add_error(Path("test.md"), "Test error")
        
        assert report.failed_migrations == 1
        assert len(report.errors) == 1
        assert report.errors[0]["file"] == "test.md"
        assert report.errors[0]["error"] == "Test error"
    
    def test_save_report(self, tmp_path):
        """Test saving report to file."""
        report = MigrationReport()
        report.total_files = 2
        report.add_success("note1", "Note 1")
        report.add_error(Path("failed.md"), "Parse error")
        report.add_warning("Test warning")
        
        report_path = tmp_path / "report.json"
        report.save_report(report_path)
        
        assert report_path.exists()
        
        # Verify content
        import json
        with open(report_path) as f:
            data = json.load(f)
        
        assert data["statistics"]["total_files"] == 2
        assert data["statistics"]["successful"] == 1
        assert data["statistics"]["failed"] == 1
        assert len(data["warnings"]) == 1

class TestMarkdownToSQLiteMigrator:
    """Test markdown to SQLite migration."""
    
    def test_parse_note_from_markdown(self, temp_notes_dir, temp_db, sample_markdown_note):
        """Test parsing note from markdown."""
        # Create test file
        note_file = temp_notes_dir / "test_note.md"
        note_file.write_text(sample_markdown_note)
        
        # Create migrator
        migrator = MarkdownToSQLiteMigrator(temp_notes_dir, temp_db)
        
        # Parse note
        note = migrator.parse_note_from_markdown(note_file)
        
        # Verify
        assert note is not None
        assert note.id == "20240101000000000000000"
        assert note.title == "Test Note"
        assert note.note_type == NoteType.PERMANENT
        assert len(note.tags) == 3
        assert {t.name for t in note.tags} == {"test", "sample", "migration"}
        assert len(note.links) == 2
        assert note.links[0].target_id == "20240102000000000000000"
        assert note.links[0].link_type == LinkType.REFERENCE
        assert note.links[1].target_id == "20240103000000000000000"
        assert note.links[1].link_type == LinkType.CONTRAST
        assert note.metadata["custom_field"] == "custom_value"
    
    def test_parse_note_without_id(self, temp_notes_dir, temp_db, sample_markdown_note_without_id):
        """Test parsing note without ID uses filename."""
        # Create test file
        note_file = temp_notes_dir / "note_without_id.md"
        note_file.write_text(sample_markdown_note_without_id)
        
        # Create migrator
        migrator = MarkdownToSQLiteMigrator(temp_notes_dir, temp_db)
        
        # Parse note
        note = migrator.parse_note_from_markdown(note_file)
        
        # Verify
        assert note is not None
        assert note.id == "note_without_id"
        assert note.title == "Note Without ID"
        assert len(migrator.report.warnings) == 1
        assert "No ID in frontmatter" in migrator.report.warnings[0]
    
    def test_parse_minimal_note(self, temp_notes_dir, temp_db, sample_markdown_note_minimal):
        """Test parsing minimal note without frontmatter."""
        # Create test file  
        note_file = temp_notes_dir / "minimal_note.md"
        note_file.write_text(sample_markdown_note_minimal)
        
        # Create migrator
        migrator = MarkdownToSQLiteMigrator(temp_notes_dir, temp_db)
        
        # Parse note
        note = migrator.parse_note_from_markdown(note_file)
        
        # Verify
        assert note is not None
        assert note.id == "minimal_note"
        assert note.title == "Minimal Note"
        assert note.note_type == NoteType.PERMANENT  # Default
        assert len(note.links) == 1
    
    def test_migrate_single_note(self, temp_notes_dir, temp_db, sample_markdown_note):
        """Test migrating a single note."""
        # Create test file
        note_file = temp_notes_dir / "test_note.md"
        note_file.write_text(sample_markdown_note)
        
        # Create migrator
        migrator = MarkdownToSQLiteMigrator(temp_notes_dir, temp_db)
        
        # Migrate note
        success = migrator.migrate_note(note_file)
        assert success is True
        assert migrator.report.successful_migrations == 1
        
        # Verify in database
        repo = SQLiteNoteRepository(temp_db)
        note = repo.read("20240101000000000000000")
        assert note is not None
        assert note.title == "Test Note"
    
    def test_migrate_invalid_note(self, temp_notes_dir, temp_db):
        """Test migrating invalid note."""
        # Create invalid file
        note_file = temp_notes_dir / "invalid.md"
        note_file.write_text("Invalid content without proper structure")
        
        # Create migrator
        migrator = MarkdownToSQLiteMigrator(temp_notes_dir, temp_db)
        
        # Migrate note
        success = migrator.migrate_note(note_file)
        assert success is False
        assert migrator.report.failed_migrations == 1
    
    def test_create_backup(self, temp_notes_dir, temp_db, sample_markdown_note):
        """Test backup creation."""
        # Create test files
        note_file = temp_notes_dir / "test_note.md"
        note_file.write_text(sample_markdown_note)
        
        # Create migrator
        backup_dir = temp_notes_dir.parent / "backups"
        migrator = MarkdownToSQLiteMigrator(temp_notes_dir, temp_db, backup_dir)
        
        # Create backup
        backup_path = migrator.create_backup()
        
        # Verify
        assert backup_path.exists()
        assert (backup_path / "test_note.md").exists()
        assert (backup_path / "test_note.md").read_text() == sample_markdown_note
    
    def test_verify_migration(self, temp_notes_dir, temp_db, sample_markdown_note):
        """Test migration verification."""
        # Create test file
        note_file = temp_notes_dir / "20240101000000000000000.md"
        note_file.write_text(sample_markdown_note)
        
        # Create migrator and migrate
        migrator = MarkdownToSQLiteMigrator(temp_notes_dir, temp_db)
        migrator.migrate_note(note_file)
        
        # Verify
        is_valid, issues = migrator.verify_migration()
        assert is_valid is True
        assert len(issues) == 0
    
    def test_verify_migration_with_issues(self, temp_notes_dir, temp_db, sample_markdown_note):
        """Test migration verification with issues."""
        # Create test file
        note_file = temp_notes_dir / "20240101000000000000000.md"
        note_file.write_text(sample_markdown_note)
        
        # Create migrator and migrate
        migrator = MarkdownToSQLiteMigrator(temp_notes_dir, temp_db)
        migrator.migrate_note(note_file)
        
        # Modify the database note to create mismatch
        repo = SQLiteNoteRepository(temp_db)
        note = repo.read("20240101000000000000000")
        note.title = "Modified Title"
        repo.update(note)
        
        # Verify
        is_valid, issues = migrator.verify_migration()
        assert is_valid is False
        assert len(issues) > 0
        assert any("Title mismatch" in issue for issue in issues)
    
    def test_run_migration_complete(self, temp_notes_dir, temp_db, sample_markdown_note):
        """Test complete migration process."""
        # Create multiple test files
        for i in range(3):
            note_content = sample_markdown_note.replace(
                "20240101000000000000000",
                f"2024010100000000000000{i}"
            ).replace("Test Note", f"Test Note {i}")
            
            note_file = temp_notes_dir / f"note_{i}.md"
            note_file.write_text(note_content)
        
        # Create migrator
        migrator = MarkdownToSQLiteMigrator(temp_notes_dir, temp_db)
        
        # Run migration
        success = migrator.run_migration(skip_backup=False, verify=True)
        
        # Verify
        assert success is True
        assert migrator.report.successful_migrations == 3
        assert migrator.report.failed_migrations == 0
        
        # Verify in database
        repo = SQLiteNoteRepository(temp_db)
        stats = repo.get_statistics()
        assert stats["total_notes"] == 3
    
    def test_extract_links_from_content(self, temp_notes_dir, temp_db):
        """Test link extraction from content."""
        content = """# Note

Some content.

## Links

- reference [[20240102000000000000000]] Basic reference
- extends [[20240103000000000000000]] Extends this idea
- contrast [[20240104000000000000000]]
- invalid_type [[20240105000000000000000]] Will default to reference
"""
        
        migrator = MarkdownToSQLiteMigrator(temp_notes_dir, temp_db)
        links = migrator._extract_links_from_content("source_id", content)
        
        assert len(links) == 4
        assert links[0].target_id == "20240102000000000000000"
        assert links[0].link_type == LinkType.REFERENCE
        assert links[0].description == "Basic reference"
        assert links[1].link_type == LinkType.EXTENDS
        assert links[2].link_type == LinkType.CONTRAST
        assert links[2].description is None
        assert links[3].link_type == LinkType.REFERENCE  # Invalid type defaults to reference