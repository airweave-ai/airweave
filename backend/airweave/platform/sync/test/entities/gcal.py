"""Real Google Calendar entities captured from actual sync for testing."""

from datetime import datetime, timezone

from airweave.platform.entities._base import Breadcrumb
from airweave.platform.entities.google_calendar import (
    GoogleCalendarCalendarEntity,
    GoogleCalendarEventEntity,
    GoogleCalendarListEntity,
)

# CalendarList entity - primary calendar (owner)
calendar_list_primary = GoogleCalendarListEntity(
    entity_id="daan@airweave.ai",
    breadcrumbs=[],
    name="Daan",
    created_at=None,
    updated_at=None,
    summary="Daan",
    summary_override=None,
    color_id="23",
    background_color="#cc73e1",
    foreground_color="#000000",
    hidden=False,
    selected=True,
    access_role="owner",
    primary=True,
    deleted=False,
)

# CalendarList entity - shared calendar (reader)
calendar_list_shared = GoogleCalendarListEntity(
    entity_id="rauf@airweave.ai",
    breadcrumbs=[],
    name="rauf@airweave.ai",
    created_at=None,
    updated_at=None,
    summary="rauf@airweave.ai",
    summary_override=None,
    color_id="18",
    background_color="#b99aff",
    foreground_color="#000000",
    hidden=False,
    selected=True,
    access_role="reader",
    primary=False,
    deleted=False,
)

# Calendar entity - underlying calendar resource
calendar = GoogleCalendarCalendarEntity(
    entity_id="daan@airweave.ai",
    breadcrumbs=[],
    name="Daan",
    created_at=None,
    updated_at=None,
    summary="Daan",
    description=None,
    location=None,
    time_zone="Europe/Amsterdam",
)

# Event 1: Event with HTML description and conference data
event_with_description = GoogleCalendarEventEntity(
    entity_id="2cpsokufn3jc7b2plk5nlttctd",
    breadcrumbs=[Breadcrumb(entity_id="daan@airweave.ai")],
    name="Onboarding - Engineering @ Airweave",
    created_at=datetime(2025, 4, 15, 4, 11, 51, tzinfo=timezone.utc),
    updated_at=datetime(2025, 4, 17, 8, 13, 50, 89000, tzinfo=timezone.utc),
    status="confirmed",
    html_link=(
        "https://www.google.com/calendar/event?"
        "eid=MmNwc29rdWZuM2pjN2IycGxrNW5sdHRjdGQgZGFhbkBhaXJ3ZWF2ZS5haQ"
    ),
    summary="Onboarding - Engineering @ Airweave",
    description=(
        "Kick-off sessie waarin we in vogelvlucht gaan door:<br><ul><li>platform + connectors<ul>"
        "<li>auth</li><li>embedding models</li><li>destinations</li><li>sources</li><li>chunks</li>"
        "<li>data permissions</li></ul></li><li>application layer<ul><li>api</li><li>crud</li>"
        "<li>schema vs model</li><li>frontend</li><li>search</li></ul></li><li>infra<ul>"
        "<li>local-debug</li><li>local-docker</li><li>open self-hosted</li>"
        "<li>azure-terraform (dev-stg-prd)</li><li>github actions</li></ul></li>"
        "<li>dev practices<ul><li>speed vs quality</li><li>cursorrules (demo)</li><li>tests</li>"
        "<li>docstrings good</li></ul></li></ul>"
    ),
    location=None,
    color_id=None,
    start_datetime="2025-04-17T16:00:00+02:00",
    start_date=None,
    end_datetime="2025-04-17T17:00:00+02:00",
    end_date=None,
    recurrence=None,
    recurring_event_id=None,
    organizer={"email": "rauf@airweave.ai"},
    creator={"email": "rauf@airweave.ai"},
    attendees=[
        {"email": "rauf@airweave.ai", "organizer": True, "responseStatus": "accepted"},
        {"email": "lennert@airweave.ai", "responseStatus": "accepted"},
        {"email": "daan@airweave.ai", "self": True, "responseStatus": "accepted"},
    ],
    transparency=None,
    visibility=None,
    conference_data={
        "entryPoints": [
            {
                "entryPointType": "video",
                "uri": "https://meet.google.com/ndt-jzap-mfn",
                "label": "meet.google.com/ndt-jzap-mfn",
            },
            {
                "entryPointType": "more",
                "uri": "https://tel.meet/ndt-jzap-mfn?pin=2006112489558",
                "pin": "2006112489558",
            },
            {
                "regionCode": "NL",
                "entryPointType": "phone",
                "uri": "tel:+31-20-257-2456",
                "label": "+31 20 257 2456",
                "pin": "621599640",
            },
        ],
        "conferenceSolution": {
            "key": {"type": "hangoutsMeet"},
            "name": "Google Meet",
            "iconUri": (
                "https://fonts.gstatic.com/s/i/productlogos/meet_2020q4/v6/web-512dp/"
                "logo_meet_2020q4_color_2x_web_512dp.png"
            ),
        },
        "conferenceId": "ndt-jzap-mfn",
    },
    event_type="default",
)

# Event 2: Event with location
event_with_location = GoogleCalendarEventEntity(
    entity_id="_84r46h1j7523cba36t2jib9k6opk8b9p7124ab9h88rkad1h6l0kch9n8k",
    breadcrumbs=[Breadcrumb(entity_id="daan@airweave.ai")],
    name="KvK",
    created_at=datetime(2025, 5, 3, 7, 28, 37, tzinfo=timezone.utc),
    updated_at=datetime(2025, 5, 3, 7, 47, 31, 547000, tzinfo=timezone.utc),
    status="confirmed",
    html_link=(
        "https://www.google.com/calendar/event?"
        "eid=Xzg0cjQ2aDFqNzUyM2NiYTM2dDJqaWI5azZvcGs4YjlwNzEyNGFiOWg4OHJrYWQxaDZsMGtjaDluOGsgZGFhbkBhaXJ3ZWF2ZS5haQ"
    ),
    summary="KvK",
    description=None,
    location="De Ruijterkade 5\nAmsterdam, Netherlands",
    color_id=None,
    start_datetime="2025-05-07T15:30:00+02:00",
    start_date=None,
    end_datetime="2025-05-07T16:00:00+02:00",
    end_date=None,
    recurrence=None,
    recurring_event_id=None,
    organizer={"email": "daan@airweave.ai", "self": True},
    creator={"email": "daan@airweave.ai", "self": True},
    attendees=None,
    transparency=None,
    visibility=None,
    conference_data=None,
    event_type="default",
)

# Event 3: All-day event (no datetime, uses date)
event_all_day = GoogleCalendarEventEntity(
    entity_id="_74qkaci18gsj8ba38oo3ib9k6cp32ba1690j8b9n8l0j6h1n8l338d2188",
    breadcrumbs=[Breadcrumb(entity_id="daan@airweave.ai")],
    name="New Event",
    created_at=datetime(2025, 5, 12, 12, 12, 24, tzinfo=timezone.utc),
    updated_at=datetime(2025, 5, 12, 12, 12, 25, 167000, tzinfo=timezone.utc),
    status="confirmed",
    html_link=(
        "https://www.google.com/calendar/event?"
        "eid=Xzc0cWthY2kxOGdzajhiYTM4b28zaWI5azZjcDMyYmExNjkwajhiOW44bDBqNmgxbjhsMzM4ZDIxODggZGFhbkBhaXJ3ZWF2ZS5haQ"
    ),
    summary="New Event",
    description=None,
    location=None,
    color_id=None,
    start_datetime=None,
    start_date="2025-06-13",
    end_datetime=None,
    end_date="2025-06-14",
    recurrence=None,
    recurring_event_id=None,
    organizer={"email": "daan@airweave.ai", "self": True},
    creator={"email": "daan@airweave.ai", "self": True},
    attendees=None,
    transparency="transparent",
    visibility=None,
    conference_data=None,
    event_type="default",
)

# Event 4: Multi-day all-day event with location and description
event_multi_day = GoogleCalendarEventEntity(
    entity_id="_8cq44ca26gskcb9m6t238b9k6oq3iba184r32ba28go36ca36oqk8gpk60",
    breadcrumbs=[Breadcrumb(entity_id="daan@airweave.ai")],
    name="Stay: Quercus Villa, Achilleion Palace, Corfu",
    created_at=datetime(2025, 5, 12, 18, 23, 15, tzinfo=timezone.utc),
    updated_at=datetime(2025, 5, 13, 17, 40, 23, 881000, tzinfo=timezone.utc),
    status="confirmed",
    html_link=(
        "https://www.google.com/calendar/event?"
        "eid=XzhjcTQ0Y2EyNmdza2NiOW02dDIzOGI5azZvcTNpYmExODRyMzJiYTI4Z28zNmNhMzZvcWs4Z3BrNjAgZGFhbkBhaXJ3ZWF2ZS5haQ"
    ),
    summary="Stay: Quercus Villa, Achilleion Palace, Corfu",
    description="Confirmation Code: 4782665800\n\nCheck-in: 15:00\nCheckout: 00:00",
    location="Quercus Villa, Achilleion Palace, Corfu",
    color_id=None,
    start_datetime=None,
    start_date="2025-06-11",
    end_datetime=None,
    end_date="2025-06-15",
    recurrence=None,
    recurring_event_id=None,
    organizer={"email": "daan@airweave.ai", "self": True},
    creator={"email": "daan@airweave.ai", "self": True},
    attendees=None,
    transparency="transparent",
    visibility=None,
    conference_data=None,
    event_type="default",
)

# Event 5: Recurring event (base event with RRULE)
event_recurring_base = GoogleCalendarEventEntity(
    entity_id="3mbionqln5kieva4m7o6cbc05n",
    breadcrumbs=[Breadcrumb(entity_id="daan@airweave.ai")],
    name="Daily stand-up",
    created_at=datetime(2025, 4, 14, 17, 53, 29, tzinfo=timezone.utc),
    updated_at=datetime(2025, 6, 19, 10, 4, 31, 460000, tzinfo=timezone.utc),
    status="confirmed",
    html_link=(
        "https://www.google.com/calendar/event?"
        "eid=M21iaW9ucWxuNWtpZXZhNG03bzZjYmMwNW5fMjAyNTA0MTZUMTUxNTAwWiBkYWFuQGFpcndlYXZlLmFp"
    ),
    summary="Daily stand-up",
    description=None,
    location=None,
    color_id=None,
    start_datetime="2025-04-16T17:15:00+02:00",
    start_date=None,
    end_datetime="2025-04-16T17:30:00+02:00",
    end_date=None,
    recurrence=["RRULE:FREQ=WEEKLY;WKST=MO;UNTIL=20250619T065959Z;BYDAY=FR,TH,TU,WE"],
    recurring_event_id=None,
    organizer={"email": "rauf@airweave.ai"},
    creator={"email": "rauf@airweave.ai"},
    attendees=[
        {"email": "rauf@airweave.ai", "organizer": True, "responseStatus": "accepted"},
        {"email": "lennert@airweave.ai", "responseStatus": "accepted"},
        {"email": "daan@airweave.ai", "self": True, "responseStatus": "accepted"},
    ],
    transparency=None,
    visibility=None,
    conference_data={
        "entryPoints": [
            {
                "entryPointType": "video",
                "uri": "https://meet.google.com/fqe-zdrw-tba",
                "label": "meet.google.com/fqe-zdrw-tba",
            },
            {
                "entryPointType": "more",
                "uri": "https://tel.meet/fqe-zdrw-tba?pin=1480234045776",
                "pin": "1480234045776",
            },
            {
                "regionCode": "NL",
                "entryPointType": "phone",
                "uri": "tel:+31-20-257-2944",
                "label": "+31 20 257 2944",
                "pin": "993589779",
            },
        ],
        "conferenceSolution": {
            "key": {"type": "hangoutsMeet"},
            "name": "Google Meet",
            "iconUri": (
                "https://fonts.gstatic.com/s/i/productlogos/meet_2020q4/v6/web-512dp/"
                "logo_meet_2020q4_color_2x_web_512dp.png"
            ),
        },
        "conferenceId": "fqe-zdrw-tba",
    },
    event_type="default",
)

# Event 6: Recurring event instance (specific occurrence)
event_recurring_instance = GoogleCalendarEventEntity(
    entity_id="3mbionqln5kieva4m7o6cbc05n_20250603T151500Z",
    breadcrumbs=[Breadcrumb(entity_id="daan@airweave.ai")],
    name="Daily stand-up",
    created_at=datetime(2025, 4, 14, 17, 53, 29, tzinfo=timezone.utc),
    updated_at=datetime(2025, 6, 19, 10, 4, 31, 460000, tzinfo=timezone.utc),
    status="confirmed",
    html_link=(
        "https://www.google.com/calendar/event?"
        "eid=M21iaW9ucWxuNWtpZXZhNG03bzZjYmMwNW5fMjAyNTA2MDNUMTUxNTAwWiBkYWFuQGFpcndlYXZlLmFp"
    ),
    summary="Daily stand-up",
    description=None,
    location=None,
    color_id=None,
    start_datetime="2025-06-03T17:15:00+02:00",
    start_date=None,
    end_datetime="2025-06-03T17:30:00+02:00",
    end_date=None,
    recurrence=None,
    recurring_event_id="3mbionqln5kieva4m7o6cbc05n",
    organizer={"email": "rauf@airweave.ai"},
    creator={"email": "rauf@airweave.ai"},
    attendees=[
        {"email": "rauf@airweave.ai", "organizer": True, "responseStatus": "accepted"},
        {"email": "lennert@airweave.ai", "responseStatus": "declined"},
        {"email": "daan@airweave.ai", "self": True, "responseStatus": "accepted"},
    ],
    transparency=None,
    visibility=None,
    conference_data={
        "entryPoints": [
            {
                "entryPointType": "video",
                "uri": "https://meet.google.com/fqe-zdrw-tba",
                "label": "meet.google.com/fqe-zdrw-tba",
            },
            {
                "entryPointType": "more",
                "uri": "https://tel.meet/fqe-zdrw-tba?pin=1480234045776",
                "pin": "1480234045776",
            },
            {
                "regionCode": "NL",
                "entryPointType": "phone",
                "uri": "tel:+31-20-257-2944",
                "label": "+31 20 257 2944",
                "pin": "993589779",
            },
        ],
        "conferenceSolution": {
            "key": {"type": "hangoutsMeet"},
            "name": "Google Meet",
            "iconUri": (
                "https://fonts.gstatic.com/s/i/productlogos/meet_2020q4/v6/web-512dp/"
                "logo_meet_2020q4_color_2x_web_512dp.png"
            ),
        },
        "conferenceId": "fqe-zdrw-tba",
    },
    event_type="default",
)

# Event 7: Event with emoji and multiple attendees
event_with_emoji = GoogleCalendarEventEntity(
    entity_id="39t1u5mtv4unpo23aqalu3k9gg",
    breadcrumbs=[Breadcrumb(entity_id="daan@airweave.ai")],
    name="ORDER SWAG💦🫦😳",
    created_at=datetime(2025, 6, 1, 1, 17, 4, tzinfo=timezone.utc),
    updated_at=datetime(2025, 6, 19, 3, 16, 34, 788000, tzinfo=timezone.utc),
    status="confirmed",
    html_link=(
        "https://www.google.com/calendar/event?"
        "eid=Mzl0MXU1bXR2NHVucG8yM2FxYWx1M2s5Z2cgZGFhbkBhaXJ3ZWF2ZS5haQ"
    ),
    summary="ORDER SWAG💦🫦😳",
    description=None,
    location=None,
    color_id=None,
    start_datetime="2025-06-01T05:15:00+02:00",
    start_date=None,
    end_datetime="2025-06-01T06:15:00+02:00",
    end_date=None,
    recurrence=None,
    recurring_event_id=None,
    organizer={"email": "lennert@airweave.ai"},
    creator={"email": "lennert@airweave.ai"},
    attendees=[
        {"email": "rauf@airweave.ai", "responseStatus": "accepted"},
        {"email": "lennert@airweave.ai", "organizer": True, "responseStatus": "accepted"},
        {"email": "daan@airweave.ai", "self": True, "responseStatus": "needsAction"},
    ],
    transparency=None,
    visibility=None,
    conference_data={
        "entryPoints": [
            {
                "entryPointType": "video",
                "uri": "https://meet.google.com/nek-fhqx-icw",
                "label": "meet.google.com/nek-fhqx-icw",
            },
            {
                "entryPointType": "more",
                "uri": "https://tel.meet/nek-fhqx-icw?pin=4698026501638",
                "pin": "4698026501638",
            },
            {
                "regionCode": "NL",
                "entryPointType": "phone",
                "uri": "tel:+31-20-257-3350",
                "label": "+31 20 257 3350",
                "pin": "982509900",
            },
        ],
        "conferenceSolution": {
            "key": {"type": "hangoutsMeet"},
            "name": "Google Meet",
            "iconUri": (
                "https://fonts.gstatic.com/s/i/productlogos/meet_2020q4/v6/web-512dp/"
                "logo_meet_2020q4_color_2x_web_512dp.png"
            ),
        },
        "conferenceId": "nek-fhqx-icw",
    },
    event_type="default",
)

# Event 8: Design sprint with description
event_design_sprint = GoogleCalendarEventEntity(
    entity_id="3mjhek052bmgeno7f3onk75ghr",
    breadcrumbs=[Breadcrumb(entity_id="daan@airweave.ai")],
    name="Endpoint-centric Airweave  - Design sprint",
    created_at=datetime(2025, 4, 29, 19, 11, 55, tzinfo=timezone.utc),
    updated_at=datetime(2025, 4, 30, 15, 21, 1, 811000, tzinfo=timezone.utc),
    status="confirmed",
    html_link=(
        "https://www.google.com/calendar/event?"
        "eid=M21qaGVrMDUyYm1nZW5vN2Yzb25rNzVnaHIgZGFhbkBhaXJ3ZWF2ZS5haQ"
    ),
    summary="Endpoint-centric Airweave  - Design sprint",
    description=(
        "Design sprint om hoog over uit te werken:\n- API flows\n- UI flows\n- Wireframes\n\n"
        "Alvast over nadenken:\n- Hoe noemen we dingen\n- Hoe moet het er uit zien\n"
        "- Wat is configureerbaar? Wat is niet configureerbaar? Waar is wat configureerbaar?"
    ),
    location=None,
    color_id=None,
    start_datetime="2025-04-30T17:30:00+02:00",
    start_date=None,
    end_datetime="2025-04-30T19:30:00+02:00",
    end_date=None,
    recurrence=None,
    recurring_event_id=None,
    organizer={"email": "rauf@airweave.ai"},
    creator={"email": "rauf@airweave.ai"},
    attendees=[
        {"email": "daan@airweave.ai", "self": True, "responseStatus": "needsAction"},
        {"email": "lennert@airweave.ai", "responseStatus": "accepted"},
        {"email": "rauf@airweave.ai", "organizer": True, "responseStatus": "accepted"},
    ],
    transparency=None,
    visibility=None,
    conference_data={
        "entryPoints": [
            {
                "entryPointType": "video",
                "uri": "https://meet.google.com/ymg-ktbe-dcp",
                "label": "meet.google.com/ymg-ktbe-dcp",
            },
            {
                "entryPointType": "more",
                "uri": "https://tel.meet/ymg-ktbe-dcp?pin=4395168824162",
                "pin": "4395168824162",
            },
            {
                "regionCode": "NL",
                "entryPointType": "phone",
                "uri": "tel:+31-20-257-2251",
                "label": "+31 20 257 2251",
                "pin": "841725288",
            },
        ],
        "conferenceSolution": {
            "key": {"type": "hangoutsMeet"},
            "name": "Google Meet",
            "iconUri": (
                "https://fonts.gstatic.com/s/i/productlogos/meet_2020q4/v6/web-512dp/"
                "logo_meet_2020q4_color_2x_web_512dp.png"
            ),
        },
        "conferenceId": "ymg-ktbe-dcp",
    },
    event_type="default",
)

# All entities in one list
gcal_examples = [
    calendar_list_primary,
    calendar_list_shared,
    calendar,
    event_with_description,
    event_with_location,
    event_all_day,
    event_multi_day,
    event_recurring_base,
    event_recurring_instance,
    event_with_emoji,
]
