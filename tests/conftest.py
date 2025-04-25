"""Common test fixtures for the Zettelkasten MCP server."""
import os
import tempfile
from pathlib import Path
import pytest
import gc
import shutil
from sqlalchemy import create_engine
from zettelkasten_mcp.config import config
from zettelkasten_mcp.models.db_models import Base
from zettelkasten_mcp.services.zettel_service import ZettelService
from zettelkasten_mcp.storage.note_repository import NoteRepository

@pytest.fixture
def temp_dirs(request):
    """Create temporary directories for notes and database.
    
    This implementation uses a custom cleanup method to avoid Windows-specific
    permission errors when trying to delete files that may still be in use.
    """
    notes_dir = tempfile.mkdtemp()
    db_dir = tempfile.mkdtemp()
    
    def cleanup():
        # Force garbage collection to release any file handles
        gc.collect()
        # Try to clean up, but don't fail if we can't
        try:
            shutil.rmtree(notes_dir, ignore_errors=True)
        except:
            pass
        try:
            shutil.rmtree(db_dir, ignore_errors=True)
        except:
            pass
    
    request.addfinalizer(cleanup)
    yield Path(notes_dir), Path(db_dir)

@pytest.fixture
def test_config(temp_dirs):
    """Configure with test paths."""
    notes_dir, db_dir = temp_dirs
    database_path = db_dir / "test_zettelkasten.db"
    # Save original config values
    original_notes_dir = config.notes_dir
    original_database_path = config.database_path
    # Update config for tests
    config.notes_dir = notes_dir
    config.database_path = database_path
    yield config
    # Restore original config
    config.notes_dir = original_notes_dir
    config.database_path = original_database_path

@pytest.fixture
def note_repository(test_config, request):
    """Create a test note repository."""
    # Create tables
    database_path = test_config.get_absolute_path(test_config.database_path)
    # Create sync engine to initialize tables
    engine = create_engine(f"sqlite:///{database_path}")
    Base.metadata.create_all(engine)
    
    # Create repository
    repository = NoteRepository(
        notes_dir=test_config.notes_dir
    )
    
    def cleanup():
        # Explicitly close any connections
        if hasattr(repository, '_session'):
            repository._session.close()
        if hasattr(repository, '_engine'):
            repository._engine.dispose()
        # Also dispose the initial engine we created
        engine.dispose()
        # Force garbage collection
        gc.collect()
    
    request.addfinalizer(cleanup)
    yield repository

@pytest.fixture
def zettel_service(note_repository, request):
    """Create a test ZettelService."""
    service = ZettelService(repository=note_repository)
    
    def cleanup():
        # Force any potential references to be cleaned up
        service._repository = None
        gc.collect()
    
    request.addfinalizer(cleanup)
    yield service
