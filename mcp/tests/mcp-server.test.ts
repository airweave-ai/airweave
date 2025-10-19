/**
 * MCP Server Tests - Tests the actual MCP server functionality
 * 
 * These tests verify:
 * 1. Tool registration works correctly
 * 2. Tool handlers execute with correct parameters
 * 3. Parameters flow correctly from MCP → SDK → API
 * 4. Response formatting works
 * 5. Error handling works
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { AirweaveSDKClient } from '@airweave/sdk';
import { createSearchTool } from '../src/tools/search-tool.js';
import { createConfigTool } from '../src/tools/config-tool.js';
import { AirweaveClient } from '../src/api/airweave-client.js';

// Mock the Airweave SDK
vi.mock('@airweave/sdk');

describe('MCP Server - Tool Registration and Execution', () => {
    let mockSdkClient: any;
    let airweaveClient: AirweaveClient;

    beforeEach(() => {
        vi.clearAllMocks();

        // Mock the SDK client
        mockSdkClient = {
            collections: {
                search: vi.fn().mockResolvedValue({
                    results: [
                        {
                            score: 0.95,
                            payload: {
                                title: 'Test Document',
                                md_content: 'This is test content about machine learning algorithms.',
                                source_name: 'github',
                                entity_id: 'test-123'
                            }
                        }
                    ],
                    completion: null
                })
            }
        };

        vi.mocked(AirweaveSDKClient).mockImplementation(() => mockSdkClient);

        airweaveClient = new AirweaveClient({
            apiKey: 'test-api-key',
            collection: 'test-collection',
            baseUrl: 'https://api.airweave.ai'
        });
    });

    describe('Search Tool Creation', () => {
        it('should create search tool with correct name', () => {
            const tool = createSearchTool('search-my-collection', 'my-collection', airweaveClient);

            expect(tool.name).toBe('search-my-collection');
            expect(tool.description).toContain('my-collection');
            expect(tool.handler).toBeDefined();
            expect(typeof tool.handler).toBe('function');
        });

        it('should have correct schema with all parameters', () => {
            const tool = createSearchTool('search-test', 'test', airweaveClient);

            // Check that schema has all required fields
            expect(tool.schema).toHaveProperty('query');
            expect(tool.schema).toHaveProperty('response_type');
            expect(tool.schema).toHaveProperty('limit');
            expect(tool.schema).toHaveProperty('offset');
            expect(tool.schema).toHaveProperty('recency_bias');

            // Check advanced parameters
            expect(tool.schema).toHaveProperty('score_threshold');
            expect(tool.schema).toHaveProperty('search_method');
            expect(tool.schema).toHaveProperty('expansion_strategy');
            expect(tool.schema).toHaveProperty('enable_reranking');
            expect(tool.schema).toHaveProperty('enable_query_interpretation');
        });
    });

    describe('Search Tool Execution - Parameter Passing', () => {
        it('should pass basic parameters correctly to SDK', async () => {
            const tool = createSearchTool('search-test', 'test-collection', airweaveClient);

            await tool.handler({
                query: 'machine learning',
                limit: 5,
                offset: 10
            });

            expect(mockSdkClient.collections.search).toHaveBeenCalledWith(
                'test-collection',
                expect.objectContaining({
                    query: 'machine learning',
                    limit: 5,
                    offset: 10
                })
            );
        });

        it('should pass advanced parameters correctly to SDK', async () => {
            const tool = createSearchTool('search-test', 'test-collection', airweaveClient);

            await tool.handler({
                query: 'neural networks',
                score_threshold: 0.8,
                search_method: 'neural',
                enable_reranking: true
            });

            expect(mockSdkClient.collections.search).toHaveBeenCalledWith(
                'test-collection',
                expect.objectContaining({
                    query: 'neural networks',
                    score_threshold: 0.8,
                    search_method: 'neural',
                    enable_reranking: true
                })
            );
        });

        it('should pass all parameters together correctly', async () => {
            const tool = createSearchTool('search-test', 'test-collection', airweaveClient);

            await tool.handler({
                query: 'AI research',
                limit: 20,
                offset: 5,
                recency_bias: 0.7,
                response_type: 'completion',
                score_threshold: 0.8,
                search_method: 'hybrid',
                expansion_strategy: 'llm',
                enable_reranking: true,
                enable_query_interpretation: false
            });

            const call = mockSdkClient.collections.search.mock.calls[0];
            expect(call[0]).toBe('test-collection');
            expect(call[1]).toMatchObject({
                query: 'AI research',
                limit: 20,
                offset: 5,
                recency_bias: 0.7,
                response_type: 'completion',
                score_threshold: 0.8,
                search_method: 'hybrid',
                expansion_strategy: 'llm',
                enable_reranking: true,
                enable_query_interpretation: false
            });
        });

        it('should NOT pass undefined parameters to SDK', async () => {
            const tool = createSearchTool('search-test', 'test-collection', airweaveClient);

            await tool.handler({
                query: 'test query',
                limit: 5
                // No other parameters
            });

            const call = mockSdkClient.collections.search.mock.calls[0];
            const params = call[1];

            // Should have these
            expect(params).toHaveProperty('query');
            expect(params).toHaveProperty('limit');
            expect(params).toHaveProperty('response_type'); // Has default
            expect(params).toHaveProperty('offset'); // Has default

            // Should NOT have these (no defaults, not provided)
            expect(params.score_threshold).toBeUndefined();
            expect(params.search_method).toBeUndefined();
            expect(params.enable_reranking).toBeUndefined();
        });
    });

    describe('Search Tool Execution - Response Formatting', () => {
        it('should format raw search results correctly', async () => {
            const tool = createSearchTool('search-test', 'test-collection', airweaveClient);

            const result = await tool.handler({
                query: 'test',
                response_type: 'raw'
            });

            expect(result).toHaveProperty('content');
            expect(Array.isArray(result.content)).toBe(true);
            expect(result.content[0]).toHaveProperty('type', 'text');
            expect(result.content[0]).toHaveProperty('text');
            expect(result.content[0].text).toContain('Test Document');
        });

        it('should format completion response correctly', async () => {
            mockSdkClient.collections.search.mockResolvedValue({
                results: [],
                completion: 'This is an AI-generated summary of the search results.'
            });

            const tool = createSearchTool('search-test', 'test-collection', airweaveClient);

            const result = await tool.handler({
                query: 'test',
                response_type: 'completion'
            });

            expect(result.content[0].text).toBe('This is an AI-generated summary of the search results.');
        });

        it('should handle empty results gracefully', async () => {
            mockSdkClient.collections.search.mockResolvedValue({
                results: [],
                completion: null
            });

            const tool = createSearchTool('search-test', 'test-collection', airweaveClient);

            const result = await tool.handler({
                query: 'nonexistent query'
            });

            expect(result.content[0].text).toContain('No results found');
        });
    });

    describe('Search Tool Execution - Error Handling', () => {
        it('should handle validation errors correctly', async () => {
            const tool = createSearchTool('search-test', 'test-collection', airweaveClient);

            const result = await tool.handler({
                // Missing required 'query' parameter
                limit: 5
            });

            expect(result.content[0].text).toContain('Parameter Validation Errors');
            expect(result.content[0].text).toContain('query');
        });

        it('should handle API errors correctly', async () => {
            mockSdkClient.collections.search.mockRejectedValue(
                new Error('Airweave API error (404): Collection not found')
            );

            const tool = createSearchTool('search-test', 'test-collection', airweaveClient);

            const result = await tool.handler({
                query: 'test'
            });

            expect(result.content[0].text).toContain('Failed to search collection');
            expect(result.content[0].text).toContain('404');
        });

        it('should handle network errors correctly', async () => {
            mockSdkClient.collections.search.mockRejectedValue(
                new Error('Network error: timeout')
            );

            const tool = createSearchTool('search-test', 'test-collection', airweaveClient);

            const result = await tool.handler({
                query: 'test'
            });

            expect(result.content[0].text).toContain('Failed to search collection');
            expect(result.content[0].text).toContain('Network error');
        });
    });

    describe('Config Tool', () => {
        it('should create config tool correctly', () => {
            const tool = createConfigTool('search-test', 'test-collection', 'https://api.airweave.ai', 'test-key');

            expect(tool.name).toBe('get-config');
            expect(tool.description).toContain('configuration');
            expect(tool.handler).toBeDefined();
        });

        it('should return correct configuration', async () => {
            const tool = createConfigTool('search-test', 'my-collection', 'https://api.airweave.ai', 'test-key-123');

            const result = await tool.handler({});

            expect(result.content[0].text).toContain('my-collection');
            expect(result.content[0].text).toContain('https://api.airweave.ai');
            expect(result.content[0].text).toContain('Configured'); // API key status
        });
    });

    describe('MCP Server Integration', () => {
        it('should register tools correctly on MCP server', () => {
            const server = new McpServer({
                name: 'test-server',
                version: '1.0.0'
            }, {
                capabilities: { tools: {} }
            });

            const searchTool = createSearchTool('search-test', 'test', airweaveClient);
            const configTool = createConfigTool('search-test', 'test', 'https://api.airweave.ai', 'key');

            // Register tools
            server.tool(searchTool.name, searchTool.description, searchTool.schema, searchTool.handler);
            server.tool(configTool.name, configTool.description, configTool.schema, configTool.handler);

            // Server should have tools registered
            expect(server).toBeDefined();
        });
    });

    describe('Parameter Type Validation', () => {
        it('should validate string parameters', async () => {
            const tool = createSearchTool('search-test', 'test-collection', airweaveClient);

            const result = await tool.handler({
                query: 123 // Should be string
            });

            expect(result.content[0].text).toContain('Parameter Validation Errors');
        });

        it('should validate number parameters', async () => {
            const tool = createSearchTool('search-test', 'test-collection', airweaveClient);

            const result = await tool.handler({
                query: 'test',
                limit: 'five' // Should be number
            });

            expect(result.content[0].text).toContain('Parameter Validation Errors');
        });

        it('should validate enum parameters', async () => {
            const tool = createSearchTool('search-test', 'test-collection', airweaveClient);

            const result = await tool.handler({
                query: 'test',
                search_method: 'invalid-method' // Should be one of: hybrid, neural, keyword
            });

            expect(result.content[0].text).toContain('Parameter Validation Errors');
        });

        it('should validate boolean parameters', async () => {
            const tool = createSearchTool('search-test', 'test-collection', airweaveClient);

            const result = await tool.handler({
                query: 'test',
                enable_reranking: 'true' // Should be boolean, not string
            });

            expect(result.content[0].text).toContain('Parameter Validation Errors');
        });
    });
});

