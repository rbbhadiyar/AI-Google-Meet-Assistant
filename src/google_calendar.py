import random
import string
from typing import Any, Dict, List, Optional
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

CONFERENCE_REQUEST_ID_PREFIX = "meet-assistant-"


def build_calendar_service(creds: Credentials):
    return build("calendar", "v3", credentials=creds)


def random_request_id(length: int = 12) -> str:
    return CONFERENCE_REQUEST_ID_PREFIX + "".join(
        random.choice(string.ascii_lowercase + string.digits) for _ in range(length)
    )


def schedule_event(creds: Credentials, event_payload: Dict[str, Any]) -> Dict[str, Any]:
    service = build_calendar_service(creds)
    event = service.events().insert(
        calendarId="primary",
        body=event_payload,
        conferenceDataVersion=1,
    ).execute()
    return event


def get_event_by_query(creds: Credentials, query: str, max_results: int = 20) -> Optional[Dict[str, Any]]:
    service = build_calendar_service(creds)
    events_result = (
        service.events()
        .list(
            calendarId="primary",
            maxResults=max_results,
            q=query,
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )
    events = events_result.get("items", [])
    if events:
        return events[0]

    upcoming_result = (
        service.events()
        .list(
            calendarId="primary",
            maxResults=max_results,
            singleEvents=True,
            orderBy="startTime",
            timeMin="2020-01-01T00:00:00Z",
        )
        .execute()
    )
    query_words = [word for word in query.lower().split() if len(word) > 2]
    for event in upcoming_result.get("items", []):
        summary = (event.get("summary") or "").lower()
        if query_words and all(word in summary for word in query_words):
            return event
    return None


def delete_event(creds: Credentials, event_id: str) -> None:
    service = build_calendar_service(creds)
    service.events().delete(calendarId="primary", eventId=event_id).execute()


def update_event(creds: Credentials, event_id: str, update_payload: Dict[str, Any]) -> Dict[str, Any]:
    service = build_calendar_service(creds)
    event = service.events().patch(
        calendarId="primary",
        eventId=event_id,
        body=update_payload,
        conferenceDataVersion=1,
    ).execute()
    return event


def build_event_payload(
    summary: str,
    start_datetime: str,
    end_datetime: str,
    description: Optional[str] = None,
    attendees: Optional[List[Dict[str, str]]] = None,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "summary": summary,
        "start": {"dateTime": start_datetime, "timeZone": "UTC"},
        "end": {"dateTime": end_datetime, "timeZone": "UTC"},
        "conferenceData": {
            "createRequest": {
                "requestId": random_request_id(),
            }
        },
    }
    if description:
        payload["description"] = description
    if attendees:
        payload["attendees"] = attendees
    return payload
