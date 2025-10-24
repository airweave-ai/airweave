"""Real Asana entities captured from actual sync for testing."""

from datetime import datetime, timezone

from airweave.platform.entities._base import Breadcrumb
from airweave.platform.entities.asana import (
    AsanaCommentEntity,
    AsanaFileEntity,
    AsanaProjectEntity,
    AsanaSectionEntity,
    AsanaTaskEntity,
    AsanaWorkspaceEntity,
)

# Workspace entity (captured from real sync)
workspace = AsanaWorkspaceEntity(
    entity_id="1209332293895359",
    breadcrumbs=[],
    name="airweave.ai",
    created_at=None,
    updated_at=None,
    is_organization=True,
    email_domains=["airweave.ai"],
    permalink_url="https://app.asana.com/0/1209332293895359",
)

# Project entity
project = AsanaProjectEntity(
    entity_id="1209332198044166",
    breadcrumbs=[Breadcrumb(entity_id="1209332293895359")],
    name="Build Integrations",
    created_at=datetime(2025, 2, 5, 15, 9, 54, 987000, tzinfo=timezone.utc),
    updated_at=datetime(2025, 9, 26, 0, 34, 41, 376000, tzinfo=timezone.utc),
    workspace_gid="1209332293895359",
    workspace_name="airweave.ai",
    color="aqua",
    archived=False,
    default_view="list",
    html_notes="<body></body>",
    notes="",
    is_public=False,
    owner={"gid": "1209332203471167", "name": "Airweave Apps"},
    team={"gid": "1209332293895361", "name": "Airweave's first team"},
    members=[{"gid": "1209332203471167", "name": "Airweave Apps"}],
    followers=[{"gid": "1209332203471167", "name": "Airweave Apps"}],
    custom_fields=[],
    custom_field_settings=[
        {"gid": "1209332198044175", "resource_type": "custom_field_setting"},
        {"gid": "1209332198044180", "resource_type": "custom_field_setting"},
    ],
    default_access_level="editor",
    icon=None,
    permalink_url="https://app.asana.com/1/1209332293895359/project/1209332198044166",
)

# Section entity
section = AsanaSectionEntity(
    entity_id="1209332198044167",
    breadcrumbs=[
        Breadcrumb(entity_id="1209332293895359"),
        Breadcrumb(entity_id="1209332198044166"),
    ],
    name="To do",
    created_at=datetime(2025, 2, 5, 15, 9, 55, 507000, tzinfo=timezone.utc),
    updated_at=None,
    project_gid="1209332198044166",
    projects=[],
)

# Task entity with rich data (captured from real sync with full custom fields)
task = AsanaTaskEntity(
    entity_id="1211565181540505",
    breadcrumbs=[
        Breadcrumb(entity_id="1209332293895359"),
        Breadcrumb(entity_id="1209332198044166"),
        Breadcrumb(entity_id="1209332198044167"),
    ],
    name="Fix problem",
    created_at=datetime(2025, 10, 6, 15, 45, 18, 543000, tzinfo=timezone.utc),
    updated_at=datetime(2025, 10, 17, 14, 8, 4, 432000, tzinfo=timezone.utc),
    project_gid="1209332198044166",
    section_gid="1209332198044167",
    assignee={"gid": "1209332203471167", "name": "Airweave Apps"},
    assignee_status="inbox",
    completed=False,
    dependencies=[],
    dependents=[],
    due_on="2026-05-08",
    html_notes="<body>Julius schutten needs a vitesse shirt</body>",
    notes="Julius schutten needs a vitesse shirt",
    is_rendered_as_separator=False,
    liked=False,
    memberships=[{}],
    num_likes=0,
    num_subtasks=0,
    permalink_url="https://app.asana.com/1/1209332293895359/project/1209332198044166/task/1211565181540505",
    resource_subtype="default_task",
    tags=[],
    custom_fields=[
        {
            "gid": "1209332198044171",
            "enabled": True,
            "enum_options": [
                {
                    "gid": "1209332198044172",
                    "color": "aqua",
                    "enabled": True,
                    "name": "Low",
                    "resource_type": "enum_option",
                },
                {
                    "gid": "1209332198044173",
                    "color": "yellow-orange",
                    "enabled": True,
                    "name": "Medium",
                    "resource_type": "enum_option",
                },
                {
                    "gid": "1209332198044174",
                    "color": "purple",
                    "enabled": True,
                    "name": "High",
                    "resource_type": "enum_option",
                },
            ],
            "enum_value": {
                "gid": "1209332198044174",
                "color": "purple",
                "enabled": True,
                "name": "High",
                "resource_type": "enum_option",
            },
            "name": "Priority",
            "description": "Track the priority of each task.",
            "created_by": {
                "gid": "1209332203471167",
                "name": "Airweave Apps",
                "resource_type": "user",
            },
            "display_value": "High",
            "resource_subtype": "enum",
            "resource_type": "custom_field",
            "is_formula_field": False,
            "is_value_read_only": False,
            "type": "enum",
        },
        {
            "gid": "1209332198044176",
            "enabled": True,
            "enum_options": [
                {
                    "gid": "1209332198044177",
                    "color": "blue-green",
                    "enabled": True,
                    "name": "On track",
                    "resource_type": "enum_option",
                },
                {
                    "gid": "1209332198044178",
                    "color": "yellow",
                    "enabled": True,
                    "name": "At risk",
                    "resource_type": "enum_option",
                },
                {
                    "gid": "1209332198044179",
                    "color": "red",
                    "enabled": True,
                    "name": "Off track",
                    "resource_type": "enum_option",
                },
            ],
            "enum_value": {
                "gid": "1209332198044177",
                "color": "blue-green",
                "enabled": True,
                "name": "On track",
                "resource_type": "enum_option",
            },
            "name": "Status",
            "description": "Track the status of each task.",
            "created_by": {
                "gid": "1209332203471167",
                "name": "Airweave Apps",
                "resource_type": "user",
            },
            "display_value": "On track",
            "resource_subtype": "enum",
            "resource_type": "custom_field",
            "is_formula_field": False,
            "is_value_read_only": False,
            "type": "enum",
        },
    ],
    followers=[{"gid": "1209332203471167", "name": "Airweave Apps"}],
    workspace={"gid": "1209332293895359", "name": "airweave.ai"},
)

# Comment entity (mock - for testing comment processing)
comment = AsanaCommentEntity(
    entity_id="1211700000000000",
    breadcrumbs=[
        Breadcrumb(entity_id="1209332293895359"),
        Breadcrumb(entity_id="1209332198044166"),
        Breadcrumb(entity_id="1211565181540505"),
    ],
    name="Comment by Airweave Apps: We should order the shirt in size XL",
    created_at=datetime(2025, 10, 17, 15, 30, 0, tzinfo=timezone.utc),
    updated_at=None,
    task_gid="1211565181540505",
    author={"gid": "1209332203471167", "name": "Airweave Apps"},
    resource_subtype="comment_added",
    text="We should order the shirt in size XL since Julius is quite tall",
    html_text="<body>We should order the shirt in size XL since Julius is quite tall</body>",
    is_pinned=False,
    is_edited=False,
    sticker_name=None,
    num_likes=2,
    liked=False,
    type="comment",
    previews=[],
)

# File entity (captured from real sync with full pre-signed S3 URL)
file_entity = AsanaFileEntity(
    entity_id="1211673490428967",
    breadcrumbs=[
        Breadcrumb(entity_id="1209332293895359"),
        Breadcrumb(entity_id="1209332198044166"),
        Breadcrumb(entity_id="1211565181540505"),
    ],
    name="Story2.pdf",
    created_at=datetime(2025, 10, 17, 14, 8, 4, 272000, tzinfo=timezone.utc),
    updated_at=None,
    url="https://asana-user-private-us-east-1.s3.amazonaws.com/assets/1209332293895359/1211673490428966/f1c04ca2b7fb2e0049b38ecf03a4207e?X-Amz-Security-Token=IQoJb3JpZ2luX2VjEBUaCXVzLWVhc3QtMSJHMEUCIQDHpI3w%2BmEc%2FUws%2F937qd4AoEzppMpjzIwWIZ5lDeSzbgIgQp59UurN7bWvRwJ26%2B9nyuxL%2BPOcMO0XE4R0mbqErKUqngUIvv%2F%2F%2F%2F%2F%2F%2F%2F%2F%2FARAAGgw0MDM0ODM0NDY4NDAiDJL%2BCTeHJC51knJgeCryBDMU0TqQ%2FMXOnpiFk77b7TTWm4zMdUSqzOjg%2Fj3C5lcYV8WrdfT7qf8W043z2FePE5lRGioT7QApw8Exic9%2FSzhRS%2FOCBiO%2BEYnYsykuAZFwoXR8ZJ3vXZffw0BPUGB0wTz8uFEtF7CSHnH6QtmhxwLj1AJAHw1bpwCjNPKPA0G5PNx2CBunaLd%2FAaaAnp%2BF52lFFJQ%2BoiLFk8FJLonISJcdlsCTPsXInzoYlv0blR5Dg7134ZRb4EhwD9Dmx%2F1ucXpiTkImiuSgob53gI6q0Y74MamugUz%2B0owE9YaAiGLgoy4QwNacpAbfo7LrbZ07gmPZd06c3LXZ6FQqdnC6m49oLcQj8nTN0mdIiEtk9%2FT%2BwU7ROPwEQZFf%2FXYCxjtIq35cKcUFqBH4Bhge%2BeslKTU3Z7dcrRVbvlRnW%2FigZxQ9%2FY3tGAOMJxbFCWTL1iOhIlWemEj7iNtyxOdU%2BvkJc4YVpi9Q7u7hhonWZsOHimainDvpd2Zu5OB7B85Ostrcg1QiqTVn%2BzGvPhmsonPkJjEH9Pl7UfkZlhltl%2BTnuYOVEkQ8ZztWZGYpQXjsgLEPhpvXuhxpEXnuONTAi%2BVWFVEjnMbekeDGzuetTwzOghvlfNrPh3sQzZBaDeH6gbMqdxPC%2F9gwfxfcOGc7LOFOdBucP12%2Fs1XJYu78i3%2FEeW72r%2Fxvq1ROeXfYYxeU17r9U13VPo1j8q9WzSersJRe4shPjl%2Bxu3MQiqEfq7D30rhTrYlojiRdsRh4Csa%2Bd4QU93p6NNg%2B0m0w1nSjzCh5GtXMH181nVS1jru7bC3%2BKQ1pijQw6TYSOnWSIJ5eNCmKHEBHMIyQzscGOpsBGBieMMDfc1ysCDZEwc9CRN3sBg37Ms4MCbEA4RslnvUlZZOKRHpx%2Ffrkj5kg7ewoSVqOU7W%2FQXybiOlDGt1DFwS6Ed2u%2FBVNjJmQyAwQOlgRMliqIFNouAHxXNTe2r%2FQLeJD01nNTZ2qQ2bvnrspPmJ3b%2FBobKV%2Fc71s9n%2B2kf8TofFUi%2BCarxEUK4Cy2Elb1p%2BzdUqdaSPE6vQ%3D&X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Date=20251018T123749Z&X-Amz-SignedHeaders=host&X-Amz-Credential=ASIAV34L4ZY4CR7RU63O%2F20251018%2Fus-east-1%2Fs3%2Faws4_request&X-Amz-Expires=1800&X-Amz-Signature=f41c401769d01ad5bcfd2d87411f2f06063f984ddb3a99e31fc2a334a5d5c86c#_=_",
    size=1367,
    file_type="application",
    mime_type="application/octet-stream",
    local_path=(
        "/Users/daanmanneke/Desktop/airweave/backend/airweave/platform/sync/test/entities/tmp/"
        "Story2.pdf"
    ),
    task_gid="1211565181540505",
    task_name="Fix problem",
    resource_type="attachment",
    host="asana",
    parent={"gid": "1211565181540505", "name": "Fix problem"},
    view_url="https://asana-user-private-us-east-1.s3.amazonaws.com/assets/1209332293895359/1211673490428966/f1c04ca2b7fb2e0049b38ecf03a4207e?X-Amz-Security-Token=IQoJb3JpZ2luX2VjEBUaCXVzLWVhc3QtMSJHMEUCIQDHpI3w%2BmEc%2FUws%2F937qd4AoEzppMpjzIwWIZ5lDeSzbgIgQp59UurN7bWvRwJ26%2B9nyuxL%2BPOcMO0XE4R0mbqErKUqngUIvv%2F%2F%2F%2F%2F%2F%2F%2F%2F%2FARAAGgw0MDM0ODM0NDY4NDAiDJL%2BCTeHJC51knJgeCryBDMU0TqQ%2FMXOnpiFk77b7TTWm4zMdUSqzOjg%2Fj3C5lcYV8WrdfT7qf8W043z2FePE5lRGioT7QApw8Exic9%2FSzhRS%2FOCBiO%2BEYnYsykuAZFwoXR8ZJ3vXZffw0BPUGB0wTz8uFEtF7CSHnH6QtmhxwLj1AJAHw1bpwCjNPKPA0G5PNx2CBunaLd%2FAaaAnp%2BF52lFFJQ%2BoiLFk8FJLonISJcdlsCTPsXInzoYlv0blR5Dg7134ZRb4EhwD9Dmx%2F1ucXpiTkImiuSgob53gI6q0Y74MamugUz%2B0owE9YaAiGLgoy4QwNacpAbfo7LrbZ07gmPZd06c3LXZ6FQqdnC6m49oLcQj8nTN0mdIiEtk9%2FT%2BwU7ROPwEQZFf%2FXYCxjtIq35cKcUFqBH4Bhge%2BeslKTU3Z7dcrRVbvlRnW%2FigZxQ9%2FY3tGAOMJxbFCWTL1iOhIlWemEj7iNtyxOdU%2BvkJc4YVpi9Q7u7hhonWZsOHimainDvpd2Zu5OB7B85Ostrcg1QiqTVn%2BzGvPhmsonPkJjEH9Pl7UfkZlhltl%2BTnuYOVEkQ8ZztWZGYpQXjsgLEPhpvXuhxpEXnuONTAi%2BVWFVEjnMbekeDGzuetTwzOghvlfNrPh3sQzZBaDeH6gbMqdxPC%2F9gwfxfcOGc7LOFOdBucP12%2Fs1XJYu78i3%2FEeW72r%2Fxvq1ROeXfYYxeU17r9U13VPo1j8q9WzSersJRe4shPjl%2Bxu3MQiqEfq7D30rhTrYlojiRdsRh4Csa%2Bd4QU93p6NNg%2B0m0w1nSjzCh5GtXMH181nVS1jru7bC3%2BKQ1pijQw6TYSOnWSIJ5eNCmKHEBHMIyQzscGOpsBGBieMMDfc1ysCDZEwc9CRN3sBg37Ms4MCbEA4RslnvUlZZOKRHpx%2Ffrkj5kg7ewoSVqOU7W%2FQXybiOlDGt1DFwS6Ed2u%2FBVNjJmQyAwQOlgRMliqIFNouAHxXNTe2r%2FQLeJD01nNTZ2qQ2bvnrspPmJ3b%2FBobKV%2Fc71s9n%2B2kf8TofFUi%2BCarxEUK4Cy2Elb1p%2BzdUqdaSPE6vQ%3D&X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Date=20251018T123749Z&X-Amz-SignedHeaders=host&X-Amz-Credential=ASIAV34L4ZY4CR7RU63O%2F20251018%2Fus-east-1%2Fs3%2Faws4_request&X-Amz-Expires=1800&X-Amz-Signature=f41c401769d01ad5bcfd2d87411f2f06063f984ddb3a99e31fc2a334a5d5c86c#_=_",
    permanent=False,
)

# All entities in one list
asana_examples = [workspace, project, section, task, comment, file_entity]
