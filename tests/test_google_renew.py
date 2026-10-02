"""A Gmail sync outlives its hour-long access token: on a 401 the client renews once, and workers share the renewal."""

from __future__ import annotations

import httpx

from jason.google import gmail as gm
from jason.google.drive import GoogleDrive
from jason.google.gmail import GoogleGmail


def _fast(monkeypatch) -> None:
    monkeypatch.setattr(gm, "_wait_turn", lambda: None)


def test_a_401_renews_the_token_once_and_asks_again(monkeypatch) -> None:
    _fast(monkeypatch)
    seen: list[str] = []

    def answer(request: httpx.Request) -> httpx.Response:
        seen.append(request.headers["Authorization"])
        if request.headers["Authorization"] == "Bearer old":
            return httpx.Response(401, json={"error": {"message": "invalid"}})
        return httpx.Response(200, json={"id": "m1", "threadId": "t1", "payload": {"headers": []}})

    renewals = []

    def renew() -> str:
        renewals.append(1)
        return "new"

    gmail = GoogleGmail("old", http=httpx.Client(transport=httpx.MockTransport(answer)), renew=renew)
    assert gmail.get_metadata("m1")["id"] == "m1"
    assert seen == ["Bearer old", "Bearer new"] and renewals == [1]
    # A second worker holding the stale header does not renew again.
    assert gmail._renewed("Bearer old") == {"Authorization": "Bearer new"} and renewals == [1]


def test_without_a_refresh_token_a_401_is_the_callers(monkeypatch) -> None:
    _fast(monkeypatch)
    gmail = GoogleGmail("old", http=httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(401, json={}))))
    try:
        gmail.get_metadata("m1")
    except Exception as exc:
        assert "401" in str(exc)
    else:
        raise AssertionError("a 401 with no way to renew must fail")


def test_drive_hands_its_renewal_to_gmail() -> None:
    tokens = iter(["first", "second"])

    def answer(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"access_token": next(tokens)})

    drive = GoogleDrive.from_refresh_token(client_id="c", client_secret="s", refresh_token="r",
                                           http=httpx.Client(transport=httpx.MockTransport(answer)))
    gmail = drive.gmail()
    assert gmail._token == "first" and gmail._renewed("Bearer first") == {"Authorization": "Bearer second"}
