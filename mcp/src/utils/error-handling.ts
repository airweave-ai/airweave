// Error handling utilities

import { SearchResponse } from "../api/types.js";

export function formatSearchResponse(searchResponse: SearchResponse, responseType: string, collection: string) {
    if (responseType === "completion") {
        return {
            content: [
                {
                    type: "text" as const,
                    text: searchResponse.completion || "No response generated",
                },
            ],
        };
    } else {
        const formattedResults = searchResponse.results
            .map((result: any, index) => {
                const parts = [
                    `**Result ${index + 1}${result.score ? ` (Score: ${result.score.toFixed(3)})` : ""}:**`
                ];

                if (result.entity_id || result.name) {
                    const metadata = [];
                    if (result.entity_id) metadata.push(`ID: ${result.entity_id}`);
                    if (result.name) metadata.push(`Name: ${result.name}`);
                    parts.push(metadata.join(" | "));
                }

                const content = result.textual_representation ||
                    result.content ||
                    result.text ||
                    result.payload?.content ||
                    result.payload?.text;

                if (content) {
                    parts.push(content);
                } else {
                    const jsonStr = JSON.stringify(result, null, 2);
                    parts.push(jsonStr.length > 500 ? jsonStr.substring(0, 500) + "..." : jsonStr);
                }

                return parts.join("\n");
            })
            .join("\n\n---\n\n");

        const summaryText = [
            `**Collection:** ${collection}`,
            `**Results:** ${searchResponse.results.length}`,
            "",
            formattedResults || "No results found.",
        ].join("\n");

        return {
            content: [
                {
                    type: "text" as const,
                    text: summaryText,
                },
            ],
        };
    }
}

export function formatErrorResponse(error: Error, searchRequest: any, collection: string, baseUrl: string) {
    return {
        content: [
            {
                type: "text" as const,
                text: `**Error:** Failed to search collection.\n\n**Details:** ${error.message}\n\n**Debugging Info:**\n- Collection: ${collection}\n- Base URL: ${baseUrl}\n- Endpoint: /collections/${collection}/search\n- Parameters: ${JSON.stringify(searchRequest, null, 2)}`,
            },
        ],
    };
}
