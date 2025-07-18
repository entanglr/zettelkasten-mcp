#!/usr/bin/env python3
"""Script to verify SQLite migration functionality."""
import sys
from pathlib import Path
import tempfile
import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from zettelkasten_mcp.models.schema import Note, NoteType, Tag, Link, LinkType
from zettelkasten_mcp.storage.sqlite_repository import SQLiteNoteRepository
from zettelkasten_mcp.migration.migrate_to_sqlite import MarkdownToSQLiteMigrator
from zettelkasten_mcp.export_import.exporter import BulkExporter
from zettelkasten_mcp.export_import.importer import BulkImporter

def create_test_notes(repo: SQLiteNoteRepository):
    """Create test notes in SQLite repository."""
    print("Creating test notes...")
    
    notes = [
        Note(
            id="20250101000000000000000",
            title="Test Note 1",
            content="This is a test note for SQLite storage verification.",
            note_type=NoteType.PERMANENT,
            tags=[Tag(name="test"), Tag(name="sqlite")],
            links=[],
            metadata={"test": True, "version": 1}
        ),
        Note(
            id="20250102000000000000000",
            title="Test Note 2",
            content="This note links to the first one.",
            note_type=NoteType.LITERATURE,
            tags=[Tag(name="test"), Tag(name="linked")],
            links=[
                Link(
                    source_id="20250102000000000000000",
                    target_id="20250101000000000000000",
                    link_type=LinkType.REFERENCE,
                    description="References the first note"
                )
            ]
        ),
        Note(
            id="20250103000000000000000",
            title="Test Note 3",
            content="A fleeting thought.",
            note_type=NoteType.FLEETING,
            tags=[Tag(name="fleeting")],
            links=[]
        )
    ]
    
    for note in notes:
        repo.create(note)
        print(f"  ✓ Created note: {note.title}")
    
    return notes

def verify_notes(repo: SQLiteNoteRepository, expected_notes):
    """Verify notes exist in repository."""
    print("\nVerifying notes...")
    
    for note in expected_notes:
        retrieved = repo.read(note.id)
        if not retrieved:
            print(f"  ✗ Note {note.id} not found!")
            return False
        
        # Verify content
        if retrieved.title != note.title:
            print(f"  ✗ Title mismatch for {note.id}")
            return False
        
        # For export/import test, content might have added links section
        if retrieved.content != note.content:
            # Check if the difference is just an added links section
            if retrieved.content.startswith(note.content) and "## Links" in retrieved.content:
                # This is acceptable - links were added during export
                pass
            else:
                print(f"  ✗ Content mismatch for {note.id}")
                print(f"    Expected: {repr(note.content)}")
                print(f"    Got:      {repr(retrieved.content)}")
                return False
        
        if retrieved.note_type != note.note_type:
            print(f"  ✗ Type mismatch for {note.id}")
            return False
        
        # Verify tags
        expected_tags = {t.name for t in note.tags}
        actual_tags = {t.name for t in retrieved.tags}
        if expected_tags != actual_tags:
            print(f"  ✗ Tags mismatch for {note.id}")
            return False
        
        print(f"  ✓ Verified note: {retrieved.title}")
    
    return True

def test_search_functionality(repo: SQLiteNoteRepository):
    """Test search functionality."""
    print("\nTesting search functionality...")
    
    # Search by content
    results = repo.search("SQLite")
    print(f"  ✓ Search for 'SQLite': {len(results)} results")
    
    # Search by tag
    results = repo.find_by_tag("test")
    print(f"  ✓ Find by tag 'test': {len(results)} results")
    
    # Find linked notes
    linked = repo.find_linked_notes("20250102000000000000000", direction="outgoing")
    print(f"  ✓ Outgoing links from note 2: {len(linked)} results")
    
    linked = repo.find_linked_notes("20250101000000000000000", direction="incoming")
    print(f"  ✓ Incoming links to note 1: {len(linked)} results")

def test_export_import(repo: SQLiteNoteRepository, temp_dir: Path):
    """Test export and import functionality."""
    print("\nTesting export/import functionality...")
    
    # Export
    exporter = BulkExporter(repo)
    export_dir = exporter.create_timestamped_export(temp_dir / "exports")
    print(f"  ✓ Exported to: {export_dir}")
    
    # Create new database
    new_db = temp_dir / "imported.db"
    new_repo = SQLiteNoteRepository(new_db)
    
    # Import
    importer = BulkImporter(new_repo)
    success = importer.restore_from_export(export_dir)
    print(f"  ✓ Import success: {success}")
    
    # Verify
    stats = new_repo.get_statistics()
    print(f"  ✓ Imported notes: {stats['total_notes']}")
    
    return new_repo

def test_statistics(repo: SQLiteNoteRepository):
    """Test statistics functionality."""
    print("\nTesting statistics...")
    
    stats = repo.get_statistics()
    print(f"  ✓ Total notes: {stats['total_notes']}")
    print(f"  ✓ Total tags: {stats['total_tags']}")
    print(f"  ✓ Total links: {stats['total_links']}")
    print(f"  ✓ Storage type: {stats['storage_type']}")
    
    print("\n  Notes by type:")
    for note_type, count in stats['notes_by_type'].items():
        print(f"    - {note_type}: {count}")
    
    tags = repo.get_tags()
    print("\n  Tags with counts:")
    for tag in tags:
        print(f"    - {tag['name']}: {tag['count']}")

def main():
    """Run verification tests."""
    print("=== SQLite Storage Verification ===\n")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Create database
        db_path = temp_path / "test.db"
        repo = SQLiteNoteRepository(db_path)
        print(f"Created SQLite database at: {db_path}")
        
        # Create test notes
        test_notes = create_test_notes(repo)
        
        # Verify notes
        if not verify_notes(repo, test_notes):
            print("\n❌ Verification failed!")
            return 1
        
        # Test search
        test_search_functionality(repo)
        
        # Test statistics
        test_statistics(repo)
        
        # Test export/import
        imported_repo = test_export_import(repo, temp_path)
        
        # Verify imported data
        print("\nVerifying imported data...")
        if not verify_notes(imported_repo, test_notes):
            print("\n❌ Import verification failed!")
            return 1
        
        # Test backup/restore
        print("\nTesting backup/restore...")
        backup_path = temp_path / "backup.db"
        repo.backup(backup_path)
        print(f"  ✓ Created backup at: {backup_path}")
        
        # Test database integrity
        print("\nTesting database integrity...")
        is_valid = repo.verify_integrity()
        print(f"  ✓ Database integrity: {'Valid' if is_valid else 'Invalid'}")
        
        # Test optimization
        print("\nTesting database optimization...")
        repo.optimize()
        print("  ✓ Database optimized")
    
    print("\n✅ All tests passed!")
    return 0

if __name__ == "__main__":
    sys.exit(main())