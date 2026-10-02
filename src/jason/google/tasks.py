"""Google Tasks (``tasks.googleapis.com/tasks/v1``): the signed-in account's task lists and tasks.

A task list belongs to one Google account; it is not shared with other people the way a Sheet is. jason keeps the
board's action items as one list in the association's account, a reminder beside Gmail and Calendar, while the Sheet stays
the record the directors share. A task carries no private properties, so jason finds its own tasks by a marker line in
the notes (``jason:<item id>``). There is no delete: a task jason no longer plans is reported, and a person removes it.

The ``tasks`` scope rides on a token of its own (``google-tasks-token.json``), so granting it never asks Drive to consent
again; the first run needs a person's consent in a browser (``--interactive``).
"""

from __future__ import annotations

from typing import Any, Iterator

import httpx

from jason.google.errors import GoogleError

API = "https://tasks.googleapis.com/tasks/v1"
_TOKEN_URL = "https://oauth2.googleapis.com/token"
MARKER = "jason:"


class GoogleTasks:
    def __init__(self, access_token: str, *, http: httpx.Client | None = None) -> None:
        if not access_token:
            raise GoogleError("missing access token")
        self._token = access_token
        self._owns_http = http is None
        self._http = http or httpx.Client(timeout=60.0)

    @classmethod
    def from_refresh_token(cls, *, client_id: str, client_secret: str, refresh_token: str,
                           http: httpx.Client | None = None) -> GoogleTasks:
        client = http or httpx.Client(timeout=60.0)
        response = client.post(_TOKEN_URL, data={"client_id": client_id, "client_secret": client_secret,
                                                 "refresh_token": refresh_token, "grant_type": "refresh_token"})
        token = (response.json() if response.content else {}).get("access_token")
        if not token:
            raise GoogleError("the Tasks token was refused; sign in again with `jason board --tasks --interactive`")
        tasks = cls(str(token), http=client)
        tasks._owns_http = http is None
        return tasks

    def close(self) -> None:
        if self._owns_http:
            self._http.close()

    def __enter__(self) -> GoogleTasks:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def _call(self, method: str, path: str, *, params: dict[str, Any] | None = None, body: Any = None) -> dict[str, Any]:
        response = self._http.request(method, f"{API}/{path.lstrip('/')}", params=params, json=body,
                                      headers={"Authorization": f"Bearer {self._token}"})
        if not response.is_success:
            try:
                message = response.json().get("error", {}).get("message", "")
            except Exception:
                message = response.text[:200]
            raise GoogleError(f"HTTP {response.status_code} {method} {path}: {message}")
        return response.json() if response.content else {}

    def _pages(self, path: str, params: dict[str, Any]) -> Iterator[dict[str, Any]]:
        params = dict(params)
        while True:
            body = self._call("GET", path, params=params)
            yield from body.get("items") or []
            token = body.get("nextPageToken")
            if not token:
                return
            params["pageToken"] = token

    def task_lists(self) -> list[dict[str, Any]]:
        return list(self._pages("users/@me/lists", {"maxResults": 100}))

    def task_list(self, title: str) -> str:
        """The id of the list with this title, created when the account has none."""
        for tl in self.task_lists():
            if tl.get("title") == title:
                return str(tl["id"])
        return str(self._call("POST", "users/@me/lists", body={"title": title})["id"])

    def tasks(self, list_id: str) -> list[dict[str, Any]]:
        """Every task on the list, completed and hidden ones included."""
        return list(self._pages(f"lists/{list_id}/tasks", {"maxResults": 100, "showCompleted": "true", "showHidden": "true"}))

    def insert(self, list_id: str, task: dict[str, Any]) -> dict[str, Any]:
        return self._call("POST", f"lists/{list_id}/tasks", body=task)

    def patch(self, list_id: str, task_id: str, task: dict[str, Any]) -> dict[str, Any]:
        return self._call("PATCH", f"lists/{list_id}/tasks/{task_id}", body=task)


def marker_of(task: dict[str, Any]) -> str:
    """The id jason wrote in a task's notes (``jason:<id>``), or empty for a person's own task."""
    for line in (task.get("notes") or "").splitlines():
        if line.startswith(MARKER):
            return line[len(MARKER):].strip()
    return ""


__all__ = ["GoogleTasks", "MARKER", "marker_of"]
