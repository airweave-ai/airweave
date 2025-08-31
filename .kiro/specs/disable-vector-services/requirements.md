# Requirements Document

## Introduction

This feature involves disabling vector-based services and changing default billing configuration in the Airweave platform. The changes include disabling vector RAG-based destinations, Redis-based sync monitoring system, Qdrant vector database integration, and updating the default billing plan to "Enterprise" level.

## Requirements

### Requirement 1

**User Story:** As a platform administrator, I want to disable vector RAG-based destinations, so that the system operates without vector search capabilities and reduces infrastructure complexity.

#### Acceptance Criteria

1. WHEN the system starts THEN vector RAG-based destinations SHALL be disabled by default
2. WHEN a user attempts to create a vector destination THEN the system SHALL prevent the creation
3. WHEN existing vector destinations exist THEN they SHALL be marked as inactive or removed
4. IF vector destination endpoints are called THEN the system SHALL return appropriate error responses

### Requirement 2

**User Story:** As a platform administrator, I want to disable Redis-based sync monitoring, so that sync operations don't rely on Redis for state management and monitoring.

#### Acceptance Criteria

1. WHEN sync operations are initiated THEN they SHALL NOT use Redis for monitoring
2. WHEN sync status is queried THEN the system SHALL use alternative storage mechanisms
3. IF Redis monitoring services are running THEN they SHALL be stopped or bypassed
4. WHEN sync jobs complete THEN status updates SHALL be stored in the primary database instead of Redis

### Requirement 3

**User Story:** As a platform administrator, I want to disable Qdrant integration, so that the system doesn't attempt to connect to or use Qdrant vector database services.

#### Acceptance Criteria

1. WHEN the application starts THEN Qdrant connections SHALL be disabled
2. WHEN vector operations are requested THEN the system SHALL return appropriate error messages
3. IF Qdrant configuration exists THEN it SHALL be ignored or overridden
4. WHEN embedding operations are attempted THEN they SHALL be blocked or redirected to alternative handlers

### Requirement 4

**User Story:** As a platform administrator, I want the default billing plan to be "Enterprise", so that new organizations automatically receive Enterprise-level features and billing.

#### Acceptance Criteria

1. WHEN a new organization is created THEN it SHALL be assigned the "Enterprise" billing plan by default
2. WHEN billing status is queried for new organizations THEN it SHALL show "Enterprise" plan
3. IF no billing plan is specified during organization creation THEN "Enterprise" SHALL be used
4. WHEN existing organizations are migrated THEN they SHALL optionally be upgraded to "Enterprise" plan