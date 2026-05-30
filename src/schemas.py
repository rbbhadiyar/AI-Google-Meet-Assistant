from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, EmailStr

class OAuthUrlResponse(BaseModel):
    auth_url: str

class Attendee(BaseModel):
    email: EmailStr

class ScheduleRequest(BaseModel):
    summary: str
    description: Optional[str] = None
    start_datetime: datetime
    end_datetime: datetime
    attendees: Optional[List[Attendee]] = []

class ListRequest(BaseModel):
    max_results: Optional[int] = 10
    date: Optional[str] = None

class CancelRequest(BaseModel):
    event_id: Optional[str] = None
    query: Optional[str] = None

class RescheduleRequest(BaseModel):
    event_id: Optional[str] = None
    query: Optional[str] = None
    new_start: datetime
    new_end: datetime

class ParseRequest(BaseModel):
    text: str
