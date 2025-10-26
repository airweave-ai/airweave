"""Real Gmail entities captured from actual sync for testing."""

from datetime import datetime, timezone

from airweave.platform.entities._base import Breadcrumb
from airweave.platform.entities.gmail import GmailMessageEntity, GmailThreadEntity

# Thread entity - O-1 visa discussion thread
thread_o1_discussion = GmailThreadEntity(
    entity_id="thread_198766f5352b2d73",
    breadcrumbs=[],
    name="Check-in moment for O1s",
    created_at=None,
    updated_at=datetime(2025, 8, 30, 13, 46, 35, tzinfo=timezone.utc),
    snippet="",
    history_id="182000",
    message_count=2,
    label_ids=["Label_2", "INBOX"],
)

# Message 1: Lennert's detailed response about O-1 inconsistencies (30KB HTML)
message_o1_lennert_response = GmailMessageEntity(
    entity_id="msg_198fb3b02e50246c",
    breadcrumbs=[Breadcrumb(entity_id="thread_198766f5352b2d73")],
    name="Re: Check-in moment for O1s",
    created_at=datetime(2025, 8, 30, 13, 46, 35, tzinfo=timezone.utc),
    updated_at=datetime(2025, 8, 30, 13, 46, 35, tzinfo=timezone.utc),
    # File fields (required for FileEntity)
    url="https://mail.google.com/mail/u/0/#inbox/198fb3b02e50246c",
    size=38384,  # Actual HTML body size (excluding attachments)
    file_type="html",
    mime_type="text/html",
    local_path=(
        "/Users/daanmanneke/Desktop/airweave/backend/airweave/platform/sync/test/entities/tmp/"
        "msg_198fb3b02e50246c.html"
    ),
    # Gmail API fields
    thread_id="198766f5352b2d73",
    subject="Re: Check-in moment for O1s",
    sender="Lennert Jansen <lennert@airweave.ai>",
    to=["Luke <luke@lighthousehq.com>"],
    cc=[
        "Daan Manneke <daan@airweave.ai>",
        "Rauf Akdemir <rauf@airweave.ai>",
        "ewan@airweave.ai",
        "Robby Villanueva <success@lighthousehq.com>",
    ],
    bcc=[],
    date=datetime(2025, 8, 30, 13, 46, 35, tzinfo=timezone.utc),
    snippet=(
        "Hi Luke & Robby, We're confused and frustrated with the inconsistency between "
        "Lighthouse's instructions for Daan and Ewan's O-1 applications and the way those "
        "same criteria are later"
    ),
    label_ids=["INBOX"],
    internal_date=datetime(2025, 8, 30, 13, 46, 35, tzinfo=timezone.utc),
)

# Message 2: Luke's response explaining O-1 criteria (42KB HTML)
message_o1_luke_response = GmailMessageEntity(
    entity_id="msg_198ebfc612b2ddce",
    breadcrumbs=[Breadcrumb(entity_id="thread_198766f5352b2d73")],
    name="Re: Check-in moment for O1s",
    created_at=datetime(2025, 8, 27, 14, 44, 0, tzinfo=timezone.utc),
    updated_at=datetime(2025, 8, 27, 14, 44, 0, tzinfo=timezone.utc),
    # File fields (required for FileEntity)
    url="https://mail.google.com/mail/u/0/#inbox/198ebfc612b2ddce",
    size=42286,  # Actual HTML body size
    file_type="html",
    mime_type="text/html",
    local_path=(
        "/Users/daanmanneke/Desktop/airweave/backend/airweave/platform/sync/test/entities/tmp/"
        "msg_198ebfc612b2ddce.html"
    ),
    # Gmail API fields
    thread_id="198766f5352b2d73",
    subject="Re: Check-in moment for O1s",
    sender="Luke from Lighthouse <luke@lighthousehq.com>",
    to=["Daan Manneke <daan@airweave.ai>"],
    cc=[
        "Lennert Jansen <lennert@airweave.ai>",
        "Rauf Akdemir <rauf@airweave.ai>",
        '"ewan@airweave.ai" <ewan@airweave.ai>',
    ],
    bcc=[],
    date=datetime(2025, 8, 27, 14, 44, 0, tzinfo=timezone.utc),
    snippet=(
        "Hi Daan, Very good question! Making an argument under Original Contributions of "
        "Major Significance requires that we show not only that you have invented something "
        'new ("original contributions'
    ),
    label_ids=["Label_2", "INBOX"],
    internal_date=datetime(2025, 8, 27, 14, 44, 0, tzinfo=timezone.utc),
)

# All entities in one list
gmail_examples = [
    thread_o1_discussion,
    message_o1_lennert_response,
    message_o1_luke_response,
]
