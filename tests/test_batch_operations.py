"""Tests for batch operations functionality."""
import pytest
from typing import List, Dict, Any, Tuple, Set, Optional

from zettelkasten_mcp.models.schema import (
    LinkType, NoteType, Note, BatchResult, BatchOperationResult
)
from zettelkasten_mcp.services.zettel_service import ZettelService
from zettelkasten_mcp.services.search_service import SearchService, SearchResult


def test_batch_create_notes(zettel_service):
    """Test creating multiple notes in a batch operation."""
    # Prepare test data
    notes_data = [
        {
            'title': 'Batch Note 1',
            'content': 'Content for batch note 1',
            'note_type': NoteType.PERMANENT,
            'tags': ['batch', 'test', 'note1']
        },
        {
            'title': 'Batch Note 2',
            'content': 'Content for batch note 2',
            'note_type': NoteType.LITERATURE,
            'tags': ['batch', 'test', 'note2']
        },
        # Test with minimal data
        {
            'title': 'Batch Note 3',
            'content': 'Content for batch note 3'
        },
        # Test with invalid data (missing title)
        {
            'content': 'Content with missing title'
        }
    ]
    
    # Call batch create notes
    result = zettel_service.batch_create_notes(notes_data)
    
    # Verify results
    assert result.total_count == 4
    assert result.success_count == 3
    assert result.failure_count == 1
    
    # Check successful notes
    successful_notes = [r.result for r in result.results if r.success]
    assert len(successful_notes) == 3
    
    # Verify content of created notes
    for i, note in enumerate(successful_notes):
        assert note.id is not None
        assert f'Batch Note {i+1}' in note.title
        assert f'Content for batch note {i+1}' in note.content
    
    # Check failed operation
    failed_ops = [r for r in result.results if not r.success]
    assert len(failed_ops) == 1
    assert "Title is required" in failed_ops[0].error


def test_batch_update_notes(zettel_service):
    """Test updating multiple notes in a batch operation."""
    # Create test notes
    note1 = zettel_service.create_note(
        title="Update Batch Test 1",
        content="Original content 1",
        note_type=NoteType.PERMANENT,
        tags=["original", "test1"]
    )
    
    note2 = zettel_service.create_note(
        title="Update Batch Test 2",
        content="Original content 2",
        note_type=NoteType.LITERATURE,
        tags=["original", "test2"]
    )
    
    # Prepare update data
    updates = [
        {
            'note_id': note1.id,
            'title': 'Updated Title 1',
            'content': 'Updated content 1',
            'tags': ['updated', 'test1']
        },
        {
            'note_id': note2.id,
            'content': 'Updated content 2',
            # Only updating content, not title or tags
        },
        # Test with non-existent note ID
        {
            'note_id': 'non-existent-note-id',
            'title': 'This should fail'
        }
    ]
    
    # Call batch update
    result = zettel_service.batch_update_notes(updates)
    
    # Verify results
    assert result.total_count == 3
    assert result.success_count == 2
    assert result.failure_count == 1
    
    # Check successful updates
    successful_updates = [r.result for r in result.results if r.success]
    assert len(successful_updates) == 2
    
    # Verify content of updated notes
    updated_note1 = zettel_service.get_note(note1.id)
    assert updated_note1.title == 'Updated Title 1'
    assert 'Updated content 1' in updated_note1.content
    assert len(updated_note1.tags) == 2
    assert {tag.name for tag in updated_note1.tags} == {'updated', 'test1'}
    
    updated_note2 = zettel_service.get_note(note2.id)
    assert updated_note2.title == 'Update Batch Test 2'  # Unchanged
    assert 'Updated content 2' in updated_note2.content
    assert {tag.name for tag in updated_note2.tags} == {'original', 'test2'}  # Unchanged
    
    # Check failed operation
    failed_ops = [r for r in result.results if not r.success]
    assert len(failed_ops) == 1
    assert failed_ops[0].item_id == 'non-existent-note-id'


def test_batch_delete_notes(zettel_service):
    """Test deleting multiple notes in a batch operation."""
    # Create test notes
    note1 = zettel_service.create_note(
        title="Delete Batch Test 1",
        content="Content for delete test 1",
    )
    
    note2 = zettel_service.create_note(
        title="Delete Batch Test 2",
        content="Content for delete test 2",
    )
    
    # Prepare note IDs to delete
    note_ids = [
        note1.id,
        note2.id,
        'non-existent-note-id'  # Should fail
    ]
    
    # Call batch delete
    result = zettel_service.batch_delete_notes(note_ids)
    
    # Verify results
    assert result.total_count == 3
    assert result.success_count == 2
    assert result.failure_count == 1
    
    # Verify notes were deleted
    assert zettel_service.get_note(note1.id) is None
    assert zettel_service.get_note(note2.id) is None
    
    # Check failed operation
    failed_ops = [r for r in result.results if not r.success]
    assert len(failed_ops) == 1
    assert failed_ops[0].item_id == 'non-existent-note-id'


def test_batch_create_links(zettel_service):
    """Test creating links between notes in a batch operation."""
    # Create test notes
    note1 = zettel_service.create_note(
        title="Link Source 1",
        content="Source content 1",
    )
    
    note2 = zettel_service.create_note(
        title="Link Target 1",
        content="Target content 1",
    )
    
    note3 = zettel_service.create_note(
        title="Link Source 2",
        content="Source content 2",
    )
    
    # Prepare link operations
    link_operations = [
        {
            'source_id': note1.id,
            'target_id': note2.id,
            'link_type': LinkType.REFERENCE,
            'description': 'Test link 1',
            'bidirectional': True
        },
        {
            'source_id': note3.id,
            'target_id': note2.id,
            'link_type': LinkType.EXTENDS,
            'description': 'Test link 2',
            'bidirectional': False
        },
        # Invalid link (non-existent target)
        {
            'source_id': note1.id,
            'target_id': 'non-existent-note-id',
            'link_type': LinkType.REFERENCE
        },
        # Missing required field
        {
            'source_id': note1.id,
            # Missing target_id
        }
    ]
    
    # Call batch create links
    result = zettel_service.batch_create_links(link_operations)
    
    # Verify results
    assert result.total_count == 4
    assert result.success_count == 2
    assert result.failure_count == 2
    
    # Check successful links
    successful_links = [r.result for r in result.results if r.success]
    assert len(successful_links) == 2
    
    # Verify links were created
    # First link (bidirectional)
    source1, target1 = successful_links[0]
    assert len(source1.links) == 1
    assert source1.links[0].target_id == note2.id
    assert source1.links[0].link_type == LinkType.REFERENCE
    assert source1.links[0].description == 'Test link 1'
    
    assert len(target1.links) == 1  # Bidirectional link
    assert target1.links[0].target_id == note1.id
    assert target1.links[0].link_type == LinkType.REFERENCE
    
    # Second link (one-way)
    source2, target2 = successful_links[1]
    assert len(source2.links) == 1
    assert source2.links[0].target_id == note2.id
    assert source2.links[0].link_type == LinkType.EXTENDS
    assert source2.links[0].description == 'Test link 2'
    
    # The target note might be None for non-bidirectional links or when the target already has links
    # Verify that the link was created properly by checking the source note's links
    # Instead of asserting target2 is not None, get the note from the service to confirm
    target2_note = zettel_service.get_note(note2.id)
    assert target2_note is not None
    # Note2 has incoming links from both note1 and note3, but only one outgoing link (to note1)
    # because only the first link is bidirectional
    assert len(target2_note.links) == 1
    assert target2_note.links[0].target_id == note1.id
    
    # Check failed operations
    failed_ops = [r for r in result.results if not r.success]
    assert len(failed_ops) == 2
    # First failure (non-existent target)
    assert "not found" in failed_ops[0].error
    # Second failure (missing target_id)
    assert "target_id is required" in failed_ops[1].error


def test_batch_search_by_text(zettel_service):
    """Test performing multiple text searches in a batch."""
    # Create a search service
    search_service = SearchService(zettel_service=zettel_service)
    
    # Create test notes
    zettel_service.create_note(
        title="Python Programming",
        content="Python is a programming language.",
        tags=["python", "programming"]
    )
    
    zettel_service.create_note(
        title="Machine Learning",
        content="Machine learning with Python and TensorFlow.",
        tags=["ml", "python", "tensorflow"]
    )
    
    zettel_service.create_note(
        title="JavaScript Basics",
        content="Introduction to JavaScript programming.",
        tags=["javascript", "programming"]
    )
    
    # Prepare search queries
    queries = [
        "python",
        "programming",
        "nonexistent term"
    ]
    
    # Call batch search
    result = search_service.batch_search_by_text(
        queries=queries,
        include_content=True,
        include_title=True,
        limit=5
    )
    
    # Verify results
    assert result.total_count == 3
    assert result.success_count == 3
    assert result.failure_count == 0
    
    # Check search results
    python_results = next(r.result for r in result.results if r.item_id == "python")
    assert len(python_results) == 2  # Two notes contain "python"
    
    programming_results = next(r.result for r in result.results if r.item_id == "programming")
    assert len(programming_results) == 2  # Two notes contain "programming"
    
    nonexistent_results = next(r.result for r in result.results if r.item_id == "nonexistent term")
    assert len(nonexistent_results) == 0  # No notes contain "nonexistent term"


def test_batch_search_by_tag(zettel_service):
    """Test performing multiple tag searches in a batch."""
    # Create a search service
    search_service = SearchService(zettel_service=zettel_service)
    
    # Create test notes with different tags
    zettel_service.create_note(
        title="Python Tutorial",
        content="A beginner's guide to Python.",
        tags=["python", "tutorial", "beginner"]
    )
    
    zettel_service.create_note(
        title="Advanced Python",
        content="Advanced Python programming techniques.",
        tags=["python", "advanced"]
    )
    
    zettel_service.create_note(
        title="JavaScript for Beginners",
        content="Getting started with JavaScript.",
        tags=["javascript", "beginner", "tutorial"]
    )
    
    # Prepare tag queries
    tag_queries = [
        "python",           # Single tag as string
        ["beginner"],       # Single tag in list
        ["tutorial", "beginner"],  # Multiple tags (AND operation)
        "nonexistent-tag"   # Tag that doesn't exist
    ]
    
    # Call batch search by tag
    result = search_service.batch_search_by_tag(tag_queries)
    
    # Verify results
    assert result.total_count == 4
    assert result.success_count == 4
    assert result.failure_count == 0
    
    # Check search results
    python_results = next(r.result for r in result.results if r.item_id == "python")
    assert len(python_results) == 2  # Two notes have the "python" tag
    
    beginner_results = next(r.result for r in result.results if r.item_id == "beginner")
    assert len(beginner_results) == 2  # Two notes have the "beginner" tag
    
    tutorial_beginner_results = next(r.result for r in result.results if r.item_id == "tutorial,beginner")
    assert len(tutorial_beginner_results) == 2  # Two notes have both "tutorial" and "beginner" tags
    
    nonexistent_results = next(r.result for r in result.results if r.item_id == "nonexistent-tag")
    assert len(nonexistent_results) == 0  # No notes have the "nonexistent-tag"


def test_batch_search_by_link(zettel_service):
    """Test performing multiple link searches in a batch."""
    # Create a search service
    search_service = SearchService(zettel_service=zettel_service)
    
    # Create test notes
    note1 = zettel_service.create_note(
        title="Central Note",
        content="This note links to multiple other notes.",
        tags=["central"]
    )
    
    note2 = zettel_service.create_note(
        title="Connected Note 1",
        content="This note is connected to the central note.",
        tags=["connected"]
    )
    
    note3 = zettel_service.create_note(
        title="Connected Note 2",
        content="This note is also connected to the central note.",
        tags=["connected"]
    )
    
    note4 = zettel_service.create_note(
        title="Isolated Note",
        content="This note has no connections.",
        tags=["isolated"]
    )
    
    # Create links between notes
    zettel_service.create_link(
        source_id=note1.id,
        target_id=note2.id,
        link_type=LinkType.REFERENCE,
        bidirectional=False
    )
    
    zettel_service.create_link(
        source_id=note1.id,
        target_id=note3.id,
        link_type=LinkType.EXTENDS,
        bidirectional=True
    )
    
    # Prepare link queries
    link_queries = [
        {'note_id': note1.id, 'direction': 'outgoing'},  # Should find 2 notes
        {'note_id': note1.id, 'direction': 'incoming'},  # Should find 1 note
        {'note_id': note1.id, 'direction': 'both'},      # Should find 2 notes
        {'note_id': note2.id, 'direction': 'incoming'},  # Should find 1 note
        {'note_id': note4.id, 'direction': 'both'},      # Should find 0 notes
        {'note_id': 'non-existent-id', 'direction': 'both'}  # Should fail
    ]
    
    # Call batch search by link
    result = search_service.batch_search_by_link(link_queries)
    
    # Verify results
    assert result.total_count == 6
    assert result.success_count == 5
    assert result.failure_count == 1
    
    # Check search results for outgoing links from note1
    outgoing_results = next(r.result for r in result.results if r.item_id == f"{note1.id}:outgoing")
    assert len(outgoing_results) == 2
    assert {n.id for n in outgoing_results} == {note2.id, note3.id}
    
    # Check search results for incoming links to note1
    incoming_results = next(r.result for r in result.results if r.item_id == f"{note1.id}:incoming")
    assert len(incoming_results) == 1
    assert incoming_results[0].id == note3.id  # Only note3 has a link to note1 (bidirectional)
    
    # Check search results for both directions from note1
    both_results = next(r.result for r in result.results if r.item_id == f"{note1.id}:both")
    assert len(both_results) == 2
    assert {n.id for n in both_results} == {note2.id, note3.id}
    
    # Check search results for incoming links to note2
    note2_incoming = next(r.result for r in result.results if r.item_id == f"{note2.id}:incoming")
    assert len(note2_incoming) == 1
    assert note2_incoming[0].id == note1.id
    
    # Check search results for links to/from note4 (isolated)
    note4_both = next(r.result for r in result.results if r.item_id == f"{note4.id}:both")
    assert len(note4_both) == 0
    
    # Check failed operation
    failed_ops = [r for r in result.results if not r.success]
    assert len(failed_ops) == 1
    assert "non-existent-id" in failed_ops[0].item_id


def test_batch_find_similar_notes(zettel_service):
    """Test finding similar notes for multiple notes in a batch."""
    # Create a search service
    search_service = SearchService(zettel_service=zettel_service)
    
    # Create test notes with varying degrees of similarity
    note1 = zettel_service.create_note(
        title="Machine Learning Basics",
        content="Introduction to machine learning concepts.",
        tags=["AI", "machine learning", "data science"]
    )
    
    note2 = zettel_service.create_note(
        title="Neural Networks",
        content="Overview of neural network architectures in machine learning.",
        tags=["AI", "machine learning", "neural networks"]
    )
    
    note3 = zettel_service.create_note(
        title="Data Science with Python",
        content="Using Python for data analysis and machine learning.",
        tags=["python", "data science", "machine learning"]
    )
    
    note4 = zettel_service.create_note(
        title="History of Computing",
        content="Evolution of computing technology.",
        tags=["history", "computing"]
    )
    
    # Create links to increase similarity
    zettel_service.create_link(note1.id, note2.id, LinkType.REFERENCE)
    zettel_service.create_link(note1.id, note3.id, LinkType.REFERENCE)
    
    # Prepare note IDs to find similar notes for
    note_ids = [
        note1.id,  # Should have similar notes (note2 and note3)
        note4.id,  # Should have fewer or no similar notes
        'non-existent-id'  # Should fail
    ]
    
    # Call batch find similar notes with low threshold to ensure results
    result = search_service.batch_find_similar_notes(note_ids, threshold=0.0)
    
    # Verify results
    assert result.total_count == 3
    assert result.success_count == 2
    assert result.failure_count == 1
    
    # Check similar notes for note1
    note1_similar = next(r.result for r in result.results if r.item_id == note1.id)
    assert len(note1_similar) >= 1  # Should find at least one similar note
    # Extract note IDs from results (which are tuples of note and similarity score)
    similar_ids = {note_tuple[0].id for note_tuple in note1_similar}
    assert note2.id in similar_ids  # note2 should be similar to note1
    
    # Check similar notes for note4
    note4_similar = next(r.result for r in result.results if r.item_id == note4.id)
    # This note has less in common with others, but with threshold 0.0 should find some
    assert isinstance(note4_similar, list)
    
    # Check failed operation
    failed_ops = [r for r in result.results if not r.success]
    assert len(failed_ops) == 1
    assert failed_ops[0].item_id == 'non-existent-id' 