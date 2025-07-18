"""Tests for import functionality."""
import datetime
import json
import tempfile
from pathlib import Path
import pytest

from zettelkasten_mcp.export_import.importer import MarkdownImporter, BulkImporter
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
def sample_markdown_files(tmp_path):
    """Create sample markdown files for import."""
    files = []
    
    # First note
    content1 = """---
id: 20240101000000000000000
title: First Note
type: permanent
tags: test, import
created: 2024-01-01T00:00:00
updated: 2024-01-01T12:00:00
author: Test Author
---

# First Note

This is the first note for import testing.

## Links

- reference [[20240102000000000000000]] Links to second note
"""
    file1 = tmp_path / "20240101000000000000000.md"
    file1.write_text(content1)
    files.append(file1)
    
    # Second note
    content2 = """---
id: 20240102000000000000000
title: Second Note
type: literature
tags: test, literature
created: 2024-01-02T00:00:00
updated: 2024-01-02T00:00:00
---

# Second Note

This is the second note.
"""
    file2 = tmp_path / "20240102000000000000000.md"
    file2.write_text(content2)
    files.append(file2)
    
    # Note without ID
    content3 = """---
title: Note Without ID
type: fleeting
tags: fleeting
---

Content without ID.
"""
    file3 = tmp_path / "note_without_id.md"
    file3.write_text(content3)
    files.append(file3)
    
    return files

class TestMarkdownImporter:
    """Test markdown import functionality."""
    
    def test_parse_note_from_markdown(self, repository, sample_markdown_files):
        """Test parsing note from markdown file."""
        importer = MarkdownImporter(repository)
        
        # Parse first note
        note = importer.parse_note_from_markdown(sample_markdown_files[0])
        
        # Verify
        assert note is not None
        assert note.id == "20240101000000000000000"
        assert note.title == "First Note"
        assert note.note_type == NoteType.PERMANENT
        assert len(note.tags) == 2
        assert {t.name for t in note.tags} == {"test", "import"}
        assert len(note.links) == 1
        assert note.links[0].target_id == "20240102000000000000000"
        assert note.metadata["author"] == "Test Author"
    
    def test_parse_note_without_id(self, repository, sample_markdown_files):
        """Test parsing note without ID returns None."""
        importer = MarkdownImporter(repository)
        
        # Parse note without ID
        note = importer.parse_note_from_markdown(sample_markdown_files[2])
        
        # Verify
        assert note is None
        assert len(importer.import_stats["warnings"]) == 1
        assert "No ID" in importer.import_stats["warnings"][0]
    
    def test_import_single_file(self, repository, sample_markdown_files):
        """Test importing a single markdown file."""
        importer = MarkdownImporter(repository)
        
        # Import first file
        success = importer.import_single_file(sample_markdown_files[0])
        
        # Verify
        assert success is True
        assert importer.import_stats["imported"] == 1
        
        # Verify in database
        note = repository.read("20240101000000000000000")
        assert note is not None
        assert note.title == "First Note"
    
    def test_import_existing_file_skip(self, repository, sample_markdown_files):
        """Test importing existing file without update."""
        importer = MarkdownImporter(repository)
        
        # Import file twice
        importer.import_single_file(sample_markdown_files[0])
        importer.import_single_file(sample_markdown_files[0], update_existing=False)
        
        # Verify
        assert importer.import_stats["imported"] == 1
        assert importer.import_stats["skipped"] == 1
    
    def test_import_existing_file_update(self, repository, sample_markdown_files):
        """Test importing existing file with update."""
        importer = MarkdownImporter(repository)
        
        # Import file
        importer.import_single_file(sample_markdown_files[0])
        
        # Modify the note in database
        note = repository.read("20240101000000000000000")
        note.title = "Modified Title"
        repository.update(note)
        
        # Import again with update
        importer.import_single_file(sample_markdown_files[0], update_existing=True)
        
        # Verify
        assert importer.import_stats["updated"] == 1
        
        # Check title restored
        note = repository.read("20240101000000000000000")
        assert note.title == "First Note"
    
    def test_import_directory(self, repository, sample_markdown_files):
        """Test importing all files from directory."""
        importer = MarkdownImporter(repository)
        
        # Import directory
        stats = importer.import_directory(sample_markdown_files[0].parent)
        
        # Verify stats
        assert stats["total_files"] == 3
        assert stats["imported"] == 2  # Two valid files
        assert stats["failed"] == 1     # One without ID
        assert stats["skipped"] == 0
        
        # Verify in database
        assert repository.read("20240101000000000000000") is not None
        assert repository.read("20240102000000000000000") is not None
    
    def test_validate_links(self, repository, sample_markdown_files):
        """Test link validation."""
        importer = MarkdownImporter(repository)
        
        # Import only first file (has link to second which doesn't exist)
        importer.import_single_file(sample_markdown_files[0])
        
        # Validate links
        broken_links = importer.validate_links()
        
        # Verify
        assert len(broken_links) == 1
        assert "20240101000000000000000" in broken_links
        assert "20240102000000000000000" in broken_links["20240101000000000000000"]
        
        # Import second file
        importer.import_single_file(sample_markdown_files[1])
        
        # Validate again
        broken_links = importer.validate_links()
        assert len(broken_links) == 0

class TestBulkImporter:
    """Test bulk import functionality."""
    
    def test_restore_from_export(self, repository, sample_markdown_files):
        """Test restoring from export directory."""
        importer = BulkImporter(repository)
        
        # Create export metadata
        metadata = {
            "export_date": datetime.datetime.now().isoformat(),
            "statistics": {
                "total_notes": 2,
                "exported": 2,
                "failed": 0
            }
        }
        metadata_file = sample_markdown_files[0].parent / "_export_metadata.json"
        with open(metadata_file, "w") as f:
            json.dump(metadata, f)
        
        # Restore
        success = importer.restore_from_export(sample_markdown_files[0].parent)
        
        # Verify
        assert success is True
        
        # Check notes in database
        stats = repository.get_statistics()
        assert stats["total_notes"] == 2
    
    def test_restore_with_clear_existing(self, repository, sample_markdown_files):
        """Test restore with clearing existing data."""
        importer = BulkImporter(repository)
        
        # Add some existing data
        existing_note = Note(
            id="existing_note",
            title="Existing Note",
            content="This should be deleted",
            note_type=NoteType.PERMANENT,
            tags=[],
            links=[]
        )
        repository.create(existing_note)
        
        # Restore with clear (we'll mock the confirmation)
        import unittest.mock
        with unittest.mock.patch('rich.prompt.Confirm.ask', return_value=True):
            success = importer.restore_from_export(
                sample_markdown_files[0].parent,
                clear_existing=True
            )
        
        # Verify
        assert success is True
        
        # Check existing note is gone
        assert repository.read("existing_note") is None
        
        # Check imported notes exist
        assert repository.read("20240101000000000000000") is not None
    
    def test_merge_imports_newest_strategy(self, repository, tmp_path):
        """Test merging imports with newest strategy."""
        importer = BulkImporter(repository)
        
        # Create two directories with conflicting notes
        dir1 = tmp_path / "import1"
        dir1.mkdir()
        dir2 = tmp_path / "import2"
        dir2.mkdir()
        
        # Same note ID, different content and timestamps
        content1 = """---
id: conflict_note
title: Old Version
type: permanent
tags: old
created: 2024-01-01T00:00:00
updated: 2024-01-01T00:00:00
---

Old content.
"""
        (dir1 / "conflict_note.md").write_text(content1)
        
        content2 = """---
id: conflict_note
title: New Version
type: permanent
tags: new
created: 2024-01-01T00:00:00
updated: 2024-01-02T00:00:00
---

New content.
"""
        (dir2 / "conflict_note.md").write_text(content2)
        
        # Unique note in dir2
        content3 = """---
id: unique_note
title: Unique Note
type: permanent
tags: unique
---

Unique content.
"""
        (dir2 / "unique_note.md").write_text(content3)
        
        # Merge with newest strategy
        stats = importer.merge_imports([dir1, dir2], strategy="newest")
        
        # Verify
        assert stats["total_files"] == 3
        assert stats["unique_notes"] == 2
        assert stats["conflicts"] == 1
        assert stats["imported"] == 2
        
        # Check newest version was imported
        note = repository.read("conflict_note")
        assert note is not None
        assert note.title == "New Version"
        assert {t.name for t in note.tags} == {"new"}
        
        # Check unique note was imported
        assert repository.read("unique_note") is not None
    
    def test_merge_imports_largest_strategy(self, repository, tmp_path):
        """Test merging imports with largest strategy."""
        importer = BulkImporter(repository)
        
        # Create two directories
        dir1 = tmp_path / "import1"
        dir1.mkdir()
        dir2 = tmp_path / "import2"
        dir2.mkdir()
        
        # Same note, different sizes
        content1 = """---
id: size_test
title: Small Version
type: permanent
---

Small content.
"""
        (dir1 / "size_test.md").write_text(content1)
        
        content2 = """---
id: size_test
title: Large Version
type: permanent
---

This is a much larger version with significantly more content.
It has multiple paragraphs and much more information.
This should be selected by the largest strategy.
"""
        (dir2 / "size_test.md").write_text(content2)
        
        # Merge with largest strategy
        stats = importer.merge_imports([dir1, dir2], strategy="largest")
        
        # Verify largest version was imported
        note = repository.read("size_test")
        assert note is not None
        assert note.title == "Large Version"
        assert "much larger version" in note.content