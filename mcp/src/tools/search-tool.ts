// Search tool implementation

import { z } from "zod";
import { AirweaveClient } from "../api/airweave-client.js";
import { AirweaveConfig } from "../api/types.js";
import { formatSearchResponse, formatErrorResponse } from "../utils/error-handling.js";

export function createSearchTool(
    toolName: string,
    collection: string,
    airweaveClient: AirweaveClient
) {
    const searchSchema = {
        query: z.string().min(1).max(1000).describe("The search query text to find relevant documents and data"),
        response_type: z.enum(["raw", "completion"]).optional().default("raw").describe("Format of the response: 'raw' returns search results, 'completion' returns AI-generated answers"),
        limit: z.number().min(1).max(1000).optional().default(100).describe("Maximum number of results to return"),
        offset: z.number().min(0).optional().default(0).describe("Number of results to skip for pagination"),
        recency_bias: z.number().min(0).max(1).optional().describe("How much to weigh recency vs similarity (0..1). 0 = no recency effect; 1 = rank by recency only"),
        score_threshold: z.number().min(0).max(1).optional().describe("Minimum similarity score threshold (0..1). Only return results above this score"),
        search_method: z.enum(["hybrid", "neural", "keyword"]).optional().describe("Search method: 'hybrid' (combines neural + keyword), 'neural' (semantic only), 'keyword' (text matching only)"),
        expansion_strategy: z.enum(["auto", "llm", "no_expansion"]).optional().describe("Query expansion strategy: 'auto' (generates query variations), 'llm' (AI-powered expansion), 'no_expansion' (use exact query)"),
        enable_reranking: z.boolean().optional().describe("Enable LLM-based reranking to improve result relevance"),
        enable_query_interpretation: z.boolean().optional().describe("Enable automatic filter extraction from natural language query")
    };

    const fullSchema = z.object(searchSchema);

    const parameterDescriptions = [
        "**Core Parameters:**",
        "- `query`: The search query text to find relevant documents and data (required)",
        "- `response_type`: Format of the response: 'raw' returns search results, 'completion' returns AI-generated answers (optional, default: raw)",
        "- `limit`: Maximum number of results to return (optional, default: 100)",
        "- `offset`: Number of results to skip for pagination (optional, default: 0)",
        "- `recency_bias`: How much to weigh recency vs similarity (0..1). 0 = no recency effect; 1 = rank by recency only (optional)",
        "",
        "**Advanced Parameters:**",
        "- `score_threshold`: Minimum similarity score threshold (0..1). Only return results above this score (optional)",
        "- `search_method`: Search method: 'hybrid' (default, combines neural + keyword), 'neural' (semantic only), 'keyword' (text matching only) (optional)",
        "- `expansion_strategy`: Query expansion strategy: 'auto' (default, generates query variations), 'llm' (AI-powered expansion), 'no_expansion' (use exact query) (optional)",
        "- `enable_reranking`: Enable LLM-based reranking to improve result relevance (default: true) (optional)",
        "- `enable_query_interpretation`: Enable automatic filter extraction from natural language query (default: true) (optional)"
    ].join("\n");

    const naturalLanguageExamples = [
        "**Natural Language Examples:**",
        "",
        "**Basic Search:**",
        "- 'Find the first 5 results' → limit: 5",
        "- 'Show me results 11-20' → limit: 10, offset: 10",
        "- 'Give me a summary' → response_type: 'completion'",
        "- 'Find the most recent documents' → recency_bias: 0.8",
        "",
        "**Advanced Search:**",
        "- 'Find high-quality results only' → score_threshold: 0.8",
        "- 'Use keyword search instead of semantic' → search_method: 'keyword'",
        "- 'Don't expand my query' → expansion_strategy: 'no_expansion'",
        "- 'Disable reranking' → enable_reranking: false",
        "- 'Find recent high-quality results' → recency_bias: 0.7, score_threshold: 0.8"
    ].join("\n");

    return {
        name: toolName,
        description: `Enhanced search within the Airweave collection '${collection}' with advanced filtering and ranking options.\n\n**Parameters:**\n${parameterDescriptions}\n\n${naturalLanguageExamples}`,
        schema: searchSchema,
        handler: async (params: Record<string, unknown>) => {
            try {
                const validatedParams = fullSchema.parse(params);
                const { response_type } = validatedParams;

                const searchResponse = await airweaveClient.search(validatedParams);
                return formatSearchResponse(searchResponse, response_type, collection);
            } catch (error) {
                console.error("Error in search tool:", error);

                if (error instanceof z.ZodError) {
                    const errorMessages = error.errors.map(e => `${e.path.join('.')}: ${e.message}`);
                    return {
                        content: [
                            {
                                type: "text" as const,
                                text: `**Parameter Validation Errors:**\n${errorMessages.join("\n")}`,
                            },
                        ],
                    };
                }

                return formatErrorResponse(
                    error as Error,
                    params,
                    collection,
                    airweaveClient['config'].baseUrl
                );
            }
        }
    };
}
