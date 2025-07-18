#!/usr/bin/env python3
"""Test export/import functionality in isolation."""
import sys
from pathlib import Path
import tempfile

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from zettelkasten_mcp.models.schema import Note, NoteType, Tag, Link, LinkType
from zettelkasten_mcp.storage.sqlite_repository import SQLiteNoteRepository
from zettelkasten_mcp.export_import.exporter import MarkdownExporter
from zettelkasten_mcp.export_import.importer import MarkdownImporter

def main():
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Create repository
        db_path = temp_path / "test.db"
        repo = SQLiteNoteRepository(db_path)
        
        # Create a test note
        note = Note(
            id="test_note_1",
            title="Test Note",
            content="This is test content.\n\nWith multiple lines.",
            note_type=NoteType.PERMANENT,
            tags=[Tag(name="test"), Tag(name="export")],
            links=[
                Link(
                    source_id="test_note_1",
                    target_id="test_note_2",
                    link_type=LinkType.REFERENCE,
                    description="Test link"
                )
            ]
        )
        
        print("Original note:")
        print(f"  ID: {note.id}")
        print(f"  Title: {note.title}")
        print(f"  Content: {repr(note.content)}")
        print(f"  Tags: {[t.name for t in note.tags]}")
        print(f"  Links: {len(note.links)}")
        
        # Save to repository
        repo.create(note)
        
        # Export to markdown
        exporter = MarkdownExporter(repo)
        markdown = exporter.export_note_to_markdown(note)
        print("\nExported markdown:")
        print("=" * 50)
        print(markdown)
        print("=" * 50)
        
        # Save to file
        export_dir = temp_path / "export"
        export_dir.mkdir()
        md_file = export_dir / f"{note.id}.md"
        md_file.write_text(markdown)
        
        # Import from file
        new_repo = SQLiteNoteRepository(temp_path / "imported.db")
        importer = MarkdownImporter(new_repo)
        
        parsed_note = importer.parse_note_from_markdown(md_file)
        if parsed_note:
            print("\nParsed note:")
            print(f"  ID: {parsed_note.id}")
            print(f"  Title: {parsed_note.title}")
            print(f"  Content: {repr(parsed_note.content)}")
            print(f"  Tags: {[t.name for t in parsed_note.tags]}")
            print(f"  Links: {len(parsed_note.links)}")
            
            # Check for differences
            print("\nComparison:")
            print(f"  Content match: {note.content == parsed_note.content}")
            print(f"  Content lengths: original={len(note.content)}, parsed={len(parsed_note.content)}")
            
            if note.content != parsed_note.content:
                print("\nContent difference:")
                print(f"  Original: {repr(note.content)}")
                print(f"  Parsed:   {repr(parsed_note.content)}")

if __name__ == "__main__":
    main()