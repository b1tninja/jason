"""The PDF preflight: blank and near-blank pages, page facts, cleaning, renditions, and what a PDF carries.

Every PDF here is made in the test with PyMuPDF and numpy; no real document is read.
"""

from __future__ import annotations

import io
import json

import numpy as np
import pymupdf
import pytest
from PIL import Image

from jason.community import page_prep as prep
from jason.community import pdf_media, pdf_preflight as pf

W, H = 2550, 3300          # a letter page at 300 dpi

LINES = ["The association shall maintain the common area in good repair and keep the grounds in order.",
         "Each owner shall pay the regular assessment when it is due, in equal monthly installments.",
         "The board may adopt reasonable rules for the use of the common area after notice to members."]


def text_image(items, dpi=300) -> np.ndarray:
    """Black text on white at ``dpi``: items are (x_in, y_in, text, point size)."""
    doc = pymupdf.open()
    page = doc.new_page(width=612, height=792)
    for x, y, t, size in items:
        page.insert_text((x * 72, y * 72), t, fontsize=size, fontname="tiro")
    pix = page.get_pixmap(dpi=dpi, colorspace=pymupdf.csGRAY)
    g = np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width).copy()
    return np.where(g < 140, 0, 255).astype(np.uint8)


def prose_image() -> np.ndarray:
    items = [(1.0, 1.2 + 0.34 * k, LINES[k % 3], 11) for k in range(24)]
    return text_image(items)


def scan_pdf(images, *, text=None, bilevel=True) -> pymupdf.Document:
    """A PDF of full-page raster images (a scan), with an optional invisible text layer per page."""
    doc = pymupdf.open()
    for n, img in enumerate(images):
        buf = io.BytesIO()
        im = Image.fromarray(img)
        im = im.convert("1") if bilevel else im
        im.save(buf, "PNG", dpi=(300, 300))
        page = doc.new_page(width=img.shape[1] * 72 / 300, height=img.shape[0] * 72 / 300)
        page.insert_image(page.rect, stream=buf.getvalue())
        if text and text[n]:
            page.insert_textbox(pymupdf.Rect(36, 36, page.rect.width - 36, page.rect.height - 36), text[n], fontsize=8,
                                render_mode=3)
    data = doc.tobytes()
    doc.close()
    return pymupdf.open("pdf", data)


def saved(tmp_path, doc, name="scan.pdf"):
    path = tmp_path / name
    doc.save(path)
    return path


def facts_of(tmp_path, images, text=None, **kw):
    path = saved(tmp_path, scan_pdf(images, text=text))
    return pf.inspect_pdf(path, osd=False, media=False, **kw)


# --- blank and near-blank pages ----------------------------------------------------------------------------------


def dirt(img, seed=1, specks=300, hairs=3):
    rng = np.random.default_rng(seed)
    out = img.copy()
    h, w = out.shape
    for _ in range(specks):
        y, x = int(rng.integers(0, h - 4)), int(rng.integers(0, w - 4))
        s = int(rng.integers(1, 4))
        out[y:y + s, x:x + s] = 0
    for _ in range(hairs):
        y, x = int(rng.integers(100, h - 600)), int(rng.integers(100, w - 600))
        a = rng.uniform(0, np.pi / 2)
        for t in range(int(rng.integers(60, 200))):
            out[y + int(t * np.sin(a)):y + int(t * np.sin(a)) + 2, x + int(t * np.cos(a)):x + int(t * np.cos(a)) + 2] = 0
    return out


def test_a_blank_page_is_blank_even_dirty(tmp_path):
    blank = np.full((H, W), 255, np.uint8)
    dirty = dirt(blank)
    dirty[:, :14] = 0                      # the scanner's edge shadow
    f = facts_of(tmp_path, [blank, dirty, prose_image()])
    assert [p.blank for p in f.pages][0] is pf.Blank.BLANK
    assert f.pages[2].blank is pf.Blank.CONTENT
    assert f.pages[1].blank in (pf.Blank.BLANK, pf.Blank.MARKED)      # dust is never content
    assert f.pages[1].blank is not pf.Blank.CONTENT


@pytest.mark.parametrize("items", [
    [(4.2, 10.5, "7", 10)],                                   # a page number
    [(4.1, 10.5, "12", 9)],
    [(3.0, 5.0, "RECEIVED", 30)],                             # a stamp
    [(3.0, 5.0, "This page intentionally left blank", 14)],
])
def test_a_near_blank_page_is_marked_never_blank(tmp_path, items):
    f = facts_of(tmp_path, [text_image(items)])
    assert f.pages[0].blank is pf.Blank.MARKED
    assert f.pages[0].why
    assert pf.recommend(f)                                    # something is still to be done with it, not "nothing"
    assert all(r.action is not pf.Action.NOTHING for r in pf.recommend(f))


def test_a_signature_is_marked(tmp_path):
    img = np.full((H, W), 255, np.uint8)
    t = np.linspace(0, 6 * np.pi, 3000)
    xs = (900 + 1.6 * t * 40 / 6).astype(int) + (np.sin(t) * 30).astype(int)
    ys = (2300 + np.cos(t * 1.3) * 60).astype(int)
    for x, y in zip(xs, ys):
        img[y:y + 5, x:x + 5] = 0
    f = facts_of(tmp_path, [img])
    assert f.pages[0].blank is pf.Blank.MARKED


def test_a_left_blank_note_in_the_text_layer_is_marked(tmp_path):
    f = facts_of(tmp_path, [np.full((H, W), 255, np.uint8)], text=["This page is intentionally left blank."])
    assert f.pages[0].blank is pf.Blank.MARKED
    assert "left blank" in f.pages[0].why


def test_punch_holes_are_not_marks():
    img = np.full((1100, 850), 255, np.uint8)
    yy, xx = np.mgrid[0:1100, 0:850]
    for y in (275, 550, 825):
        ring = (np.hypot(yy - y, xx - 45) < 14) & (np.hypot(yy - y, xx - 45) > 11)
        img[ring] = 0
    ink = pf.ink_of(img, 100)
    kind, _ = pf.classify_blank(ink, "")
    assert kind is pf.Blank.BLANK


def test_blank_pages_stay_in_the_original_and_out_of_the_rendition(tmp_path):
    path = saved(tmp_path, scan_pdf([prose_image(), np.full((H, W), 255, np.uint8), prose_image()]))
    before = path.read_bytes()
    f = pf.inspect_pdf(path, osd=False, media=False)
    folder = pf.write_rendition(f, tmp_path / "store", variant="scanned", pdf=True)
    rec = json.loads((folder / "rendition.json").read_text())
    assert rec["blank"] == [1] and set(rec["pages"]) == {"0", "2"}
    assert (folder / "page-0001.png").is_file() and not (folder / "page-0002.png").exists()
    assert path.read_bytes() == before                         # the original is not touched
    assert folder.parent == tmp_path / "store" and path.parent == tmp_path
    with pymupdf.open(folder / "clean.pdf") as clean:
        assert clean.page_count == 2 and not clean[0].get_text().strip()      # an image has no text layer
    assert pf.rendition_dir(tmp_path / "store", f.sha256) == folder


# --- page facts ---------------------------------------------------------------------------------------------------


def test_page_facts_of_a_scan(tmp_path):
    f = facts_of(tmp_path, [prose_image()])
    p = f.pages[0]
    assert p.colour is pf.ColorMode.BILEVEL
    assert p.dpi == 300 and p.codec
    assert abs(p.width_in - 8.5) < 0.01 and abs(p.height_in - 11) < 0.01
    assert p.text_chars == 0 and p.blank is pf.Blank.CONTENT and "no text layer" in p.why
    rows = pf.recommend(f)
    assert rows[0].action is pf.Action.OCR_MISSING and rows[0].pages == (0,)


def test_color_and_gray_modes(tmp_path):
    rgb = np.dstack([np.full((600, 450), 255, np.uint8)] * 3)
    rgb[100:300, 100:300] = (220, 30, 30)
    gray_rgb = np.dstack([np.full((600, 450), 200, np.uint8)] * 3)
    doc = pymupdf.open()
    for arr in (rgb, gray_rgb):
        buf = io.BytesIO()
        Image.fromarray(arr).save(buf, "PNG")
        page = doc.new_page(width=450 * 72 / 100, height=600 * 72 / 100)
        page.insert_image(page.rect, stream=buf.getvalue())
    path = saved(tmp_path, doc, "c.pdf")
    f = pf.inspect_pdf(path, osd=False, media=False)
    assert f.pages[0].colour is pf.ColorMode.COLOUR
    assert f.pages[1].colour is pf.ColorMode.GREY
    assert f.pages[0].dpi == 100


def test_skew_is_measured_and_a_tilted_page_is_cleaned(tmp_path):
    straight = prose_image()
    tilted = prep.rotate(straight, 2.0)
    s_angle, _ = prep.estimate_skew(tilted, 300.0)
    assert s_angle is not None and abs(s_angle - 2.0) < 0.3
    f = facts_of(tmp_path, [straight, tilted])
    assert f.pages[0].steps == () and "deskew" in f.pages[1].steps
    assert abs(f.pages[1].skew - 2.0) < 0.3


def test_auto_cleaning_leaves_a_clean_page_as_it_was():
    page = prose_image()
    found = prep.defects(page, 300.0)
    assert prep.steps_for(found) == ()
    out, steps = prep.auto_clean(page, 300.0, found)
    assert out is page and steps == []


def test_speckle_and_shading_are_found_and_fixed():
    rng = np.random.default_rng(5)
    page = prose_image()
    speckled = page.copy()
    m = rng.random(page.shape)
    speckled = np.where(m < 0.0075, 0, np.where(m > 0.9925, 255, speckled)).astype(np.uint8)
    assert prep.speckle(speckled) > prep.SPECKLE_MIN > prep.speckle(page)
    cleaned, steps = prep.auto_clean(speckled, 300.0)
    assert "median" in steps and prep.speckle(cleaned) < 0.01
    yy, xx = np.mgrid[0:page.shape[0], 0:page.shape[1]]
    shaded = np.clip(page * (1.0 - 0.45 * (xx / page.shape[1]) - 0.25 * (yy / page.shape[0])), 0, 255).astype(np.uint8)
    assert prep.unevenness(shaded) > prep.UNEVEN_MIN > prep.unevenness(page)
    flat, steps = prep.auto_clean(shaded, 300.0)
    assert "flatten" in steps
    assert prep.unevenness(flat) < prep.UNEVEN_MIN


def test_image_operations_keep_their_contracts():
    page = prose_image()
    assert prep.otsu_threshold(page) in range(0, 255)
    assert set(np.unique(prep.binarize_global(page))) <= {0, 255}
    assert prep.sauvola(page, 51).shape == page.shape
    assert prep.niblack(page, 51).shape == page.shape
    assert prep.median(page, 3).shape == page.shape
    assert prep.blur(page, 0.8).dtype == np.uint8
    c = prep.clahe(prep.blur(page, 1.0))
    assert c.shape == page.shape and c.dtype == np.uint8
    assert prep.upscale(page[:200, :200], 1.5).shape == (300, 300)
    comps = prep.components(np.pad(np.ones((3, 4), bool), 5))
    assert len(comps) == 1 and comps[0].area == 12
    diag = np.zeros((10, 10), bool)
    diag[2, 2] = diag[3, 3] = True
    assert len(prep.components(diag)) == 1                     # 8-connected


def test_text_layer_quality_scores_a_text_layer(tmp_path):
    from jason.community.lexicon import Lexicon

    good = " ".join(LINES * 3)
    bad = " ".join("".join(chr(97 + (i * 7 + j * 3) % 26) for j in range(6)) for i in range(60))
    lex = Lexicon.from_texts([good], english=lambda w: 1.0 if w in {"the", "shall", "and", "of"} else 0.0)
    shares = pf.text_quality([good, bad, "short"], lex)
    assert shares[0][0] < 0.05 and shares[1][0] > 0.5 and shares[2][0] is None
    f = facts_of(tmp_path, [prose_image(), prose_image()], text=[good, bad], lexicon=lex)
    assert f.pages[1].suspect_share > f.pages[0].suspect_share
    again = [r for r in pf.recommend(f) if r.action is pf.Action.REREAD]
    assert again and 1 in again[0].pages


def test_report_says_what_it_found(tmp_path):
    f = facts_of(tmp_path, [prose_image(), np.full((H, W), 255, np.uint8), text_image([(4.2, 10.5, "7", 10)])])
    text = "\n".join(pf.report_lines(f))
    assert "1 blank" in text and "kept in the original" in text
    assert "kept, near blank: page 3" in text
    assert pf.ranges([0, 1, 2, 4, 6, 7]) == "1-3, 5, 7-8"


def test_orientation_reads_a_turned_page(tmp_path):
    from jason.community.ocr import TesseractCli

    if not TesseractCli.available():
        pytest.skip("Tesseract is not installed")
    page = np.ascontiguousarray(np.rot90(prose_image(), 1))     # turned a quarter
    rotation, confidence = pf.orientation(prep.downscale(page, 2.0), 150)
    assert rotation in (90, 270, None)                           # synthetic text is thin: sure of a turn, or not sure
    upright, _ = pf.orientation(prep.downscale(prose_image(), 2.0), 150)
    assert upright in (0, None)


def test_a_rendition_can_be_read_by_tesseract(tmp_path):
    from jason.community.ocr import TesseractCli

    if not TesseractCli.available():
        pytest.skip("Tesseract is not installed")
    path = saved(tmp_path, scan_pdf([prose_image()]))
    f = pf.inspect_pdf(path, osd=False, media=False)
    folder = pf.write_rendition(f, tmp_path / "store")
    out = pf.ocr_rendition(folder)
    assert "association" in out.read_text(encoding="utf-8").lower()
    assert json.loads((folder / "ocr.pages.json").read_text())["0"]
    words = json.loads((folder / "ocr.words.json").read_text())
    assert words and {"page", "left", "top", "conf", "text"} <= set(words[0]) and 0 <= words[0]["conf"] <= 100


def test_variants_apply_in_order_and_unknown_is_refused():
    page = prose_image()
    out, steps = pf.apply_variant(page, "smooth")
    assert steps == ["blur", "median"] and out.shape == page.shape
    same, none = pf.apply_variant(page, "scanned")
    assert same is page and none == []
    with pytest.raises(KeyError):
        pf.apply_variant(page, "nonsense")
    assert pf.DEFAULT_VARIANT in pf.VARIANTS


def test_the_command_is_registered():
    from jason.cli import build_parser

    args = build_parser().parse_args(["preflight", "x.pdf", "--render", "--variant", "smooth"])
    assert args.render and args.variant == "smooth" and args.func


# --- what a PDF carries -------------------------------------------------------------------------------------------


def carrying_pdf(tmp_path):
    """A PDF with an embedded file, a FileAttachment annotation, a full-page scan, a photo, a logo, a form answer, and a
    JavaScript action."""
    doc = pymupdf.open()
    scan = doc.new_page(width=612, height=792)
    buf = io.BytesIO()
    Image.fromarray(prose_image()).convert("1").save(buf, "PNG", dpi=(300, 300))
    scan.insert_image(scan.rect, stream=buf.getvalue())
    notes = doc.new_page(width=612, height=792)
    rng = np.random.default_rng(2)
    photo = rng.integers(0, 255, (400, 600, 3), dtype=np.uint8)
    buf = io.BytesIO()
    Image.fromarray(photo).save(buf, "PNG")
    notes.insert_image(pymupdf.Rect(72, 72, 372, 272), stream=buf.getvalue())
    logo = io.BytesIO()
    Image.fromarray(np.full((40, 40, 3), 90, np.uint8)).save(logo, "PNG")
    notes.insert_image(pymupdf.Rect(500, 20, 530, 50), stream=logo.getvalue())
    doc.embfile_add("ledger.csv", b"unit,amount\n1,100\n", filename="ledger.csv", desc="the ledger")
    notes.add_file_annot(pymupdf.Point(100, 400), b"%PDF-1.4\n% an attached pdf\n", "inner.pdf", desc="attached")
    notes.add_file_annot(pymupdf.Point(130, 400), b"unit,amount\n1,100\n", "again.csv")      # same bytes as the ledger
    w = pymupdf.Widget()
    w.field_type = pymupdf.PDF_WIDGET_TYPE_TEXT
    w.field_name = "owner_unit"
    w.field_value = "12B"
    w.rect = pymupdf.Rect(72, 500, 250, 530)
    notes.add_widget(w)
    doc.xref_set_key(doc.pdf_catalog(), "OpenAction", "<</S/JavaScript/JS(app.alert\\(1\\))>>")
    return saved(tmp_path, doc, "carry.pdf")


def test_a_pdf_carries_attachments_images_form_answers_and_flags(tmp_path):
    path = carrying_pdf(tmp_path)
    f = pf.inspect_pdf(path, osd=False)
    c = f.carried
    kinds = [m.kind for m in c.media]
    assert kinds.count(pdf_media.MediaKind.ATTACHMENT) == 3
    assert pdf_media.MediaKind.SCAN in kinds and pdf_media.MediaKind.IMAGE in kinds
    assert kinds.count(pdf_media.MediaKind.DECORATION) == 1        # the logo is listed, never read
    ledger = next(m for m in c.media if m.name == "ledger.csv")
    assert ledger.parent == f.sha256 and ledger.page is None and ledger.depth == 1
    assert ledger.size == len(b"unit,amount\n1,100\n") and ledger.sha256 and ledger.mime == "text/csv"
    inner = next(m for m in c.media if m.name == "inner.pdf")
    assert inner.page == 1 and inner.mime == "application/pdf"
    assert [(x.name, x.value) for x in c.fields] == [("owner_unit", "12B")]
    assert "javascript" in c.flags
    text = "\n".join(pf.report_lines(f))
    assert "flags: javascript" in text and "(never run)" in text and "filled form fields" in text


def test_attachments_and_photos_are_saved_by_hash_and_never_run(tmp_path):
    path = carrying_pdf(tmp_path)
    before = path.read_bytes()
    with pymupdf.open(path) as doc:
        found, files = pdf_media.carried(doc, "f" * 64)
        folder = tmp_path / "media"
        written = pdf_media.save(folder, found, files, doc)
    names = sorted(p.name for p in written)
    assert all(len(n.split(".")[0]) == 64 for n in names)            # named by sha256, never by their own names
    assert not any("ledger" in n or "inner" in n for n in names)
    assert len(written) == 3                       # the ledger, the inner PDF, and the photo; the ledger's twin is skipped
    assert (folder / "media.json").is_file()
    dup = [m for m in found.media if "duplicate" in m.note]
    assert len(dup) == 1
    assert path.read_bytes() == before


def test_an_unsafe_extension_is_saved_as_bin():
    assert pdf_media.safe_name("a" * 64, "run.exe").endswith(".bin")
    assert pdf_media.safe_name("a" * 64, "sheet.XLSX").endswith(".xlsx")
    assert pdf_media.safe_name("a" * 64, "noext").endswith(".bin")
    assert pdf_media.sniff_mime("x.bin", b"%PDF-1.7") == "application/pdf"


def test_a_locked_pdf_is_reported_not_cracked(tmp_path):
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), "private")
    path = tmp_path / "locked.pdf"
    doc.save(path, encryption=pymupdf.PDF_ENCRYPT_AES_256, user_pw="secret", owner_pw="owner")
    f = pf.inspect_pdf(path, osd=False)
    assert f.locked and f.encrypted and f.pages == []
    assert "not cracked" in "\n".join(pf.report_lines(f))


def test_a_permission_locked_pdf_opens_and_says_what_it_forbids(tmp_path):
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), "a visible text")
    path = tmp_path / "limited.pdf"
    doc.save(path, encryption=pymupdf.PDF_ENCRYPT_AES_256, owner_pw="owner", user_pw="",
             permissions=pymupdf.PDF_PERM_PRINT)
    f = pf.inspect_pdf(path, osd=False)
    assert not f.locked and f.encrypted and len(f.pages) == 1
    assert "copy" in f.carried.restrictions


def test_optional_content_and_annotations_are_left_off_the_drawn_page(tmp_path):
    doc = pymupdf.open()
    page = doc.new_page(width=300, height=300)
    layer = doc.add_ocg("Markup", on=True)
    page.insert_text((20, 50), "BASE TEXT", fontsize=30)
    page.insert_text((20, 120), "LAYER TEXT", fontsize=30, oc=layer)
    page.add_highlight_annot(pymupdf.Rect(20, 20, 200, 55))
    w = pymupdf.Widget()
    w.field_type = pymupdf.PDF_WIDGET_TYPE_TEXT
    w.rect = pymupdf.Rect(20, 220, 200, 260)
    w.field_name = "f"
    w.field_value = "FORM"
    w.text_fontsize = 18
    page.add_widget(w)
    path = saved(tmp_path, doc, "layers.pdf")
    with pymupdf.open(path) as d:
        flat = pf.draw_gray(d, 0, 72)
        raw = pf.draw_gray(d, 0, 72, flatten=False)

    def ink(g, a, b):
        return int((g[a:b] < 160).sum())

    assert flat.annotations == 1 and flat.fields == 1 and flat.layers_off == 1
    assert ink(raw.gray, 220, 270) > 0 and ink(flat.gray, 220, 270) == 0         # the form field is not drawn
    assert ink(raw.gray, 90, 140) > 0 and ink(flat.gray, 90, 140) == 0           # the layer is off
    assert ink(flat.gray, 20, 70) > 0                                             # the page's own text stays


def test_a_page_drawn_in_a_layer_keeps_it(tmp_path):
    doc = pymupdf.open()
    page = doc.new_page(width=300, height=300)
    layer = doc.add_ocg("Scan", on=True)
    page.insert_text((20, 120), "ALL THE PAGE", fontsize=40, oc=layer)
    path = saved(tmp_path, doc, "layer-only.pdf")
    with pymupdf.open(path) as d:
        drawn = pf.draw_gray(d, 0, 72)
    assert drawn.layers_off == 0 and "layer" in drawn.layers_kept and int((drawn.gray < 160).sum()) > 0


def test_a_native_scan_is_read_at_its_true_resolution(tmp_path):
    path = saved(tmp_path, scan_pdf([prose_image()]))
    with pymupdf.open(path) as d:
        got = pf.native_gray(d, 0)
        assert got is not None
        gray, dpi = got
        assert abs(dpi - 300) < 2 and gray.shape == (H, W) and gray.mean() > 128
        clean = pf.render_clean(d, 0, "scanned", source="native")
        assert clean.dpi == 300
