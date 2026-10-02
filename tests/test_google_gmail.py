"""Gmail helper lists messages and fetches one with format=full."""

import json

import httpx

from jason.google.errors import GoogleError
from jason.google.gmail import GoogleGmail


class _Http:
    def __init__(self, responses: list[httpx.Response]) -> None:
        self.responses = list(responses)
        self.calls: list[tuple[str, str]] = []
        self.params: list[dict | None] = []

    def get(self, url, *, params=None, headers=None):
        self.calls.append(("GET", url))
        self.params.append(params)
        return self.responses.pop(0)

    def close(self) -> None:
        return None


def _response(status: int, body: dict | bytes, *, text: str = "") -> httpx.Response:
    content = body if isinstance(body, bytes) else json.dumps(body).encode()
    return httpx.Response(status, content=content, text=text or content.decode())


def test_list_messages_returns_id_and_thread():
    http = _Http(
        [
            _response(
                200,
                {
                    "messages": [
                        {"id": "m1", "threadId": "t1"},
                        {"id": "m2", "threadId": "t2"},
                    ]
                },
            )
        ]
    )
    gmail = GoogleGmail("token", http=http)  # type: ignore[arg-type]
    rows = gmail.list_messages("from:board@example.com", max_results=5)
    assert rows == [
        {"id": "m1", "threadId": "t1"},
        {"id": "m2", "threadId": "t2"},
    ]
    assert http.calls[0] == (
        "GET",
        "https://gmail.googleapis.com/gmail/v1/users/me/messages",
    )
    assert http.params[0] == {"q": "from:board@example.com", "maxResults": 5}


def test_get_message_uses_format_full():
    http = _Http(
        [
            _response(
                200,
                {
                    "id": "m1",
                    "threadId": "t1",
                    "snippet": "hello",
                    "payload": {"mimeType": "text/plain"},
                },
            )
        ]
    )
    gmail = GoogleGmail("token", http=http)  # type: ignore[arg-type]
    message = gmail.get_message("m1")
    assert message["id"] == "m1"
    assert message["threadId"] == "t1"
    assert http.calls[0] == (
        "GET",
        "https://gmail.googleapis.com/gmail/v1/users/me/messages/m1",
    )
    assert http.params[0] == {"format": "full"}


def test_list_messages_raises_google_error_on_non_200():
    http = _Http(
        [
            _response(
                403,
                {"error": {"message": "Insufficient Permission"}},
            )
        ]
    )
    gmail = GoogleGmail("token", http=http)  # type: ignore[arg-type]
    try:
        gmail.list_messages("in:inbox")
    except GoogleError as exc:
        assert "403" in str(exc)
        assert "Insufficient Permission" in str(exc)
    else:
        raise AssertionError("expected GoogleError")


def test_get_message_raises_google_error_on_non_200():
    http = _Http([_response(404, {"error": {"message": "Not Found"}})])
    gmail = GoogleGmail("token", http=http)  # type: ignore[arg-type]
    try:
        gmail.get_message("missing")
    except GoogleError as exc:
        assert "404" in str(exc)
        assert "Not Found" in str(exc)
    else:
        raise AssertionError("expected GoogleError")


def test_missing_access_token_raises():
    try:
        GoogleGmail("")
    except GoogleError as exc:
        assert "access token" in str(exc)
    else:
        raise AssertionError("expected GoogleError")
