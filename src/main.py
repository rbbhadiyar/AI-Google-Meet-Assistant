import base64
import binascii
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Optional
from urllib.parse import urlencode
import requests
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request as GoogleAuthRequest
from googleapiclient.errors import HttpError
from .config import BASE_URL, GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_SCOPES
from .google_calendar import (
    build_event_payload,
    delete_event,
    get_event_by_query,
    schedule_event,
    update_event,
    build_calendar_service,
)

ROOT_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = ROOT_DIR / "static"
TOKEN_STORE_PATH = ROOT_DIR / ".tokens.json"

app = FastAPI(title="AI Google Meet Assistant")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
def root():
    return FileResponse(STATIC_DIR / "index.html")

from .schemas import (
    CancelRequest,
    ListRequest,
    OAuthUrlResponse,
    ParseRequest,
    RescheduleRequest,
    ScheduleRequest,
)
from .llm_parser import parse_meeting_instruction

# In-memory credential store for example purposes only.
credential_store: Dict[str, Dict[str, str]] = {}


def load_credential_store() -> None:
    if not TOKEN_STORE_PATH.exists():
        return
    try:
        data = json.loads(TOKEN_STORE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    if isinstance(data, dict):
        credential_store.update({
            email: tokens for email, tokens in data.items()
            if isinstance(email, str) and isinstance(tokens, dict)
        })


def save_credential_store() -> None:
    TOKEN_STORE_PATH.write_text(json.dumps(credential_store, indent=2), encoding="utf-8")


load_credential_store()


def oauth_redirect_uri() -> str:
    return f"{BASE_URL.rstrip('/')}/auth/callback"


def email_from_id_token(id_token: Optional[object]) -> Optional[str]:
    if not id_token:
        return None
    if isinstance(id_token, dict):
        return id_token.get("email")
    if not isinstance(id_token, str):
        return None

    try:
        payload = id_token.split(".")[1]
        padding = "=" * (-len(payload) % 4)
        decoded = base64.urlsafe_b64decode(payload + padding)
        claims = json.loads(decoded)
    except (IndexError, binascii.Error, json.JSONDecodeError, UnicodeDecodeError):
        return None
    return claims.get("email")


def seconds_until_expiry(expiry: Optional[datetime]) -> Optional[int]:
    if not expiry:
        return None
    now = datetime.now(timezone.utc) if expiry.tzinfo else datetime.utcnow()
    return int((expiry - now).total_seconds())


def google_api_error_detail(exc: HttpError) -> str:
    try:
        payload = json.loads(exc.content.decode("utf-8"))
        error = payload.get("error", {})
        message = error.get("message")
        if message:
            return message
    except (AttributeError, UnicodeDecodeError, json.JSONDecodeError):
        pass
    return str(exc)


def google_api_error_payload(exc: HttpError):
    message = google_api_error_detail(exc)
    if "calendar-json.googleapis.com" in message and "disabled" in message.lower():
        return {
            "message": "Google Calendar API is disabled for this Google Cloud project.",
            "action": "Enable Google Calendar API, wait a few minutes, then authenticate again.",
            "url": "https://console.developers.google.com/apis/api/calendar-json.googleapis.com/overview?project=45607169410",
            "raw": message,
        }
    return message


def raise_google_api_error(exc: HttpError) -> None:
    status = getattr(exc.resp, "status", None) or 400
    raise HTTPException(status_code=status, detail=google_api_error_payload(exc)) from exc


def raise_event_not_found(event_id: str) -> None:
    raise HTTPException(
        status_code=404,
        detail=(
            f"Meeting not found for event ID '{event_id}'. "
            "Make sure you copied only the event ID and are using the same authenticated Google account."
        ),
    )


def event_summary(event: Dict) -> Dict:
    return {
        "id": event.get("id"),
        "title": event.get("summary") or "Untitled meeting",
        "start": event.get("start"),
        "end": event.get("end"),
        "calendar_link": event.get("htmlLink"),
        "meet_link": event.get("hangoutLink") or event.get("conferenceData", {}).get("entryPoints", [{}])[0].get("uri"),
    }


def portal_redirect(**params: str) -> RedirectResponse:
    return RedirectResponse(url=f"/?{urlencode(params)}", status_code=303)


def make_flow() -> Flow:
    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [oauth_redirect_uri()],
            }
        },
        scopes=GOOGLE_SCOPES,
    )
    flow.redirect_uri = oauth_redirect_uri()
    return flow


@app.get("/auth/url", response_model=OAuthUrlResponse)
def auth_url():
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        raise HTTPException(status_code=500, detail="Google OAuth credentials are not configured.")
    flow = make_flow()
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    return {"auth_url": auth_url}


@app.get("/auth/callback")
def auth_callback(code: Optional[str] = None, error: Optional[str] = None):
    if error:
        return portal_redirect(auth="error", message=f"Google authentication failed: {error}")
    if not code:
        return portal_redirect(auth="error", message="Google authentication did not return an authorization code.")

    flow = make_flow()
    try:
        flow.fetch_token(code=code)
    except Exception as exc:
        return portal_redirect(auth="error", message=f"Google OAuth token exchange failed: {exc}")

    creds = flow.credentials
    if not creds or not creds.valid:
        raise HTTPException(status_code=400, detail="Unable to obtain Google credentials.")

    email = email_from_id_token(creds.id_token)
    if not email:
        try:
            service = build_calendar_service(creds)
            calendar_list = service.calendarList().list(maxResults=250).execute()
        except Exception as exc:
            return portal_redirect(auth="error", message=f"Could not read Google Calendar profile: {exc}")

        primary_calendar = next(
            (item for item in calendar_list.get("items", []) if item.get("primary")),
            None,
        )
        email = primary_calendar.get("id") if primary_calendar else None

    if not email:
        return portal_redirect(auth="error", message="Could not determine the signed-in Google account email.")

    if not creds.token:
        return portal_redirect(auth="error", message="Google did not return an access token.")

    credential_store[email] = {
        "access_token": creds.token,
        "refresh_token": creds.refresh_token or "",
        "expiry": creds.expiry.isoformat() if creds.expiry else "",
    }
    save_credential_store()
    return portal_redirect(auth="success", email=email, expires_in=str(seconds_until_expiry(creds.expiry) or ""))


def get_credentials_for_user(email: str) -> Credentials:
    stored = credential_store.get(email)
    if not stored:
        raise HTTPException(status_code=404, detail="User credentials not found. Authenticate first.")
    expiry = None
    if stored.get("expiry"):
        try:
            expiry = datetime.fromisoformat(stored["expiry"])
        except ValueError:
            expiry = None
    creds = Credentials(
        token=stored["access_token"],
        refresh_token=stored.get("refresh_token"),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET,
        scopes=GOOGLE_SCOPES,
        expiry=expiry,
    )
    if creds.expired and creds.refresh_token:
        creds.refresh(GoogleAuthRequest())
        credential_store[email] = {
            "access_token": creds.token,
            "refresh_token": creds.refresh_token or stored.get("refresh_token", ""),
            "expiry": creds.expiry.isoformat() if creds.expiry else "",
        }
        save_credential_store()
    return creds


@app.get("/auth/status")
def auth_status(email: Optional[str] = Query(None)):
    if email:
        return {"authenticated": email in credential_store, "email": email}
    emails = sorted(credential_store.keys())
    return {"authenticated": bool(emails), "email": emails[0] if emails else None}


@app.post("/auth/logout")
def auth_logout(email: Optional[str] = Query(None)):
    if email:
        credential_store.pop(email, None)
    else:
        credential_store.clear()
    save_credential_store()
    return {"message": "Logged out successfully."}


@app.post("/events/schedule")
def schedule_meeting(request: ScheduleRequest, email: str = Query(...)):
    creds = get_credentials_for_user(email)
    payload = build_event_payload(
        summary=request.summary,
        start_datetime=request.start_datetime.isoformat(),
        end_datetime=request.end_datetime.isoformat(),
        description=request.description,
        attendees=[{"email": attendee.email} for attendee in request.attendees] if request.attendees else None,
    )
    try:
        event = schedule_event(creds, payload)
    except HttpError as exc:
        raise_google_api_error(exc)
    meet_link = event.get("hangoutLink") or event.get("conferenceData", {}).get("entryPoints", [{}])[0].get("uri")
    return {
        "message": "Meeting scheduled successfully.",
        "event_id": event.get("id"),
        "hangout_link": meet_link,
        "meeting": event_summary(event),
    }


@app.post("/events/list")
def list_meetings(request: ListRequest, email: str = Query(...)):
    creds = get_credentials_for_user(email)
    service = build_calendar_service(creds)
    time_min = datetime.now(timezone.utc).isoformat()
    time_max = None
    if request.date:
        try:
            requested_day = datetime.fromisoformat(request.date).date()
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="List date must use YYYY-MM-DD format.") from exc
        time_min = datetime.combine(requested_day, datetime.min.time(), tzinfo=timezone.utc).isoformat()
        time_max = datetime.combine(requested_day + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc).isoformat()

    list_request = service.events().list(
        calendarId="primary",
        timeMin=time_min,
        maxResults=request.max_results,
        singleEvents=True,
        orderBy="startTime",
    )
    if time_max:
        list_request = service.events().list(
            calendarId="primary",
            timeMin=time_min,
            timeMax=time_max,
            maxResults=request.max_results,
            singleEvents=True,
            orderBy="startTime",
        )
    try:
        events_result = list_request.execute()
    except HttpError as exc:
        raise_google_api_error(exc)
    events = events_result.get("items", [])
    return [{
        "id": event.get("id"),
        "summary": event.get("summary"),
        "start": event.get("start"),
        "end": event.get("end"),
    } for event in events]


@app.post("/events/cancel")
def cancel_meeting(request: CancelRequest, email: str = Query(...)):
    creds = get_credentials_for_user(email)
    event_id = request.event_id
    if not event_id:
        if not request.query:
            raise HTTPException(status_code=400, detail="Provide event_id or query to identify the meeting.")
        try:
            event = get_event_by_query(creds, request.query)
        except HttpError as exc:
            raise_google_api_error(exc)
        if not event:
            raise HTTPException(status_code=404, detail="Meeting not found.")
        event_id = event.get("id")
    try:
        delete_event(creds, event_id)
    except HttpError as exc:
        if getattr(exc.resp, "status", None) == 404:
            raise_event_not_found(event_id)
        raise_google_api_error(exc)
    return {"message": "Meeting cancelled successfully.", "event_id": event_id}


@app.post("/events/reschedule")
def reschedule_meeting(request: RescheduleRequest, email: str = Query(...)):
    creds = get_credentials_for_user(email)
    event_id = request.event_id
    if not event_id:
        if not request.query:
            raise HTTPException(status_code=400, detail="Provide event_id or query to identify the meeting.")
        try:
            event = get_event_by_query(creds, request.query)
        except HttpError as exc:
            raise_google_api_error(exc)
        if not event:
            raise HTTPException(status_code=404, detail="Meeting not found.")
        event_id = event.get("id")
    payload = {
        "start": {"dateTime": request.new_start.isoformat(), "timeZone": "UTC"},
        "end": {"dateTime": request.new_end.isoformat(), "timeZone": "UTC"},
    }
    try:
        updated = update_event(creds, event_id, payload)
    except HttpError as exc:
        if getattr(exc.resp, "status", None) == 404:
            raise_event_not_found(event_id)
        raise_google_api_error(exc)
    return {
        "message": "Meeting rescheduled successfully.",
        "event_id": event_id,
        "meeting": event_summary(updated),
    }


@app.post("/parse")
def parse_instruction(request: ParseRequest):
    try:
        parsed = parse_meeting_instruction(request.text)
    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else 502
        detail = "Natural-language parser request failed."
        try:
            payload = exc.response.json() if exc.response is not None else {}
            detail = payload.get("error", {}).get("message") or payload.get("message") or detail
        except ValueError:
            if exc.response is not None and exc.response.text:
                detail = exc.response.text
        raise HTTPException(
            status_code=502,
            detail={
                "message": detail,
                "action": "Check GROQ_API_KEY and GROQ_MODEL in .env, or leave GROQ_API_KEY empty to use local parsing.",
                "upstream_status": status,
            },
        ) from exc
    except requests.RequestException as exc:
        raise HTTPException(
            status_code=502,
            detail={
                "message": f"Could not reach the natural-language parser: {exc}",
                "action": "Check your internet connection or leave GROQ_API_KEY empty to use local parsing.",
            },
        ) from exc
    except (json.JSONDecodeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=f"Could not parse the assistant response: {exc}") from exc
    return JSONResponse(content=parsed)


@app.get("/health")
def health_check():
    return {"message": "AI Google Meet Assistant backend is running."}
