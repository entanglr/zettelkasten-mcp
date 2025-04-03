# Zettelkasten MCP Server

A Model Context Protocol (MCP) server that implements the Zettelkasten knowledge management methodology, allowing you to create, link, and search atomic notes through Claude and other MCP-compatible clients.

## What is Zettelkasten?

The Zettelkasten method is a knowledge management system developed by German sociologist Niklas Luhmann, who used it to produce over 70 books and hundreds of articles. It consists of three core principles:

1. **Atomicity**: Each note contains exactly one idea, making it a discrete unit of knowledge
2. **Connectivity**: Notes are linked together to create a network of knowledge, with meaningful relationships between ideas
3. **Emergence**: As the network grows, new patterns and insights emerge that weren't obvious when the individual notes were created

What makes the Zettelkasten approach powerful is how it enables exploration in multiple ways:

- **Vertical exploration**: dive deeper into specific topics by following connections within a subject area.
- **Horizontal exploration**: discover unexpected relationships between different fields by traversing links that cross domains.

This structure invites serendipitous discoveries as you follow trails of thought from note to note, all while keeping each piece of information easily accessible through its unique identifier. Luhmann called his system his "second brain" or "communication partner" - this digital implementation aims to provide similar benefits through modern technology.

## Features

- Create atomic notes with unique timestamp-based IDs
- Link notes bidirectionally to build a knowledge graph
- Tag notes for categorical organization
- Search notes by content, tags, or links
- Use markdown format for human readability and editing
- Integrate with Claude through MCP for AI-assisted knowledge management
- Dual storage architecture (see below)
- Synchronous operation model for simplified architecture

## Example

### Screenshot

![example](https://github.com/user-attachments/assets/a72161b6-5a3e-43e8-8359-95b8e7175356)

### Result

>I've successfully created a small Zettelkasten knowledge network about the Zettelkasten method itself. Here's a summary of what I've demonstrated:
>
>1. **Created a central hub note** ("Zettelkasten Method Overview") that acts as the main entry point to the knowledge network, providing an overview and linking to more specific notes.
>
>2. **Created atomic notes** on specific topics:
>   - "Principle of Atomicity"
>   - "Connectivity Between Notes"
>   - "Emergent Knowledge"
>   - "Niklas Luhmann"
>   - "Digital Zettelkasten Implementation"
>   - Plus a fleeting note for future ideas
>
>3. **Created bidirectional links** between notes:
>   - The hub note links to all key concept notes
>   - Concept notes link to each other in meaningful ways
>   - Different link types demonstrate various relationships (reference, related, supports, contradicts)
>
>4. **Demonstrated central notes**: The `zk_find_central_notes` command shows that our hub note has become the most connected note (10 connections), followed by the "Connectivity Between Notes" note (6 connections).
>
>5. **Showed searching and filtering** by tags and similarity, which helps navigate the knowledge network.
>
>This demonstrates **the power of the Zettelkasten method**, where knowledge is stored atomically but connected in a network, with hub notes serving as navigation aids. The structure allows for **exploring the network** via multiple paths, facilitating **deeper understanding** and **unexpected connections**.

## Prompting

To ensure maximum effectiveness, we recommend using a system prompt ("project instructions"), project knowledge, and an appropriate chat prompt when asking the LLM to process information, or explore or synthesize your Zettelkasten notes. The `docs` directory in this repository contains the necessary files to get you started:

### System prompts

Pick one:

- [system-prompt.md](https://github.com/entanglr/zettelkasten-mcp/blob/main/docs/prompts/system/system-prompt.md)
- [system-prompt-with-protocol.md](https://github.com/entanglr/zettelkasten-mcp/blob/main/docs/prompts/system/system-prompt-with-protocol.md)

### Project knowledge

For end users:

- [zettelkasten-methodology-technical.md](https://github.com/entanglr/zettelkasten-mcp/blob/main/docs/project-knowledge/user/zettelkasten-methodology-technical.md)
- [link-types-in-zettelkasten-mcp-server.md](https://github.com/entanglr/zettelkasten-mcp/blob/main/docs/project-knowledge/user/link-types-in-zettelkasten-mcp-server.md)
- (more info relevant to your project)

### Chat Prompts

- [chat-prompt-knowledge-creation.md](https://github.com/entanglr/zettelkasten-mcp/blob/main/docs/prompts/chat/chat-prompt-knowledge-creation.md)
- [chat-prompt-knowledge-creation-batch.md](https://github.com/entanglr/zettelkasten-mcp/blob/main/docs/prompts/chat/chat-prompt-knowledge-creation-batch.md)
- [chat-prompt-knowledge-exploration.md](https://github.com/entanglr/zettelkasten-mcp/blob/main/docs/prompts/chat/chat-prompt-knowledge-exploration.md)
- [chat-prompt-knowledge-synthesis.md](https://github.com/entanglr/zettelkasten-mcp/blob/main/docs/prompts/chat/chat-prompt-knowledge-synthesis.md)

### Project knowledge (dev)

For developers and contributors:

- [Example - A simple MCP server.md](https://github.com/entanglr/zettelkasten-mcp/blob/main/docs/project-knowledge/dev/Example%20-%20A%20simple%20MCP%20server%20that%20exposes%20a%20website%20fetching%20tool.md)
- [MCP Python SDK-README.md](https://github.com/entanglr/zettelkasten-mcp/blob/main/docs/project-knowledge/dev/MCP%20Python%20SDK-README.md)
- [llms-full.txt](https://github.com/entanglr/zettelkasten-mcp/blob/main/docs/project-knowledge/dev/llms-full.txt)

NB: Optionally include the source code with a tool like [repomix](https://github.com/yamadashy/repomix).

## Note Types

The Zettelkasten MCP server supports different types of notes:

1. **Fleeting notes** (fleeting): Quick, temporary notes for capturing ideas
2. **Literature notes** (literature): Notes from reading material
3. **Permanent notes** (permanent): Well-formulated, evergreen notes
4. **Structure notes** (structure): Index or outline notes that organize other notes
5. **Hub notes** (hub): Entry points to the Zettelkasten on key topics

## Link Types

The Zettelkasten MCP server uses a comprehensive semantic linking system that creates meaningful connections between notes. Each link type represents a specific relationship, allowing for a rich, multi-dimensional knowledge graph.

| Primary Link Type | Inverse Link Type | Relationship Description |
|-------------------|-------------------|--------------------------|
| `reference` | `reference` | Simple reference to related information (symmetric relationship) |
| `extends` | `extended_by` | One note builds upon or develops concepts from another |
| `refines` | `refined_by` | One note clarifies or improves upon another |
| `contradicts` | `contradicted_by` | One note presents opposing views to another |
| `questions` | `questioned_by` | One note poses questions about another |
| `supports` | `supported_by` | One note provides evidence for another |
| `related` | `related` | Generic relationship (symmetric relationship) |

## Storage Architecture

This system uses a dual storage approach:

1. **Markdown Files**: All notes are stored as human-readable Markdown files with YAML frontmatter for metadata. These files are the **source of truth** and can be:
   - Edited directly in any text editor
   - Placed under version control (Git, etc.)
   - Backed up using standard file backup procedures
   - Shared or transferred like any other text files

2. **SQLite Database**: Functions as an indexing layer that:
   - Facilitates efficient querying and search operations
   - Enables Claude to quickly traverse the knowledge graph
   - Maintains relationship information for faster link traversal
   - Is automatically rebuilt from Markdown files when needed

If you edit Markdown files directly outside the system, you'll need to run the `zk_rebuild_index` tool to update the database. The database itself can be deleted at any time - it will be regenerated from your Markdown files.

## Installation

```bash
# Clone the repository
git clone https://github.com/entanglr/zettelkasten-mcp.git
cd zettelkasten-mcp

# Create a virtual environment with uv
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
uv add "mcp[cli]"

# Install dev dependencies
uv sync --all-extras
```

## Configuration

Create a `.env` file in the project root by copying the example:

```bash
cp .env.example .env
```

Then edit the file to configure your connection parameters.

## Usage

### Starting the Server

```bash
python -m zettelkasten_mcp.main
```

Or with explicit configuration:

```bash
python -m zettelkasten_mcp.main --notes-dir ./data/notes --database-path ./data/db/zettelkasten.db
```

### Connecting to Claude Desktop

Add the following configuration to your Claude Desktop:

```json
{
  "mcpServers": {
    "zettelkasten": {
      "command": "/absolute/path/to/zettelkasten-mcp/.venv/bin/python",
      "args": [
        "-m",
        "zettelkasten_mcp.main"
      ],
      "env": {
        "ZETTELKASTEN_NOTES_DIR": "/absolute/path/to/zettelkasten-mcp/data/notes",
        "ZETTELKASTEN_DATABASE_PATH": "/absolute/path/to/zettelkasten-mcp/data/db/zettelkasten.db",
        "ZETTELKASTEN_LOG_LEVEL": "INFO"
      }
    }
  }
}
```

## Available MCP Tools

All tools have been prefixed with `zk_` for better organization:

| Tool | Description |
|---|---|
| `zk_create_note` | Create a new note with a title, content, and optional tags |
| `zk_get_note` | Retrieve a specific note by ID or title |
| `zk_update_note` | Update an existing note's content or metadata |
| `zk_delete_note` | Delete a note |
| `zk_create_link` | Create links between notes |
| `zk_remove_link` | Remove links between notes |
| `zk_search_notes` | Search for notes by content, tags, or links |
| `zk_get_linked_notes` | Find notes linked to a specific note |
| `zk_get_all_tags` | List all tags in the system |
| `zk_find_similar_notes` | Find notes similar to a given note |
| `zk_find_central_notes` | Find notes with the most connections |
| `zk_find_orphaned_notes` | Find notes with no connections |
| `zk_list_notes_by_date` | List notes by creation/update date |
| `zk_rebuild_index` | Rebuild the database index from Markdown files |

## Project Structure

```
zettelkasten-mcp/
├── src/
│   └── zettelkasten_mcp/
│       ├── models/       # Data models
│       ├── storage/      # Storage layer
│       ├── services/     # Business logic
│       └── server/       # MCP server implementation
├── data/
│   ├── notes/            # Note storage (Markdown files)
│   └── db/               # Database for indexing
├── tests/                # Test suite
├── .env.example          # Environment variable template
└── README.md
```

## Tests

Comprehensive test suite for Zettelkasten MCP covering all layers of the application from models to the MCP server implementation.

### How to Run the Tests

From the project root directory, run:

#### Using pytest directly
```bash
python -m pytest -v tests/
```

#### Using UV
```bash
uv run pytest -v tests/
```

#### With coverage report
```bash
uv run pytest --cov=zettelkasten_mcp --cov-report=term-missing tests/
```

#### Running a specific test file
```bash
uv run pytest -v tests/test_models.py
```

#### Running a specific test class
```bash
uv run pytest -v tests/test_models.py::TestNoteModel
```

#### Running a specific test function
```bash
uv run pytest -v tests/test_models.py::TestNoteModel::test_note_validation
```

### Tests Directory Structure

```
tests/
├── conftest.py - Common fixtures for all tests
├── test_models.py - Tests for data models
├── test_note_repository.py - Tests for note repository
├── test_zettel_service.py - Tests for zettel service
├── test_search_service.py - Tests for search service
├── test_mcp_server.py - Tests for MCP server tools
└── test_integration.py - Integration tests for the entire system
```

## Important Notice

**⚠️ USE AT YOUR OWN RISK**: This software is experimental and provided as-is without warranty of any kind. While efforts have been made to ensure data integrity, it may contain bugs that could potentially lead to data loss or corruption. Always back up your notes regularly and use caution when testing with important information.

## Credit Where Credit's Due

This MCP server was crafted with the assistance of Claude, who helped organize the atomic thoughts of this project into a coherent knowledge graph. Much like a good Zettelkasten system, Claude connected the dots between ideas that might otherwise have remained isolated. Unlike Luhmann's paper-based system, however, Claude didn't require 90,000 index cards to be effective.

## License

MIT License
