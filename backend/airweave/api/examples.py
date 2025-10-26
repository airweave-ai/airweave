# flake8: noqa: E501

"""Reusable API response examples for consistent documentation."""

# SourceConnectionJob examples for different states
SOURCE_CONNECTION_JOB_EXAMPLES = {
    "completed": {
        "source_connection_id": "550e8400-e29b-41d4-a716-446655440000",
        "id": "987fcdeb-51a2-43d7-8f3e-1234567890ab",
        "organization_id": "org12345-6789-abcd-ef01-234567890abc",
        "created_by_email": "engineering@company.com",
        "modified_by_email": "engineering@company.com",
        "created_at": "2024-01-15T14:00:00Z",
        "modified_at": "2024-01-15T14:05:22Z",
        "status": "completed",
        "entities_inserted": 45,
        "entities_updated": 12,
        "entities_deleted": 3,
        "entities_kept": 234,
        "entities_skipped": 8,
        "entities_encountered": {
            "issues": 67,
            "pull_requests": 23,
            "commits": 156,
            "releases": 12,
            "readme_files": 8,
        },
        "started_at": "2024-01-15T14:00:15Z",
        "completed_at": "2024-01-15T14:05:22Z",
        "failed_at": None,
        "error": None,
    },
    "pending": {
        "source_connection_id": "550e8400-e29b-41d4-a716-446655440000",
        "id": "987fcdeb-51a2-43d7-8f3e-1234567890ab",
        "organization_id": "org12345-6789-abcd-ef01-234567890abc",
        "created_by_email": "engineering@company.com",
        "modified_by_email": "engineering@company.com",
        "created_at": "2024-01-15T16:30:00Z",
        "modified_at": "2024-01-15T16:30:00Z",
        "status": "pending",
        "entities_inserted": 0,
        "entities_updated": 0,
        "entities_deleted": 0,
        "entities_kept": 0,
        "entities_skipped": 0,
        "entities_encountered": {},
        "started_at": None,
        "completed_at": None,
        "failed_at": None,
        "error": None,
    },
    "cancelled": {
        "source_connection_id": "550e8400-e29b-41d4-a716-446655440000",
        "id": "987fcdeb-51a2-43d7-8f3e-1234567890ab",
        "organization_id": "org12345-6789-abcd-ef01-234567890abc",
        "created_by_email": "engineering@company.com",
        "modified_by_email": "engineering@company.com",
        "created_at": "2024-01-15T14:00:00Z",
        "modified_at": "2024-01-15T14:02:30Z",
        "status": "cancelled",
        "entities_inserted": 12,
        "entities_updated": 3,
        "entities_deleted": 0,
        "entities_kept": 89,
        "entities_skipped": 2,
        "entities_encountered": {
            "issues": 23,
            "pull_requests": 8,
            "commits": 67,
        },
        "started_at": "2024-01-15T14:00:15Z",
        "completed_at": None,
        "failed_at": "2024-01-15T14:02:30Z",
        "error": "Job cancelled by user",
    },
    "failed": {
        "source_connection_id": "550e8400-e29b-41d4-a716-446655440000",
        "id": "abc12345-67ef-89ab-cdef-1234567890ab",
        "organization_id": "org12345-6789-abcd-ef01-234567890abc",
        "created_by_email": "engineering@company.com",
        "modified_by_email": "engineering@company.com",
        "created_at": "2024-01-14T08:00:00Z",
        "modified_at": "2024-01-14T08:02:30Z",
        "status": "failed",
        "entities_inserted": 0,
        "entities_updated": 0,
        "entities_deleted": 0,
        "entities_kept": 0,
        "entities_skipped": 0,
        "entities_encountered": {},
        "started_at": "2024-01-14T08:00:15Z",
        "completed_at": None,
        "failed_at": "2024-01-14T08:02:30Z",
        "error": "Authentication failed: GitHub personal access token is invalid or expired",
    },
}

# SourceConnectionListItem examples for different scenarios
SOURCE_CONNECTION_LIST_EXAMPLES = {
    "engineering_docs": {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "name": "GitHub - Engineering Documentation",
        "description": "Sync technical documentation and code from our engineering repos",
        "short_name": "github",
        "status": "active",
        "created_at": "2024-01-15T09:30:00Z",
        "modified_at": "2024-01-15T14:22:15Z",
        "sync_id": "123e4567-e89b-12d3-a456-426614174000",
        "collection": "engineering-docs-ab123",
    },
    "slack_workspace": {
        "id": "660f9511-f39c-52e5-b827-557766551111",
        "name": "Slack - Company Workspace",
        "description": "Sync messages and threads from company Slack channels",
        "short_name": "slack",
        "status": "active",
        "created_at": "2024-01-10T11:00:00Z",
        "modified_at": "2024-01-16T08:15:30Z",
        "sync_id": "234f5678-f90c-23e4-b567-537725285111",
        "collection": "slack-workspace-cd456",
    },
    "google_drive": {
        "id": "770g0622-g40d-63f6-c938-668877662222",
        "name": "Google Drive - Product Docs",
        "description": "Sync product documentation from shared Google Drive folders",
        "short_name": "google_drive",
        "status": "active",
        "created_at": "2024-01-12T13:45:00Z",
        "modified_at": "2024-01-17T10:30:45Z",
        "sync_id": "345g6789-g01d-34f5-c678-648836396222",
        "collection": "product-docs-ef789",
    },
}

# OAuth flow examples for source connections
SOURCE_CONNECTION_OAUTH_EXAMPLES = {
    "oauth_init_response": {
        "authentication_url": "https://api.airweave.ai/source-connections/authorize/a1b2c3d4",
        "authentication_url_expiry": "2024-01-15T14:30:00Z",
        "source_connection": {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "name": "Slack - Company Workspace",
            "short_name": "slack",
            "status": "pending_auth",
            "collection": "slack-workspace-cd456",
            "created_at": "2024-01-15T14:00:00Z",
        },
    },
    "oauth_callback_redirect": {
        "status_code": 302,
        "headers": {
            "Location": "https://app.airweave.ai/connections?status=sync_started&source_connection_id=550e8400-e29b-41d4-a716-446655440000&collection=slack-workspace-cd456&sync_job_id=987fcdeb-51a2-43d7-8f3e-1234567890ab"
        },
        "description": "Redirect to app with connection and sync status",
    },
    "oauth_authorize_redirect": {
        "status_code": 302,
        "headers": {
            "Location": "https://slack.com/oauth/v2/authorize?client_id=YOUR_CLIENT_ID&scope=channels:read,chat:write&redirect_uri=https://api.airweave.ai/source-connections/callback&state=SECURE_STATE_TOKEN"
        },
        "description": "Redirect to OAuth provider for user consent",
    },
}

# Source connection create examples
SOURCE_CONNECTION_CREATE_EXAMPLES = {
    "oauth_flow": {
        "name": "Slack - Company Workspace",
        "short_name": "slack",
        "collection": "slack-workspace-cd456",
        "config_fields": {
            "workspace_name": "company-workspace",
            "channels": ["general", "engineering", "product"],
            "include_private_channels": False,
        },
        "auth_mode": "oauth",
        "sync_immediately": True,
        "redirect_url": "https://app.airweave.ai/connections",
    },
    "api_key_flow": {
        "name": "GitHub - Engineering Repos",
        "short_name": "github",
        "collection": "engineering-docs-ab123",
        "config_fields": {
            "repo_name": "company/main-repo",
            "include_issues": True,
            "include_pull_requests": True,
        },
        "auth_fields": {
            "personal_access_token": "ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
        },
        "auth_mode": "manual",
        "sync_immediately": True,
    },
    "token_inject_flow": {
        "name": "Google Drive - Product Docs",
        "short_name": "google_drive",
        "collection": "product-docs-ef789",
        "config_fields": {
            "folder_ids": ["1A2B3C4D5E6F", "7G8H9I0J1K2L"],
            "include_shared_drives": True,
        },
        "auth_mode": "token_inject",
        "access_token": "ya29.a0AfH6SMBxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
        "refresh_token": "1//0gxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
        "sync_immediately": False,
    },
}

# Source examples for different source types
SOURCE_EXAMPLES = {
    "github": {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "name": "GitHub",
        "description": (
            "Connect to GitHub repositories for code, issues, pull requests, and documentation"
        ),
        "auth_type": "config_class",
        "auth_config_class": "GitHubAuthConfig",
        "config_class": "GitHubConfig",
        "short_name": "github",
        "class_name": "GitHubSource",
        "output_entity_definition_ids": [
            "def12345-6789-abcd-ef01-234567890abc",
            "def67890-abcd-ef01-2345-67890abcdef1",
        ],
        "organization_id": None,
        "labels": ["code"],
        "created_at": "2024-01-01T00:00:00Z",
        "modified_at": "2024-01-01T00:00:00Z",
        "auth_fields": {
            "fields": [
                {
                    "name": "personal_access_token",
                    "title": "Personal Access Token",
                    "description": "GitHub Personal Access Token with repository read permissions",
                    "type": "string",
                    "secret": True,
                },
                {
                    "name": "repo_name",
                    "title": "Repository Name",
                    "description": "Full repository name in format 'owner/repo'",
                    "type": "string",
                },
            ]
        },
    },
}

# Collection examples for different scenarios
COLLECTION_EXAMPLES = {
    "finance_data": {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "name": "Finance Data",
        "readable_id": "finance-data-ab123",
        "created_at": "2024-01-15T09:30:00Z",
        "modified_at": "2024-01-15T14:22:15Z",
        "organization_id": "org12345-6789-abcd-ef01-234567890abc",
        "created_by_email": "admin@company.com",
        "modified_by_email": "finance@company.com",
        "status": "ACTIVE",
    },
}

# Search response examples for different scenarios
SEARCH_RESPONSE_EXAMPLES = {
    "raw_results": {
        "results": [
            {
                "id": "f30bf505-cc33-4c74-920c-524eab49334c",
                "score": 0.92,
                "payload": {
                    "entity_id": "1207573546742333__chunk_0",
                    "name": "Implement user authentication",
                    "breadcrumbs": [],
                    "airweave_system_metadata": {
                        "source_name": "asana",
                        "entity_type": "AsanaTaskEntity",
                        "chunk_index": 0,
                        "original_entity_id": "1207573546742333",
                    },
                    "textual_representation": "# Metadata\n\n**Source**: asana\n**Type**: Task\n**Name**: Implement user authentication\n\n**Project**: Q4 Development Sprint\n**Assignee**: john.doe@company.com\n**Due Date**: 2024-01-20\n**Priority**: high\n**Tags**: authentication, security, backend\n\n# Content\n\nBuild secure login system with JWT tokens",
                    "created_at": "2024-01-10T09:15:00Z",
                    "updated_at": "2024-01-18T14:30:00Z",
                },
            },
            {
                "id": "fb6c49f7-2f9a-4000-ad50-96d1047a8f10",
                "score": 0.87,
                "payload": {
                    "entity_id": "1207921130902216__chunk_0",
                    "name": "Review and update API authentication documentation",
                    "breadcrumbs": [],
                    "airweave_system_metadata": {
                        "source_name": "asana",
                        "entity_type": "AsanaTaskEntity",
                        "chunk_index": 0,
                        "original_entity_id": "1207921130902216",
                    },
                    "textual_representation": "# Metadata\n\n**Source**: asana\n**Type**: Task\n**Name**: Review and update API authentication documentation\n\n**Project**: Documentation Updates\n**Assignee**: sarah.smith@company.com\n**Status**: in_progress\n\n# Content\n\nReview and update API authentication documentation",
                    "created_at": "2024-01-16T10:00:00Z",
                    "updated_at": "2024-01-18T14:30:00Z",
                },
            },
        ],
        "response_type": "raw",
        "status": "success",
    },
    "completion_response": {
        "results": [
            {
                "id": "stripe_cust_1234567890",
                "score": 0.94,
                "payload": {
                    "entity_id": "cust_1234567890__chunk_0",
                    "name": "Customer Payment Record",
                    "airweave_system_metadata": {
                        "source_name": "stripe",
                        "entity_type": "StripePaymentEntity",
                        "chunk_index": 0,
                        "original_entity_id": "cust_1234567890",
                    },
                    "textual_representation": "# Metadata\n\n**Source**: stripe\n**Type**: Payment\n**Name**: Customer Payment Record\n\n**Amount**: $99.00\n**Currency**: USD\n**Customer**: john@company.com\n\n# Content\n\nMonthly subscription payment of $99.00 processed successfully for customer John Doe (john@company.com). Payment method: Visa ending in 4242.",
                    "created_at": "2024-01-15T10:30:00Z",
                    "updated_at": "2024-01-15T10:30:00Z",
                },
            },
            {
                "id": "zendesk_ticket_789",
                "score": 0.89,
                "payload": {
                    "entity_id": "ticket_789__chunk_0",
                    "name": "Billing Question - Subscription Upgrade",
                    "airweave_system_metadata": {
                        "source_name": "zendesk",
                        "entity_type": "ZendeskTicketEntity",
                        "chunk_index": 0,
                        "original_entity_id": "ticket_789",
                    },
                    "textual_representation": "# Metadata\n\n**Source**: zendesk\n**Type**: Ticket\n**Name**: Billing Question - Subscription Upgrade\n\n**Status**: resolved\n**Priority**: medium\n**Agent**: support@company.com\n\n# Content\n\nCustomer inquiry about upgrading from Basic to Pro plan. Customer mentioned they need advanced analytics features.",
                    "created_at": "2024-01-14T14:22:00Z",
                    "updated_at": "2024-01-14T14:22:00Z",
                },
            },
        ],
        "completion": "Based on your recent data:\n\n## Payment Processing\nCustomer John Doe successfully processed a **$99 monthly subscription payment** on January 15th using a Visa card ending in 4242.\n\n## Customer Support Activity\nThere was a related support ticket from January 14th where a customer inquired about **upgrading from Basic to Pro plan** for advanced analytics features. This ticket has been resolved.\n\n### Summary\nThis shows strong customer engagement with your premium offerings, with successful payment processing and interest in higher-tier features.",
        "response_type": "completion",
        "status": "success",
    },
    "no_results": {"results": [], "response_type": "raw", "status": "no_results"},
    "filtered_search": {
        "results": [
            {
                "id": "6973c318-d065-4fb8-bdd6-2e18bc3ee86a",
                "score": 0.91,
                "payload": {
                    "entity_id": "1207756551982870__chunk_0",
                    "name": "Implement Learnability POC",
                    "breadcrumbs": [
                        {"entity_id": "1204858079189506"},
                        {"entity_id": "1207324698039595"},
                    ],
                    "airweave_system_metadata": {
                        "source_name": "asana",
                        "entity_type": "AsanaTaskEntity",
                        "chunk_index": 0,
                        "original_entity_id": "1207756551982870",
                    },
                    "textual_representation": "# Metadata\n\n**Source**: asana\n**Type**: Task\n**Name**: Implement Learnability POC\n\n**Project**: Neena Core Planning\n**Priority**: high\n**Sprint**: Q1-2024\n**Completed**: false\n\n# Content\n\nImplement Learnability POC",
                    "created_at": "2024-01-10T09:15:00Z",
                    "updated_at": "2024-01-18T10:20:00Z",
                },
            }
        ],
        "response_type": "raw",
        "status": "success",
    },
    "no_relevant_results": {
        "results": [],
        "response_type": "raw",
        "status": "no_relevant_results",
        "completion": None,
    },
}

# Search request examples for different scenarios
SEARCH_REQUEST_EXAMPLES = {
    "basic_search": {
        "query": "customer payment issues",
        "limit": 20,
        "offset": 0,
        "response_type": "raw",
    },
    "advanced_search_with_filters": {
        "query": "open support tickets from last week",
        "filter": {
            "must": [
                {"key": "source_name", "match": {"value": "Zendesk"}},
                {"key": "status", "match": {"value": "open"}},
                {
                    "key": "created_at",
                    "range": {"gte": "2024-01-08T00:00:00Z"},
                },
            ]
        },
        "limit": 50,
        "offset": 0,
        "score_threshold": 0.7,
        "response_type": "raw",
        "search_method": "hybrid",
        "recency_bias": 0.5,
        "expansion_strategy": "llm",
        "enable_reranking": True,
        "enable_query_interpretation": False,
    },
    "search_with_query_interpretation": {
        "query": "critical bugs from GitHub this month",
        "enable_query_interpretation": True,
        "expansion_strategy": "auto",
        "response_type": "raw",
    },
    "search_with_completion": {
        "query": "What are our customer refund policies?",
        "response_type": "completion",
        "enable_reranking": True,
        "limit": 10,
    },
    "search_no_expansion": {
        "query": "CVE-2024-1234",
        "expansion_strategy": "no_expansion",
        "search_method": "keyword",
        "enable_query_interpretation": False,
        "enable_reranking": False,
    },
}


# Helper functions to generate response examples
def create_single_job_response(status: str, summary: str):
    """Create a single job response example."""
    return {
        "200": {
            "description": "Successful Response",
            "content": {
                "application/json": {
                    "examples": {
                        f"{status}_job": {
                            "summary": summary,
                            "value": SOURCE_CONNECTION_JOB_EXAMPLES[status],
                        }
                    }
                }
            },
        }
    }


def create_job_list_response(job_statuses: list, summary: str):
    """Create a job list response example with multiple jobs."""
    return {
        "200": {
            "description": "Successful Response",
            "content": {
                "application/json": {
                    "examples": {
                        "sync_job_history": {
                            "summary": summary,
                            "value": [
                                SOURCE_CONNECTION_JOB_EXAMPLES[status] for status in job_statuses
                            ],
                        }
                    }
                }
            },
        }
    }


def create_source_connection_list_response(connection_types: list, summary: str):
    """Create a source connection list response example."""
    return {
        "200": {
            "description": "Successful Response",
            "content": {
                "application/json": {
                    "examples": {
                        "source_connections_list": {
                            "summary": summary,
                            "value": [
                                SOURCE_CONNECTION_LIST_EXAMPLES[conn_type]
                                for conn_type in connection_types
                            ],
                        }
                    }
                }
            },
        }
    }


def create_single_source_response(source_type: str, summary: str):
    """Create a single source response example."""
    return {
        "200": {
            "description": "Successful Response",
            "content": {
                "application/json": {
                    "examples": {
                        f"{source_type}_source": {
                            "summary": summary,
                            "value": SOURCE_EXAMPLES[source_type],
                        }
                    }
                }
            },
        }
    }


def create_source_list_response(source_types: list, summary: str):
    """Create a source list response example with multiple sources."""
    return {
        "200": {
            "description": "Successful Response",
            "content": {
                "application/json": {
                    "examples": {
                        "available_sources": {
                            "summary": summary,
                            "value": [SOURCE_EXAMPLES[source_type] for source_type in source_types],
                        }
                    }
                }
            },
        }
    }


def create_collection_list_response(collection_types: list, summary: str):
    """Create a collection list response example with multiple collections."""
    return {
        "200": {
            "description": "Successful Response",
            "content": {
                "application/json": {
                    "examples": {
                        "collections_list": {
                            "summary": summary,
                            "value": [
                                COLLECTION_EXAMPLES[collection_type]
                                for collection_type in collection_types
                            ],
                        }
                    }
                }
            },
        }
    }


def create_search_response(response_type: str, summary: str):
    """Create a search response example."""
    return {
        "200": {
            "description": "Successful Response",
            "content": {
                "application/json": {
                    "examples": {
                        f"{response_type}_search": {
                            "summary": summary,
                            "value": SEARCH_RESPONSE_EXAMPLES[response_type],
                        }
                    }
                }
            },
        }
    }


def create_source_connection_create_examples():
    """Create source connection creation request examples."""
    return {
        "oauth_flow": {
            "summary": "OAuth Flow - Slack Connection",
            "description": "Create a Slack connection using OAuth authentication",
            "value": SOURCE_CONNECTION_CREATE_EXAMPLES["oauth_flow"],
        },
        "api_key_flow": {
            "summary": "API Key Flow - GitHub Connection",
            "description": "Create a GitHub connection using personal access token",
            "value": SOURCE_CONNECTION_CREATE_EXAMPLES["api_key_flow"],
        },
        "token_inject_flow": {
            "summary": "Token Inject Flow - Google Drive",
            "description": "Create a Google Drive connection with pre-obtained tokens",
            "value": SOURCE_CONNECTION_CREATE_EXAMPLES["token_inject_flow"],
        },
    }


def create_oauth_response_examples():
    """Create OAuth flow response examples."""
    return {
        "oauth_init": {
            "summary": "OAuth Initialization Response",
            "description": "Response when initiating OAuth flow with authentication URL",
            "value": SOURCE_CONNECTION_OAUTH_EXAMPLES["oauth_init_response"],
        },
        "oauth_callback": {
            "summary": "OAuth Callback Redirect",
            "description": "Redirect response after successful OAuth callback",
            "value": SOURCE_CONNECTION_OAUTH_EXAMPLES["oauth_callback_redirect"],
        },
        "oauth_authorize": {
            "summary": "OAuth Provider Redirect",
            "description": "Redirect to OAuth provider for user consent",
            "value": SOURCE_CONNECTION_OAUTH_EXAMPLES["oauth_authorize_redirect"],
        },
    }
