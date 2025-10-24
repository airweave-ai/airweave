"""Real Microsoft Teams entities captured from actual sync for testing."""

from datetime import datetime, timezone

from airweave.platform.entities._base import Breadcrumb
from airweave.platform.entities.teams import (
    TeamsChannelEntity,
    TeamsChatEntity,
    TeamsMessageEntity,
    TeamsTeamEntity,
    TeamsUserEntity,
)

# ============================================================================
# USER ENTITIES
# ============================================================================

# Active user with full details
user_full_details = TeamsUserEntity(
    entity_id="5266eff1-b643-4fc3-9b7a-573f7f30f91f",
    breadcrumbs=[],
    name="Daan Manneke",
    created_at=None,
    updated_at=None,
    display_name="Daan Manneke",
    user_principal_name="daan@airweave.ai",
    mail="daan@airweave.ai",
    job_title="Software Engineer",
    department="Engineering",
    office_location="Amsterdam Office",
)

# User with minimal details
user_minimal = TeamsUserEntity(
    entity_id="b14fd6f2-1f0c-41f3-983f-7dae3d516a33",
    breadcrumbs=[],
    name="External User",
    created_at=None,
    updated_at=None,
    display_name="External User",
    user_principal_name="external@partner.com",
    mail="external@partner.com",
    job_title=None,
    department=None,
    office_location=None,
)

# ============================================================================
# TEAM ENTITIES
# ============================================================================

# Team with full details
team_full = TeamsTeamEntity(
    entity_id="58cb1814-203a-44d0-8578-b53f63860579",
    breadcrumbs=[],
    name="Neena",
    created_at=datetime(2024, 4, 23, 16, 9, 13, 275000, tzinfo=timezone.utc),
    updated_at=None,
    display_name="Neena",
    description="Neena",
    visibility="Public",
    is_archived=False,
    web_url=(
        "https://teams.microsoft.com/l/team/"
        "19%3AGZlL61vQA5J50cKCDM6UGnFE8SanBL9YDYfEBSw3PCE1%40thread.tacv2/"
        "conversations?groupId=58cb1814-203a-44d0-8578-b53f63860579"
        "&tenantId=26adf163-2699-4d04-a0ad-3d935411bf45"
    ),
    classification="High",
    specialization="None",
    internal_id="team_neena_internal_123",
)

# Private archived team
team_private_archived = TeamsTeamEntity(
    entity_id="a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    breadcrumbs=[],
    name="Legacy Project Alpha",
    created_at=datetime(2023, 1, 15, 10, 30, 0, tzinfo=timezone.utc),
    updated_at=None,
    display_name="Legacy Project Alpha",
    description="Historical project team - archived for reference",
    visibility="Private",
    is_archived=True,
    web_url=(
        "https://teams.microsoft.com/l/team/"
        "19%3Alegacy123%40thread.tacv2/"
        "conversations?groupId=a1b2c3d4-e5f6-7890-abcd-ef1234567890"
    ),
    classification="Medium",
    specialization="EducationClass",
    internal_id="team_alpha_legacy",
)

# ============================================================================
# CHANNEL ENTITIES
# ============================================================================

# Standard channel with email
channel_standard = TeamsChannelEntity(
    entity_id="19:GZlL61vQA5J50cKCDM6UGnFE8SanBL9YDYfEBSw3PCE1@thread.tacv2",
    breadcrumbs=[Breadcrumb(entity_id="58cb1814-203a-44d0-8578-b53f63860579")],
    name="General",
    created_at=datetime(2024, 4, 23, 16, 9, 13, 275000, tzinfo=timezone.utc),
    updated_at=None,
    team_id="58cb1814-203a-44d0-8578-b53f63860579",
    display_name="General",
    description="Neena",
    email="Neena@neenacorp.onmicrosoft.com",
    membership_type="standard",
    is_archived=False,
    is_favorite_by_default=True,
    web_url=(
        "https://teams.cloud.microsoft/l/channel/"
        "19%3AGZlL61vQA5J50cKCDM6UGnFE8SanBL9YDYfEBSw3PCE1%40thread.tacv2/Neena"
        "?groupId=58cb1814-203a-44d0-8578-b53f63860579"
        "&tenantId=26adf163-2699-4d04-a0ad-3d935411bf45"
        "&allowXTenantAccess=True&ngc=True"
    ),
)

# Private archived channel
channel_private_archived = TeamsChannelEntity(
    entity_id="19:PrivateChannel123@thread.tacv2",
    breadcrumbs=[Breadcrumb(entity_id="a1b2c3d4-e5f6-7890-abcd-ef1234567890")],
    name="Confidential Planning",
    created_at=datetime(2023, 2, 10, 14, 20, 0, tzinfo=timezone.utc),
    updated_at=None,
    team_id="a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    display_name="Confidential Planning",
    description="Private channel for sensitive project discussions",
    email=None,  # Private channels don't have email
    membership_type="private",
    is_archived=True,
    is_favorite_by_default=False,
    web_url=(
        "https://teams.cloud.microsoft/l/channel/"
        "19%3APrivateChannel123%40thread.tacv2/Confidential%20Planning"
    ),
)

# ============================================================================
# CHAT ENTITIES
# ============================================================================

# Group chat with topic
chat_group = TeamsChatEntity(
    entity_id="19:1f036d13748745acb58114a29ed3f469@thread.v2",
    breadcrumbs=[],
    name="Monke Test Chat 09bca8",
    created_at=datetime(2025, 10, 1, 18, 58, 24, 696000, tzinfo=timezone.utc),
    updated_at=datetime(2025, 10, 1, 18, 58, 24, 696000, tzinfo=timezone.utc),
    chat_type="group",
    topic="Monke Test Chat 09bca8",
    web_url=(
        "https://teams.microsoft.com/l/chat/"
        "19%3A1f036d13748745acb58114a29ed3f469%40thread.v2/0"
        "?tenantId=26adf163-2699-4d04-a0ad-3d935411bf45"
    ),
)

# One-on-one chat
chat_one_on_one = TeamsChatEntity(
    entity_id="19:0f1eedcd-98b6-4ebd-9232-02ee27391765_5266eff1-b643-4fc3-9b7a-573f7f30f91f@unq.gbl.spaces",
    breadcrumbs=[],
    name="oneOnOne chat",
    created_at=datetime(2025, 10, 1, 17, 5, 34, 101000, tzinfo=timezone.utc),
    updated_at=datetime(2025, 10, 1, 17, 5, 34, 101000, tzinfo=timezone.utc),
    chat_type="oneOnOne",
    topic=None,
    web_url=(
        "https://teams.microsoft.com/l/chat/"
        "19%3A0f1eedcd-98b6-4ebd-9232-02ee27391765_5266eff1-b643-4fc3-9b7a-573f7f30f91f%40unq.gbl.spaces/0"
        "?tenantId=26adf163-2699-4d04-a0ad-3d935411bf45"
    ),
)

# ============================================================================
# MESSAGE ENTITIES (Channel Messages)
# ============================================================================

# Channel message - system event
message_channel_system = TeamsMessageEntity(
    entity_id="1759345151412",
    breadcrumbs=[
        Breadcrumb(entity_id="58cb1814-203a-44d0-8578-b53f63860579"),
        Breadcrumb(entity_id="19:GZlL61vQA5J50cKCDM6UGnFE8SanBL9YDYfEBSw3PCE1@thread.tacv2"),
    ],
    name="<systemEventMessage/>",
    created_at=datetime(2025, 10, 1, 18, 59, 11, 412000, tzinfo=timezone.utc),
    updated_at=datetime(2025, 10, 1, 18, 59, 11, 412000, tzinfo=timezone.utc),
    team_id="58cb1814-203a-44d0-8578-b53f63860579",
    channel_id="19:GZlL61vQA5J50cKCDM6UGnFE8SanBL9YDYfEBSw3PCE1@thread.tacv2",
    chat_id=None,
    reply_to_id=None,
    message_type="unknownFutureValue",
    subject=None,
    body_content="<systemEventMessage/>",
    body_content_type="html",
    from_user=None,
    last_edited_datetime=None,
    deleted_datetime=None,
    importance="normal",
    mentions=[],
    attachments=[],
    reactions=[],
    web_url=(
        "https://teams.microsoft.com/l/message/"
        "19%3AGZlL61vQA5J50cKCDM6UGnFE8SanBL9YDYfEBSw3PCE1%40thread.tacv2/"
        "1759345151412"
        "?groupId=58cb1814-203a-44d0-8578-b53f63860579"
        "&tenantId=26adf163-2699-4d04-a0ad-3d935411bf45"
        "&createdTime=1759345151412"
        "&parentMessageId=1759345151412"
    ),
)

# ============================================================================
# MESSAGE ENTITIES (Chat Messages)
# ============================================================================

# Group chat message with detailed content and tracking token
message_chat_detailed = TeamsMessageEntity(
    entity_id="1759345111591",
    breadcrumbs=[Breadcrumb(entity_id="19:1f036d13748745acb58114a29ed3f469@thread.v2")],
    name="Hi team,\n\nI wanted to provide a quick update on th...",
    created_at=datetime(2025, 10, 1, 18, 58, 31, 591000, tzinfo=timezone.utc),
    updated_at=datetime(2025, 10, 1, 18, 58, 31, 591000, tzinfo=timezone.utc),
    team_id=None,
    channel_id=None,
    chat_id="19:1f036d13748745acb58114a29ed3f469@thread.v2",
    reply_to_id=None,
    message_type="message",
    subject=None,
    body_content=(
        "Hi team,\n\n"
        "I wanted to provide a quick update on the API integration work. "
        "As of today, the authentication module is fully implemented and tested. "
        "The next step is to start integrating the payment gateway, which is scheduled for next week.\n\n"
        "Also, a quick question: has anyone encountered issues with rate limiting when testing the API endpoints? "
        "If so, please share your experience so we can adjust our testing strategy accordingly.\n\n"
        "Please remember to include the verification token 505c2156 in your commit messages "
        "related to this feature for tracking purposes.\n\n"
        "Thanks,\n"
        "Alex"
    ),
    body_content_type="html",
    from_user={
        "application": None,
        "device": None,
        "user": {
            "@odata.type": "#microsoft.graph.teamworkUserIdentity",
            "id": "5266eff1-b643-4fc3-9b7a-573f7f30f91f",
            "displayName": "Daan Manneke",
            "userIdentityType": "aadUser",
            "tenantId": "26adf163-2699-4d04-a0ad-3d935411bf45",
        },
    },
    last_edited_datetime=None,
    deleted_datetime=None,
    importance="normal",
    mentions=[],
    attachments=[],
    reactions=[],
    web_url=None,
)

# Group chat message with sprint reminder
message_chat_sprint_reminder = TeamsMessageEntity(
    entity_id="1759344622991",
    breadcrumbs=[Breadcrumb(entity_id="19:dd12b51e6f274f8aa6e07649178cff90@thread.v2")],
    name="Hi Team,\n\nAs we approach the end of Sprint 12, ple...",
    created_at=datetime(2025, 10, 1, 18, 50, 22, 991000, tzinfo=timezone.utc),
    updated_at=datetime(2025, 10, 1, 18, 50, 22, 991000, tzinfo=timezone.utc),
    team_id=None,
    channel_id=None,
    chat_id="19:dd12b51e6f274f8aa6e07649178cff90@thread.v2",
    reply_to_id=None,
    message_type="message",
    subject=None,
    body_content=(
        "Hi Team,\n\n"
        "As we approach the end of Sprint 12, please ensure that all your feature branches "
        "are merged into develop by EOD Wednesday. Also, don't forget to complete your code reviews "
        "for at least two peers before Thursday's stand-up. \n\n"
        "If anyone encounters blockers, especially related to the new API integration, "
        "please flag them early so we can address them promptly. Additionally, I've noticed "
        "some tests failing intermittently in the payment module; if you have insights or fixes, please share.\n\n"
        "For tracking purposes, please reference the token eef5bcaa in your updates "
        "so we can easily correlate discussions with sprint tasks.\n\n"
        "Thanks for your hard work!\n\n"
        "Best,\n"
        "[Your Name]"
    ),
    body_content_type="html",
    from_user={
        "application": None,
        "device": None,
        "user": {
            "@odata.type": "#microsoft.graph.teamworkUserIdentity",
            "id": "5266eff1-b643-4fc3-9b7a-573f7f30f91f",
            "displayName": "Daan Manneke",
            "userIdentityType": "aadUser",
            "tenantId": "26adf163-2699-4d04-a0ad-3d935411bf45",
        },
    },
    last_edited_datetime=None,
    deleted_datetime=None,
    importance="normal",
    mentions=[],
    attachments=[],
    reactions=[],
    web_url=None,
)

# One-on-one chat message - casual
message_one_on_one_casual = TeamsMessageEntity(
    entity_id="1759338360172",
    breadcrumbs=[
        Breadcrumb(
            entity_id="19:0f1eedcd-98b6-4ebd-9232-02ee27391765_5266eff1-b643-4fc3-9b7a-573f7f30f91f@unq.gbl.spaces"
        )
    ],
    name="<p>wist je dat bartjan jorna een harry potter boek...",
    created_at=datetime(2025, 10, 1, 17, 6, 0, 172000, tzinfo=timezone.utc),
    updated_at=datetime(2025, 10, 1, 17, 6, 0, 172000, tzinfo=timezone.utc),
    team_id=None,
    channel_id=None,
    chat_id="19:0f1eedcd-98b6-4ebd-9232-02ee27391765_5266eff1-b643-4fc3-9b7a-573f7f30f91f@unq.gbl.spaces",
    reply_to_id=None,
    message_type="message",
    subject=None,
    body_content="<p>wist je dat bartjan jorna een harry potter boek wil&nbsp;</p>",
    body_content_type="html",
    from_user={
        "application": None,
        "device": None,
        "user": {
            "@odata.type": "#microsoft.graph.teamworkUserIdentity",
            "id": "5266eff1-b643-4fc3-9b7a-573f7f30f91f",
            "displayName": "Daan Manneke",
            "userIdentityType": "aadUser",
            "tenantId": "26adf163-2699-4d04-a0ad-3d935411bf45",
        },
    },
    last_edited_datetime=None,
    deleted_datetime=None,
    importance="normal",
    mentions=[],
    attachments=[],
    reactions=[],
    web_url=None,
)

# Message with mentions and attachments
message_with_mentions_attachments = TeamsMessageEntity(
    entity_id="1759999999999",
    breadcrumbs=[
        Breadcrumb(entity_id="58cb1814-203a-44d0-8578-b53f63860579"),
        Breadcrumb(entity_id="19:GZlL61vQA5J50cKCDM6UGnFE8SanBL9YDYfEBSw3PCE1@thread.tacv2"),
    ],
    name="@Daan - urgent design review needed",
    created_at=datetime(2025, 10, 15, 10, 30, 0, tzinfo=timezone.utc),
    updated_at=datetime(2025, 10, 15, 11, 45, 0, tzinfo=timezone.utc),
    team_id="58cb1814-203a-44d0-8578-b53f63860579",
    channel_id="19:GZlL61vQA5J50cKCDM6UGnFE8SanBL9YDYfEBSw3PCE1@thread.tacv2",
    chat_id=None,
    reply_to_id="1759888888888",
    message_type="message",
    subject="Urgent: Design Review",
    body_content=(
        '<p><at id="0">@Daan Manneke</at> Could you please review the attached design mockups '
        "for the new dashboard? We need your feedback by EOD today to stay on schedule.</p>"
        "<p>Key areas to focus on:</p>"
        "<ul><li>Color scheme and branding consistency</li>"
        "<li>Mobile responsiveness</li>"
        "<li>Accessibility compliance</li></ul>"
        "<p>Thanks!</p>"
    ),
    body_content_type="html",
    from_user={
        "application": None,
        "device": None,
        "user": {
            "@odata.type": "#microsoft.graph.teamworkUserIdentity",
            "id": "b14fd6f2-1f0c-41f3-983f-7dae3d516a33",
            "displayName": "Sarah Johnson",
            "userIdentityType": "aadUser",
            "tenantId": "26adf163-2699-4d04-a0ad-3d935411bf45",
        },
    },
    last_edited_datetime=datetime(2025, 10, 15, 11, 45, 0, tzinfo=timezone.utc),
    deleted_datetime=None,
    importance="urgent",
    mentions=[
        {
            "id": 0,
            "mentionText": "Daan Manneke",
            "mentioned": {
                "user": {
                    "id": "5266eff1-b643-4fc3-9b7a-573f7f30f91f",
                    "displayName": "Daan Manneke",
                    "userIdentityType": "aadUser",
                }
            },
        }
    ],
    attachments=[
        {
            "id": "att_12345",
            "contentType": "application/vnd.microsoft.teams.file.download.info",
            "contentUrl": "https://files.teams.microsoft.com/dashboard-mockup-v2.pdf",
            "name": "dashboard-mockup-v2.pdf",
            "thumbnailUrl": None,
        },
        {
            "id": "att_12346",
            "contentType": "application/vnd.microsoft.teams.file.download.info",
            "contentUrl": "https://files.teams.microsoft.com/mobile-wireframes.figma",
            "name": "mobile-wireframes.figma",
            "thumbnailUrl": None,
        },
    ],
    reactions=[
        {
            "reactionType": "like",
            "createdDateTime": "2025-10-15T10:35:00Z",
            "user": {
                "id": "5266eff1-b643-4fc3-9b7a-573f7f30f91f",
                "displayName": "Daan Manneke",
            },
        },
        {
            "reactionType": "heart",
            "createdDateTime": "2025-10-15T10:40:00Z",
            "user": {
                "id": "0f1eedcd-98b6-4ebd-9232-02ee27391765",
                "displayName": "John Doe",
            },
        },
    ],
    web_url=(
        "https://teams.microsoft.com/l/message/"
        "19%3AGZlL61vQA5J50cKCDM6UGnFE8SanBL9YDYfEBSw3PCE1%40thread.tacv2/"
        "1759999999999"
        "?groupId=58cb1814-203a-44d0-8578-b53f63860579"
        "&tenantId=26adf163-2699-4d04-a0ad-3d935411bf45"
        "&createdTime=1759999999999"
        "&parentMessageId=1759888888888"
    ),
)

# Short one-on-one message
message_one_on_one_short = TeamsMessageEntity(
    entity_id="1759338334659",
    breadcrumbs=[
        Breadcrumb(
            entity_id="19:0f1eedcd-98b6-4ebd-9232-02ee27391765_5266eff1-b643-4fc3-9b7a-573f7f30f91f@unq.gbl.spaces"
        )
    ],
    name="<p>waddup yo!</p>",
    created_at=datetime(2025, 10, 1, 17, 5, 34, 659000, tzinfo=timezone.utc),
    updated_at=datetime(2025, 10, 1, 17, 5, 34, 659000, tzinfo=timezone.utc),
    team_id=None,
    channel_id=None,
    chat_id="19:0f1eedcd-98b6-4ebd-9232-02ee27391765_5266eff1-b643-4fc3-9b7a-573f7f30f91f@unq.gbl.spaces",
    reply_to_id=None,
    message_type="message",
    subject=None,
    body_content="<p>waddup yo!</p>",
    body_content_type="html",
    from_user={
        "application": None,
        "device": None,
        "user": {
            "@odata.type": "#microsoft.graph.teamworkUserIdentity",
            "id": "5266eff1-b643-4fc3-9b7a-573f7f30f91f",
            "displayName": "Daan Manneke",
            "userIdentityType": "aadUser",
            "tenantId": "26adf163-2699-4d04-a0ad-3d935411bf45",
        },
    },
    last_edited_datetime=None,
    deleted_datetime=None,
    importance="normal",
    mentions=[],
    attachments=[],
    reactions=[],
    web_url=None,
)

# Edited and deleted message
message_edited_deleted = TeamsMessageEntity(
    entity_id="1759000000001",
    breadcrumbs=[
        Breadcrumb(entity_id="58cb1814-203a-44d0-8578-b53f63860579"),
        Breadcrumb(entity_id="19:GZlL61vQA5J50cKCDM6UGnFE8SanBL9YDYfEBSw3PCE1@thread.tacv2"),
    ],
    name="[Deleted] Meeting notes from yesterday",
    created_at=datetime(2025, 9, 28, 14, 20, 0, tzinfo=timezone.utc),
    updated_at=datetime(2025, 9, 28, 16, 30, 0, tzinfo=timezone.utc),
    team_id="58cb1814-203a-44d0-8578-b53f63860579",
    channel_id="19:GZlL61vQA5J50cKCDM6UGnFE8SanBL9YDYfEBSw3PCE1@thread.tacv2",
    chat_id=None,
    reply_to_id=None,
    message_type="message",
    subject="Meeting notes",
    body_content="<p>[Message deleted]</p>",
    body_content_type="html",
    from_user={
        "application": None,
        "device": None,
        "user": {
            "@odata.type": "#microsoft.graph.teamworkUserIdentity",
            "id": "b14fd6f2-1f0c-41f3-983f-7dae3d516a33",
            "displayName": "Sarah Johnson",
            "userIdentityType": "aadUser",
            "tenantId": "26adf163-2699-4d04-a0ad-3d935411bf45",
        },
    },
    last_edited_datetime=datetime(2025, 9, 28, 15, 10, 0, tzinfo=timezone.utc),
    deleted_datetime=datetime(2025, 9, 28, 16, 30, 0, tzinfo=timezone.utc),
    importance="high",
    mentions=[],
    attachments=[],
    reactions=[],
    web_url=(
        "https://teams.microsoft.com/l/message/"
        "19%3AGZlL61vQA5J50cKCDM6UGnFE8SanBL9YDYfEBSw3PCE1%40thread.tacv2/"
        "1759000000001"
    ),
)

# All entities in one list
teams_examples = [
    # Users
    user_full_details,
    user_minimal,
    # Teams
    team_full,
    team_private_archived,
    # Channels
    channel_standard,
    channel_private_archived,
    # Chats
    chat_group,
    chat_one_on_one,
    # Messages
    message_channel_system,
    message_chat_detailed,
    message_chat_sprint_reminder,
    message_one_on_one_short,
    message_edited_deleted,
]
