"""Tests for export functionality."""
import datetime
import json
import tempfile
from pathlib import Path
import pytest

from zettelkasten_mcp.export_import.exporter import MarkdownExporter, BulkExporter
from zettelkasten_mcp.models.schema import Note, NoteType, Tag, Link, LinkType
from zettelkasten_mcp.storage.sqlite_repository import SQLiteNoteRepository

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
def repository(temp_db):
    """Create a repository instance for testing."""
    return SQLiteNoteRepository(temp_db)

@pytest.fixture
def sample_notes(repository):
    """Create sample notes in repository."""
    notes = [
        Note(
            id="20240101000000000000000",
            title="First Note",
            content="This is the first note.",
            note_type=NoteType.PERMANENT,
            tags=[Tag(name="test"), Tag(name="export")],
            links=[
                Link(
                    source_id="20240101000000000000000",
                    target_id="20240102000000000000000",
                    link_type=LinkType.REFERENCE,
                    description="Links to second note"
                )
            ],
            created_at=datetime.datetime(2024, 1, 1, 0, 0, 0),
            updated_at=datetime.datetime(2024, 1, 1, 12, 0, 0),
            metadata={"author": "Test Author", "category": "Testing"}
        ),
        Note(
            id="20240102000000000000000",
            title="Second Note",
            content="This is the second note.",
            note_type=NoteType.LITERATURE,
            tags=[Tag(name="test"), Tag(name="literature")],
            links=[],
            created_at=datetime.datetime(2024, 1, 2, 0, 0, 0),
            updated_at=datetime.datetime(2024, 1, 2, 0, 0, 0)
        ),
        Note(
            id="20240103000000000000000",
            title="Third Note",
            content="This is the third note.",
            note_type=NoteType.FLEETING,
            tags=[Tag(name="fleeting")],
            links=[],
            created_at=datetime.datetime(2024, 1, 3, 0, 0, 0),
            updated_at=datetime.datetime(2024, 1, 3, 0, 0, 0)
        )
    ]
    
    for note in notes:
        repository.create(note)
    
    return notes

class TestMarkdownExporter:
    """Test markdown export functionality."""
    
    def test_export_note_to_markdown(self, repository, sample_notes):
        """Test converting note to markdown format."""
        exporter = MarkdownExporter(repository)
        
        # Export first note
        markdown = exporter.export_note_to_markdown(sample_notes[0])
        
        # Verify frontmatter
        assert "id: 20240101000000000000000" in markdown
        assert "title: First Note" in markdown
        assert "type: permanent" in markdown
        assert "tags: test, export" in markdown
        assert "created: 2024-01-01T00:00:00" in markdown
        assert "updated: 2024-01-01T12:00:00" in markdown
        assert "author: Test Author" in markdown
        assert "category: Testing" in markdown
        
        # Verify content
        assert "This is the first note." in markdown
        
        # Verify links section
        assert "## Links" in markdown
        assert "- reference [[20240102000000000000000]] Links to second note" in markdown
    
    def test_export_note_without_links(self, repository, sample_notes):
        """Test exporting note without links."""
        exporter = MarkdownExporter(repository)
        
        # Export second note (no links)
        markdown = exporter.export_note_to_markdown(sample_notes[1])
        
        # Verify no links section
        assert "## Links" not in markdown
    
    def test_export_single_note(self, repository, sample_notes, tmp_path):
        """Test exporting a single note to file."""
        exporter = MarkdownExporter(repository)
        
        # Export single note
        success = exporter.export_single_note("20240101000000000000000", tmp_path)
        
        # Verify
        assert success is True
        note_file = tmp_path / "20240101000000000000000.md"
        assert note_file.exists()
        
        content = note_file.read_text()
        assert "title: First Note" in content
        assert "This is the first note." in content
    
    def test_export_nonexistent_note(self, repository, tmp_path):
        """Test exporting nonexistent note."""
        exporter = MarkdownExporter(repository)
        
        # Export nonexistent note
        success = exporter.export_single_note("nonexistent", tmp_path)
        
        # Verify
        assert success is False
    
    def test_export_all_notes(self, repository, sample_notes, tmp_path):
        """Test exporting all notes."""
        exporter = MarkdownExporter(repository)
        
        # Export all notes
        stats = exporter.export_all_notes(tmp_path)
        
        # Verify stats
        assert stats["total_notes"] == 3
        assert stats["exported"] == 3
        assert stats["failed"] == 0
        
        # Verify files
        for note in sample_notes:
            note_file = tmp_path / f"{note.id}.md"
            assert note_file.exists()
        
        # Verify metadata file
        metadata_file = tmp_path / "_export_metadata.json"
        assert metadata_file.exists()
        
        with open(metadata_file) as f:
            metadata = json.load(f)
        assert metadata["statistics"]["total_notes"] == 3
        assert metadata["statistics"]["exported"] == 3
    
    def test_export_by_tag(self, repository, sample_notes, tmp_path):
        """Test exporting notes by tag."""
        exporter = MarkdownExporter(repository)
        
        # Export notes with "test" tag
        stats = exporter.export_by_criteria(tmp_path, tag="test")
        
        # Verify
        assert stats["total_notes"] == 2  # First and second notes have "test" tag
        assert stats["exported"] == 2
        
        # Verify files
        assert (tmp_path / "20240101000000000000000.md").exists()
        assert (tmp_path / "20240102000000000000000.md").exists()
        assert not (tmp_path / "20240103000000000000000.md").exists()
    
    def test_export_by_note_type(self, repository, sample_notes, tmp_path):
        """Test exporting notes by type."""
        exporter = MarkdownExporter(repository)
        
        # Export literature notes
        stats = exporter.export_by_criteria(tmp_path, note_type=NoteType.LITERATURE.value)
        
        # Verify
        assert stats["total_notes"] == 1
        assert stats["exported"] == 1
        assert (tmp_path / "20240102000000000000000.md").exists()
    
    def test_export_by_search(self, repository, sample_notes, tmp_path):
        """Test exporting notes by search query."""
        exporter = MarkdownExporter(repository)
        
        # Export notes containing "first"
        stats = exporter.export_by_criteria(tmp_path, search_query="first")
        
        # Verify
        assert stats["total_notes"] == 1
        assert stats["exported"] == 1
        assert (tmp_path / "20240101000000000000000.md").exists()

class TestBulkExporter:
    """Test bulk export functionality."""
    
    def test_create_timestamped_export(self, repository, sample_notes, tmp_path):
        """Test creating timestamped export."""
        exporter = BulkExporter(repository)
        
        # Create export
        export_dir = exporter.create_timestamped_export(tmp_path)
        
        # Verify
        assert export_dir.exists()
        assert export_dir.name.startswith("export_")
        
        # Verify all notes exported
        for note in sample_notes:
            assert (export_dir / f"{note.id}.md").exists()
        
        # Verify summary file
        summary_file = export_dir / "_export_summary.txt"
        assert summary_file.exists()
        
        summary = summary_file.read_text()
        assert "Total Notes: 3" in summary
        assert "Successfully Exported: 3" in summary
    
    def test_create_incremental_export(self, repository, sample_notes, tmp_path):
        """Test creating incremental export."""
        exporter = BulkExporter(repository)
        
        # Export notes modified after Jan 2, 2024
        since = datetime.datetime(2024, 1, 2, 0, 0, 0)
        export_dir = exporter.create_incremental_export(tmp_path, since)
        
        # Verify
        assert export_dir.exists()
        assert export_dir.name.startswith("incremental_")
        
        # Only second and third notes should be exported (created on/after Jan 2)
        assert not (export_dir / "20240101000000000000000.md").exists()
        assert (export_dir / "20240102000000000000000.md").exists()
        assert (export_dir / "20240103000000000000000.md").exists()
        
        # Verify metadata
        metadata_file = export_dir / "_incremental_metadata.json"
        assert metadata_file.exists()
        
        with open(metadata_file) as f:
            metadata = json.load(f)
        assert metadata["notes_exported"] == 2
        assert len(metadata["note_ids"]) == 2