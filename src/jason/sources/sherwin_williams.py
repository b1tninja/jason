"""Sherwin-Williams color catalog: every color's number, name, RGB, hex, LRV, and family, from the site's open API.

Read from ``www.sherwin-williams.com.har`` (October 3, 2026), a visit to a color page on the public site. The page's
script calls three things on ``api.sherwin-williams.com``, none with a login, key, or cookie (the browser sent only
``Origin`` and ``Referer`` of the site, and the API answers CORS for them):

- ``GET /prism/v1/colors/sherwin?lng=en-US`` is the whole catalog in one answer: a JSON list of every color (2,004 on
  the day, about 280 KB gzipped, ``Cache-Control: public, max-age=592627``, so a week). A color is its
  ``colorNumber`` ("7027", no "SW"), ``name``, ``hex`` ("#564537"), ``red``/``green``/``blue``, ``lrv`` (light
  reflectance value), ``lab``, ``colorFamilyNames``, ``brandedCollectionNames``, ``isExterior``/``isInterior``,
  ``storeStripLocator``, ``archived`` (discontinued), and ``ignore`` (not shown on the site). ``similarColors`` and
  ``coordinatingColors`` hold catalog ids, not numbers.
- ``GET /shared-color-service/color/byColorNumber/SW7027`` is one color's page data: the same fields as strings, its
  description, the ``coordinatingColors`` and ``similarColors`` with names and hex, and its color strip.
- ``GET /colorsamples/items/all?color=SW7027`` lists the sample SKUs for sale (a chip, a peel-and-stick sample, a
  quart sample), with prices. This reader does not use it.

The page's own calls to ``prism.sherwin-williams.com`` are the site's color-visualizer assets, and scene7 serves the
images; neither is needed for the color data. This client only reads, and keeps the catalog on disk so a lookup is one
request a week, not one a color.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx

API = "https://api.sherwin-williams.com"
CATALOG_PATH = "/prism/v1/colors/sherwin"
DETAIL_PATH = "/shared-color-service/color/byColorNumber/{number}"
HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Origin": "https://www.sherwin-williams.com",
    "Referer": "https://www.sherwin-williams.com/",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36",
}
MAX_AGE = timedelta(days=7)
NUMBER_RE = re.compile(r"^(?:SW)?\s*(\d{4,5})$", re.IGNORECASE)


class SherwinWilliamsError(Exception):
    """The API answered with something this reader does not understand."""


def number_of(code: str) -> str:
    """"SW 7027", "sw7027", and "7027" are all "7027". Raises ``ValueError`` for a code that is not a number of the
    catalog's (a roof tile's "1FACS 0024")."""
    match = NUMBER_RE.match(code.strip().replace("-", ""))
    if not match:
        raise ValueError(f"not a Sherwin-Williams color number: {code!r}")
    return match.group(1)


def display_number(code: str) -> str:
    return f"SW {number_of(code)}"


@dataclass(frozen=True)
class SwColor:
    number: str
    name: str
    hex: str
    red: int
    green: int
    blue: int
    lrv: float
    families: tuple[str, ...]
    collections: tuple[str, ...]
    exterior: bool
    interior: bool
    archived: bool
    hidden: bool
    strip: str
    lab: tuple[float, float, float]
    id: str = ""
    coordinating_ids: tuple[str, ...] = ()
    similar_ids: tuple[str, ...] = ()

    @property
    def code(self) -> str:
        return display_number(self.number)

    @classmethod
    def from_api(cls, raw: dict[str, Any]) -> "SwColor":
        lab = raw.get("lab") or {}
        coord = raw.get("coordinatingColors") or {}
        return cls(
            number=str(raw["colorNumber"]),
            name=raw.get("name", ""),
            hex=str(raw.get("hex", "")).upper() if str(raw.get("hex", "")).startswith("#") else "#" + str(raw.get("hex", "")).upper(),
            red=int(raw.get("red", 0)),
            green=int(raw.get("green", 0)),
            blue=int(raw.get("blue", 0)),
            lrv=float(raw.get("lrv") or 0),
            families=tuple(raw.get("colorFamilyNames") or ()),
            collections=tuple(raw.get("brandedCollectionNames") or ()),
            exterior=bool(raw.get("isExterior")),
            interior=bool(raw.get("isInterior")),
            archived=bool(raw.get("archived")),
            hidden=bool(raw.get("ignore")),
            strip=raw.get("storeStripLocator") or "",
            lab=(float(lab.get("L", 0)), float(lab.get("A", 0)), float(lab.get("B", 0))),
            id=str(raw.get("id", "")),
            # the white first, as the color's own page lists them; ids, resolved against the same catalog
            coordinating_ids=tuple(
                str(coord[k]) for k in ("whiteColorId", "coord1ColorId", "coord2ColorId") if coord.get(k)
            ),
            similar_ids=tuple(str(i) for i in raw.get("similarColors") or ()),
        )

    def distance(self, other: "SwColor") -> float:
        """CIE76 color difference: about 2.3 is the least a person notices, and under 1 is the same to the eye."""
        return sum((a - b) ** 2 for a, b in zip(self.lab, other.lab)) ** 0.5


class SherwinWilliams:
    """The catalog, fetched once and kept in ``cache`` (a JSON file). ``SherwinWilliams(cache).color("SW 7027")``."""

    def __init__(self, cache: Path | None = None, *, http: httpx.Client | None = None, timeout: float = 60.0) -> None:
        self.cache = cache
        self._http = http or httpx.Client(timeout=timeout, headers=HEADERS, follow_redirects=True)
        self._owns_http = http is None
        self._colors: dict[str, SwColor] | None = None
        self.fetched: datetime | None = None

    def close(self) -> None:
        if self._owns_http:
            self._http.close()

    def __enter__(self) -> "SherwinWilliams":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def _get(self, path: str, **params: str) -> Any:
        response = self._http.get(API + path, params=params or None, headers=HEADERS)
        if response.status_code != 200:
            raise SherwinWilliamsError(f"{path}: HTTP {response.status_code}")
        try:
            return response.json()
        except ValueError as exc:
            raise SherwinWilliamsError(f"{path}: not JSON") from exc

    def _read_cache(self) -> tuple[list[dict[str, Any]], datetime] | None:
        if not self.cache or not self.cache.exists():
            return None
        try:
            stored = json.loads(self.cache.read_text(encoding="utf-8"))
            return stored["colors"], datetime.fromisoformat(stored["fetched"])
        except (OSError, ValueError, KeyError):
            return None

    def load(self, *, refresh: bool = False) -> dict[str, SwColor]:
        """The catalog by number. From the cache while it is under a week old, else from the API (and cached)."""
        if self._colors is not None and not refresh:
            return self._colors
        stored = None if refresh else self._read_cache()
        if stored and datetime.now(timezone.utc) - stored[1] < MAX_AGE:
            raw, self.fetched = stored
        else:
            raw = self._get(CATALOG_PATH, lng="en-US")
            if not isinstance(raw, list) or not raw:
                raise SherwinWilliamsError("the catalog came back empty")
            self.fetched = datetime.now(timezone.utc)
            if self.cache:
                self.cache.parent.mkdir(parents=True, exist_ok=True)
                self.cache.write_text(
                    json.dumps({"fetched": self.fetched.isoformat(), "colors": raw}), encoding="utf-8"
                )
        self._colors = {c.number: c for c in map(SwColor.from_api, raw)}
        return self._colors

    def load_offline(self) -> dict[str, SwColor] | None:
        """The catalog from the copy on disk whatever its age, and never from the API: None when there is no copy.
        ``self.fetched`` is set to when the copy was made, so a reader can say how old it is. A screen reads this way."""
        if self._colors is None:
            stored = self._read_cache()
            if stored is None:
                return None
            raw, self.fetched = stored
            self._colors = {c.number: c for c in map(SwColor.from_api, raw)}
        return self._colors

    def color(self, code: str) -> SwColor | None:
        """One color by number ("SW 7027", "7027"), or None when the catalog has none (or the code is not a number)."""
        try:
            return self.load().get(number_of(code))
        except ValueError:
            return None

    def search(self, text: str, *, limit: int = 20) -> list[SwColor]:
        """Colors whose name contains the text, or whose number starts with it. Discontinued colors come last."""
        needle = re.sub(r"[^a-z0-9]", "", text.lower().replace("grey", "gray"))
        hits = [
            c
            for c in self.load().values()
            if needle and (needle in re.sub(r"[^a-z0-9]", "", c.name.lower()) or c.number.startswith(needle.lstrip("sw")))
        ]
        return sorted(hits, key=lambda c: (c.archived, c.name))[:limit]

    def nearest(self, color: SwColor, *, count: int = 5, exterior: bool | None = None) -> list[tuple[float, SwColor]]:
        """The catalog's closest colors to this one (not itself, not discontinued), by CIE76 distance."""
        pool = [
            c
            for c in self.load().values()
            if c.number != color.number and not c.archived and (exterior is None or c.exterior == exterior)
        ]
        return sorted(((color.distance(c), c) for c in pool), key=lambda pair: pair[0])[:count]

    def related(self, code: str, *, descriptions: Path | bool = False) -> dict[str, Any]:
        """A color's coordinating and similar colors, resolved from the catalog already on disk: no call per color.
        The shape is ``detail``'s (``coordinatingColors``, ``similarColors``, ``description``), so a page takes either.
        The prose description is only in ``detail``; ``descriptions`` (True, or a folder to keep them in) fetches it."""
        colors = self.load()
        color = self.color(code)
        if color is None:
            return {}
        by_id = {c.id: c for c in colors.values()}

        def shape(c: SwColor) -> dict[str, str]:
            return {"number": "SW" + c.number, "name": c.name, "hex": c.hex.lstrip("#")}

        text: list[str] = []
        if descriptions:
            folder = descriptions if isinstance(descriptions, Path) else None
            text = list(self.detail(code, cache_dir=folder).get("description") or ())
        return {
            "coordinatingColors": [shape(by_id[i]) for i in color.coordinating_ids if i in by_id],
            "similarColors": [shape(by_id[i]) for i in color.similar_ids if i in by_id],
            "description": text,
        }

    def detail(self, code: str, *, cache_dir: Path | None = None) -> dict[str, Any]:
        """One color's page data (description, coordinating and similar colors, strip), live from the API; kept under
        ``cache_dir`` for a week when one is given."""
        key = display_number(code).replace(" ", "")
        file = cache_dir / f"{key}.json" if cache_dir else None
        if file and file.exists() and datetime.now() - datetime.fromtimestamp(file.stat().st_mtime) < MAX_AGE:
            try:
                return json.loads(file.read_text(encoding="utf-8"))
            except ValueError:
                pass
        data = self._get(DETAIL_PATH.format(number=key))
        if file:
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_text(json.dumps(data), encoding="utf-8")
        return data
