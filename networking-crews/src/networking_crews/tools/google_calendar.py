from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import os
import json


class CalendarCheckInput(BaseModel):
    action: str = Field(
        description="'check' to verify availability, 'create' to create an event"
    )
    date: str = Field(description="Date in ISO format YYYY-MM-DD")
    time_from: str = Field(description="Start time HH:MM")
    time_to: str = Field(description="End time HH:MM")
    title: str | None = Field(default=None, description="Event title (for create)")
    location: str | None = Field(default=None, description="Location (for create)")
    description: str | None = Field(
        default=None, description="Description (for create)"
    )


class GoogleCalendarTool(BaseTool):
    name: str = "google_calendar"
    description: str = (
        "Work with Google Calendar. Two modes: "
        "'check' - verify if a time slot is free, "
        "'create' - create an event with reminders (24h and 2h before)."
    )
    args_schema: type[BaseModel] = CalendarCheckInput

    def _run(
        self,
        action: str,
        date: str,
        time_from: str,
        time_to: str,
        title: str = None,
        location: str = None,
        description: str = None,
    ) -> str:
        creds = Credentials.from_authorized_user_info(
            json.loads(os.environ["GOOGLE_CALENDAR_CREDENTIALS"])
        )
        service = build("calendar", "v3", credentials=creds)

        if action == "check":
            events = (
                service.events()
                .list(
                    calendarId="primary",
                    timeMin=f"{date}T{time_from}:00Z",
                    timeMax=f"{date}T{time_to}:00Z",
                    singleEvents=True,
                )
                .execute()
            )
            conflicts = events.get("items", [])
            if conflicts:
                names = [e.get("summary", "Unnamed") for e in conflicts]
                return (
                    f"CONFLICT: {len(conflicts)} events found: {', '.join(names)}"
                )
            return "FREE: no conflicts"

        elif action == "create":
            event = {
                "summary": title,
                "location": location,
                "description": description,
                "start": {
                    "dateTime": f"{date}T{time_from}:00",
                    "timeZone": "UTC",
                },
                "end": {
                    "dateTime": f"{date}T{time_to}:00",
                    "timeZone": "UTC",
                },
                "reminders": {
                    "useDefault": False,
                    "overrides": [
                        {"method": "popup", "minutes": 1440},  # 24 hours
                        {"method": "popup", "minutes": 120},  # 2 hours
                    ],
                },
            }
            created = (
                service.events()
                .insert(calendarId="primary", body=event)
                .execute()
            )
            return f"CREATED: {created['id']}"

        return "ERROR: unknown action"
