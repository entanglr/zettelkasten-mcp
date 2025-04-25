"""Tests for the ExportService class."""
import os
import tempfile
from pathlib import Path
import pytest
import shutil
import gc
from unittest.mock import MagicMock
import re

from zettelkasten_mcp.models.schema import LinkType, NoteType, Link, Note, Tag
from zettelkasten_mcp.services.export_service import ExportService
from zettelkasten_mcp.services.zettel_service import ZettelService


@pytest.fixture
def export_service(zettel_service, request):
    """Create a test ExportService."""
    service = ExportService(zettel_service=zettel_service)
    
    def cleanup():
        # Explicitly clean up references
        service.zettel_service = None
        gc.collect()
    
    request.addfinalizer(cleanup)
    yield service


@pytest.fixture
def temp_export_dir(request):
    """Create a temporary directory for exports."""
    export_dir = Path(tempfile.mkdtemp())
    
    def cleanup():
        # Force garbage collection to release any file handles
        gc.collect()
        
        # Try to clean up, but don't fail if we can't
        try:
            shutil.rmtree(export_dir, ignore_errors=True)
        except:
            pass
    
    request.addfinalizer(cleanup)
    yield export_dir


def test_sanitize_filename(export_service):
    """Test sanitizing filenames."""
    # Test with normal title
    result = export_service._sanitize_filename("Test Title")
    assert result == "Test-Title"
    
    # Test with special characters
    result = export_service._sanitize_filename("Test: Title with special chars!?")
    assert result == "Test_-Title-with-special-chars__"
    
    # Test with very long title
    long_title = "This is a very long title that should be truncated " * 5
    result = export_service._sanitize_filename(long_title)
    assert len(result) <= 100
    
    # Test with empty title
    result = export_service._sanitize_filename("")
    assert result == ""


def test_export_to_markdown_empty(export_service, temp_export_dir):
    """Test exporting an empty knowledge base."""
    # Export to the temporary directory
    result_path = export_service.export_to_markdown(export_dir=temp_export_dir)
    
    # Verify the result is the correct path
    assert result_path == temp_export_dir
    
    # Verify the index file was created
    index_path = temp_export_dir / "index.md"
    assert index_path.exists()
    
    # Verify the content of the index file
    with open(index_path, "r", encoding="utf-8") as f:
        content = f.read()
        assert "# Zettelkasten Knowledge Base" in content
        assert "Total notes: 0" in content


def test_export_to_markdown_with_notes(export_service, zettel_service, temp_export_dir):
    """Test exporting a knowledge base with notes."""
    # Create some test notes of different types
    hub_note = zettel_service.create_note(
        title="Hub Note",
        content="This is a hub note.",
        note_type=NoteType.HUB,
        tags=["hub", "test"]
    )
    
    structure_note = zettel_service.create_note(
        title="Structure Note",
        content="This is a structure note.",
        note_type=NoteType.STRUCTURE,
        tags=["structure", "test"]
    )
    
    permanent_note1 = zettel_service.create_note(
        title="Permanent Note 1",
        content="This is a permanent note.",
        note_type=NoteType.PERMANENT,
        tags=["permanent", "test"]
    )
    
    permanent_note2 = zettel_service.create_note(
        title="Permanent Note 2",
        content="This is another permanent note.",
        note_type=NoteType.PERMANENT,
        tags=["permanent", "test"]
    )
    
    literature_note = zettel_service.create_note(
        title="Literature Note",
        content="This is a literature note.",
        note_type=NoteType.LITERATURE,
        tags=["literature", "test"]
    )
    
    fleeting_note = zettel_service.create_note(
        title="Fleeting Note",
        content="This is a fleeting note.",
        note_type=NoteType.FLEETING,
        tags=["fleeting", "test"]
    )
    
    # Create some links between notes
    zettel_service.create_link(
        source_id=hub_note.id,
        target_id=structure_note.id,
        link_type=LinkType.REFERENCE,
        description="Reference to structure note"
    )
    
    zettel_service.create_link(
        source_id=structure_note.id,
        target_id=permanent_note1.id,
        link_type=LinkType.REFERENCE,
        description="Reference to permanent note 1"
    )
    
    zettel_service.create_link(
        source_id=structure_note.id,
        target_id=permanent_note2.id,
        link_type=LinkType.REFERENCE,
        description="Reference to permanent note 2"
    )
    
    zettel_service.create_link(
        source_id=permanent_note1.id,
        target_id=literature_note.id,
        link_type=LinkType.EXTENDS,
        description="Extends literature note"
    )
    
    zettel_service.create_link(
        source_id=permanent_note2.id,
        target_id=fleeting_note.id,
        link_type=LinkType.REFINES,
        description="Refines fleeting note"
    )
    
    # Export to the temporary directory
    result_path = export_service.export_to_markdown(export_dir=temp_export_dir)
    
    # Verify the result is the correct path
    assert result_path == temp_export_dir
    
    # Verify directories were created for each note type
    assert (temp_export_dir / "hub_notes").exists()
    assert (temp_export_dir / "structure_notes").exists()
    assert (temp_export_dir / "permanent_notes").exists()
    assert (temp_export_dir / "literature_notes").exists()
    assert (temp_export_dir / "fleeting_notes").exists()
    
    # Verify the index file was created
    index_path = temp_export_dir / "index.md"
    assert index_path.exists()
    
    # Verify the content of the index file
    with open(index_path, "r", encoding="utf-8") as f:
        content = f.read()
        assert "# Zettelkasten Knowledge Base" in content
        assert "## Hub Notes" in content
        assert "## Structure Notes" in content
        assert "## Browse by Tag" in content
        assert "Total notes: 6" in content
        assert "Hub notes: 1" in content
        assert "Structure notes: 1" in content
        assert "Permanent notes: 2" in content
        assert "Literature notes: 1" in content
        assert "Fleeting notes: 1" in content
    
    # Verify note files were created
    hub_dir = temp_export_dir / "hub_notes"
    structure_dir = temp_export_dir / "structure_notes"
    permanent_dir = temp_export_dir / "permanent_notes"
    literature_dir = temp_export_dir / "literature_notes"
    fleeting_dir = temp_export_dir / "fleeting_notes"
    
    # Find the hub note file
    hub_files = list(hub_dir.glob(f"{hub_note.id}_*.md"))
    assert len(hub_files) == 1
    hub_file = hub_files[0]
    
    # Verify hub note content contains frontmatter and links
    with open(hub_file, "r", encoding="utf-8") as f:
        content = f.read()
        assert "---" in content  # Frontmatter
        assert f"id: {hub_note.id}" in content
        assert "title: \"Hub Note\"" in content
        assert "type: hub" in content
        assert "tags: [" in content
        assert "# Hub Note" in content
        assert "## Links" in content
        assert "### Reference Links" in content
        assert "Structure Note" in content
    
    # Verify structure note has links to both permanent notes
    structure_files = list(structure_dir.glob(f"{structure_note.id}_*.md"))
    assert len(structure_files) == 1
    structure_file = structure_files[0]
    
    with open(structure_file, "r", encoding="utf-8") as f:
        content = f.read()
        assert "### Reference Links" in content
        assert "Permanent Note 1" in content
        assert "Permanent Note 2" in content


def test_export_with_clean_dir(export_service, zettel_service, temp_export_dir):
    """Test exporting with clean_dir option."""
    # Create a file in the export directory
    test_file = temp_export_dir / "test_file.txt"
    with open(test_file, "w") as f:
        f.write("This file should be deleted when clean_dir=True")
    
    # Create a subdirectory with a file
    subdir = temp_export_dir / "subdir"
    subdir.mkdir()
    subdir_file = subdir / "subdir_file.txt"
    with open(subdir_file, "w") as f:
        f.write("This file should also be deleted")
    
    # Create a test note
    zettel_service.create_note(
        title="Test Note",
        content="This is a test note.",
        note_type=NoteType.PERMANENT
    )
    
    # Export with clean_dir=True (default)
    export_service.export_to_markdown(export_dir=temp_export_dir)
    
    # Verify the test file and subdirectory were removed
    assert not test_file.exists()
    assert not subdir.exists()
    
    # Verify the export files were created
    assert (temp_export_dir / "index.md").exists()
    assert (temp_export_dir / "permanent_notes").exists()


def test_export_without_clean_dir(export_service, zettel_service, temp_export_dir):
    """Test exporting without cleaning the directory."""
    # Create a file in the export directory
    test_file = temp_export_dir / "test_file.txt"
    with open(test_file, "w") as f:
        f.write("This file should NOT be deleted when clean_dir=False")
    
    # Create a subdirectory with a file
    subdir = temp_export_dir / "subdir"
    subdir.mkdir()
    subdir_file = subdir / "subdir_file.txt"
    with open(subdir_file, "w") as f:
        f.write("This file should also NOT be deleted")
    
    # Create a test note
    zettel_service.create_note(
        title="Test Note",
        content="This is a test note.",
        note_type=NoteType.PERMANENT
    )
    
    # Export with clean_dir=False
    export_service.export_to_markdown(export_dir=temp_export_dir, clean_dir=False)
    
    # Verify the test file and subdirectory still exist
    assert test_file.exists()
    assert subdir.exists()
    assert subdir_file.exists()
    
    # Verify the export files were created
    assert (temp_export_dir / "index.md").exists()
    assert (temp_export_dir / "permanent_notes").exists()


def test_export_links_between_notes(export_service, temp_export_dir, monkeypatch):
    """Test that links between notes are correctly included in the exported markdown."""
    # Mock the ZettelService
    mock_zettel_service = MagicMock(spec=ZettelService)

    # Create two notes with a link between them
    source_note = Note(
        id="20220101120000",
        title="Source Note",
        content="This note links to the target note",
        note_type=NoteType.PERMANENT,
        created_at="2022-01-01T12:00:00",
        updated_at="2022-01-01T12:00:00",
    )

    target_note = Note(
        id="20220101120001",
        title="Target Note",
        content="This is the target note",
        note_type=NoteType.PERMANENT,
        created_at="2022-01-01T12:00:00",
        updated_at="2022-01-01T12:00:00",
    )

    # Create a link between them
    link = Link(
        source_id=source_note.id,
        target_id=target_note.id,
        link_type=LinkType.REFERENCE,
        description="Reference link"
    )
    
    source_note.links.append(link)

    # Setup mock returns
    all_notes = [source_note, target_note]
    mock_zettel_service.get_all_notes.return_value = all_notes
    
    # Setup mock returns for specific notes
    mock_zettel_service.get_note.side_effect = lambda note_id: next(
        (note for note in all_notes if note.id == note_id), None
    )
    
    # Setup mock returns for links
    mock_zettel_service.get_linked_notes.side_effect = lambda note_id, direction="both": (
        [{"note": target_note, "link_type": LinkType.REFERENCE, "description": "Reference link"}] 
        if note_id == source_note.id else []
    )

    # Set the mock service
    monkeypatch.setattr(export_service, "zettel_service", mock_zettel_service)
    
    # Export the notes
    export_service.export_to_markdown(temp_export_dir, clean_dir=True)
    
    export_dir = Path(temp_export_dir)
    
    # Check source note
    source_note_path = export_dir / "permanent_notes" / f"{source_note.id}_source-note.md"
    assert source_note_path.exists()
    source_note_content = source_note_path.read_text()
    assert "# Source Note" in source_note_content
    assert "## Links" in source_note_content
    assert f"- [Target Note]({target_note.id}_Target-Note.md) - Reference link" in source_note_content
    
    # Check target note
    target_note_path = export_dir / "permanent_notes" / f"{target_note.id}_target-note.md"
    assert target_note_path.exists()
    
    # Verify index file includes statistics about all notes
    index_path = export_dir / "index.md"
    assert index_path.exists()
    index_content = index_path.read_text()
    
    assert "Total notes: 2" in index_content
    assert "Permanent notes: 2" in index_content


def test_export_bidirectional_links(export_service, temp_export_dir, monkeypatch):
    """Test that bidirectional links between notes are correctly exported."""
    # Mock the ZettelService
    mock_zettel_service = MagicMock(spec=ZettelService)

    # Create two notes with bidirectional links
    note1 = Note(
        id="20220101120000",
        title="First Note",
        content="Content of the first note",
        note_type=NoteType.PERMANENT,
        created_at="2022-01-01T12:00:00",
        updated_at="2022-01-01T12:00:00",
    )

    note2 = Note(
        id="20220101120001",
        title="Second Note",
        content="Content of the second note",
        note_type=NoteType.PERMANENT,
        created_at="2022-01-01T12:00:00",
        updated_at="2022-01-01T12:00:00",
    )

    # Create bidirectional links
    link1 = Link(
        source_id=note1.id,
        target_id=note2.id,
        link_type=LinkType.RELATED,
        description="Related to second note"
    )

    link2 = Link(
        source_id=note2.id,
        target_id=note1.id,
        link_type=LinkType.RELATED,
        description="Related to first note"
    )
    
    # Add links to notes
    note1.links.append(link1)
    note2.links.append(link2)

    # Setup mock returns
    all_notes = [note1, note2]
    mock_zettel_service.get_all_notes.return_value = all_notes
    
    # Setup mock returns for specific notes
    mock_zettel_service.get_note.side_effect = lambda note_id: next(
        (note for note in all_notes if note.id == note_id), None
    )

    # Setup mock returns for links
    mock_zettel_service.get_linked_notes.side_effect = lambda note_id, direction="both": (
        [{"note": note2, "link_type": LinkType.RELATED, "description": "Related to second note"}] 
        if note_id == note1.id 
        else ([{"note": note1, "link_type": LinkType.RELATED, "description": "Related to first note"}] 
              if note_id == note2.id else [])
    )

    # Set the mock service
    monkeypatch.setattr(export_service, "zettel_service", mock_zettel_service)
    
    # Export the notes
    export_service.export_to_markdown(temp_export_dir, clean_dir=True)
    
    export_dir = Path(temp_export_dir)
    
    # Check first note
    note1_path = export_dir / "permanent_notes" / f"{note1.id}_first-note.md"
    assert note1_path.exists()
    note1_content = note1_path.read_text()
    assert "# First Note" in note1_content
    assert "## Links" in note1_content
    assert f"- [Second Note]({note2.id}_Second-Note.md) - Related to second note" in note1_content
    
    # Check second note
    note2_path = export_dir / "permanent_notes" / f"{note2.id}_second-note.md"
    assert note2_path.exists()
    note2_content = note2_path.read_text()
    assert "# Second Note" in note2_content
    assert "## Links" in note2_content
    assert f"- [First Note]({note1.id}_First-Note.md) - Related to first note" in note2_content
    
    # Verify index file includes statistics about all notes
    index_path = export_dir / "index.md"
    assert index_path.exists()
    index_content = index_path.read_text()
    
    assert "Total notes: 2" in index_content
    assert "Permanent notes: 2" in index_content


def test_export_notes_with_tags(export_service, temp_export_dir, monkeypatch):
    """Test that tags are correctly included in the exported markdown."""
    # Mock the ZettelService
    mock_zettel_service = MagicMock(spec=ZettelService)

    # Create notes with tags
    note1 = Note(
        id="20220101120000",
        title="Tagged Note 1",
        content="This note has tags",
        note_type=NoteType.PERMANENT,
        created_at="2022-01-01T12:00:00",
        updated_at="2022-01-01T12:00:00",
        tags=[Tag(name="python"), Tag(name="programming"), Tag(name="test")]
    )
    
    note2 = Note(
        id="20220101120001",
        title="Tagged Note 2",
        content="This note also has tags",
        note_type=NoteType.PERMANENT,
        created_at="2022-01-01T12:00:00",
        updated_at="2022-01-01T12:00:00",
        tags=[Tag(name="test"), Tag(name="zettelkasten")]
    )
    
    # Setup mock returns
    all_notes = [note1, note2]
    mock_zettel_service.get_all_notes.return_value = all_notes
    
    # Setup mock returns for specific notes
    mock_zettel_service.get_note.side_effect = lambda note_id: next(
        (note for note in all_notes if note.id == note_id), None
    )
    
    # Setup mock returns for links
    mock_zettel_service.get_linked_notes.return_value = []
    
    # Set the mock service
    monkeypatch.setattr(export_service, "zettel_service", mock_zettel_service)
    
    # Export the notes
    export_service.export_to_markdown(temp_export_dir, clean_dir=True)
    
    # Check that each note was exported correctly with tags
    export_dir = Path(temp_export_dir)
    
    # Check note1
    note1_path = export_dir / "permanent_notes" / f"{note1.id}_tagged-note-1.md"
    assert note1_path.exists()
    note1_content = note1_path.read_text()
    assert "# Tagged Note 1" in note1_content
    assert 'tags: ["python", "programming", "test"]' in note1_content
    
    # Check note2
    note2_path = export_dir / "permanent_notes" / f"{note2.id}_tagged-note-2.md"
    assert note2_path.exists()
    note2_content = note2_path.read_text()
    assert "# Tagged Note 2" in note2_content
    assert 'tags: ["test", "zettelkasten"]' in note2_content
    
    # Verify index file includes statistics about all notes
    index_path = export_dir / "index.md"
    assert index_path.exists()
    index_content = index_path.read_text()
    
    assert "Total notes: 2" in index_content
    assert "Permanent notes: 2" in index_content


def test_export_notes_with_links(export_service, temp_export_dir, monkeypatch):
    """Test that links between notes are correctly formatted in the exported markdown."""
    # Mock the ZettelService
    mock_zettel_service = MagicMock(spec=ZettelService)

    # Create notes
    source_note = Note(
        id="20220101120000",
        title="Source Note",
        content="This note links to the target note",
        note_type=NoteType.PERMANENT,
        created_at="2022-01-01T12:00:00",
        updated_at="2022-01-01T12:00:00"
    )
    
    target_note = Note(
        id="20220101120001",
        title="Target Note",
        content="This is the target note",
        note_type=NoteType.PERMANENT,
        created_at="2022-01-01T12:00:00",
        updated_at="2022-01-01T12:00:00"
    )
    
    # Create links
    link1 = Link(
        source_id=source_note.id,
        target_id=target_note.id,
        link_type=LinkType.REFERENCE,
        description="Reference link"
    )
    
    # Add link to source note
    source_note.links.append(link1)
    
    # Setup mock returns
    all_notes = [source_note, target_note]
    mock_zettel_service.get_all_notes.return_value = all_notes
    
    # Setup mock returns for specific notes
    mock_zettel_service.get_note.side_effect = lambda note_id: next(
        (note for note in all_notes if note.id == note_id), None
    )
    
    # Setup mock returns for links
    mock_zettel_service.get_linked_notes.side_effect = lambda note_id, direction="both": (
        [{"note": target_note, "link_type": LinkType.REFERENCE, "description": "Reference link"}] 
        if note_id == source_note.id else []
    )
    
    # Set the mock service
    monkeypatch.setattr(export_service, "zettel_service", mock_zettel_service)
    
    # Export the notes
    export_service.export_to_markdown(temp_export_dir, clean_dir=True)
    
    # Check that the source note includes the formatted link to the target note
    export_dir = Path(temp_export_dir)
    
    # Check source note
    source_note_path = export_dir / "permanent_notes" / f"{source_note.id}_source-note.md"
    assert source_note_path.exists()
    source_note_content = source_note_path.read_text()
    assert "# Source Note" in source_note_content
    assert "## Links" in source_note_content
    assert f"- [Target Note]({target_note.id}_Target-Note.md) - Reference link" in source_note_content
    
    # Check target note
    target_note_path = export_dir / "permanent_notes" / f"{target_note.id}_target-note.md"
    assert target_note_path.exists()
    
    # Verify index file includes statistics about all notes
    index_path = export_dir / "index.md"
    assert index_path.exists()
    index_content = index_path.read_text()
    
    assert "Total notes: 2" in index_content
    assert "Permanent notes: 2" in index_content


def _sanitize_filename(title: str) -> str:
    """Helper method to sanitize filenames the same way as the ExportService."""
    # Replace non-alphanumeric characters with underscores
    sanitized = re.sub(r'[^\w\s.-]', '_', title)
    # Replace spaces with hyphens
    sanitized = re.sub(r'\s+', '-', sanitized)
    # Ensure it's not too long
    if len(sanitized) > 100:
        sanitized = sanitized[:100]
    return sanitized