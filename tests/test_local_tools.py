import json
from pathlib import Path

from jason.community.anythingllm import AnythingLLM, AnythingLLMUnavailable, mcp_server_entry, merged_mcp_config
from jason.community.ocr import OcrReport, ocr_folder
from jason.community.ollama_extractor import READING_SCHEMA, OllamaExtractor, OllamaUnavailable, vision_models


def test_vision_models_and_the_check_read_ollama_capabilities():
    def fetch(url, payload=None):
        if url.endswith("/api/tags"):
            return {"models": [{"name": "qwen3.5:9b"}, {"name": "qwen3:14b"}]}
        if url.endswith("/api/show"):
            return {"capabilities": ["completion", "vision"] if payload["name"] == "qwen3.5:9b" else ["completion"]}
        raise AssertionError(url)

    assert vision_models(fetch=fetch) == ("qwen3.5:9b",)
    OllamaExtractor(model="qwen3.5:9b", fetch=fetch).check()
    try:
        OllamaExtractor(model="qwen3:14b", fetch=fetch).check()
    except OllamaUnavailable as exc:
        assert "not a local vision model" in str(exc)
    else:
        raise AssertionError("a text model passed the vision check")
    assert vision_models(fetch=lambda url, payload=None: (_ for _ in ()).throw(OSError("down"))) == ()


def test_the_ollama_reader_posts_page_images_with_the_schema_and_parses_the_answer(tmp_path: Path, monkeypatch):
    import jason.community.ollama_extractor as module

    monkeypatch.setattr(module, "page_images", lambda path, **kw: ["aGVsbG8="])
    sent = {}

    def fetch(url, payload):
        sent.update(payload)
        return {"message": {"content": json.dumps({"number": "201901161003", "title": "DECLARATION OF ANNEXATION AND RESERVATION OF EASEMENTS FOR MYSTIQUE, PHASE 3", "phase": 3, "annexed": {"first_unit": 1, "last_unit": 7, "association_common_area": 1}, "citations": []})}}

    reading = OllamaExtractor(model="qwen3.5:9b", fetch=fetch).extract(tmp_path / "phase3.pdf")
    assert sent["model"] == "qwen3.5:9b" and sent["format"] == READING_SCHEMA and sent["messages"][0]["images"] == ["aGVsbG8="] and sent["stream"] is False
    # Thinking off, and the annexed object required, so a thinking model does not drop the unit range.
    assert sent["think"] is False and "annexed" in READING_SCHEMA["required"]
    assert reading.number == "201901161003" and reading.phase == 3 and reading.annexed.last_unit == 7


def test_the_ollama_reader_thinks_again_only_for_a_stamp_it_could_not_read(tmp_path: Path, monkeypatch):
    import jason.community.ollama_extractor as module

    monkeypatch.setattr(module, "page_images", lambda path, **kw: ["aGVsbG8="])
    thinking = []

    def fetch(url, payload):
        thinking.append(payload["think"])
        number = "200709120758" if payload["think"] else ""
        return {"message": {"content": json.dumps({"number": number, "title": "DECLARATION", "citations": []})}}

    reading = OllamaExtractor(fetch=fetch).extract(tmp_path / "ccrs.pdf")
    assert thinking == [False, True] and reading.number == "200709120758"


def test_the_anythingllm_client_fails_fast_without_a_key_and_reads_answers_with_it():
    try:
        AnythingLLM(api_key="").workspaces()
    except AnythingLLMUnavailable as exc:
        assert "ANYTHINGLLM_API_KEY" in str(exc)
    else:
        raise AssertionError("sent without a key")
    calls = []

    def fetch(method, url, payload):
        calls.append((method, url, payload))
        if url.endswith("/workspaces"):
            return {"workspaces": [{"name": "My Workspace", "slug": "my-workspace"}]}
        if url.endswith("/documents"):
            return {"localFiles": {"items": [{"type": "folder", "items": [{"type": "file", "title": "CCRs.pdf"}]}]}}
        if url.endswith("/workspace/my-workspace/chat"):
            return {"textResponse": "Section 5.2 sets it.", "sources": [{"title": "CCRs.pdf", "text": "Section 5.2 ...", "score": 0.81}]}
        raise AssertionError(url)

    client = AnythingLLM(api_key="k", fetch=fetch)
    assert client.workspaces()[0]["slug"] == "my-workspace" and client.documents()[0]["title"] == "CCRs.pdf"
    answer = client.query("my-workspace", "which section sets the lien threshold")
    assert answer.text.startswith("Section 5.2") and answer.sources[0].title == "CCRs.pdf" and answer.sources[0].score == 0.81
    assert calls[-1][0] == "POST" and calls[-1][2] == {"message": "which section sets the lien threshold", "mode": "query"}


def test_the_mcp_entry_merges_into_an_existing_config():
    entry = mcp_server_entry(r"D:\code\jason\.venv\Scripts\jason-mcp.exe", cwd=r"D:\code\jason")
    merged = merged_mcp_config({"mcpServers": {"other": {"command": "x"}}}, entry)
    assert set(merged["mcpServers"]) == {"other", "jason"}
    assert merged["mcpServers"]["jason"]["command"].endswith("jason-mcp.exe") and merged["mcpServers"]["jason"]["anythingllm"] == {"autoStart": False}
    assert merged_mcp_config({}, entry)["mcpServers"]["jason"]["env"]["JASON_CWD"] == r"D:\code\jason"


def test_ocr_with_no_engine_writes_nothing_and_says_so(tmp_path: Path, monkeypatch):
    import jason.community.ocr as module

    monkeypatch.setattr(module, "engines", lambda: ())
    (tmp_path / "scan.pdf").write_bytes(b"%PDF-1.4")
    report = ocr_folder(tmp_path)
    assert isinstance(report, OcrReport) and report.written == [] and report.errors and "no OCR engine" in report.errors[0]
    assert "engine=none" in report.summary()

    class Fake:
        name = "fake"

        def text_of(self, path):
            return "RECORDING REQUESTED BY Doc# 201905221469"

    monkeypatch.setattr(module, "image_only", lambda path, threshold=400: True)
    report = ocr_folder(tmp_path, engine=Fake())
    assert report.engine == "fake" and report.written == [tmp_path / "scan.pdf.md"]
    assert (tmp_path / "scan.pdf.md").read_text(encoding="utf-8").startswith("# scan.pdf - ocr: `fake`")


def test_read_scans_stores_readings_and_the_request_reads_them(tmp_path: Path, monkeypatch):
    import jason.tasks.read_scans as module
    from jason.community.readings import Reader
    from jason.tasks.read_scans import model_read_numbers, read_image_only
    from tests.test_readings import MODERN

    folder = tmp_path / "artifacts" / "site-docs" / "governing_documents_Annexations"
    folder.mkdir(parents=True)
    (folder / "Annexation - Phase 4 AMENDED.pdf").write_bytes(b"%PDF-1.4")
    monkeypatch.setattr(module, "image_only", lambda path, threshold=400: True)

    class FakeReader:
        model = "fake-vision"

        def extract(self, path):
            return Reader().read(MODERN, path)

    report = read_image_only(tmp_path, FakeReader())
    assert report.read == ["Annexation - Phase 4 AMENDED.pdf"] and report.model == "fake-vision"
    numbers = model_read_numbers(tmp_path)
    assert numbers["202003021215"]["file"] == "Annexation - Phase 4 AMENDED.pdf" and numbers["202003021215"]["model"] == "fake-vision"
    again = read_image_only(tmp_path, FakeReader())
    assert again.read == [] and again.skipped == ["Annexation - Phase 4 AMENDED.pdf: already read"]


def test_the_vault_session_creates_a_login_record_and_reads_the_secret_back(monkeypatch):
    import jason.secrets as secrets
    from keepersdk.vault import record_management

    session = secrets.VaultSession()
    session._vault = object()  # already open
    made = {}

    def fake_add(vault, record, folder_uid=None):
        made["record"] = record
        return "UID123"

    monkeypatch.setattr(record_management, "add_record_to_folder", fake_add)
    uid = session.create_login_record("AnythingLLM Desktop API key", password="secret-value", url="http://localhost:3001", notes="n")
    record = made["record"]
    assert uid == "UID123" and record.record_type == "login" and record.title == "AnythingLLM Desktop API key"
    assert [(f.type, f.value) for f in record.fields] == [("login", []), ("password", ["secret-value"]), ("url", ["http://localhost:3001"])]
    monkeypatch.setattr(session, "load_record", lambda uid: record)
    assert session.get_secret("UID123") == "secret-value"


def test_the_ollama_vision_engine_reads_each_page_without_thinking(tmp_path: Path):
    import pymupdf

    from jason.community.ocr import OllamaVisionOcr, engines

    document = pymupdf.open()
    for _ in range(3):
        document.new_page()
    document.save(tmp_path / "scan.pdf")
    sent = []

    def fetch(url, payload):
        sent.append(payload)
        return {"message": {"content": f"<think>x</think>page {len(sent)}"}}

    engine = OllamaVisionOcr(model="qwen3.6:27b", max_pages=2, fetch=fetch)
    assert engine.text_of(tmp_path / "scan.pdf") == "page 1\n\npage 2"
    assert all(p["think"] is False and p["options"]["temperature"] == 0 and len(p["messages"][0]["images"]) == 1 for p in sent)
    assert not engine.available() and "ollama-vision" not in [e.name for e in engines()]


def test_the_anythingllm_collector_engine_reads_the_apps_extracted_text(tmp_path: Path):
    import json

    from jason.community.ocr import AnythingLLMCollector

    store = tmp_path / "documents" / "custom-documents"
    store.mkdir(parents=True)
    (store / "a.json").write_text(json.dumps({"title": "CCRs - 1st Amendment.pdf", "pageContent": "Doc# 202001170712 FIRST AMENDMENT"}), encoding="utf-8")
    (store / "b.json").write_text(json.dumps({"title": "Other.pdf", "pageContent": "x"}), encoding="utf-8")
    engine = AnythingLLMCollector(tmp_path / "documents")
    assert engine.available() and engine.text_of(Path("CCRs - 1st Amendment.pdf")).startswith("Doc# 202001170712")
    assert engine.text_of(Path("Missing.pdf")) == "" and not AnythingLLMCollector(tmp_path / "nowhere").available()


def test_the_board_profile_serves_a_short_list_and_anythingllm_registers_it():
    import pytest

    from jason.mcp.server import ALL_TOOLS, PROFILES, tools_for

    board = [tool.__name__ for tool in tools_for("board")]
    assert board[0] == "board_digest" and len(board) == len(PROFILES["board"]) == 38
    assert set(board) <= {tool.__name__ for tool in ALL_TOOLS} and len(tools_for("")) == len(ALL_TOOLS) == len(tools_for("all"))
    with pytest.raises(SystemExit):
        tools_for("nope")
    entry = mcp_server_entry("jason-mcp.exe", cwd="D:/code/jason")["jason"]
    assert entry["args"] == ["--profile", "board"] and entry["env"]["JASON_CWD"] == "D:/code/jason"
    assert mcp_server_entry("jason-mcp.exe", profile="all")["jason"]["args"] == []
