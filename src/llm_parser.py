import json
import re
from datetime import date, timedelta
from typing import Dict
import requests
from .config import GROQ_API_KEY, GROQ_MODEL

SYSTEM_PROMPT = (
    "You are an assistant that extracts Google Calendar meeting instructions from user text. "
    "Return only valid JSON with the keys: title, date, time, duration, attendees, query, action. "
    "If the request is to list or cancel/reschedule events, set action appropriately and include query or event_id if available. "
    "Use ISO 8601 date values and 24-hour time. "
)

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
HEADERS = {
    "Authorization": f"Bearer {GROQ_API_KEY}",
    "Content-Type": "application/json",
}


def local_parse_meeting_instruction(text: str) -> Dict[str, object]:
    normalized = text.strip()
    lower = normalized.lower()
    today = date.today()
    parsed: Dict[str, object] = {
        "title": None,
        "date": None,
        "time": None,
        "duration": None,
        "attendees": [],
        "query": normalized,
        "action": "unknown",
        "source": "local",
    }

    if any(word in lower for word in ("what meetings", "upcoming", "list", "show meetings", "do i have")):
        parsed["action"] = "list"
    elif any(word in lower for word in ("cancel", "delete", "remove")):
        parsed["action"] = "cancel"
    elif any(word in lower for word in ("reschedule", "move", "postpone")):
        parsed["action"] = "reschedule"
    elif any(word in lower for word in ("schedule", "book", "create", "set up")):
        parsed["action"] = "schedule"

    if "tomorrow" in lower:
        parsed["date"] = (today + timedelta(days=1)).isoformat()
    elif "today" in lower:
        parsed["date"] = today.isoformat()
    else:
        weekdays = {
            "monday": 0,
            "tuesday": 1,
            "wednesday": 2,
            "thursday": 3,
            "friday": 4,
            "saturday": 5,
            "sunday": 6,
        }
        for weekday_name, weekday_index in weekdays.items():
            if re.search(rf"\b(?:on\s+)?{weekday_name}\b", lower):
                days_ahead = (weekday_index - today.weekday()) % 7
                if days_ahead == 0:
                    days_ahead = 7
                parsed["date"] = (today + timedelta(days=days_ahead)).isoformat()
                break

    time_match = re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b", lower)
    if time_match and parsed["action"] in {"schedule", "reschedule"}:
        hour = int(time_match.group(1))
        minute = int(time_match.group(2) or "0")
        period = time_match.group(3)
        if period == "pm" and hour < 12:
            hour += 12
        if period == "am" and hour == 12:
            hour = 0
        parsed["time"] = f"{hour:02d}:{minute:02d}"

    duration_match = re.search(r"\b(\d+)\s*(min|mins|minutes|hour|hours|hr|hrs)\b", lower)
    if duration_match:
        amount = int(duration_match.group(1))
        unit = duration_match.group(2)
        parsed["duration"] = amount * 60 if unit.startswith(("hour", "hr")) else amount
    elif parsed["action"] in {"schedule", "reschedule"}:
        parsed["duration"] = 30

    email_matches = re.findall(r"[\w.+-]+@[\w-]+\.[\w.-]+", normalized)
    parsed["attendees"] = email_matches

    if parsed["action"] == "schedule":
        title_match = re.search(r"(?:schedule|book|create|set up)\s+(?:a\s+)?(?:meeting|call)?\s*(?:with\s+)?(.+?)(?:\s+(?:today|tomorrow|on|at|for)\b|$)", lower)
        title_name = title_match.group(1).strip() if title_match else ""
        parsed["title"] = f"Meeting with {title_name.title()}" if title_name else "Meeting"

    if parsed["action"] in {"cancel", "reschedule", "list"}:
        query = lower
        query = re.sub(r"\b(cancel|delete|remove|reschedule|move|postpone|what|which|show|list|upcoming|meetings?|do|i|have|my|to|with)\b", " ", query)
        query = re.sub(r"\b(today|tomorrow|on|at|for|am|pm|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b", " ", query)
        query = re.sub(r"\b\d{1,2}(?::\d{2})?\b", " ", query)
        query = re.sub(r"\b\d+\s*(min|mins|minutes|hour|hours|hr|hrs)\b", " ", query)
        query = re.sub(r"\s+", " ", query).strip()
        parsed["query"] = query.title() if query else normalized

    return parsed


def parse_meeting_instruction(text: str) -> Dict[str, str]:
    if not GROQ_API_KEY:
        return local_parse_meeting_instruction(text)

    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Parse this text into JSON only: {text}"},
        ],
        "max_tokens": 250,
        "temperature": 0,
    }
    try:
        response = requests.post(GROQ_API_URL, headers=HEADERS, json=payload, timeout=30)
        response.raise_for_status()
    except requests.RequestException:
        parsed = local_parse_meeting_instruction(text)
        parsed["warning"] = "LLM parser unavailable; used local parser fallback."
        return parsed
    result = response.json()
    content = result.get("choices", [{}])[0].get("message", {}).get("content", "").strip()

    if content.startswith("{") and content.endswith("}"):
        parsed = json.loads(content)
        parsed["source"] = "groq"
        return parsed

    start = content.find("{")
    end = content.rfind("}")
    if start >= 0 and end >= 0:
        parsed = json.loads(content[start : end + 1])
        parsed["source"] = "groq"
        return parsed

    return local_parse_meeting_instruction(text)
