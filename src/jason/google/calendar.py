"""Google Calendar v3: the calendars a person sees, the events in a window, and inserting or patching an event.

jason keeps its own events apart by a private extended property (``extendedProperties.private.jason``), so a re-run
finds the event it made before and patches it. There is no delete: an event jason no longer plans is reported, and a
person removes it in Calendar.

The main Google token carries ``calendar.events``, which reads and writes events. Listing the calendars
(``calendarList``) needs ``calendar.readonly`` as well; without it that call is refused and ``primary`` still works.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Iterator
from urllib.parse import quote

import httpx

from jason.google.errors import GoogleError

API = "https://www.googleapis.com/calendar/v3"
PAGE = 250


class GoogleCalendar:
    def __init__(self, access_token: str, *, http: httpx.Client | None = None) -> None:
        if not access_token:
            raise GoogleError("missing access token")
        self._token = access_token
        self._owns_http = http is None
        self._http = http or httpx.Client(timeout=60.0)

    @classmethod
    def from_drive(cls, drive: Any, *, http: httpx.Client | None = None) -> GoogleCalendar:
        """A client on the Drive client's token (the main Google token, which carries ``calendar.events``)."""
        header = drive._headers().get("Authorization", "")
        return cls(header.removeprefix("Bearer ").strip(), http=http)

    def close(self) -> None:
        if self._owns_http:
            self._http.close()

    def __enter__(self) -> GoogleCalendar:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token}"}

    def _call(self, method: str, path: str, *, params: dict[str, Any] | None = None, json_body: Any = None) -> dict[str, Any]:
        response = self._http.request(method, f"{API}{path}", params=params, json=json_body, headers=self._headers())
        if not response.is_success:
            try:
                message = response.json().get("error", {}).get("message", "")
            except Exception:
                message = response.text[:200]
            raise GoogleError(f"HTTP {response.status_code} {method} {path}: {message}")
        return response.json() if response.content else {}

    def calendars(self) -> Iterator[dict[str, Any]]:
        """The calendars on the person's list: ``id``, ``summary``, ``accessRole``, ``primary``, ``timeZone``."""
        params: dict[str, Any] = {"maxResults": PAGE}
        while True:
            body = self._call("GET", "/users/me/calendarList", params=params)
            yield from body.get("items") or []
            if not body.get("nextPageToken"):
                return
            params["pageToken"] = body["nextPageToken"]

    def events(self, calendar_id: str, *, time_min: datetime, time_max: datetime,
               private: dict[str, str] | None = None) -> Iterator[dict[str, Any]]:
        """Events that overlap the window, recurring ones expanded, in start order. ``private`` keeps only events with
        each of those private extended properties."""
        params: dict[str, Any] = {"singleEvents": "true", "orderBy": "startTime", "maxResults": PAGE,
                                  "timeMin": time_min.isoformat(), "timeMax": time_max.isoformat()}
        if private:
            params["privateExtendedProperty"] = [f"{k}={v}" for k, v in private.items()]
        while True:
            body = self._call("GET", f"/calendars/{quote(calendar_id, safe='')}/events", params=params)
            yield from body.get("items") or []
            if not body.get("nextPageToken"):
                return
            params["pageToken"] = body["nextPageToken"]

    def insert(self, calendar_id: str, event: dict[str, Any]) -> dict[str, Any]:
        """Create the event; no invitation is sent (``sendUpdates=none``)."""
        return self._call("POST", f"/calendars/{quote(calendar_id, safe='')}/events", params={"sendUpdates": "none"},
                          json_body=event)

    def patch(self, calendar_id: str, event_id: str, fields: dict[str, Any]) -> dict[str, Any]:
        """Change the given fields of an event; no update is sent to guests."""
        return self._call("PATCH", f"/calendars/{quote(calendar_id, safe='')}/events/{quote(event_id, safe='')}",
                          params={"sendUpdates": "none"}, json_body=fields)


__all__ = ["API", "GoogleCalendar"]
