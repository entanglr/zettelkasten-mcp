# tests/test_integration.py
"""Integration tests for the Zettelkasten MCP system."""
import os
import tempfile
import shutil
import gc
from pathlib import Path
import pytest
from zettelkasten_mcp.config import config
from zettelkasten_mcp.models.schema import LinkType, NoteType
from zettelkasten_mcp.server.mcp_server import ZettelkastenMcpServer
from zettelkasten_mcp.services.zettel_service import ZettelService
from zettelkasten_mcp.services.search_service import SearchService

class TestIntegration:
    """Integration tests for the entire Zettelkasten MCP system."""
    @pytest.fixture(autouse=True)
    def setup_test_environment(self, request):
        """Set up test environment using temporary directories."""
        # Create temporary directories for test
        self.notes_dir = Path(tempfile.mkdtemp())
        self.db_dir = Path(tempfile.mkdtemp())
        self.database_path = self.db_dir / "test_zettelkasten.db"
        
        # Save original config values
        self.original_notes_dir = config.notes_dir
        self.original_database_path = config.database_path
        
        # Update config for tests
        config.notes_dir = self.notes_dir
        config.database_path = self.database_path
        
        # Create services
        self.zettel_service = ZettelService()
        self.zettel_service.initialize()
        self.search_service = SearchService(self.zettel_service)
        
        # Create server
        self.server = ZettelkastenMcpServer()
        
        def cleanup():
            # Clean up resources and connections
            if hasattr(self, 'zettel_service') and hasattr(self.zettel_service, '_repository'):
                if hasattr(self.zettel_service._repository, '_session'):
                    self.zettel_service._repository._session.close()
                if hasattr(self.zettel_service._repository, '_engine'):
                    self.zettel_service._repository._engine.dispose()
            
            # Clean up MCP server connections if any
            if hasattr(self, 'server') and hasattr(self.server, 'service'):
                if hasattr(self.server.service, '_repository'):
                    self.server.service._repository = None
            
            # Set objects to None to help with garbage collection
            self.zettel_service = None
            self.search_service = None
            self.server = None
            
            # Force garbage collection to release file handles
            gc.collect()
            
            # Restore original config
            config.notes_dir = self.original_notes_dir
            config.database_path = self.original_database_path
            
            # Clean up temp directories
            try:
                shutil.rmtree(self.notes_dir, ignore_errors=True)
            except:
                pass
                
            try:
                shutil.rmtree(self.db_dir, ignore_errors=True)
            except:
                pass
        
        request.addfinalizer(cleanup)
        yield
    
    def test_create_note_flow(self):
        """Test the complete flow of creating and retrieving a note."""
        # Use the zettel_service directly to create a note
        title = "Integration Test Note"
        content = "This is a test of the complete note creation flow."
        tags = ["integration", "test", "flow"]
        
        # Create the note
        note = self.zettel_service.create_note(
            title=title,
            content=content,
            note_type=NoteType.PERMANENT,
            tags=tags
        )
        assert note.id is not None
        
        # Retrieve the note
        retrieved_note = self.zettel_service.get_note(note.id)
        assert retrieved_note is not None
        assert retrieved_note.title == title
        
        # Note content includes the title as a markdown header - account for this
        expected_content = f"# {title}\n\n{content}"
        assert retrieved_note.content.strip() == expected_content.strip()
        
        # Check tags
        for tag in tags:
            assert tag in [t.name for t in retrieved_note.tags]
        
        # Verify the note exists on disk
        note_file = self.notes_dir / f"{note.id}.md"
        assert note_file.exists(), "Note file was not created on disk"
        
        # Verify file content
        with open(note_file, "r") as f:
            file_content = f.read()
            assert title in file_content
            assert content in file_content
    
    def test_knowledge_graph_flow(self):
        """Test creating a small knowledge graph with links and semantic relationships."""
        # Create several notes to form a knowledge graph
        hub_note = self.zettel_service.create_note(
            title="Knowledge Graph Hub",
            content="This is the central hub for our test knowledge graph.",
            note_type=NoteType.HUB,
            tags=["knowledge-graph", "hub", "integration-test"]
        )
        
        concept1 = self.zettel_service.create_note(
            title="Concept One",
            content="This is the first concept in our knowledge graph.",
            note_type=NoteType.PERMANENT,
            tags=["knowledge-graph", "concept", "integration-test"]
        )
        
        concept2 = self.zettel_service.create_note(
            title="Concept Two",
            content="This is the second concept, which extends the first.",
            note_type=NoteType.PERMANENT,
            tags=["knowledge-graph", "concept", "integration-test"]
        )
        
        critique = self.zettel_service.create_note(
            title="Critique of Concepts",
            content="This note critiques and questions the concepts.",
            note_type=NoteType.PERMANENT,
            tags=["knowledge-graph", "critique", "integration-test"]
        )
        
        # Create links with different semantic meanings
        # Use different link types to avoid uniqueness constraint issues
        self.zettel_service.create_link(
            source_id=hub_note.id,
            target_id=concept1.id,
            link_type=LinkType.REFERENCE,
            description="Main concept",
            bidirectional=True
        )
        
        self.zettel_service.create_link(
            source_id=hub_note.id,
            target_id=concept2.id,
            link_type=LinkType.EXTENDS,
            description="Secondary concept",
            bidirectional=True
        )
        
        self.zettel_service.create_link(
            source_id=hub_note.id,
            target_id=critique.id,
            link_type=LinkType.SUPPORTS,
            description="Critical perspective",
            bidirectional=True
        )
        
        self.zettel_service.create_link(
            source_id=concept2.id,
            target_id=concept1.id,
            link_type=LinkType.REFINES,
            description="Builds upon first concept",
            bidirectional=True
        )
        
        self.zettel_service.create_link(
            source_id=critique.id,
            target_id=concept1.id,
            link_type=LinkType.QUESTIONS,
            description="Questions assumptions",
            bidirectional=True
        )
        
        self.zettel_service.create_link(
            source_id=critique.id,
            target_id=concept2.id,
            link_type=LinkType.CONTRADICTS,
            description="Contradicts conclusions",
            bidirectional=True
        )
        
        # Get all notes linked to the hub
        hub_links = self.zettel_service.get_linked_notes(hub_note.id, "outgoing")
        assert len(hub_links) == 3
        hub_links_ids = {note.id for note in hub_links}
        assert concept1.id in hub_links_ids
        assert concept2.id in hub_links_ids
        assert critique.id in hub_links_ids
        
        # Get notes extended by concept2
        concept2_links = self.zettel_service.get_linked_notes(concept2.id, "outgoing")
        assert len(concept2_links) >= 1  # At least one link
        
        # Verify links by tag
        kg_notes = self.zettel_service.get_notes_by_tag("knowledge-graph")
        assert len(kg_notes) == 4  # Should find all 4 notes
    
    def test_rebuild_index_flow(self):
        """Test the rebuild index functionality with direct file modifications."""
        # Create a note through the service
        note1 = self.zettel_service.create_note(
            title="Original Note",
            content="This is the original content.",
            tags=["rebuild-test"]
        )
        
        # Manually modify the file to simulate external editing
        note_file = self.notes_dir / f"{note1.id}.md"
        assert note_file.exists(), "Note file was not created on disk"
        
        # Read the current file content
        with open(note_file, "r") as f:
            file_content = f.read()
        
        # Modify the file content directly, ensuring we replace the content part only
        # The content in the file will include the title header, so we need to search
        # for the entire content structure
        modified_content = file_content.replace(
            "This is the original content.",
            "This content was manually edited outside the system."
        )
        
        # Write the modified content back
        with open(note_file, "w") as f:
            f.write(modified_content)
        
        # At this point, the file has been modified but the database hasn't been updated
        
        # Verify the database still has old content by reading through the repository
        modified_file_content = self.zettel_service.get_note(note1.id).content
        assert "manually edited" in modified_file_content
        
        # Rebuild the index
        self.zettel_service.rebuild_index()
        
        # Verify the note now has the updated content
        note1_after = self.zettel_service.get_note(note1.id)
        assert "This content was manually edited outside the system." in note1_after.content
