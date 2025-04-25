# Batch Operations in Zettelkasten MCP

The Zettelkasten MCP server supports batch operations to efficiently manage multiple notes and links in a single operation. These batch tools are particularly useful for:

1. Bulk importing content from other systems
2. Creating multiple related notes at once
3. Establishing networks of connections efficiently
4. Performing multiple searches in one operation
5. Bulk editing or cleanup tasks

## Available Batch Operations

| Tool | Description |
|---|---|
| `zk_batch_create_notes` | Create multiple notes in a single operation |
| `zk_batch_update_notes` | Update multiple notes in a single operation |
| `zk_batch_delete_notes` | Delete multiple notes in a single operation |
| `zk_batch_create_links` | Create multiple links between notes in a single operation |
| `zk_batch_search_by_text` | Perform multiple text searches in a single operation |

## Batch Note Creation

### Tool: `zk_batch_create_notes`

Create multiple notes in a single operation.

**Input Format:**
```json
[
    {
        "title": "Note 1 Title",
        "content": "Content for note 1",
        "note_type": "permanent",
        "tags": "tag1,tag2"
    },
    {
        "title": "Note 2 Title",
        "content": "Content for note 2",
        "note_type": "literature",
        "tags": "tag2,tag3"
    }
]
```

**Parameters:**
- `notes_data`: A JSON string containing an array of note objects
  - `title`: Note title (required)
  - `content`: Note content (required)
  - `note_type`: Type of note (optional, default: "permanent")
  - `tags`: Comma-separated list of tags (optional)

**Example:**
```
zk_batch_create_notes('[{"title": "Note 1", "content": "Content 1", "note_type": "permanent", "tags": "tag1,tag2"}, {"title": "Note 2", "content": "Content 2"}]')
```

**Response:**
```
Batch note creation completed: 2/2 successful

1. Created: 'Note 1' (ID: 20230101120000)
2. Created: 'Note 2' (ID: 20230101120001)
```

## Batch Note Updates

### Tool: `zk_batch_update_notes`

Update multiple notes in a single operation.

**Input Format:**
```json
[
    {
        "note_id": "20230101120000",
        "title": "Updated Title"
    },
    {
        "note_id": "20230101120001",
        "content": "Updated content",
        "tags": "new_tag,another_tag"
    }
]
```

**Parameters:**
- `updates_data`: JSON string containing an array of note update objects
  - `note_id`: ID of the note to update (required)
  - `title`: New title (optional)
  - `content`: New content (optional)
  - `note_type`: New note type (optional)
  - `tags`: New comma-separated list of tags (optional)

**Example:**
```
zk_batch_update_notes('[{"note_id": "20230101120000", "title": "Updated Title"}, {"note_id": "20230101120001", "content": "Updated content", "tags": "new_tag,another_tag"}]')
```

**Response:**
```
Batch note update completed: 2/2 successful

1. Updated: ID 20230101120000 - 'Updated Title'
2. Updated: ID 20230101120001 - 'Note 2'
```

## Batch Note Deletion

### Tool: `zk_batch_delete_notes`

Delete multiple notes in a single operation.

**Input Format:**
```json
["20230101120000", "20230101120001"]
```

**Parameters:**
- `note_ids`: JSON string array of note IDs to delete

**Example:**
```
zk_batch_delete_notes('["20230101120000", "20230101120001"]')
```

**Response:**
```
Batch note deletion completed: 2/2 successful

1. Deleted: ID 20230101120000 - 'Updated Title'
2. Deleted: ID 20230101120001 - 'Note 2'
```

## Batch Link Creation

### Tool: `zk_batch_create_links`

Create multiple links between notes in a single operation.

**Input Format:**
```json
[
    {
        "source_id": "20230101120002",
        "target_id": "20230101120003"
    },
    {
        "source_id": "20230101120002",
        "target_id": "20230101120004",
        "link_type": "refines",
        "description": "Refines the concept",
        "bidirectional": true
    }
]
```

**Parameters:**
- `links_data`: JSON string containing an array of link objects
  - `source_id`: ID of source note (required)
  - `target_id`: ID of target note (required)
  - `link_type`: Type of link (optional, default: "reference")
  - `description`: Link description (optional)
  - `bidirectional`: Whether to create a reciprocal link (optional, default: false)

**Example:**
```
zk_batch_create_links('[{"source_id": "20230101120002", "target_id": "20230101120003"}, {"source_id": "20230101120002", "target_id": "20230101120004", "link_type": "refines", "description": "Refines the concept", "bidirectional": true}]')
```

**Response:**
```
Batch link creation completed: 2/2 successful

1. Created: Note A -> Note B [reference]
2. Created: Note A -> Note C [refines (bidirectional)]
```

## Batch Text Search

### Tool: `zk_batch_search_by_text`

Perform multiple text searches in a single operation.

**Input Format (array):**
```json
["search term 1", "search term 2"]
```

**Input Format (object with options):**
```json
{
    "queries": ["search term 1", "search term 2"],
    "include_content": true,
    "include_title": true,
    "limit": 5
}
```

**Parameters:**
- `queries_data`: JSON string containing an array of search queries, or a JSON object with queries array and options
  - When using object format:
    - `queries`: Array of search terms (required)
    - `include_content`: Whether to search in content (optional, default: true)
    - `include_title`: Whether to search in titles (optional, default: true)
    - `limit`: Maximum results per query (optional, default: 5)

**Example:**
```
zk_batch_search_by_text('["zettelkasten", "knowledge management"]')
```

**Response:**
```
Batch search completed for 2 queries

1. Query: "zettelkasten"
   Found: 3 results
   1. Introduction to Zettelkasten (ID: 20230101120005)
      Tags: zettelkasten, note-taking
      Score: 0.95
      Matched terms: zettelkasten
      Context: "The Zettelkasten method is a knowledge management system developed by..."

   2. Zettelkasten vs Traditional Notes (ID: 20230101120006)
      Tags: zettelkasten, comparison
      Score: 0.85
      Matched terms: zettelkasten
      Context: "Unlike traditional note-taking, Zettelkasten emphasizes connections between..."

   3. Digital Zettelkasten Tools (ID: 20230101120007)
      Tags: zettelkasten, tools, software
      Score: 0.78
      Matched terms: zettelkasten
      Context: "Modern digital Zettelkasten tools provide features such as..."

2. Query: "knowledge management"
   Found: 2 results
   1. Knowledge Management Systems (ID: 20230101120008)
      Tags: knowledge, management, systems
      Score: 0.92
      Matched terms: knowledge, management
      Context: "Effective knowledge management systems allow organizations to..."

   2. Personal Knowledge Management (ID: 20230101120009)
      Tags: pkm, knowledge
      Score: 0.87
      Matched terms: knowledge, management
      Context: "Personal knowledge management (PKM) refers to the process of..."
```

## Best Practices for Batch Operations

1. **Start Small**: Test batch operations with a small number of items before running large batches.

2. **Validate Input**: Always validate your JSON input format before executing batch operations.

3. **Error Handling**: Check the response for any failed operations and address them individually.

4. **Atomicity**: Note that batch operations are not fully atomic - successful operations in a batch will be applied even if others fail.

5. **Rate Limiting**: For extremely large batches, consider breaking them into smaller chunks to avoid timeout issues.

6. **Backup First**: Before executing large batch delete operations, it's recommended to back up your notes directory.

7. **Link Management**: When deleting notes in batch, be aware that links pointing to deleted notes will become orphaned references.

## Example Use Cases

### Importing Notes from Another System

```
zk_batch_create_notes('[
    {"title": "Imported Note 1", "content": "Content from external system 1", "tags": "imported,external"},
    {"title": "Imported Note 2", "content": "Content from external system 2", "tags": "imported,external"},
    {"title": "Imported Note 3", "content": "Content from external system 3", "tags": "imported,external"}
]')
```

### Creating a Network of Related Notes

First, create multiple notes:

```
zk_batch_create_notes('[
    {"title": "Main Concept", "content": "Description of the main concept", "note_type": "structure"},
    {"title": "Sub-concept A", "content": "Details about sub-concept A", "tags": "concept,a"},
    {"title": "Sub-concept B", "content": "Details about sub-concept B", "tags": "concept,b"}
]')
```

Then link them together:

```
zk_batch_create_links('[
    {"source_id": "20230101120010", "target_id": "20230101120011", "link_type": "extends", "bidirectional": true},
    {"source_id": "20230101120010", "target_id": "20230101120012", "link_type": "extends", "bidirectional": true},
    {"source_id": "20230101120011", "target_id": "20230101120012", "link_type": "related"}
]')
```

### Updating a Series of Notes

```
zk_batch_update_notes('[
    {"note_id": "20230101120010", "tags": "concept,main,updated"},
    {"note_id": "20230101120011", "content": "Updated details about sub-concept A", "tags": "concept,a,updated"},
    {"note_id": "20230101120012", "content": "Updated details about sub-concept B", "tags": "concept,b,updated"}
]')
```

### Searching Multiple Related Terms

```
zk_batch_search_by_text('{
    "queries": ["concept", "main", "sub-concept"],
    "include_content": true,
    "include_title": true,
    "limit": 3
}')
```