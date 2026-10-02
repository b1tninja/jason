"""PostScanMail's account API (``https://api.postscanmail.com/api/account-docs/v2/``), read-only.

Authentication is one header, ``x-api-key``, holding the key the account owner generates in the
PostScanMail console (kept in Keeper, ``postscanmail_record_uid``).

``GET /items?sort_order=desc&page=N`` pages through every mail item, 20 to a page, newest first.
Each item carries the sender, the address it came to, a signed link to the envelope's cover image,
a signed link to the scanned contents (once scanned), PostScanMail's AI summary lines (when the
account's "Auto AI summary" rule produced one), and ``pdf_metadata``: when it arrived, its status
("Scan Complete", "Assign Complete", ...), its folder, and the user it is assigned to.

The API also accepts actions on a group of items: open (scan), discard, shred, rescan, and their
cancellations, and it can switch the account's automatic rules (auto scan, auto shred, auto
discard, auto AI summary). Those change or destroy the association's mail, and some are billed.
This client does not implement them: jason only reads.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterator

import httpx

BASE_URL = "https://api.postscanmail.com/api/account-docs/v2/"
USER_AGENT = "jason (Mystique Community Association; read-only mail sync)"


class PostScanMailError(Exception):
    """The API answered with something other than the page it documents."""


class PostScanMail:
    """Read-only PostScanMail account client."""

    def __init__(self, api_key: str, *, base_url: str = BASE_URL, http: httpx.Client | None = None, timeout: float = 60.0) -> None:
        if not api_key:
            raise PostScanMailError("no PostScanMail API key; set postscanmail_record_uid to its Keeper record")
        self._key = api_key
        self._base = base_url.rstrip("/") + "/"
        self._owns_http = http is None
        self._http = http or httpx.Client(timeout=timeout, follow_redirects=True)

    def close(self) -> None:
        if self._owns_http:
            self._http.close()

    def __enter__(self) -> PostScanMail:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def _headers(self) -> dict[str, str]:
        return {"x-api-key": self._key, "Accept": "application/json", "User-Agent": USER_AGENT}

    def items_page(self, page: int = 1, *, sort_order: str = "desc") -> dict[str, Any]:
        """One page of mail items: the page object with ``data`` (the items), ``current_page``, ``last_page``, ``total``."""
        response = self._http.get(self._base + "items", params={"sort_order": sort_order, "page": page}, headers=self._headers())
        if response.status_code in (401, 403):
            raise PostScanMailError(f"HTTP {response.status_code}: the API key was refused")
        if not response.is_success:
            raise PostScanMailError(f"HTTP {response.status_code} listing items page {page}")
        body = response.json()
        # The live API wraps the page as {"status": 1, "data": {page}}; the published example puts the items at "data".
        page_body = body.get("data") if isinstance(body.get("data"), dict) else body
        if not isinstance(page_body, dict) or not isinstance(page_body.get("data"), list):
            raise PostScanMailError("items page without a list of items")
        return page_body

    def iter_items(self, *, stop_at: set[str] | None = None, max_pages: int | None = None) -> Iterator[dict[str, Any]]:
        """Every item, newest first. With ``stop_at`` (mail ids already on disk), stop after a page made only of known items."""
        page = 1
        while True:
            body = self.items_page(page)
            items = body["data"]
            for item in items:
                yield item
            last = int(body.get("last_page") or page)
            if page >= last or not items or (max_pages and page >= max_pages):
                return
            if stop_at is not None and all(str(item.get("mail_id")) in stop_at for item in items):
                return
            page += 1

    def download(self, url: str, dest: Path) -> Path:
        """Save a signed cover-image or PDF link. The signature is the credential; the API key is not sent."""
        response = self._http.get(url, headers={"User-Agent": USER_AGENT})
        if not response.is_success:
            raise PostScanMailError(f"HTTP {response.status_code} downloading {url.split('?')[0]}")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(response.content)
        return dest


__all__ = ["PostScanMail", "PostScanMailError", "BASE_URL"]
