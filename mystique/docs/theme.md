# Theme: where the brand lives

The association's brand for the console and its public owner page is the one `Theme` row in `mystique/theme.py`
(`THEME`), returned by `Mystique.theme()`. It carries the wordmark, the accent and the text that sits on it, the gold
second accent, the brand serif (Gloock, 400, uppercase, .2em tracking) with its Google Fonts stylesheet URL, the hero
surface the public page and the meeting stage use, the dark-scheme overrides (a lighter accent, so near-black text on
it), and the public page's surface layer (warm paper, 14px cards, a 22px hero, pill buttons).

The values came from the design handoff of October 3, 2026 (`themes/mystique.css` and the README's token table). The
console applies them through `GET /api/theme` on `[data-community="mystique"]`; nothing in `src/jason/` or `ui/src/`
names them. To change the brand, change the row; a second association gets its own row in its own profile, never a
second member here.

The public owner page (`GET /api/community-profile`) shows this association's site pages (`anchors.py`), its current
mailing address (`mail.py`), the groups owners may write to (`groups.py`: general, management, board, architectural),
the board calendar (`calendar_id`), and the Civil Code 5200 record kinds with whether each is on file. The association's
public site URL is the `site` property on `Mystique`, which the base class does not yet carry; the page shows paths
alone for a profile without it.
