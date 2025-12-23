"""Zoom entity schemas.

Entity schemas for Zoom objects based on Zoom API:
 - Meeting (scheduled and past meetings)
 - MeetingParticipant (attendees of meetings)
 - MeetingRecording (recording files from cloud recordings)
 - MeetingTranscript (meeting transcripts from cloud recordings)

Reference:
  https://developers.zoom.us/docs/api/
  https://developers.zoom.us/docs/api/rest/reference/zoom-api/methods/#operation/meetings
  https://developers.zoom.us/docs/api/rest/reference/zoom-api/methods/#operation/recordingGet
"""

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import computed_field

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import BaseEntity


class ZoomMeetingEntity(BaseEntity):
    """Schema for a Zoom meeting.

    Based on the Zoom API meeting resource.
    Reference: https://developers.zoom.us/docs/api/rest/reference/zoom-api/methods/#operation/meeting
    """

    # API fields
    meeting_id: str = AirweaveField(
        ...,
        description="Unique meeting ID from Zoom.",
        is_entity_id=True,
    )
    topic: str = AirweaveField(
        ...,
        description="Meeting topic/title.",
        embeddable=True,
        is_name=True,
    )
    meeting_type: Optional[int] = AirweaveField(
        None,
        description=(
            "Meeting type "
            "(1=instant, 2=scheduled, 3=recurring no fixed time, "
            "8=recurring fixed time)."
        ),
        embeddable=False,
    )
    start_time: Optional[datetime] = AirweaveField(
        None,
        description="Meeting start time.",
        embeddable=False,
        is_created_at=True,
    )
    duration: Optional[int] = AirweaveField(
        None,
        description="Scheduled duration in minutes.",
        embeddable=False,
    )
    timezone: Optional[str] = AirweaveField(
        None,
        description="Timezone for the meeting start time.",
        embeddable=False,
    )
    agenda: Optional[str] = AirweaveField(
        None,
        description="Meeting agenda/description.",
        embeddable=True,
    )
    host_id: Optional[str] = AirweaveField(
        None,
        description="ID of the meeting host.",
        embeddable=False,
    )
    host_email: Optional[str] = AirweaveField(
        None,
        description="Email of the meeting host.",
        embeddable=True,
    )
    status: Optional[str] = AirweaveField(
        None,
        description="Meeting status (waiting, started, finished).",
        embeddable=True,
    )
    join_url: Optional[str] = AirweaveField(
        None,
        description="URL to join the meeting.",
        embeddable=False,
        unhashable=True,
    )
    password: Optional[str] = AirweaveField(
        None,
        description="Meeting password (if set).",
        embeddable=False,
        unhashable=True,
    )
    settings: Optional[Dict[str, Any]] = AirweaveField(
        None,
        description="Meeting settings.",
        embeddable=False,
    )
    uuid: Optional[str] = AirweaveField(
        None,
        description="Meeting UUID (unique per meeting instance).",
        embeddable=False,
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Return best-effort link to view the meeting."""
        if self.join_url:
            return self.join_url
        return f"https://zoom.us/meeting/{self.meeting_id}"


class ZoomMeetingParticipantEntity(BaseEntity):
    """Schema for a Zoom meeting participant.

    Based on the Zoom API participant resource.
    Reference: https://developers.zoom.us/docs/api/rest/reference/zoom-api/methods/#operation/pastMeetingParticipants
    """

    # API fields
    participant_id: str = AirweaveField(
        ...,
        description="Unique participant ID (generated from user_id + meeting_id).",
        is_entity_id=True,
    )
    participant_name: str = AirweaveField(
        ...,
        description="Display name of the participant.",
        embeddable=True,
        is_name=True,
    )
    meeting_id: str = AirweaveField(
        ...,
        description="ID of the meeting this participant attended.",
        embeddable=False,
    )
    user_id: Optional[str] = AirweaveField(
        None,
        description="Zoom user ID if the participant is a Zoom user.",
        embeddable=False,
    )
    user_email: Optional[str] = AirweaveField(
        None,
        description="Email address of the participant.",
        embeddable=True,
    )
    join_time: Optional[datetime] = AirweaveField(
        None,
        description="Time when participant joined the meeting.",
        embeddable=False,
        is_created_at=True,
    )
    leave_time: Optional[datetime] = AirweaveField(
        None,
        description="Time when participant left the meeting.",
        embeddable=False,
        is_updated_at=True,
    )
    duration: Optional[int] = AirweaveField(
        None,
        description="Duration of participation in seconds.",
        embeddable=False,
    )
    registrant_id: Optional[str] = AirweaveField(
        None,
        description="Registrant ID if the participant registered for the meeting.",
        embeddable=False,
    )
    status: Optional[str] = AirweaveField(
        None,
        description="Participant status.",
        embeddable=True,
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Return best-effort link to the meeting."""
        return f"https://zoom.us/meeting/{self.meeting_id}"


class ZoomRecordingEntity(BaseEntity):
    """Schema for a Zoom meeting recording.

    Based on the Zoom API recording resource.
    Reference: https://developers.zoom.us/docs/api/rest/reference/zoom-api/methods/#operation/recordingGet
    """

    # API fields
    recording_id: str = AirweaveField(
        ...,
        description="Unique recording file ID.",
        is_entity_id=True,
    )
    recording_name: str = AirweaveField(
        ...,
        description="Recording file name (derived from meeting topic).",
        embeddable=True,
        is_name=True,
    )
    meeting_id: str = AirweaveField(
        ...,
        description="ID of the meeting this recording belongs to.",
        embeddable=False,
    )
    meeting_topic: Optional[str] = AirweaveField(
        None,
        description="Topic of the meeting this recording belongs to.",
        embeddable=True,
    )
    recording_start: Optional[datetime] = AirweaveField(
        None,
        description="When the recording started.",
        embeddable=False,
        is_created_at=True,
    )
    recording_end: Optional[datetime] = AirweaveField(
        None,
        description="When the recording ended.",
        embeddable=False,
        is_updated_at=True,
    )
    file_type: Optional[str] = AirweaveField(
        None,
        description="Recording file type (MP4, M4A, CHAT, TRANSCRIPT, etc.).",
        embeddable=True,
    )
    file_size: Optional[int] = AirweaveField(
        None,
        description="Recording file size in bytes.",
        embeddable=False,
    )
    file_extension: Optional[str] = AirweaveField(
        None,
        description="File extension.",
        embeddable=False,
    )
    play_url: Optional[str] = AirweaveField(
        None,
        description="URL to play/view the recording.",
        embeddable=False,
        unhashable=True,
    )
    download_url: Optional[str] = AirweaveField(
        None,
        description="URL to download the recording.",
        embeddable=False,
        unhashable=True,
    )
    status: Optional[str] = AirweaveField(
        None,
        description="Recording status.",
        embeddable=True,
    )
    recording_type: Optional[str] = AirweaveField(
        None,
        description="Type of recording (shared_screen, active_speaker, etc.).",
        embeddable=True,
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Return best-effort link to view the recording."""
        if self.play_url:
            return self.play_url
        return f"https://zoom.us/recording/detail?meeting_id={self.meeting_id}"


class ZoomTranscriptEntity(BaseEntity):
    """Schema for a Zoom meeting transcript.

    Based on the Zoom API transcript resource.
    Transcripts are stored as VTT files in cloud recordings.
    """

    # API fields
    transcript_id: str = AirweaveField(
        ...,
        description="Unique transcript ID.",
        is_entity_id=True,
    )
    transcript_name: str = AirweaveField(
        ...,
        description="Transcript name (derived from meeting topic).",
        embeddable=True,
        is_name=True,
    )
    meeting_id: str = AirweaveField(
        ...,
        description="ID of the meeting this transcript belongs to.",
        embeddable=False,
    )
    meeting_topic: Optional[str] = AirweaveField(
        None,
        description="Topic of the meeting this transcript belongs to.",
        embeddable=True,
    )
    recording_start: Optional[datetime] = AirweaveField(
        None,
        description="When the recording/transcript started.",
        embeddable=False,
        is_created_at=True,
    )
    transcript_content: Optional[str] = AirweaveField(
        None,
        description="Full text content of the transcript.",
        embeddable=True,
    )
    download_url: Optional[str] = AirweaveField(
        None,
        description="URL to download the transcript file.",
        embeddable=False,
        unhashable=True,
    )
    file_type: Optional[str] = AirweaveField(
        None,
        description="Transcript file type (TRANSCRIPT, CC).",
        embeddable=False,
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Return best-effort link to view the transcript."""
        return f"https://zoom.us/recording/detail?meeting_id={self.meeting_id}"
