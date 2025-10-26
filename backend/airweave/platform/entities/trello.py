"""Trello entity schemas."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import Field

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import 


class TrelloBoardEntity(BaseEntity):
    """Schema for Trello board entities."""

    name: str = AirweaveField(..., description="The name of the board", embeddable=True)
    trello_id: str = Field(..., description="Trello's unique identifier for the board")
    desc: Optional[str] = AirweaveField(
        None, description="Description of the board", embeddable=True
    )
    closed: bool = Field(False, description="Whether the board is closed/archived")
    url: Optional[str] = Field(None, description="URL to the board")
    short_url: Optional[str] = Field(None, description="Short URL to the board")
    prefs: Optional[Dict[str, Any]] = Field(None, description="Board preferences and settings")
    id_organization: Optional[str] = Field(
        None, description="ID of the organization this board belongs to"
    )
    pinned: bool = Field(False, description="Whether the board is pinned")


class TrelloListEntity(BaseEntity):
    """Schema for Trello list entities (columns on a board)."""

    name: str = AirweaveField(..., description="The name of the list", embeddable=True)
    trello_id: str = Field(..., description="Trello's unique identifier for the list")
    id_board: str = Field(..., description="ID of the board this list belongs to")
    board_name: str = AirweaveField(
        ..., description="Name of the board this list belongs to", embeddable=True
    )
    closed: bool = Field(False, description="Whether the list is archived")
    pos: Optional[float] = Field(None, description="Position of the list on the board")
    subscribed: Optional[bool] = Field(
        None, description="Whether the user is subscribed to this list"
    )


class TrelloCardEntity(BaseEntity):
    """Schema for Trello card entities."""

    name: str = AirweaveField(..., description="The name/title of the card", embeddable=True)
    trello_id: str = Field(..., description="Trello's unique identifier for the card")
    desc: Optional[str] = AirweaveField(
        None, description="Description/notes on the card", embeddable=True
    )
    id_board: str = Field(..., description="ID of the board this card belongs to")
    board_name: str = AirweaveField(..., description="Name of the board", embeddable=True)
    id_list: str = Field(..., description="ID of the list this card belongs to")
    list_name: str = AirweaveField(..., description="Name of the list", embeddable=True)
    closed: bool = AirweaveField(False, description="Whether the card is archived", embeddable=True)
    due: Optional[str] = AirweaveField(None, description="Due date for the card", embeddable=True)
    due_complete: Optional[bool] = AirweaveField(
        None, description="Whether the due date is marked complete", embeddable=True
    )
    date_last_activity: Optional[datetime] = AirweaveField(
        None,
        description="Last activity date on the card",
        embeddable=True,
        is_updated_at=True,
    )
    id_members: List[str] = Field(
        default_factory=list, description="List of member IDs assigned to this card"
    )
    members: List[Dict[str, Any]] = AirweaveField(
        default_factory=list, description="Members assigned to this card", embeddable=True
    )
    id_labels: List[str] = Field(
        default_factory=list, description="List of label IDs attached to this card"
    )
    labels: List[Dict[str, Any]] = AirweaveField(
        default_factory=list, description="Labels attached to this card", embeddable=True
    )
    id_checklists: List[str] = Field(
        default_factory=list, description="List of checklist IDs on this card"
    )
    badges: Optional[Dict[str, Any]] = AirweaveField(
        None,
        description="Badge information (comments, attachments, votes, etc.)",
        embeddable=True,
    )
    pos: Optional[float] = Field(None, description="Position of the card in the list")
    short_link: Optional[str] = Field(None, description="Short link to the card")
    short_url: Optional[str] = Field(None, description="Short URL to the card")
    url: Optional[str] = Field(None, description="Full URL to the card")
    start: Optional[str] = AirweaveField(
        None, description="Start date for the card", embeddable=True
    )
    subscribed: Optional[bool] = Field(
        None, description="Whether the user is subscribed to this card"
    )


class TrelloChecklistEntity(BaseEntity):
    """Schema for Trello checklist entities."""

    name: str = AirweaveField(..., description="The name of the checklist", embeddable=True)
    trello_id: str = Field(..., description="Trello's unique identifier for the checklist")
    id_board: str = Field(..., description="ID of the board this checklist belongs to")
    id_card: str = Field(..., description="ID of the card this checklist belongs to")
    card_name: str = AirweaveField(..., description="Name of the card", embeddable=True)
    pos: Optional[float] = Field(None, description="Position of the checklist on the card")
    check_items: List[Dict[str, Any]] = AirweaveField(
        default_factory=list,
        description="List of checklist items with their states",
        embeddable=True,
    )


class TrelloMemberEntity(BaseEntity):
    """Schema for Trello member (user) entities."""

    username: str = AirweaveField(..., description="The username of the member", embeddable=True)
    trello_id: str = Field(..., description="Trello's unique identifier for the member")
    full_name: Optional[str] = AirweaveField(
        None, description="Full name of the member", embeddable=True
    )
    initials: Optional[str] = Field(None, description="Member's initials")
    avatar_url: Optional[str] = Field(None, description="URL to the member's avatar")
    bio: Optional[str] = AirweaveField(None, description="Member's bio", embeddable=True)
    url: Optional[str] = Field(None, description="URL to the member's profile")
    id_boards: List[str] = Field(
        default_factory=list, description="List of board IDs the member belongs to"
    )
    member_type: Optional[str] = AirweaveField(
        None, description="Type of member (normal, admin, etc.)", embeddable=True
    )
