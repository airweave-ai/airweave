# Airweave Dropbox Search MCP Server

This is a Model Context Protocol (MCP) server that allows Claude Desktop to search through your Dropbox files that have been indexed by Airweave.

## Prerequisites

- Python 3.10 or higher
- Claude Desktop installed
- Airweave backend running (typically on http://localhost:8001)
- A configured Dropbox sync in Airweave

## Installation

1. Clone this repository or copy the files into a local directory
2. Install the required dependencies:

```bash
pip install "mcp[cli]" httpx
```

## Usage

### 1. Run the Server Manually (Testing)

To run the server manually for testing:

```bash
python airweave_dropbox_search.py
```

### 2. Configure Claude Desktop

To configure Claude Desktop to use this MCP server:

1. Open or create Claude Desktop's configuration file:

**macOS/Linux:**
```bash
code ~/Library/Application\ Support/Claude/claude_desktop_config.json
```

**Windows:**
```bash
code %APPDATA%\Claude\claude_desktop_config.json
```

2. Add the following configuration (adjust the path to match your actual file location):

```json
{
    "mcpServers": {
        "dropbox-search": {
            "command": "python",
            "args": [
                "/absolute/path/to/airweave_dropbox_search.py"
            ]
        }
    }
}
```

3. Restart Claude Desktop

### 3. Using the Tool in Claude Desktop

Once configured, you can use the tool by:

1. Opening Claude Desktop
2. Looking for the hammer icon in the toolbar
3. Select the "search_dropbox" tool
4. Enter your search query

Example queries:
- "Find information about the quarterly report"
- "Search for documents about the marketing strategy"

## Configuration

The server has a default sync ID configured, but you can specify a different one when calling the tool.

To change the default sync ID, edit the `DEFAULT_SYNC_ID` variable in `airweave_dropbox_search.py`.

## Troubleshooting

- If Claude Desktop doesn't show the tool, check that the configuration file is correctly formatted and the path to the script is correct
- Check the logs in `~/Library/Logs/Claude/mcp*.log` for errors
- Ensure your Airweave backend is running at the expected URL (default: http://localhost:8001)
- Verify that the sync ID is valid and corresponds to a Dropbox sync in Airweave 