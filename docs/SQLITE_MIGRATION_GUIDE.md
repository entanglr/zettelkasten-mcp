# SQLite-Only Storage Migration Guide

## Overview

This guide explains how to migrate your Zettelkasten from dual storage (markdown files + SQLite index) to SQLite-only storage. The migration preserves all note data including content, metadata, links, and timestamps.

## Benefits of SQLite-Only Storage

1. **Better Performance**: Faster queries and operations without file I/O overhead
2. **Atomic Operations**: Database transactions ensure data consistency
3. **Scalability**: Handles large note collections efficiently
4. **Advanced Features**: JSON metadata storage, better indexing, optimized queries
5. **Simplified Backup**: Single database file to backup/restore

## Prerequisites

- Python 3.8+
- Existing Zettelkasten with markdown files
- Backup of your current notes (automatic during migration)

## Migration Process

### 1. Install Dependencies

Ensure all required dependencies are installed:

```bash
pip install -r requirements.txt
```

### 2. Run Migration Script

The migration script handles the entire process including backup:

```bash
python src/zettelkasten_mcp/migration/migrate_to_sqlite.py \
  --notes-dir /path/to/your/notes \
  --db-path /path/to/new/database.db
```

Options:
- `--notes-dir`: Directory containing your markdown notes (default: from config)
- `--db-path`: Path for the new SQLite database (default: from config)
- `--backup-dir`: Directory for backups (default: notes_dir/../backups)
- `--skip-backup`: Skip creating backup (not recommended)
- `--skip-verify`: Skip migration verification
- `--log-level`: Set logging level (DEBUG, INFO, WARNING, ERROR)

### 3. Migration Output

The migration will:
1. Create a timestamped backup of your notes
2. Parse all markdown files
3. Import notes into SQLite with full metadata
4. Verify data integrity
5. Generate a migration report

Example output:
```
Starting Zettelkasten Migration to SQLite

Creating backup at /path/to/backups/notes_backup_20250718_143022...
✓ Backup created

Found 523 markdown files to migrate

Migrating notes... 100% |████████████████| 523/523

Verifying migration...
✓ Migration verification passed

Optimizing database...
✓ Database optimized

Migration Summary
╭─────────────────┬───────╮
│ Metric          │ Value │
├─────────────────┼───────┤
│ Total Files     │ 523   │
│ Successful      │ 521   │
│ Failed          │ 2     │
│ Success Rate    │ 99.6% │
│ Duration        │ 4.32s │
╰─────────────────┴───────╯

✓ Migration report saved to /path/to/backups/migration_report_20250718_143026.json
✓ Migration completed successfully!
```

## Using the New SQLite Repository

### 1. Update Your Code

Replace the dual-storage repository with the SQLite-only version:

```python
# Old dual-storage approach
from zettelkasten_mcp.storage.note_repository import NoteRepository

# New SQLite-only approach
from zettelkasten_mcp.storage.sqlite_repository import SQLiteNoteRepository

# Initialize
repository = SQLiteNoteRepository(db_path="/path/to/database.db")
```

### 2. All Operations Remain the Same

The SQLite repository implements the same interface:

```python
# Create a note
note = Note(
    id="20250718143000000000000",
    title="My Note",
    content="Note content",
    note_type=NoteType.PERMANENT,
    tags=[Tag(name="example")],
    links=[]
)
repository.create(note)

# Read a note
note = repository.read("20250718143000000000000")

# Update a note
note.title = "Updated Title"
repository.update(note)

# Search notes
results = repository.search("keyword")

# Find by tag
notes = repository.find_by_tag("example")
```

### 3. New Features

The SQLite repository adds:

```python
# JSON metadata storage
note.metadata = {
    "author": "John Doe",
    "references": ["ref1", "ref2"],
    "custom_data": {"nested": {"value": 42}}
}

# Database backup
repository.backup(Path("/path/to/backup.db"))

# Database restore
repository.restore(Path("/path/to/backup.db"))

# Optimize database
repository.optimize()

# Verify integrity
is_valid = repository.verify_integrity()
```

## Export and Import Utilities

### Export Notes to Markdown

Export all notes:
```python
from zettelkasten_mcp.export_import import BulkExporter

exporter = BulkExporter(repository)
export_dir = exporter.create_timestamped_export(Path("/exports"))
```

Export by criteria:
```python
from zettelkasten_mcp.export_import import MarkdownExporter

exporter = MarkdownExporter(repository)

# Export by tag
exporter.export_by_criteria(export_dir, tag="important")

# Export by type
exporter.export_by_criteria(export_dir, note_type="permanent")

# Export by search
exporter.export_by_criteria(export_dir, search_query="project")
```

### Import Notes from Markdown

Import from directory:
```python
from zettelkasten_mcp.export_import import BulkImporter

importer = BulkImporter(repository)

# Restore from export
success = importer.restore_from_export(export_dir)

# Merge multiple imports
importer.merge_imports([dir1, dir2], strategy="newest")
```

## Rollback Process

If you need to rollback to markdown files:

1. Use the export utility to export all notes:
   ```bash
   python -c "
   from pathlib import Path
   from zettelkasten_mcp.storage.sqlite_repository import SQLiteNoteRepository
   from zettelkasten_mcp.export_import import BulkExporter
   
   repo = SQLiteNoteRepository(Path('database.db'))
   exporter = BulkExporter(repo)
   exporter.create_timestamped_export(Path('./exports'))
   "
   ```

2. Copy exported markdown files back to your notes directory

3. Switch back to the dual-storage repository in your code

## Verification

Run the verification script to test the migration:

```bash
python scripts/verify_sqlite_migration.py
```

This will:
- Create test notes
- Verify CRUD operations
- Test search functionality
- Test export/import
- Verify database integrity

## Troubleshooting

### Migration Failures

Check the migration report for details:
```bash
cat /path/to/backups/migration_report_*.json | jq .errors
```

Common issues:
- Missing frontmatter fields
- Invalid note types
- Malformed links

### Performance Issues

1. Run database optimization:
   ```python
   repository.optimize()
   ```

2. Check database size:
   ```bash
   ls -lh database.db
   ```

3. Verify indexes are being used:
   ```python
   # Check query performance
   import time
   start = time.time()
   results = repository.search("term")
   print(f"Search took {time.time() - start:.3f}s")
   ```

### Data Integrity

Verify database integrity:
```python
if not repository.verify_integrity():
    # Restore from backup
    repository.restore(backup_path)
```

## Best Practices

1. **Regular Backups**: Schedule automated backups of the SQLite database
2. **Export Snapshots**: Periodically export to markdown for portability
3. **Monitor Size**: Track database growth over time
4. **Optimize Regularly**: Run optimization during maintenance windows
5. **Test Restore**: Regularly test your backup/restore process

## Migration Checklist

- [ ] Backup current notes directory
- [ ] Review migration warnings in report
- [ ] Verify all notes migrated successfully
- [ ] Test search and link functionality
- [ ] Update application code to use SQLite repository
- [ ] Set up automated backups
- [ ] Document any custom metadata fields
- [ ] Train team on new features