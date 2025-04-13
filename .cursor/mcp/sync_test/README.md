# mcp-server-sync-test: A Sync Test MCP Server for Cursor

## Overview

A Model Context Protocol server for e2e testing Airweave source integrations with cursor. This server provides tools to check connection status and run syncs for source integrations.

Please note that mcp-server-sync-test is currently in early development. The functionality and available tools are subject to change and expansion as we continue to develop and improve the server.

### Tools

1. `check_connection`
   * Checks if a source connection is established
   * Input:
         * `short_name` (string): Short name of the source to check
   * Returns: Connection status and details

2. `run_sync`
   * Runs a sync for a source integration
   * Input:
         * `short_name` (string): Short name of the source to sync
   * Returns: Sync status and results

## Run
`python server.py`

> **Important:** Make sure you have set `LOCAL_CURSOR_DEVELOPMENT=true` in your `.env`


### Add MCP Server to Cursor
In Cursor, navigate to Cursor Settings > MCP > Add New MCP Server

Give a name, like "Run Sync Test Server", choose "SSE" and put in `http://localhost:8002/sse` as URL.
