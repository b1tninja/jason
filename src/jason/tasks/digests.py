"""Content digests of files on disk, cached, so one file can be recognized wherever a copy of it is held.

Drive lists an MD5 for each binary file; Gmail's attachments and the PayHOA library keep a SHA-256. ``Digests`` gives
both for a local file and remembers them by path, size, and modification time in ``data/digests.json``, so a catalog
can join a Drive PDF, a Gmail attachment, and a PayHOA upload that are the same bytes. A Google Doc has no digest; its
PDF export does.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

CACHE = "digests.json"


class Digests:
    def __init__(self, data_dir: Path) -> None:
        self._path = Path(data_dir) / CACHE
        self._cache: dict[str, list] = json.loads(self._path.read_text(encoding="utf-8")) if self._path.is_file() else {}
        self._dirty = False

    def of(self, path: Path) -> tuple[str, str]:
        """(md5, sha256) of a file; empty strings when it is not on disk."""
        path = Path(path)
        if not path.is_file():
            return "", ""
        stat = path.stat()
        key = str(path.resolve())
        hit = self._cache.get(key)
        if hit and hit[0] == stat.st_size and hit[1] == int(stat.st_mtime):
            return hit[2], hit[3]
        md5, sha = hashlib.md5(), hashlib.sha256()
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                md5.update(chunk)
                sha.update(chunk)
        self._cache[key] = [stat.st_size, int(stat.st_mtime), md5.hexdigest(), sha.hexdigest()]
        self._dirty = True
        return md5.hexdigest(), sha.hexdigest()

    def save(self) -> None:
        if self._dirty:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(json.dumps(self._cache), encoding="utf-8")
            self._dirty = False


__all__ = ["Digests"]
