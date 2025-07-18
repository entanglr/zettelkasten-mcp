"""Tests for SQLite-only note repository."""
import datetime
import tempfile
from pathlib import Path
import pytest

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
def sample_note():
    """Create a sample note for testing."""
    return Note(
        id="20240101000000000000000",
        title="Test Note",
        content="This is a test note content.",
        note_type=NoteType.PERMANENT,
        tags=[Tag(name="test"), Tag(name="sample")],
        links=[],
        created_at=datetime.datetime(2024, 1, 1, 0, 0, 0),
        updated_at=datetime.datetime(2024, 1, 1, 0, 0, 0),
        metadata={"custom_field": "custom_value"}
    )

class TestSQLiteNoteRepository:
    """Test SQLite note repository functionality."""
    
    def test_create_note(self, repository, sample_note):
        """Test creating a new note."""
        # Create note
        created_note = repository.create(sample_note)
        
        # Verify
        assert created_note.id == sample_note.id
        assert created_note.title == sample_note.title
        assert created_note.content == sample_note.content
        assert created_note.note_type == sample_note.note_type
        assert len(created_note.tags) == 2
        assert created_note.metadata["custom_field"] == "custom_value"
    
    def test_create_duplicate_note(self, repository, sample_note):
        """Test creating a duplicate note raises error."""
        repository.create(sample_note)
        
        with pytest.raises(ValueError, match="already exists"):
            repository.create(sample_note)
    
    def test_read_note(self, repository, sample_note):
        """Test reading a note by ID."""
        repository.create(sample_note)
        
        # Read note
        read_note = repository.read(sample_note.id)
        
        # Verify
        assert read_note is not None
        assert read_note.id == sample_note.id
        assert read_note.title == sample_note.title
        assert read_note.content == sample_note.content
        assert len(read_note.tags) == 2
        assert {t.name for t in read_note.tags} == {"test", "sample"}
    
    def test_read_nonexistent_note(self, repository):
        """Test reading a nonexistent note returns None."""
        note = repository.read("nonexistent_id")
        assert note is None
    
    def test_update_note(self, repository, sample_note):
        """Test updating an existing note."""
        repository.create(sample_note)
        
        # Update note
        sample_note.title = "Updated Title"
        sample_note.content = "Updated content"
        sample_note.tags = [Tag(name="updated"), Tag(name="modified")]
        sample_note.metadata["new_field"] = "new_value"
        
        updated_note = repository.update(sample_note)
        
        # Verify
        assert updated_note.title == "Updated Title"
        assert updated_note.content == "Updated content"
        assert len(updated_note.tags) == 2
        assert {t.name for t in updated_note.tags} == {"updated", "modified"}
        assert updated_note.metadata["new_field"] == "new_value"
        assert updated_note.updated_at > sample_note.created_at
    
    def test_update_nonexistent_note(self, repository, sample_note):
        """Test updating a nonexistent note raises error."""
        with pytest.raises(ValueError, match="not found"):
            repository.update(sample_note)
    
    def test_delete_note(self, repository, sample_note):
        """Test deleting a note."""
        repository.create(sample_note)
        
        # Delete note
        repository.delete(sample_note.id)
        
        # Verify deleted
        assert repository.read(sample_note.id) is None
    
    def test_delete_nonexistent_note(self, repository):
        """Test deleting a nonexistent note raises error."""
        with pytest.raises(ValueError, match="does not exist"):
            repository.delete("nonexistent_id")
    
    def test_list_notes(self, repository):
        """Test listing notes with pagination."""
        # Create multiple notes
        for i in range(5):
            note = Note(
                id=f"2024010100000000000000{i}",
                title=f"Note {i}",
                content=f"Content {i}",
                note_type=NoteType.PERMANENT,
                tags=[],
                links=[],
                created_at=datetime.datetime(2024, 1, 1, 0, 0, i),
                updated_at=datetime.datetime(2024, 1, 1, 0, 0, i)
            )
            repository.create(note)
        
        # Test listing all
        notes = repository.list()
        assert len(notes) == 5
        
        # Test pagination
        notes = repository.list(limit=2, offset=0)
        assert len(notes) == 2
        
        notes = repository.list(limit=2, offset=2)
        assert len(notes) == 2
        
        notes = repository.list(limit=2, offset=4)
        assert len(notes) == 1
    
    def test_list_by_type(self, repository):
        """Test listing notes by type."""
        # Create notes of different types
        note1 = Note(
            id="note1",
            title="Permanent Note",
            content="Content",
            note_type=NoteType.PERMANENT,
            tags=[],
            links=[]
        )
        note2 = Note(
            id="note2",
            title="Literature Note",
            content="Content",
            note_type=NoteType.LITERATURE,
            tags=[],
            links=[]
        )
        repository.create(note1)
        repository.create(note2)
        
        # List by type
        permanent_notes = repository.list(note_type=NoteType.PERMANENT.value)
        assert len(permanent_notes) == 1
        assert permanent_notes[0].id == "note1"
        
        literature_notes = repository.list(note_type=NoteType.LITERATURE.value)
        assert len(literature_notes) == 1
        assert literature_notes[0].id == "note2"
    
    def test_search_notes(self, repository):
        """Test searching notes."""
        # Create notes
        note1 = Note(
            id="note1",
            title="Python Programming",
            content="Python is a great programming language.",
            note_type=NoteType.PERMANENT,
            tags=[Tag(name="python"), Tag(name="programming")],
            links=[]
        )
        note2 = Note(
            id="note2",
            title="JavaScript Guide",
            content="JavaScript is used for web development.",
            note_type=NoteType.PERMANENT,
            tags=[Tag(name="javascript"), Tag(name="web")],
            links=[]
        )
        repository.create(note1)
        repository.create(note2)
        
        # Search by title
        results = repository.search("Python", search_content=False)
        assert len(results) == 1
        assert results[0].id == "note1"
        
        # Search by content
        results = repository.search("programming", search_title=False)
        assert len(results) == 1
        assert results[0].id == "note1"
        
        # Search by tag
        results = repository.search("web", search_title=False, search_content=False)
        assert len(results) == 1
        assert results[0].id == "note2"
        
        # Search all fields
        results = repository.search("programming")
        assert len(results) == 1
    
    def test_find_by_tag(self, repository):
        """Test finding notes by tag."""
        # Create notes with tags
        note1 = Note(
            id="note1",
            title="Note 1",
            content="Content",
            note_type=NoteType.PERMANENT,
            tags=[Tag(name="tag1"), Tag(name="common")],
            links=[]
        )
        note2 = Note(
            id="note2",
            title="Note 2",
            content="Content",
            note_type=NoteType.PERMANENT,
            tags=[Tag(name="tag2"), Tag(name="common")],
            links=[]
        )
        repository.create(note1)
        repository.create(note2)
        
        # Find by specific tag
        results = repository.find_by_tag("tag1")
        assert len(results) == 1
        assert results[0].id == "note1"
        
        # Find by common tag
        results = repository.find_by_tag("common")
        assert len(results) == 2
        assert {n.id for n in results} == {"note1", "note2"}
    
    def test_links_between_notes(self, repository):
        """Test creating and querying links between notes."""
        # Create notes
        note1 = Note(
            id="note1",
            title="Source Note",
            content="Content",
            note_type=NoteType.PERMANENT,
            tags=[],
            links=[]
        )
        note2 = Note(
            id="note2",
            title="Target Note",
            content="Content",
            note_type=NoteType.PERMANENT,
            tags=[],
            links=[]
        )
        repository.create(note1)
        repository.create(note2)
        
        # Add link from note1 to note2
        note1.links = [
            Link(
                source_id="note1",
                target_id="note2",
                link_type=LinkType.REFERENCE,
                description="References note 2"
            )
        ]
        repository.update(note1)
        
        # Test outgoing links
        linked = repository.find_linked_notes("note1", direction="outgoing")
        assert len(linked) == 1
        assert linked[0].id == "note2"
        
        # Test incoming links
        linked = repository.find_linked_notes("note2", direction="incoming")
        assert len(linked) == 1
        assert linked[0].id == "note1"
        
        # Test both directions
        linked = repository.find_linked_notes("note1", direction="both")
        assert len(linked) == 1  # Only outgoing in this case
    
    def test_get_tags(self, repository):
        """Test getting all tags with counts."""
        # Create notes with tags
        notes = [
            Note(id="1", title="Note 1", content="", note_type=NoteType.PERMANENT,
                 tags=[Tag(name="python"), Tag(name="programming")], links=[]),
            Note(id="2", title="Note 2", content="", note_type=NoteType.PERMANENT,
                 tags=[Tag(name="python"), Tag(name="web")], links=[]),
            Note(id="3", title="Note 3", content="", note_type=NoteType.PERMANENT,
                 tags=[Tag(name="python")], links=[])
        ]
        for note in notes:
            repository.create(note)
        
        # Get tags
        tags = repository.get_tags()
        
        # Verify
        assert len(tags) == 3
        tag_dict = {t["name"]: t["count"] for t in tags}
        assert tag_dict["python"] == 3
        assert tag_dict["programming"] == 1
        assert tag_dict["web"] == 1
    
    def test_get_statistics(self, repository):
        """Test getting repository statistics."""
        # Create notes
        notes = [
            Note(id="1", title="Permanent", content="", note_type=NoteType.PERMANENT,
                 tags=[Tag(name="tag1")], links=[]),
            Note(id="2", title="Literature", content="", note_type=NoteType.LITERATURE,
                 tags=[Tag(name="tag2")], links=[]),
            Note(id="3", title="Fleeting", content="", note_type=NoteType.FLEETING,
                 tags=[], links=[])
        ]
        for note in notes:
            repository.create(note)
        
        # Add a link
        notes[0].links = [Link(source_id="1", target_id="2", link_type=LinkType.REFERENCE)]
        repository.update(notes[0])
        
        # Get statistics
        stats = repository.get_statistics()
        
        # Verify
        assert stats["total_notes"] == 3
        assert stats["total_tags"] == 2
        assert stats["total_links"] == 1
        assert stats["storage_type"] == "sqlite"
        assert stats["notes_by_type"][NoteType.PERMANENT.value] == 1
        assert stats["notes_by_type"][NoteType.LITERATURE.value] == 1
        assert stats["notes_by_type"][NoteType.FLEETING.value] == 1
    
    def test_backup_and_restore(self, repository, sample_note, tmp_path):
        """Test backup and restore functionality."""
        # Create some data
        repository.create(sample_note)
        
        # Backup
        backup_path = tmp_path / "backup.db"
        repository.backup(backup_path)
        assert backup_path.exists()
        
        # Modify data
        sample_note.title = "Modified Title"
        repository.update(sample_note)
        
        # Verify modification
        modified = repository.read(sample_note.id)
        assert modified.title == "Modified Title"
        
        # Restore
        repository.restore(backup_path)
        
        # Verify restored
        restored = repository.read(sample_note.id)
        assert restored.title == "Test Note"  # Original title
    
    def test_optimize(self, repository, sample_note):
        """Test database optimization."""
        # Create and delete many notes to fragment the database
        for i in range(10):
            note = Note(
                id=f"temp_{i}",
                title=f"Temp {i}",
                content="Content",
                note_type=NoteType.FLEETING,
                tags=[],
                links=[]
            )
            repository.create(note)
            try:
                repository.delete(note.id)
            except ValueError:
                pass  # Note already deleted
        
        # Create permanent note
        repository.create(sample_note)
        
        # Optimize
        repository.optimize()
        
        # Verify data still intact
        note = repository.read(sample_note.id)
        assert note is not None
        assert note.title == sample_note.title
    
    def test_verify_integrity(self, repository, sample_note):
        """Test database integrity verification."""
        repository.create(sample_note)
        
        # Verify integrity
        is_valid = repository.verify_integrity()
        assert is_valid is True
    
    def test_metadata_storage(self, repository):
        """Test JSON metadata storage and retrieval."""
        # Create note with complex metadata
        metadata = {
            "author": "John Doe",
            "references": ["ref1", "ref2", "ref3"],
            "custom_data": {
                "nested": {
                    "value": 42,
                    "flag": True
                }
            },
            "tags_extra": ["tag1", "tag2"]
        }
        
        note = Note(
            id="metadata_test",
            title="Metadata Test",
            content="Content",
            note_type=NoteType.PERMANENT,
            tags=[],
            links=[],
            metadata=metadata
        )
        repository.create(note)
        
        # Read and verify
        read_note = repository.read("metadata_test")
        assert read_note.metadata["author"] == "John Doe"
        assert read_note.metadata["references"] == ["ref1", "ref2", "ref3"]
        assert read_note.metadata["custom_data"]["nested"]["value"] == 42
        assert read_note.metadata["custom_data"]["nested"]["flag"] is True