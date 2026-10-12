"""A stand-in for Google's Picker and Drive, for the console's end-to-end suite. Nothing here reaches Google.

The launcher (``serve_e2e.py``) installs it on its own app object, beside the other ``/__e2e/...`` routes; the shipped app has none of it.
It does three things:

- ``jason.web.pick.AUTH_URL`` (the module's address for Google's authorization endpoint) points at ``/__e2e/google/pick`` on the launcher's
  own origin, so the real start route redirects here instead of to Google. This route **checks the request the way Google's documentation
  describes it** (``trigger_onepick``, the one ``drive.file`` scope, ``access_type=online``, a ``state``, the callback as the redirect
  address) and answers 400 in words when something is missing, then sends the browser back to the real callback as Google would: with
  ``picked_file_ids`` and a ``code`` (or ``error``), according to the scenario;
- the code exchange is a function that accepts only this route's code, and the Drive client is the real ``GoogleDrive`` over an
  ``httpx.MockTransport`` holding a few made-up files;
- ``/__e2e/pick-scenario?name=ok|mixed|none|denied|badstate&reset=1`` chooses what the Picker "picks" next, and ``/__e2e/pick-last`` says what
  the start route sent.
"""

from __future__ import annotations

import dataclasses
from typing import Any
from urllib.parse import urlencode, urlsplit

import httpx

CODE = "e2e-fake-code"
PDF = "application/pdf"
FOLDER_MIME = "application/vnd.google-apps.folder"
DOC_MIME = "application/vnd.google-apps.document"
SCOPE = "https://www.googleapis.com/auth/drive.file"

ID_SCAN = "1E2eScanCombined2099aaa"
ID_MINUTES = "1E2eBoardMinutes2099bb"
ID_FOLDER = "1E2eFolderRecordsccccc"
ID_DOC = "1E2eAgendaGoogleDocddd"
ID_HUGE = "1E2eHugeScanEightHundred"
ID_GONE = "1E2eNotSharedWithJasonx"
SCENARIOS = {
    "ok": [ID_SCAN, ID_MINUTES],
    "mixed": [ID_SCAN, ID_FOLDER, ID_DOC, ID_HUGE, ID_GONE, ID_MINUTES],
    "none": [],
    "denied": [ID_SCAN],
    "badstate": [ID_SCAN],
}


def _minutes() -> bytes:
    import pymupdf

    doc = pymupdf.open()
    for text in ("Minutes of the board meeting, made up.", "Motion carried, made up."):
        doc.new_page().insert_text((72, 100), text)
    return doc.tobytes()


class FakeDriveApi:
    """Google's Drive as an HTTP stub: files by id."""

    def __init__(self) -> None:
        from jason.community import split_gold

        self.files: dict[str, dict[str, Any]] = {}
        self.bodies: dict[str, bytes] = {}
        self._add(ID_SCAN, "Combined Scan 2099.pdf", PDF, split_gold.numbered().pdf)
        self._add(ID_MINUTES, "Board Minutes 2099-06.pdf", PDF, _minutes())
        self._add(ID_FOLDER, "Records 2099", FOLDER_MIME, b"")
        self._add(ID_DOC, "Agenda 2099-06", DOC_MIME, b"")
        self._add(ID_HUGE, "Huge Scan 2099.pdf", PDF, b"", size=800 * 1024 ** 3)

    def _add(self, fid: str, name: str, mime: str, data: bytes, size: int | None = None) -> None:
        self.files[fid] = {"id": fid, "name": name, "mimeType": mime, "size": str(len(data) if size is None else size),
                           "modifiedTime": "2099-06-01T10:00:00Z", "capabilities": {"canDownload": True}}
        self.bodies[fid] = data

    def handler(self, request: httpx.Request) -> httpx.Response:
        fid = request.url.path.rsplit("/", 1)[-1]
        if request.method != "GET" or fid not in self.files:
            return httpx.Response(404, json={"error": {"code": 404, "message": "not found", "errors": [{"reason": "notFound"}]}})
        if request.url.params.get("alt") == "media":
            return httpx.Response(200, content=self.bodies[fid])
        return httpx.Response(200, json=self.files[fid])

    def client(self, token: str):
        from jason.google.drive import GoogleDrive

        return GoogleDrive(token, http=httpx.Client(transport=httpx.MockTransport(self.handler)))


def install(app: Any, origin: str) -> None:
    """Put the stand-in on ``app`` (the launcher's) and point the real pick routes at it. ``origin`` is the launcher's own."""
    from flask import jsonify, redirect, request

    from jason.tasks import drive_pick
    from jason.web import pick

    api = FakeDriveApi()
    mem: dict[str, Any] = {"scenario": "ok", "last": {}}

    def exchange(client: Any, code: str, redirect_uri: str) -> str:
        if code != CODE:
            raise pick.Refused("Google would not give jason access to the picked files (invalid_grant). Nothing was read.")
        return "e2e-fake-token"

    base = pick.default_deps()
    app.extensions[pick.KEY] = dataclasses.replace(base, exchange=exchange, drive=api.client)
    pick.AUTH_URL = f"{origin}/__e2e/google/pick"           # this process only: the real start route now leaves for the stand-in

    @app.get("/__e2e/pick-scenario")
    def e2e_pick_scenario():
        name = request.args.get("name", "ok")
        if name not in SCENARIOS:
            return jsonify(error=f"scenario is one of {', '.join(SCENARIOS)}"), 400
        mem["scenario"] = name
        removed = 0
        if request.args.get("reset"):
            removed = drive_pick.purge(pick.deps().root(), dry_run=False)["files"]
        return jsonify(ok=True, scenario=name, removed=removed)

    @app.get("/__e2e/pick-last")
    def e2e_pick_last():
        return jsonify(mem["last"])

    @app.get("/__e2e/google/pick")
    def e2e_google_pick():
        """Google's authorization endpoint with the Picker, as its documentation describes the request."""
        q = {k: v for k, v in request.args.items()}
        mem["last"] = q
        wrong = []
        if q.get("trigger_onepick") != "true":
            wrong.append("trigger_onepick=true")
        if q.get("scope") != SCOPE:
            wrong.append(f"scope={SCOPE}")
        if q.get("response_type") != "code":
            wrong.append("response_type=code")
        if q.get("access_type") != "online":
            wrong.append("access_type=online")
        if not q.get("client_id"):
            wrong.append("client_id")
        if not q.get("state"):
            wrong.append("state")
        if urlsplit(q.get("redirect_uri", "")).path != pick.CALLBACK:
            wrong.append("redirect_uri ending in the callback")
        if wrong:
            return "fake Google: bad request, missing or wrong: " + ", ".join(wrong), 400
        scenario = mem["scenario"]
        back = {"state": q["state"]}
        if scenario == "denied":
            back["error"] = "access_denied"
        else:
            back.update({"picked_file_ids": ",".join(SCENARIOS[scenario]), "code": CODE})
        if scenario == "badstate":
            back["state"] = "not-the-state-that-was-sent"
        return redirect(f"{q['redirect_uri']}?{urlencode(back)}")


__all__ = ["CODE", "FakeDriveApi", "ID_MINUTES", "ID_SCAN", "SCENARIOS", "install"]
