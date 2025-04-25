# Exporting Knowledge Base to Markdown

The Zettelkasten MCP server includes functionality to export your entire knowledge base to a well-structured, well-linked collection of markdown files. This feature is useful for:

- Creating documentation websites from your knowledge base
- Sharing your knowledge in a portable format
- Publishing your notes online
- Creating backups in a human-readable format
- Migrating to other systems

## Using the Export Tool

### Basic Usage

The simplest way to export your knowledge base is by calling the `zk_export_knowledge_base` tool without any parameters:

```
zk_export_knowledge_base()
```

This will export all notes to the default export directory (configured as `data/export` relative to your base directory).

### Custom Export Location

You can specify a custom export directory:

```
zk_export_knowledge_base("/path/to/custom/export/directory")
```

### Configuration Options

The export tool accepts the following parameters:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `export_dir` | string | `data/export` | Directory to export to (optional) |
| `clean_dir` | boolean | `true` | Whether to clean the export directory before exporting |

## Export Directory Configuration

The export directory can be configured in three ways (in order of precedence):

1. Passed directly to the `zk_export_knowledge_base` tool
2. Specified via command line argument when starting the server: `--export-dir /path/to/export`
3. Set through the `ZETTELKASTEN_EXPORT_DIR` environment variable
4. Default value in config (`data/export` relative to base directory)

## Export Structure

The export process creates a well-organized directory structure:

```
export_dir/
├── index.md                     # Main entry point with overview and navigation
├── hub_notes/                   # Entry points into the knowledge base
│   ├── <note-id>-<title>.md
│   └── ...
├── structure_notes/             # Organizing notes
│   ├── <note-id>-<title>.md
│   └── ...
├── permanent_notes/             # Well-formulated, evergreen notes
│   ├── <note-id>-<title>.md
│   └── ...
├── literature_notes/            # Notes from reading material
│   ├── <note-id>-<title>.md
│   └── ...
└── fleeting_notes/              # Quick, temporary notes
    ├── <note-id>-<title>.md
    └── ...
```

## Features of the Exported Collection

### 1. Human-Readable Filenames

Each note is exported with a filename format of `<note-id>-<slugified-title>.md`, making it easy to identify notes by both their unique ID and descriptive title.

### 2. YAML Frontmatter

Each exported note includes YAML frontmatter with essential metadata:

```yaml
---
id: 20230101120000
title: Example Note Title
type: permanent
tags: [example, note, tags]
created_at: 2023-01-01T12:00:00
updated_at: 2023-01-02T15:30:00
---
```

### 3. Markdown Content

The note content is formatted as clean Markdown, preserving the original formatting.

### 4. Proper Cross-Linking

All links between notes are transformed into proper relative links that work in Markdown viewers and documentation sites:

```markdown
## Links

- [Reference to Another Note](../permanent_notes/20230101120001-another-note-title.md)
- [Extends Research Finding](../literature_notes/20230101120002-research-finding.md)
```

### 5. Main Index

The `index.md` file serves as the main entry point and includes:

- An overview of the knowledge base
- Navigation links to different note types
- Links to all hub notes (primary entry points)
- Links to all structure notes (organizational notes)
- List of all tags with counts
- Statistics about the knowledge base

## Using the Exported Collection

The exported collection can be used in various ways:

### 1. Documentation Websites

Upload to static site generators that support Markdown:

- GitHub Pages
- GitBook
- MkDocs
- Docusaurus
- Jekyll
- Hugo

### 2. Local Browsing

Browse locally using Markdown viewers or editors:

- VS Code with Markdown extensions
- Obsidian
- Typora
- Zettlr

### 3. Sharing and Distribution

Package and share your knowledge base with others in a format that doesn't require the original system to view or use.

## Example

Here's an example of how the export process works:

1. Start with a Zettelkasten containing various interconnected notes
2. Call the export function: `zk_export_knowledge_base()`
3. The system creates the directory structure and generates all files
4. The export directory now contains a fully browsable knowledge base

## Technical Details

The export functionality:

1. Creates necessary directories based on note types
2. Processes each note to generate Markdown with proper frontmatter
3. Transforms links between notes into relative file paths
4. Creates the index page with navigation and statistics
5. Handles slugification of titles for filenames
6. Preserves all metadata from the original notes

## Best Practices

- Export regularly to create backups of your knowledge base
- Use the exported files to publish and share your knowledge
- Keep the export directory separate from your main notes directory
- Consider version controlling your exported knowledge base