/**
 * Mock SSE events for demoing the agentic search trace UI.
 *
 * Scenario: "What did we agree on in the Acme Corp deal and what's still open?"
 *
 * Demonstrates multi-hop reasoning across 5 sources (Notion, Slack, Google Drive,
 * HubSpot, Asana), hierarchy navigation, self-correction, and diverse tool usage.
 *
 * Usage: In Search.tsx, import and call `injectMockEvents(setEvents)`
 * to simulate a full agentic search flow without running the backend.
 */
import type { SearchEvent, EntitySummary } from './types';

const e = (id: string, name: string, type: string, source: string, score?: number): EntitySummary => ({
    entity_id: id, name, entity_type: type, source_name: source, relevance_score: score ?? null,
});

export const MOCK_EVENTS: SearchEvent[] = [
    // ── Started ──
    {
        type: 'started',
        request_id: 'demo-acme-001',
        tier: 'agentic',
        collection_readable_id: 'company-knowledge',
    },

    // ═══════════════════════════════════════════════════════════════════
    // Iteration 0 — Broad hybrid search to discover the landscape
    // ═══════════════════════════════════════════════════════════════════
    {
        type: 'thinking',
        thinking: null,
        text: "The user wants to know about agreements and open items from the Acme Corp deal. This kind of information is typically scattered across CRM records, shared documents, meeting notes, and task trackers. I'll start with a broad hybrid search to locate all mentions of Acme Corp across connected sources, using query variations to capture different phrasings — 'Acme agreement', 'Acme contract terms', 'Acme action items'. Hybrid retrieval will give me both exact keyword matches and semantic similarity, which is important here since deal terms might be described in very different ways across sources.",
        duration_ms: 1680,
        diagnostics: { iteration: 0, prompt_tokens: 8234, completion_tokens: 96 },
    },
    {
        type: 'tool_call',
        tool_name: 'search',
        duration_ms: 1342,
        diagnostics: {
            iteration: 0,
            tool_call_id: 'tc-001',
            arguments: {
                query: {
                    primary: 'Acme Corp deal agreements open items',
                    variations: [
                        'Acme contract terms pricing',
                        'Acme Corp action items follow-up',
                        'Acme enterprise deal status',
                    ],
                },
                retrieval_strategy: 'hybrid',
                filter_groups: [],
                limit: 100,
                offset: 0,
            },
            stats: {
                result_count: 67, new_results: 67,
                first_results: [
                    e('notion-pg-8a3f2e', 'Acme Corp — Deal Brief', 'NotionPageEntity', 'notion', 0.96),
                    e('gdrive-f4b91c', 'Acme_Proposal_v3_Final.pdf', 'GoogleDriveFileEntity', 'google_drive', 0.93),
                    e('slack-ent-1710847200', '#enterprise-deals: Acme pricing locked in', 'SlackMessageEntity', 'slack', 0.89),
                    e('asana-1208774523', 'Send revised proposal to Acme', 'AsanaTaskEntity', 'asana', 0.85),
                    e('hs-deal-48291', 'Acme Corp — Enterprise (Pipeline)', 'HubSpotDealEntity', 'hubspot', 0.82),
                ],
            },
        },
    },

    // ═══════════════════════════════════════════════════════════════════
    // Iteration 1 — Read top results, collect key docs, search Notion
    // ═══════════════════════════════════════════════════════════════════
    {
        type: 'thinking',
        thinking: null,
        text: "67 results across 5 sources — good coverage. I can see a Notion page 'Acme Corp — Deal Brief' at 0.96 relevance which is likely the central deal document, a Google Drive PDF with the commercial terms, Slack messages in #enterprise-deals, an Asana task about sending a revised proposal, and a HubSpot deal record. Let me read the top results to understand the deal structure. I'll collect the deal brief and proposal immediately since they're clearly core documents, and search Notion specifically for meeting notes — that's where decisions and agreements are usually recorded.",
        duration_ms: 1245,
        diagnostics: { iteration: 1, prompt_tokens: 16891, completion_tokens: 124 },
    },
    {
        type: 'tool_call',
        tool_name: 'read',
        duration_ms: 156,
        diagnostics: {
            iteration: 1,
            tool_call_id: 'tc-002',
            arguments: { entity_ids: Array.from({ length: 20 }, (_, i) => `batch-1-${i}`) },
            stats: {
                found: 19, not_found: 1,
                entities: [
                    e('notion-pg-8a3f2e', 'Acme Corp — Deal Brief', 'NotionPageEntity', 'notion'),
                    e('gdrive-f4b91c', 'Acme_Proposal_v3_Final.pdf', 'GoogleDriveFileEntity', 'google_drive'),
                    e('slack-ent-1710847200', '#enterprise-deals: Acme pricing locked in', 'SlackMessageEntity', 'slack'),
                    e('asana-1208774523', 'Send revised proposal to Acme', 'AsanaTaskEntity', 'asana'),
                    e('hs-deal-48291', 'Acme Corp — Enterprise (Pipeline)', 'HubSpotDealEntity', 'hubspot'),
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
            arguments: { entity_ids: ['notion-pg-8a3f2e', 'gdrive-f4b91c'] },
            stats: {
                added: 2, already_collected: 0, not_found: 0, total_collected: 2,
                entities: [
                    e('notion-pg-8a3f2e', 'Acme Corp — Deal Brief', 'NotionPageEntity', 'notion'),
                    e('gdrive-f4b91c', 'Acme_Proposal_v3_Final.pdf', 'GoogleDriveFileEntity', 'google_drive'),
                ],
            },
        },
    },
    {
        type: 'tool_call',
        tool_name: 'search',
        duration_ms: 934,
        diagnostics: {
            iteration: 1,
            tool_call_id: 'tc-004',
            arguments: {
                query: {
                    primary: 'Acme Corp meeting notes agreements decisions',
                    variations: ['Acme alignment call recap', 'Acme meeting summary'],
                },
                retrieval_strategy: 'semantic',
                filter_groups: [
                    {
                        conditions: [
                            { field: 'airweave_system_metadata.source_name', operator: 'equals', value: 'notion' },
                        ],
                    },
                ],
                limit: 50,
                offset: 0,
            },
            stats: {
                result_count: 12, new_results: 9,
                first_results: [
                    e('notion-pg-c7e412', 'Acme — March 7 Alignment Call', 'NotionPageEntity', 'notion', 0.94),
                    e('notion-pg-d1f089', 'Acme — March 12 Legal Review Sync', 'NotionPageEntity', 'notion', 0.91),
                    e('notion-pg-a9b3c5', 'Acme — Stakeholder Map', 'NotionPageEntity', 'notion', 0.78),
                    e('notion-pg-e2d567', 'Enterprise Deals — Decisions Log', 'NotionPageEntity', 'notion', 0.72),
                ],
            },
        },
    },

    // ═══════════════════════════════════════════════════════════════════
    // Iteration 2 — Navigate the deal brief, keyword search for tasks
    // ═══════════════════════════════════════════════════════════════════
    {
        type: 'thinking',
        thinking: null,
        text: "The Notion semantic search found exactly what I need — meeting notes from March 7 ('Alignment Call') and March 12 ('Legal Review Sync'), plus a stakeholder map and a decisions log. The Deal Brief I already read confirms this is a 3-year enterprise contract negotiation with Acme Corp (450 employees, expanding to ~600). The proposal PDF shows $180k/year with a 15% volume discount above 500 seats. But the actual agreements were made in those meetings. Let me get the children of the Deal Brief to see the full document hierarchy — there might be sub-pages I'm missing. I'll also do a keyword search for action items in Asana, since those tend to use exact terms like 'TODO', 'action item', 'follow-up', 'blocked' that keyword/BM25 matching handles well.",
        duration_ms: 1456,
        diagnostics: { iteration: 2, prompt_tokens: 24567, completion_tokens: 142 },
    },
    {
        type: 'tool_call',
        tool_name: 'get_children',
        duration_ms: 42,
        diagnostics: {
            iteration: 2,
            tool_call_id: 'tc-005',
            arguments: { entity_id: 'notion-pg-8a3f2e' },
            stats: {
                result_count: 8,
                context_label: 'children of "Acme Corp — Deal Brief" (notion)',
                first_results: [
                    e('notion-pg-c7e412', 'Acme — March 7 Alignment Call', 'NotionPageEntity', 'notion'),
                    e('notion-pg-d1f089', 'Acme — March 12 Legal Review Sync', 'NotionPageEntity', 'notion'),
                    e('notion-pg-a9b3c5', 'Acme — Stakeholder Map', 'NotionPageEntity', 'notion'),
                    e('notion-pg-b4c891', 'Acme — Technical Requirements', 'NotionPageEntity', 'notion'),
                    e('notion-pg-f8a234', 'Acme — Security & Compliance Q&A', 'NotionPageEntity', 'notion'),
                ],
            },
        },
    },
    {
        type: 'tool_call',
        tool_name: 'search',
        duration_ms: 723,
        diagnostics: {
            iteration: 2,
            tool_call_id: 'tc-006',
            arguments: {
                query: {
                    primary: 'Acme action item TODO follow-up open blocked',
                    variations: [],
                },
                retrieval_strategy: 'keyword',
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
                result_count: 5, new_results: 4,
                first_results: [
                    e('asana-1208774523', 'Send revised proposal to Acme', 'AsanaTaskEntity', 'asana', 0.92),
                    e('asana-1209881456', 'Acme: Complete security questionnaire', 'AsanaTaskEntity', 'asana', 0.88),
                    e('asana-1209992034', 'Acme: Legal review — redline MSA', 'AsanaTaskEntity', 'asana', 0.85),
                    e('asana-1210103578', 'Schedule Acme exec alignment (CEO ↔ CTO)', 'AsanaTaskEntity', 'asana', 0.79),
                    e('asana-1210214901', 'Acme: Update pricing sheet with volume tiers', 'AsanaTaskEntity', 'asana', 0.74),
                ],
            },
        },
    },
    {
        type: 'tool_call',
        tool_name: 'read',
        duration_ms: 134,
        diagnostics: {
            iteration: 2,
            tool_call_id: 'tc-007',
            arguments: { entity_ids: [
                'notion-pg-c7e412', 'notion-pg-d1f089', 'notion-pg-e2d567',
                'asana-1208774523', 'asana-1209881456', 'asana-1209992034',
                'asana-1210103578', 'asana-1210214901',
            ] },
            stats: {
                found: 8, not_found: 0,
                entities: [
                    e('notion-pg-c7e412', 'Acme — March 7 Alignment Call', 'NotionPageEntity', 'notion'),
                    e('notion-pg-d1f089', 'Acme — March 12 Legal Review Sync', 'NotionPageEntity', 'notion'),
                    e('notion-pg-e2d567', 'Enterprise Deals — Decisions Log', 'NotionPageEntity', 'notion'),
                    e('asana-1208774523', 'Send revised proposal to Acme', 'AsanaTaskEntity', 'asana'),
                    e('asana-1209881456', 'Acme: Complete security questionnaire', 'AsanaTaskEntity', 'asana'),
                ],
            },
        },
    },

    // ═══════════════════════════════════════════════════════════════════
    // Iteration 3 — Cross-reference with Slack, explore Drive, collect
    // ═══════════════════════════════════════════════════════════════════
    {
        type: 'thinking',
        thinking: null,
        text: "Now I have the full picture from the structured sources. The March 7 alignment call notes confirm they agreed on: (1) 3-year term at $180k/yr, (2) 15% volume discount above 500 seats, (3) dedicated Customer Success Manager, (4) quarterly business reviews. The March 12 legal sync notes show Acme's counsel requested changes to the limitation of liability clause and data processing addendum. There are 5 Asana tasks — I need to cross-reference with Slack to figure out which are actually still open versus already completed. Let me search Slack for the latest Acme discussions filtered to the last two weeks, and get siblings of the proposal in Google Drive to see if there's a more recent version or related documents like the MSA draft.",
        duration_ms: 1823,
        diagnostics: { iteration: 3, prompt_tokens: 31245, completion_tokens: 167 },
    },
    {
        type: 'tool_call',
        tool_name: 'search',
        duration_ms: 1156,
        diagnostics: {
            iteration: 3,
            tool_call_id: 'tc-008',
            arguments: {
                query: {
                    primary: 'Acme Corp update status',
                    variations: ['Acme proposal sent', 'Acme security questionnaire', 'Acme legal review'],
                },
                retrieval_strategy: 'hybrid',
                filter_groups: [
                    {
                        conditions: [
                            { field: 'airweave_system_metadata.source_name', operator: 'equals', value: 'slack' },
                            { field: 'created_at', operator: 'greater_than', value: '2026-03-06T00:00:00Z' },
                        ],
                    },
                ],
                limit: 50,
                offset: 0,
            },
            stats: {
                result_count: 18, new_results: 14,
                first_results: [
                    e('slack-ent-1710934800', '#enterprise-deals: Revised proposal sent to Acme ✓', 'SlackMessageEntity', 'slack', 0.91),
                    e('slack-ent-1711020000', '#enterprise-deals: Acme legal came back with redlines on MSA §7', 'SlackMessageEntity', 'slack', 0.88),
                    e('slack-sec-1711106400', '#security: Acme security questionnaire — blocked on SOC 2 report', 'SlackMessageEntity', 'slack', 0.86),
                    e('slack-ent-1711192800', '#enterprise-deals: CEO call with Acme pushed to next week', 'SlackMessageEntity', 'slack', 0.81),
                    e('slack-gen-1711279200', '#general: Pricing sheet v2 is live in Drive', 'SlackMessageEntity', 'slack', 0.64),
                ],
            },
        },
    },
    {
        type: 'tool_call',
        tool_name: 'get_siblings',
        duration_ms: 38,
        diagnostics: {
            iteration: 3,
            tool_call_id: 'tc-009',
            arguments: { entity_id: 'gdrive-f4b91c' },
            stats: {
                result_count: 4,
                context_label: 'siblings of "Acme_Proposal_v3_Final.pdf" (google_drive)',
                first_results: [
                    e('gdrive-f4b91c', 'Acme_Proposal_v3_Final.pdf', 'GoogleDriveFileEntity', 'google_drive'),
                    e('gdrive-a2c748', 'Acme_MSA_Draft_v2.docx', 'GoogleDriveFileEntity', 'google_drive'),
                    e('gdrive-d9e312', 'Acme_Pricing_Sheet_v2.xlsx', 'GoogleDriveFileEntity', 'google_drive'),
                    e('gdrive-b7f456', 'Acme_Security_Questionnaire.pdf', 'GoogleDriveFileEntity', 'google_drive'),
                ],
            },
        },
    },
    {
        type: 'tool_call',
        tool_name: 'add_to_results',
        duration_ms: 3,
        diagnostics: {
            iteration: 3,
            tool_call_id: 'tc-010',
            arguments: { entity_ids: [
                'notion-pg-c7e412', 'notion-pg-d1f089', 'notion-pg-e2d567',
                'asana-1209881456', 'asana-1209992034', 'asana-1210103578',
                'slack-sec-1711106400', 'gdrive-a2c748', 'hs-deal-48291',
            ] },
            stats: {
                added: 9, already_collected: 0, not_found: 0, total_collected: 11,
                entities: [
                    e('notion-pg-c7e412', 'Acme — March 7 Alignment Call', 'NotionPageEntity', 'notion'),
                    e('notion-pg-d1f089', 'Acme — March 12 Legal Review Sync', 'NotionPageEntity', 'notion'),
                    e('notion-pg-e2d567', 'Enterprise Deals — Decisions Log', 'NotionPageEntity', 'notion'),
                    e('asana-1209881456', 'Acme: Complete security questionnaire', 'AsanaTaskEntity', 'asana'),
                    e('asana-1209992034', 'Acme: Legal review — redline MSA', 'AsanaTaskEntity', 'asana'),
                ],
            },
        },
    },

    // ═══════════════════════════════════════════════════════════════════
    // Iteration 4 — Self-correct, review, and return
    // ═══════════════════════════════════════════════════════════════════
    {
        type: 'thinking',
        thinking: null,
        text: "The Slack messages paint a clear timeline: the revised proposal was sent March 18 (done), the pricing sheet v2 is live in Drive (done), but three items remain open — the security questionnaire is blocked on an updated SOC 2 report from engineering, the MSA redlines on §7 liability are still in negotiation with Acme's counsel, and the CEO-to-CTO alignment call was pushed to next week. I have 11 items collected. Let me remove the HubSpot pipeline card — it's just a deal-stage tracker with no substantive agreement details, and the Notion decisions log already covers that context better. The remaining 10 items give a complete picture: core agreements in the meeting notes and proposal, open items in the Asana tasks, and current status in Slack.",
        duration_ms: 987,
        diagnostics: { iteration: 4, prompt_tokens: 39128, completion_tokens: 89 },
    },
    {
        type: 'tool_call',
        tool_name: 'remove_from_results',
        duration_ms: 1,
        diagnostics: {
            iteration: 4,
            tool_call_id: 'tc-011',
            arguments: { entity_ids: ['hs-deal-48291'] },
            stats: {
                added: 0, already_collected: 0, not_found: 0, total_collected: 10,
                entities: [
                    e('hs-deal-48291', 'Acme Corp — Enterprise (Pipeline)', 'HubSpotDealEntity', 'hubspot'),
                ],
            },
        },
    },
    {
        type: 'tool_call',
        tool_name: 'review_results',
        duration_ms: 3,
        diagnostics: {
            iteration: 4,
            tool_call_id: 'tc-012',
            arguments: {},
            stats: {
                total_collected: 10,
                entity_count: 10,
                first_results: [
                    e('notion-pg-8a3f2e', 'Acme Corp — Deal Brief', 'NotionPageEntity', 'notion'),
                    e('gdrive-f4b91c', 'Acme_Proposal_v3_Final.pdf', 'GoogleDriveFileEntity', 'google_drive'),
                    e('notion-pg-c7e412', 'Acme — March 7 Alignment Call', 'NotionPageEntity', 'notion'),
                    e('notion-pg-d1f089', 'Acme — March 12 Legal Review Sync', 'NotionPageEntity', 'notion'),
                    e('asana-1209881456', 'Acme: Complete security questionnaire', 'AsanaTaskEntity', 'asana'),
                ],
            },
        },
    },
    {
        type: 'tool_call',
        tool_name: 'return_results_to_user',
        duration_ms: 0,
        diagnostics: {
            iteration: 4,
            tool_call_id: 'tc-013',
            arguments: {},
            stats: { accepted: true, total_collected: 10 },
        },
    },

    // ── Reranking ──
    {
        type: 'reranking',
        duration_ms: 487,
        diagnostics: {
            input_count: 10,
            output_count: 10,
            model: 'cohere/rerank-v4.0-pro',
            top_relevance_score: 0.98,
            bottom_relevance_score: 0.52,
            first_results: [
                e('notion-pg-c7e412', 'Acme — March 7 Alignment Call', 'NotionPageEntity', 'notion', 0.98),
                e('gdrive-f4b91c', 'Acme_Proposal_v3_Final.pdf', 'GoogleDriveFileEntity', 'google_drive', 0.95),
                e('notion-pg-d1f089', 'Acme — March 12 Legal Review Sync', 'NotionPageEntity', 'notion', 0.93),
                e('asana-1209992034', 'Acme: Legal review — redline MSA', 'AsanaTaskEntity', 'asana', 0.89),
                e('asana-1209881456', 'Acme: Complete security questionnaire', 'AsanaTaskEntity', 'asana', 0.86),
                e('slack-sec-1711106400', '#security: SOC 2 blocking questionnaire', 'SlackMessageEntity', 'slack', 0.82),
                e('notion-pg-8a3f2e', 'Acme Corp — Deal Brief', 'NotionPageEntity', 'notion', 0.79),
                e('gdrive-a2c748', 'Acme_MSA_Draft_v2.docx', 'GoogleDriveFileEntity', 'google_drive', 0.74),
                e('notion-pg-e2d567', 'Enterprise Deals — Decisions Log', 'NotionPageEntity', 'notion', 0.68),
                e('asana-1210103578', 'Schedule Acme exec alignment (CEO ↔ CTO)', 'AsanaTaskEntity', 'asana', 0.52),
            ],
        },
    },

    // ── Done ──
    {
        type: 'done',
        results: [],
        duration_ms: 16842,
        diagnostics: {
            total_iterations: 5,
            all_seen_entity_ids: Array.from({ length: 67 }, (_, i) => `seen-${i}`),
            all_read_entity_ids: Array.from({ length: 28 }, (_, i) => `read-${i}`),
            all_collected_entity_ids: [
                'notion-pg-8a3f2e', 'gdrive-f4b91c', 'notion-pg-c7e412',
                'notion-pg-d1f089', 'notion-pg-e2d567', 'asana-1209881456',
                'asana-1209992034', 'asana-1210103578', 'slack-sec-1711106400',
                'gdrive-a2c748',
            ],
            max_iterations_hit: false,
            total_llm_retries: 0,
            stagnation_nudges_sent: 0,
            prompt_tokens: 39128,
            completion_tokens: 2847,
            cache_creation_input_tokens: 8234,
            cache_read_input_tokens: 15672,
        },
    },
];

// ── Error scenario: LLM provider fails mid-investigation ──
export const MOCK_EVENTS_ERROR: SearchEvent[] = [
    MOCK_EVENTS[0],  // started
    MOCK_EVENTS[1],  // thinking (iter 0)
    MOCK_EVENTS[2],  // hybrid search
    MOCK_EVENTS[3],  // thinking (iter 1)
    MOCK_EVENTS[4],  // read
    MOCK_EVENTS[5],  // collect
    MOCK_EVENTS[6],  // semantic search
    MOCK_EVENTS[7],  // thinking (iter 2)
    MOCK_EVENTS[8],  // get_children
    {
        type: 'error',
        message: 'LLM provider exhausted: cerebras/gpt-oss-120b failed after 4 attempts: Rate limit exceeded (429). Fallback groq/gpt-oss-120b also failed: Service unavailable (503). No providers remaining.',
        duration_ms: 11340,
    },
];

// ── Cancelled scenario: user cancels during cross-referencing ──
export const MOCK_EVENTS_CANCELLED: SearchEvent[] = [
    MOCK_EVENTS[0],  // started
    MOCK_EVENTS[1],  // thinking (iter 0)
    MOCK_EVENTS[2],  // hybrid search
    MOCK_EVENTS[3],  // thinking (iter 1)
    MOCK_EVENTS[4],  // read
    MOCK_EVENTS[5],  // collect
    MOCK_EVENTS[6],  // semantic search
    MOCK_EVENTS[7],  // thinking (iter 2)
    MOCK_EVENTS[8],  // get_children
    MOCK_EVENTS[9],  // keyword search
    MOCK_EVENTS[10], // read
    MOCK_EVENTS[11], // thinking (iter 3)
    MOCK_EVENTS[12], // Slack search
    MOCK_EVENTS[13], // get_siblings
    { type: 'cancelled' } as any,
];

/**
 * Inject mock events into the trace with realistic timing.
 * Each event is delayed proportionally to its duration_ms to simulate streaming.
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
