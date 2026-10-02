"""How Mystique keeps the photos a person picks from a shared Google Photos album.

A board member shares an album in an agenda (a photos.app.goo.gl link). The album is in that person's account; jason
cannot open it. The person picks its photos in the Google Photos Picker, jason saves them under ``data/photos``, and can
keep them in an album jason created and in a Drive folder. Each album is named by ``ALBUM_NAME``.

``PHOTOS_DRIVE_FOLDER`` is the Drive folder the copies go under. It is empty until the board picks one; until then
``jason photos --to-drive`` needs ``--drive-folder``.
"""

from __future__ import annotations

from jason.community.photos import AlbumNameRule

ALBUM_NAME = AlbumNameRule(prefix="Mystique", unlabeled="unlabeled", claim_word="claim")

PHOTOS_DRIVE_FOLDER = ""
