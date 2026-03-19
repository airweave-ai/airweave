/**
 * Mock SSE events for developing the agentic search trace UI.
 *
 * Usage: In Search.tsx, import and call `injectMockEvents(setEvents)`
 * to simulate a full agentic search flow without running the backend.
 */
import type { SearchEvent, EntitySummary } from './types';

// Helper to create mock entity summaries
const e = (id: string, name: string, type: string, source: string, score?: number): EntitySummary => ({
    entity_id: id, name, entity_type: type, source_name: source, relevance_score: score ?? null,
});

export const MOCK_EVENTS: SearchEvent[] = [
    // ── Started ──
    {
        type: 'started',
        request_id: 'mock-req-001',
        tier: 'agentic',
        collection_readable_id: 'test-collection',
    },

    // ── Iteration 1: Thinking + Hybrid search ──
    {
        type: 'thinking',
        thinking: null,
        text: "I need to search for information about what Julius wants. Let me start with a broad hybrid search to find relevant entities across all sources. The collection has both Slack and Asana as sources, so I should search across both. Slack uses federated search which means it queries the Slack API directly, while Asana entities are indexed in Vespa. I'll use a hybrid retrieval strategy to combine semantic and keyword matching for the best coverage. Let me also generate some query variations to capture different phrasings of the user's intent — things like 'Julius requests', 'Julius needs', 'what Julius is looking for'. Since I don't know the specific context yet, I won't add any filters on the first search. Better to cast a wide net and narrow down based on what I find.",
        duration_ms: 1842,
        diagnostics: { iteration: 0, prompt_tokens: 7639, completion_tokens: 87 },
    },
    {
        type: 'tool_call',
        tool_name: 'search',
        duration_ms: 1247,
        diagnostics: {
            iteration: 0,
            tool_call_id: 'tc-001',
            arguments: {
                query: {
                    primary: 'Julius wants needs requirements',
                    variations: [
                        'what does Julius want',
                        'Julius requests preferences',
                        'Julius Schutten desires',
                        'things Julius is looking for',
                    ],
                },
                retrieval_strategy: 'hybrid',
                filter_groups: [],
                limit: 100,
                offset: 0,
            },
            stats: {
                result_count: 42, new_results: 42,
                first_results: [
                    e('1211673490428967__chunk_0', 'Story2.pdf', 'AsanaFileEntity', 'asana', 0.95),
                    e('1211565181540505__chunk_0', 'Fix problem', 'AsanaTaskEntity', 'asana', 0.91),
                    e('1209332198044183__chunk_0', 'Build it', 'AsanaTaskEntity', 'asana', 0.85),
                    e('slack-msg-001', 'Hey, can we talk about the Julius situation?', 'SlackMessageEntity', 'slack', 0.72),
                    e('slack-msg-002', 'Julius mentioned he wants a new shirt', 'SlackMessageEntity', 'slack', 0.68),
                ],
            },
        },
    },

    // ── Iteration 2: Thinking + Read + Collect ──
    {
        type: 'thinking',
        thinking: null,
        text: "Found 42 results from the initial search. I can see a mix of Slack messages and Asana entities. Several look promising — there's a PDF called Story2.pdf that mentions Julius and a Vitesse t-shirt, and an Asana task called 'Fix problem' with a note about Julius needing a vitesse shirt. Let me read the top results in detail to confirm they're relevant. I should also do a targeted search in Asana specifically for tasks assigned to or mentioning Julius, using a semantic strategy with source and entity type filters. The semantic strategy will work better here since I'm looking for conceptual matches rather than exact keyword hits.",
        duration_ms: 1156,
        diagnostics: { iteration: 1, prompt_tokens: 15446, completion_tokens: 111 },
    },
    {
        type: 'tool_call',
        tool_name: 'read',
        duration_ms: 89,
        diagnostics: {
            iteration: 1,
            tool_call_id: 'tc-002',
            arguments: { entity_ids: Array.from({ length: 50 }, (_, i) => `entity-${i + 1}`) },
            stats: {
                found: 47, not_found: 3,
                entities: [
                    e('entity-1', 'Story2.pdf', 'AsanaFileEntity', 'asana'),
                    e('entity-2', 'Fix problem', 'AsanaTaskEntity', 'asana'),
                    e('entity-3', 'Build it', 'AsanaTaskEntity', 'asana'),
                    e('entity-4', 'Ship it', 'AsanaTaskEntity', 'asana'),
                    e('entity-5', 'Draft integration', 'AsanaTaskEntity', 'asana'),
                ],
            },
        },
    },
    {
        type: 'tool_call',
        tool_name: 'add_to_results',
        duration_ms: 2,
        diagnostics: {
            iteration: 1,
            tool_call_id: 'tc-003',
            arguments: { entity_ids: ['entity-1', 'entity-2', 'entity-99'] },
            stats: {
                added: 2, already_collected: 0, not_found: 1, total_collected: 2,
                entities: [
                    e('entity-1', 'Story2.pdf', 'AsanaFileEntity', 'asana'),
                    e('entity-2', 'Fix problem', 'AsanaTaskEntity', 'asana'),
                ],
            },
        },
    },
    {
        type: 'tool_call',
        tool_name: 'search',
        duration_ms: 876,
        diagnostics: {
            iteration: 1,
            tool_call_id: 'tc-004',
            arguments: {
                query: {
                    primary: 'Julius Schutten tasks',
                    variations: ['Julius task assignments', 'Schutten work items'],
                },
                retrieval_strategy: 'semantic',
                filter_groups: [
                    {
                        conditions: [
                            { field: 'airweave_system_metadata.source_name', operator: 'equals', value: 'asana' },
                            { field: 'airweave_system_metadata.entity_type', operator: 'equals', value: 'AsanaTaskEntity' },
                        ],
                    },
                ],
                limit: 50,
                offset: 0,
            },
            stats: {
                result_count: 11, new_results: 8,
                first_results: [
                    e('asana-task-010', 'Review PR feedback', 'AsanaTaskEntity', 'asana', 0.88),
                    e('asana-task-011', 'Update documentation', 'AsanaTaskEntity', 'asana', 0.82),
                    e('asana-task-012', 'Deploy staging', 'AsanaTaskEntity', 'asana', 0.79),
                ],
            },
        },
    },

    // ── Iteration 3: Keyword search + navigate ──
    {
        type: 'thinking',
        thinking: null,
        text: "The Asana search returned 11 results, 8 of which are new. I can see tasks and file attachments related to Julius in the 'Build Integrations' project. Now I want to try a keyword search for 'Vitesse shirt' specifically — this is a proper noun so keyword/BM25 matching should work well for exact term hits. I also want to explore the project structure by getting children of the 'Build Integrations' project entity to see if there are related tasks I might have missed, and get siblings of the 'Fix problem' task to see what other tasks exist at the same level in the project hierarchy.",
        duration_ms: 987,
        diagnostics: { iteration: 2, prompt_tokens: 10952, completion_tokens: 118 },
    },
    {
        type: 'tool_call',
        tool_name: 'search',
        duration_ms: 654,
        diagnostics: {
            iteration: 2,
            tool_call_id: 'tc-005',
            arguments: {
                query: {
                    primary: 'Vitesse shirt',
                    variations: [],
                },
                retrieval_strategy: 'keyword',
                filter_groups: [],
                limit: 50,
                offset: 25,
            },
            stats: {
                result_count: 3, new_results: 1,
                first_results: [
                    e('1211673490428967__chunk_0', 'Story2.pdf', 'AsanaFileEntity', 'asana', 1.0),
                    e('1211565181540505__chunk_0', 'Fix problem', 'AsanaTaskEntity', 'asana', 0.95),
                ],
            },
        },
    },
    {
        type: 'tool_call',
        tool_name: 'get_children',
        duration_ms: 45,
        diagnostics: {
            iteration: 2,
            tool_call_id: 'tc-006',
            arguments: { entity_id: '1209332198044166' },
            stats: {
                result_count: 6, context_label: 'children of "Build Integrations" (asana)',
                first_results: [
                    e('1209332198044167', 'To do', 'AsanaSectionEntity', 'asana'),
                    e('1209332198044169', 'Doing', 'AsanaSectionEntity', 'asana'),
                    e('1209332198044170', 'Done', 'AsanaSectionEntity', 'asana'),
                    e('1211565181540505', 'Fix problem', 'AsanaTaskEntity', 'asana'),
                    e('1209332198044183', 'Build it', 'AsanaTaskEntity', 'asana'),
                ],
            },
        },
    },
    {
        type: 'tool_call',
        tool_name: 'get_siblings',
        duration_ms: 38,
        diagnostics: {
            iteration: 2,
            tool_call_id: 'tc-007',
            arguments: { entity_id: '1211565181540505' },
            stats: {
                result_count: 3, context_label: 'siblings of "To do" (asana)',
                first_results: [
                    e('1211565181540505', 'Fix problem', 'AsanaTaskEntity', 'asana'),
                    e('1209332198044183', 'Build it', 'AsanaTaskEntity', 'asana'),
                    e('1209332198044185', 'Ship it', 'AsanaTaskEntity', 'asana'),
                ],
            },
        },
    },

    // ── Iteration 4: Read + navigate + collect ──
    {
        type: 'thinking',
        thinking: null,
        text: "The keyword search for 'Vitesse shirt' returned 3 results with 1 new one — good, this confirms the exact term exists in the data. The children of 'Build Integrations' gave me 6 items including sections and tasks. The siblings of 'Fix problem' show 3 other tasks at the same level. Now I need to read these new results to verify their relevance before collecting them. I also want to get the parent of the Story2.pdf entity to understand its position in the hierarchy — it's attached to the 'Fix problem' task, so getting the parent will show me the full task context with all its metadata.",
        duration_ms: 823,
        diagnostics: { iteration: 3, prompt_tokens: 10839, completion_tokens: 32 },
    },
    {
        type: 'tool_call',
        tool_name: 'read',
        duration_ms: 112,
        diagnostics: {
            iteration: 3,
            tool_call_id: 'tc-008',
            arguments: { entity_ids: ['entity-7', 'entity-8', 'entity-9', 'entity-10'] },
            stats: {
                found: 4, not_found: 0,
                entities: [
                    e('entity-7', 'Review PR feedback', 'AsanaTaskEntity', 'asana'),
                    e('entity-8', 'Julian meeting notes', 'SlackMessageEntity', 'slack'),
                    e('entity-9', 'Update documentation', 'AsanaTaskEntity', 'asana'),
                    e('entity-10', 'Deploy staging', 'AsanaTaskEntity', 'asana'),
                ],
            },
        },
    },
    {
        type: 'tool_call',
        tool_name: 'get_parent',
        duration_ms: 31,
        diagnostics: {
            iteration: 3,
            tool_call_id: 'tc-009',
            arguments: { entity_id: '1211673490428967' },
            stats: { found: 1, not_found: 0, context_label: 'parent of "Story2.pdf" (asana)' },
        },
    },
    {
        type: 'tool_call',
        tool_name: 'add_to_results',
        duration_ms: 1,
        diagnostics: {
            iteration: 3,
            tool_call_id: 'tc-010',
            arguments: { entity_ids: ['entity-7', 'entity-8', 'entity-9', 'entity-2'] },
            stats: {
                added: 3, already_collected: 1, not_found: 0, total_collected: 5,
                entities: [
                    e('entity-7', 'Review PR feedback', 'AsanaTaskEntity', 'asana'),
                    e('entity-8', 'Julian meeting notes', 'SlackMessageEntity', 'slack'),
                    e('entity-9', 'Update documentation', 'AsanaTaskEntity', 'asana'),
                ],
            },
        },
    },

    // ── Iteration 5: Count + search with complex filters ──
    {
        type: 'thinking',
        thinking: null,
        text: "I've now collected 5 results that are directly relevant to what Julius wants. Before wrapping up, let me do one more search to make sure I haven't missed anything. I want to check how many Slack messages exist in total (the collection metadata says there are many), and do a time-filtered search to find any recent mentions of Julius. I'll use a complex filter with two groups: Slack messages from the last two weeks OR Asana items from the last three months. This way I can catch any recent activity that might be relevant without being too narrow.",
        duration_ms: 756,
        diagnostics: { iteration: 4, prompt_tokens: 9020, completion_tokens: 46 },
    },
    {
        type: 'tool_call',
        tool_name: 'count',
        duration_ms: 28,
        diagnostics: {
            iteration: 4,
            tool_call_id: 'tc-011',
            arguments: {
                filter_groups: [
                    {
                        conditions: [
                            { field: 'airweave_system_metadata.source_name', operator: 'equals', value: 'slack' },
                        ],
                    },
                ],
            },
            stats: { count: 1847 },
        },
    },
    {
        type: 'tool_call',
        tool_name: 'search',
        duration_ms: 1102,
        diagnostics: {
            iteration: 4,
            tool_call_id: 'tc-012',
            arguments: {
                query: {
                    primary: 'Julius recent updates',
                    variations: ['Julius latest activity', 'Schutten recent'],
                },
                retrieval_strategy: 'hybrid',
                filter_groups: [
                    {
                        conditions: [
                            { field: 'airweave_system_metadata.source_name', operator: 'equals', value: 'slack' },
                            { field: 'created_at', operator: 'greater_than', value: '2026-03-01T00:00:00Z' },
                        ],
                    },
                    {
                        conditions: [
                            { field: 'airweave_system_metadata.source_name', operator: 'equals', value: 'asana' },
                            { field: 'created_at', operator: 'greater_than', value: '2026-01-01T00:00:00Z' },
                        ],
                    },
                ],
                limit: 50,
                offset: 0,
            },
            stats: {
                result_count: 15, new_results: 7,
                first_results: [
                    e('slack-msg-010', 'Julius mentioned the deadline moved', 'SlackMessageEntity', 'slack', 0.76),
                    e('slack-msg-011', 'Re: vitesse jersey order', 'SlackMessageEntity', 'slack', 0.71),
                    e('asana-task-020', 'Q1 planning review', 'AsanaTaskEntity', 'asana', 0.65),
                ],
            },
        },
    },

    // ── Iteration 6: Remove + Review + Return ──
    {
        type: 'thinking',
        thinking: null,
        text: "The time-filtered search returned 15 results with 7 new ones. Looking through them, most are general project discussions not specifically about what Julius wants. One result (entity-8) is actually about a different person named Julian, not Julius — I should remove that from my collected results. Let me review everything I have, clean it up, and return the final result set to the user. I'm confident I've covered the search space well: I've used hybrid, semantic, and keyword strategies, explored the Asana project hierarchy, and checked recent Slack messages. The core answer is clear — Julius wants a Vitesse t-shirt.",
        duration_ms: 612,
        diagnostics: { iteration: 5, prompt_tokens: 8351, completion_tokens: 56 },
    },
    {
        type: 'tool_call',
        tool_name: 'remove_from_results',
        duration_ms: 1,
        diagnostics: {
            iteration: 5,
            tool_call_id: 'tc-013',
            arguments: { entity_ids: ['entity-8'] },
            stats: {
                added: 0, already_collected: 0, not_found: 0, total_collected: 4,
                entities: [
                    e('entity-8', 'Julian meeting notes', 'SlackMessageEntity', 'slack'),
                ],
            },
        },
    },
    {
        type: 'tool_call',
        tool_name: 'review_results',
        duration_ms: 3,
        diagnostics: {
            iteration: 5,
            tool_call_id: 'tc-014',
            arguments: {},
            stats: {
                total_collected: 4,
                entity_count: 4,
                first_results: [
                    e('entity-1', 'Story2.pdf', 'AsanaFileEntity', 'asana'),
                    e('entity-2', 'Fix problem', 'AsanaTaskEntity', 'asana'),
                    e('entity-7', 'Review PR feedback', 'AsanaTaskEntity', 'asana'),
                    e('entity-9', 'Update documentation', 'AsanaTaskEntity', 'asana'),
                ],
            },
        },
    },
    {
        type: 'tool_call',
        tool_name: 'return_results_to_user',
        duration_ms: 0,
        diagnostics: {
            iteration: 5,
            tool_call_id: 'tc-015',
            arguments: {},
            stats: { accepted: true, total_collected: 4 },
        },
    },

    // ── Reranking ──
    {
        type: 'reranking',
        duration_ms: 423,
        diagnostics: {
            input_count: 4,
            output_count: 4,
            model: 'cohere/rerank-v4.0-pro',
            top_relevance_score: 0.97,
            bottom_relevance_score: 0.42,
            first_results: [
                e('entity-1', 'Story2.pdf', 'AsanaFileEntity', 'asana', 0.97),
                e('entity-2', 'Fix problem', 'AsanaTaskEntity', 'asana', 0.91),
                e('entity-9', 'Update documentation', 'AsanaTaskEntity', 'asana', 0.68),
                e('entity-7', 'Review PR feedback', 'AsanaTaskEntity', 'asana', 0.42),
            ],
        },
    },

    // ── Done ──
    {
        type: 'done',
        results: [], // Empty for mock — real results come from the HTTP response
        duration_ms: 14231,
        diagnostics: {
            total_iterations: 6,
            all_seen_entity_ids: Array.from({ length: 52 }, (_, i) => `seen-${i}`),
            all_read_entity_ids: Array.from({ length: 10 }, (_, i) => `read-${i}`),
            all_collected_entity_ids: ['entity-1', 'entity-2', 'entity-7', 'entity-9'],
            max_iterations_hit: false,
            total_llm_retries: 0,
            stagnation_nudges_sent: 0,
            prompt_tokens: 18472,
            completion_tokens: 1847,
            cache_creation_input_tokens: 0,
            cache_read_input_tokens: 0,
        },
    },
];

// ── Error scenario: search fails mid-way ──
export const MOCK_EVENTS_ERROR: SearchEvent[] = [
    MOCK_EVENTS[0], // started
    MOCK_EVENTS[1], // thinking
    MOCK_EVENTS[2], // hybrid search
    MOCK_EVENTS[3], // thinking
    MOCK_EVENTS[4], // read
    {
        type: 'error',
        message: 'LLM provider exhausted: together/zai-glm-5 failed after 4 attempts: Rate limit exceeded (429). No fallback providers available.',
        duration_ms: 8420,
    },
];

// ── Cancelled scenario: user cancels during search ──
export const MOCK_EVENTS_CANCELLED: SearchEvent[] = [
    MOCK_EVENTS[0], // started
    MOCK_EVENTS[1], // thinking
    MOCK_EVENTS[2], // hybrid search
    MOCK_EVENTS[3], // thinking
    MOCK_EVENTS[4], // read
    MOCK_EVENTS[5], // collect
    MOCK_EVENTS[6], // semantic search
    { type: 'cancelled' } as any,
];

/**
 * Inject mock events into the trace with realistic timing.
 * Each event is delayed to simulate the streaming experience.
 *
 * @param setEvents - React state setter for the events array
 * @param speedMultiplier - 1.0 = realistic timing, 0.1 = 10x faster for quick iteration
 * @returns cleanup function to cancel pending timeouts
 */
export function injectMockEvents(
    setEvents: React.Dispatch<React.SetStateAction<any[]>>,
    speedMultiplier = 0.3,
): () => void {
    const timeouts: ReturnType<typeof setTimeout>[] = [];
    let cumulativeDelay = 0;

    for (const event of MOCK_EVENTS) {
        // Add delay based on event type
        const eventAny = event as any;
        if (event.type === 'thinking') {
            cumulativeDelay += (eventAny.duration_ms || 1000) * speedMultiplier;
        } else if (event.type === 'tool_call') {
            cumulativeDelay += (eventAny.duration_ms || 100) * speedMultiplier;
        } else if (event.type === 'reranking') {
            cumulativeDelay += (eventAny.duration_ms || 200) * speedMultiplier;
        } else if (event.type === 'started') {
            cumulativeDelay += 100 * speedMultiplier;
        } else if (event.type === 'done') {
            cumulativeDelay += 200 * speedMultiplier;
        } else {
            cumulativeDelay += 50 * speedMultiplier;
        }

        const delay = cumulativeDelay;
        const timeout = setTimeout(() => {
            setEvents(prev => [...prev, event]);
        }, delay);
        timeouts.push(timeout);
    }

    return () => timeouts.forEach(clearTimeout);
}
