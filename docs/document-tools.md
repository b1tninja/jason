# Open-source tools for the scanned documents

What is on this machine, what each tool is good for, and how each joins jason without changing its layers. Survey date: 2026-09-28. The concept records in [document-readings.md](document-readings.md) are the fixed point: every tool here produces or serves them, and the scorecard there says what to trust.

## What is already here

| Tool | State on this machine | Job |
| --- | --- | --- |
| Ollama 0.34 | running on port 11434 with qwen3.5:9b, qwen3.5:27b, qwen3.6:27b (all accept images), qwen3:14b (text) | local vision model for reading page images; local text model for AnythingLLM |
| AnythingLLM Desktop | installed and running on port 3001; since 2026-09-30 its chat model is `qwen3.6:27b` on the system Ollama (models in `D:\ai\models`, 64k window, twelve passages per question; see "AnythingLLM on the GPU" below), with the native MiniLM embedder and LanceDB; at first it ran its own bundled Ollama serving `qwen3-vl:4b-instruct`; its document collector runs on port 8888; one workspace, "My Workspace", holds the governing documents uploaded 2026-09-25 (the image-only PDFs parsed to one word, since the collector does no OCR); no API key generated; no MCP servers registered (its `storage/.env` and `storage/plugins/anythingllm_mcp_servers.json` say so) | chat and retrieval over the documents with a polished front end |
| PyMuPDF 1.28 | in the venv | page rendering for the vision readers; OCR through its built-in Tesseract, given the language data |
| Docker Desktop 29 | installed | the MCP Toolkit and catalog, for later |
| Tesseract 5.4 language data | `%LOCALAPPDATA%\Programs\Tesseract-OCR` (unpacked, no installer) | `eng` and `osd` data for PyMuPDF's OCR |
| Docling, Marker | not installed | OCR into a text layer |

## The jobs and the fit

**Reading a scan into the concept records.** The local vision model is the right first tool: no key, no cost, the pages never leave the machine, and Ollama's `format` field constrains the answer to the records' JSON schema. `jason.community.ollama_extractor.OllamaExtractor` does that, and `jason read-documents --extractor ollama` scores it on the pinned cases. On the first run qwen3.5:9b read the phase 4 annexation from three page images in 105 seconds and got the stamp number, the unit range, the common-area designation, the declarant, and the rescission right; it missed the phase (it did not carry the title to its end) and the page count. The full card on the eight pinned cases, against the regex reader's:

| Field | Regex over the extracts | qwen3.5:9b over the page images | qwen3.6:27b, thinking on | qwen3.6:27b, thinking off (the reader now) |
| --- | ---: | ---: | ---: | ---: |
| Instrument number from the stamp | 8 of 8 | 8 of 8 | 8 of 8 | 8 of 8 (7 without thinking; the retry reads the eighth) |
| Phase | 7 of 7 | 0 of 7 as the model filled it, 7 of 7 once the phase is read from the title it returned | 7 of 7 | 7 of 7 |
| First unit annexed | 7 of 7 | 7 of 7 | 1 of 7 | 7 of 7 |
| Last unit annexed | 5 of 7 | 7 of 7 | 1 of 7 | 7 of 7 |
| Association common area | 7 of 7 | 7 of 7 | 2 of 7 | 7 of 7 |
| Supersession stated | 2 of 2 | 2 of 2 | 2 of 2 | 2 of 2 |
| Time for the eight | | about 30 minutes (RTX 4070 Ti SUPER) | about 25 minutes | 2 minutes 40 seconds (RTX 5090) |

**Thinking off (September 30, 2026).** With Qwen's thinking on, qwen3.6:27b left the optional `annexed` object out or put the common area under the condominium field: 103 seconds on the phase 2 annexation and no unit range. With thinking off it read every field in 12 seconds, but left the 2007 CC&Rs' stamp number empty, which thinking reads. So `OllamaExtractor` asks without thinking, asks again with thinking only when the stamp number comes back empty (an unstamped copy costs about five minutes), and the schema requires `phase` and `annexed` (null where the instrument annexes nothing). On the formerly image-only copies it matched the 9b on every stamp, unit range, and common area, and added fields the 9b left empty (recording dates, page counts, phases, the sections an amendment changes, and the declaration the annexations and amendments cite), while missing a few the 9b had. A reading is evidence. This association's findings are in its private notes (mystique/notes/document-tools.md).

The model closed the two misses the OCR-dropped digits caused and got every stamp number, and it left the phase field empty every time while putting the phase in the title, so the parser now takes the phase from the title when the field is empty. The run took about half an hour for eight files at six pages each. The 27b models are slower and may read more; the scorecard is the way to find out. On the copies no parser can read, the 9b model read every stamp it could in three to four minutes a file. `jason read-scans` keeps those readings under `data/readings/`, and the records request lists any instrument such a reading covers at its lowest priority, for a person to verify the stamp on the image before dropping the order. The Claude reader stays as the higher-accuracy option behind a key. The `read_scan` tool reads one file this way, for the copies whose text layer is empty.

**A text layer for the image-only copies.** Three governing copies extract to nothing. OCR into a `.pdf.md` beside each, in the same shape as the other extracts, puts them under the regex readers and the passage search with nothing downstream changed. `jason.community.ocr` knows two engines and `jason ocr-documents` runs whichever is installed: Docling with RapidOCR (`pip install "docling[rapidocr]"`, Python-only, runs on Python 3.14 from Docling 2.59, pulls PyTorch) or PyMuPDF with a Tesseract install. Marker with Surya is the more accurate pipeline for bad scans but also needs PyTorch and is slower on CPU. Neither of those is installed, and it turned out neither is needed for these files: AnythingLLM's document collector runs OCR on an image-only PDF at upload and keeps the text as `pageContent` in a JSON under its `storage/documents` folder. `AnythingLLMCollector` is a third engine that reads that folder, and `jason ocr-documents` used it to write the three missing text layers on 2026-09-28. The regex reader can then read a stamp and the section an amendment changes straight from that text, which takes the instrument off the copy order by the ordinary on-disk rule, no model reading needed. A stamp that comes through garbled rests on the model reading until a person checks the image.

**Retrieval and chat over the documents.** AnythingLLM already does this with a local model, and it is the polished front end a person would use. Two joins: its developer API answers a question in `query` mode with the source chunks (`jason.community.anythingllm.AnythingLLM.query`, the `anythingllm_query` tool, `jason anythingllm --ask`), which is a retriever with a real embedding ranker beside the BM25 one; and its agent loads MCP tools from `plugins/anythingllm_mcp_servers.json` in its storage folder, so registering jason-mcp there (`jason anythingllm` prints the entry, `--write` installs it) with the board profile, nineteen tools led by `board_digest`, because the app's small local model chooses badly among sixty (`--profile all` registers every tool) lets a person chatting in AnythingLLM ask for a unit brief, a solar standing, or a records request and get the stores' answer. Both need an API key generated in the app under API Keys. Jason keeps it in a Keeper login record named by `anythingllm_record_uid` in `.env` (`jason anythingllm --store-key` moves a key from `.env` or the environment into a new record and rewrites `.env` to point at it); the CLI resolves it through the vault, and the MCP tool reads `ANYTHINGLLM_API_KEY` from its own environment since jason-mcp does not call Keeper. Without a key the client sends nothing. AnythingLLM loads tools only, not MCP resources or prompts, and needs v1.8 or later. As of 2026-09-28 the app is connected: the key is in Keeper, jason-mcp is registered (start it from the Agent Skills page), and the workspace holds 33 PDFs and 115 generated pages.

**AnythingLLM on the GPU (September 30, 2026).** After the upgrade to an RTX 5090 (32 GB), the app's bundled Ollama ran out of memory. It had been kept on C: under the app's storage folder. The app now uses the system Ollama, and the models stay on D:.

- **Chat model.**
  - Provider `ollama` at `http://127.0.0.1:11434`, model `qwen3.6:27b`, token limit 65536. The setting is made with `POST /v1/system/update-env`.
  - The model keeps a KV cache on only 16 of its 64 layers, so a 64k window loads at 20.6 GB, entirely on the GPU.
  - The system Ollama keeps its models where the user variable `OLLAMA_MODELS` points: `D:\ai\models`.
- **The app's own model folder.**
  - `storage\models` (the bundled Ollama, the MiniLM embedder, whisper, the meeting assistant; 5.7 GB) was moved to `D:\ai\anythingllm\models`.
  - A directory junction remains at the old path. The app follows it, so whatever it downloads lands on D:.
- **Retrieval.**
  - Every workspace passes twelve passages at a 0.25 threshold (`WORKSPACE_SETTINGS`); the app's default is four.
  - `jason anythingllm --sync` sets the same on each workspace it keeps.
- **Answers.**
  - Qwen's thinking is stripped from the answer.
  - A question takes about a minute.
- **Embedder.**
  - `qwen3-embedding:8b` on the same Ollama (6.6 GB on the GPU at its 2,000-token window), in place of the native MiniLM.
  - Changing the embedder empties every workspace. Beforehand, each workspace's document list and the old vectors were saved to `D:\ai\anythingllm\backup-2026-09-30`, and the 836 documents were then re-embedded into their nine workspaces.
  - **Chunks.** Chunks are 2,000 characters, capped by the embedder's maximum chunk length (`EmbeddingModelMaxChunkLength`).
    - The app's own chunk-size setting is unset, and the developer API can set it only in multi-user mode. With it unset, the app splits at the embedder's maximum.
    - At first that maximum was 8,192, which made 8k-character chunks.
    - Changing the maximum does not empty the workspaces. The vector cache (`storage\vector-cache`) keeps each document's old chunks, so re-chunking meant clearing it and re-embedding.
  - **Result.** With MiniLM, a question about the master policy's deductible drew only policy forms. With the new embedder and 2,000-character chunks, the answer quotes the policy's Covered Property text, the deductible on the declarations' building line, and the unit-interior endorsement.
- **One model for everything.**
  - jason's classifier (`ModelClassifier`), the scan reader (`OllamaExtractor`), OCR, and AnythingLLM all use `qwen3.6:27b` at a 65,536 window (`ollama_extractor.DEFAULT_MODEL`, `DEFAULT_CONTEXT`).
  - The chat model and the embedder fill about 27 GB of the 32 GB card. A second large model, such as the old default `qwen3.5:9b`, would evict one of them, and a different `num_ctx` reloads the model.
  - The official `qwen3.6:35b` MoE is three to five times faster to chat with, but it cannot share one load with OCR the way the 27B does.
- **Windows commit charge.**
  - A model resident on the GPU still costs about its size in Windows commit charge. With the chat model, the embedder, and an OCR model loaded, commit reached 68 of 69 GB with half the RAM free.
  - The page file is system-managed and 9 GB, on C:. Raising it, for example to a fixed 32 GB on D:, is a person's Windows setting.

**Hybrid retrieval (September 30, 2026).** `jason.community.retrieval` puts jason's BM25 passage ranking (`passages.rank`) together with `qwen3-embedding:8b` embeddings.

- **Fusion.** The two rankings are fused by reciprocal rank fusion (`rrf`, k=60).
- **Exact tokens.** Some tokens must match literally: a 5+ character token with a digit, an APN, or a named statute section. A passage that carries one verbatim ranks first (`exact_tokens`, `boost_exact`), and a reranker never moves it.
- **Embeddings.**
  - `OllamaEmbedder` calls `/api/embed` under the GPU lock and runs `preflight` before its first request.
  - It passes the `num_ctx` of the resident embedder, read from `/api/ps`, so the model is not reloaded.
  - Passage vectors are cached as float16 `.npy` files under `data/retrieval/vectors`, keyed by the SHA-256 of the text the rankers read (the heading and the words), and held in memory for the embedder's life.
- **Passages cut on sections (October 2, 2026).** `retrieval.search` cuts the extracts with `passage_sections.section_passages` (`CHUNKING = "sections"`); `passages.corpus(chunking="windows")` keeps the old 220-word windows for other callers.
  - The headings come from the document's outline in `data/outlines` when one matches the extract (by Drive id, library file name, or name) and at least half its words align with it; then from the OCR label reader (`outline_labels.outline_from_ocr`); then from Markdown headings and short all-capital lines that are not page furniture. A Doc export that lost its list numbers gets them back from the outline.
  - Each passage carries its section's path as `Passage.heading` ("Bylaws > 8.17 Limitation of Powers > 8.17(a)"), read by BM25, the embedder, and the exact-token boost (`Passage.ranked`). `Passage.text` stays a slice of the extract, so a recitation is exact. A numbered paragraph with no caption gives its number only, so the prefix does not repeat its words.
  - A section is one passage up to 220 words; a longer one splits on paragraphs, then lines, then windows. A heading with no words of its own joins the section after it. A Markdown table splits by rows, and every piece starts with the heading row. A text with no headings gets the old windows.
- **Near copies folded (October 2, 2026).** `collapse` groups the ranked passages whose 5-letter shingles (case, spaces, and punctuation dropped) overlap: 60% of the shorter one inside the longer, or 90% for a passage under about 40 words. Two passages that both carry long numbers and share none (two annexations from one form) are not copies. The best-ranked copy stays, and the others go in `Hit.also`, so the slot goes to another passage and every source is still shown. `hybrid`, `keyword_exact`, and `search` fold before the top-k cut (`COLLAPSE_COPIES`).
  - When copies tie, `collapse(prefer=...)` takes the preferred source. Neither the library nor the profile ranks a governing document's copies (`copy_priority` is for invoices' channels, and `living.Standing` is per instrument, not per file), so the order of authority is a parameter, unset by default.
- **No "nothing relevant" flag.** `no_answer_advisory` words the note ("no passage scored above X; the answer may not be in these documents"), but `NO_ANSWER_COSINE` stays unset: no threshold on the dense cosine or BM25 separated the questions answered nowhere (below). It never drops a result.
- **Where it is used.** `passage_search(mode="hybrid")` uses it, and so does `mode="exact"`, which is BM25 plus the boost with no model. The default stays `"keyword"`; since October 2 its passages are the section passages with copies folded. If the embedder cannot load, the search returns `available: false` and says why.
- **Evaluation.**
  - `scripts/eval_retrieval.py` scores the retrievers against 24 gold questions in `data/retrieval/gold.json` (6 exact-token, 18 paraphrase) over 1,530 passages.
  - A held-out set, `data/retrieval/gold-heldout.json` (116 questions with a `family` each, and an `unanswerable` list scored apart), is for checking settings tuned on `gold.json`; never tune on it. `--gold` repeats (each file's table, then the pooled one), `--fusion K:W` adds the hybrid at another RRF k and dense weight, and `--by-family` breaks the table down by family.
  - `--chunking windows|sections` and `--copies/--no-copies` choose the passages and the folding (defaults: `retrieval.CHUNKING`, `COLLAPSE_COPIES`). `--compare RUN.json` lists, per gold file and method, the questions won and lost against an earlier run and the families that moved. `--no-answer` finds the best threshold on the top dense cosine and BM25 score for the `absent` questions, with its precision and recall. A hit is relevant by its own words (spacing aside, never its heading) or by a copy folded under it; each run counts the questions credited only through a copy and the average number of near copies in each top 10.
  - **Sections and copies (October 2, 2026).** Each step was measured on both gold files against the settings before it (runs `2026-10-02-chunks-0-baseline.json`, `-1-sections.json`, `-2-copies.json` in `data/retrieval/runs`). Held out, hybrid recall@5 / MRR@10 went 0.80 / 0.69 (windows) to 0.86 / 0.73 (sections; 12 won, 5 lost) to 0.91 / 0.77 (copies folded; 5 won, none lost); pooled over 140, 0.81 to 0.85 to 0.89. On `gold.json` sections lost (0.88 to 0.79; copies of a neighbouring rule crowded the answer out) and folding won most of it back (0.83). The trials table has the rows.
  - **No answer.** On the held-out set's 6 questions answered nowhere against the 116 answerable, the best dense-cosine threshold (0.67) flags 3 of 6 and 14 answerable questions (precision 0.18); BM25's best flags 1 of 6 (precision 0.33). Neither separates, so no advisory is given. Grow the `absent` list before measuring again.
  - The first run was offline:
    - BM25 scored recall@5 0.71 and MRR 0.60.
    - The exact boost gave the same, because BM25 already finds all six exact-token questions.
  - The dense and hybrid rows could not run that day. The embedder was not resident, and with `qwen3.6:27b` loaded only 4.3 to 4.9 GB of commit was free, against the 9.7 GB `preflight` wants. Run `python scripts/eval_retrieval.py` once the embedder is loaded. The first run embeds the corpus, and later runs send only the question.
- **Reranker.**
  - Ollama has no rerank endpoint. `LlmReranker` sends one listwise request to the resident `qwen3.6:27b` (no thinking, JSON scores 0 to 3) over the top 12 passages.
  - It took a median 1.8 s of Ollama time and at most 2.8 s. Waiting for the GPU lock behind other jobs cost far more.
  - Over BM25 plus the boost it raised recall@5 from 0.71 to 0.79 and MRR from 0.60 to 0.69. On paraphrase questions recall went from 0.61 to 0.72.
  - It is off by default (`retrieval.search(..., rerank=True)`, `eval_retrieval.py --rerank`).
  - No cross-encoder was tried: onnxruntime and llama-cpp-python are not installed, and PyTorch is not to be installed.

**Managing AnythingLLM.** `jason.anythingllm_admin` keeps the app fit to hold the catalogs; `jason anythingllm` runs it, and the `anythingllm_status` tool reads it.

- **Status.** `--status` reads the app's chat and embedding settings against jason's (`PROFILE`: the system Ollama, `qwen3.6:27b` at 65,536, `qwen3-embedding:8b`), counts each workspace's embedded documents and checks its retrieval against `WORKSPACE_SETTINGS`, and names the catalogs with no workspace, the workspaces no catalog owns (the first pass's "my-workspace"), and stored documents no workspace embeds. Each finding says the command that fixes it.
- **The app.** `--start`, `--stop`, and `--restart` run the Windows app; `--start` waits for its API.
- **Settings.** `--apply` writes the chat settings that drifted and each workspace's retrieval. The embedder changes only with `--apply --embedder --reembed`, because a new embedder empties every workspace: a snapshot is taken first, then every embedding and the vector cache are cleared and the snapshot is put back.
- **Snapshots and re-embedding.** `--snapshot` saves each workspace's document list to `data/anythingllm/snapshots`. `--reembed` puts the latest back (or `--from-snapshot FILE`, which also reads the September 30 backup's flat list), `--only SLUG` for one workspace. What a workspace already embeds is skipped, so a run cut off by a restart resumes where it stopped; `--reset` clears first. Each batch holds jason's GPU lock.
- **Consent.** Everything that changes the app needs `--yes`. jason deletes no workspace and no document.

**OCR on the GPU.** `OllamaVisionOcr` (`jason.community.ocr`) is the first OCR engine whenever Ollama is running with `qwen3.6:27b`. It serves `jason ocr-documents`, the library, the mail, the invoice review, and the incident history.

- **How it reads.**
  - It sends one page image per request, with thinking off and temperature 0.
  - The prompt asks for a verbatim transcription, tables as `|` rows, and `[illegible]` rather than a guess.
- **Against Tesseract.** On the first amendment's cover page it read the recorder's stamp correctly (1/17/2020 and "PLACER TITLE COMPANY"), where Tesseract read "4117/2020" and "PLACER TITLE GON".
- **Shared load.** It asks for AnythingLLM's 64k window, because Ollama reloads a model whose context differs, so one load serves both.
- **Settings.** `JASON_OCR_MODEL` names another vision model, and `JASON_OCR_OLLAMA=0` turns the engine off; the tests set it off.
- **What it doesn't touch.**
  - A text already cached by hash is not read again.
  - AnythingLLM's own collector keeps its built-in OCR, which cannot be pointed at Ollama.
- **A second text layer for library files.**
  - `jason library --vision KIND [--pages N] [--limit N]` reads a kind's files again with the vision model into `data/library/text/<id>.vision.txt`, and notes the model and the pages read.
  - `text_for` gives the document models the vision text first. It replaces the old text when every page was read; otherwise the old text follows it under a `--- ocr: ollama-vision ---` line.
  - A deed's first page takes 16 to 30 seconds.
- **Why not AnythingLLM's own OCR.**
  - Its collector reads a PDF's text layer page by page. It runs tesseract.js only when the whole file yields no text, so a PDF mixing text pages and scanned pages loses the scanned pages.
  - An uploaded image is also read with Tesseract; no setting sends either to a vision model. Images attached in a chat do go to the multimodal chat model.
  - So jason makes the text and gives AnythingLLM text.
- **Tesseract and a vision model each have strengths.**
  - Tesseract runs on the CPU in half a second a page, repeats itself exactly, never invents text, and gives word boxes and confidences.
  - A vision model reads stamps, tables, skewed scans, and forms better. It can "correct" a word instead of copying it, or loop.
  - The prompt asks for `[illegible]`, and a reading is evidence, not a fact. Cross-checking a recording number between the two is the next refinement.
- **Dedicated OCR models.**
  - GLM-OCR (0.9B, `glm-ocr`) is small and fast and scores well on benchmarks.
  - On the amendment's cover page it looped until Ollama stopped it ("token repeat limit reached"), with its default temperature 0 at 100 to 200 dpi. It is not used.
  - The loop is not memory and not settings (September 30, 2026 retest, below). On Ollama 0.35.0 it never ends its answer, even on a cropped stamp.
  - DeepSeek-OCR (`deepseek-ocr:3b`) is fast but drops or misreads the digits that matter (below). It is not used.

**Model trials on this machine.** Check this table before trying a model, and add a row after each trial.

- **The machine:** an RTX 5090 (32 GB), one request at a time.
- **Prompts:**
  - Text: the first 14,000 characters of the CC&Rs extract, with a request for a 200-word summary.
  - Page: the first amendment's cover page at 150 dpi, to transcribe.
  - Scripts: `bench_backend.py` for Ollama and `vllm_trial.py` for vLLM, in the session scratchpad.
- **Digits:** 11 digit strings on two deeds (library ids 1018711 and 1018712, page 1), checked by eye on the scans: PO box, ZIP, the recorder's receipt number, book and page, and a handwritten reference number.
- **Speeds** are in tokens per second.

| Model | Engine, format | Prefill text / page | Decode text / OCR | Digits | Verdict |
|---|---|---|---|---|---|
| qwen3.6:27b | Ollama CUDA, Q4_K_M, 64k window | 2,924 / 1,443 | 59.7 / 59.3 | 11/11 | **in use**: chat, OCR, classifier, scan reader, AnythingLLM |
| qwen3.5:9b | Ollama Vulkan, Q4_K_M | 804 / 664 | 87.6 / 88.1 | — | Vulkan was a fallback: `CUDA_VISIBLE_DEVICES` named the old GPU |
| qwen3.5:9b | Ollama CUDA, Q4_K_M | 4,544 / 675 | 104.2 / 96.1 | — | not used: a second large model does not fit beside the 27B and the embedder |
| glm-ocr | Ollama, default | — | — | 0/11 | broken: loops until Ollama stops it (token repeat limit); retested September 30, 2026 alone on the card with 18 to 38 GB of commit free, and it loops the same, so not a memory failure |
| glm-ocr | Ollama 0.35.0, the GLM-OCR SDK's settings (`Text Recognition:`, temperature 0, top_p 0.00001, top_k 1, repeat_penalty 1.1, num_predict 8192) | — | — / ~585 | 11/11 in its first pass | rejected: never stops, so every page runs to the 8,192-token cap (about 15 s); the full page leaves out the amendment's recorder's stamp; misreads words ("County of Porter", "$119.11") |
| deepseek-ocr:3b | Ollama 0.35.0, F16, `Free OCR.` | — | — / ~680 | 4/11 | rejected: leaves out the recorder's stamp block on all three pages |
| deepseek-ocr:3b | Ollama 0.35.0, F16, `<\|grounding\|>Convert the document to markdown.` | — | — / ~680 | 9/11 | rejected: 1 to 4 s a page and reads the amendment's stamp, but misreads the receipt number (…663 for …683) and the handwritten reference number, and handwriting (a scrawled association abbreviation) |
| qwen3.6:27b-q8_0 | Ollama | — | — | — | not tried: 30 GB of weights does not fit beside qwen3-embedding:8b on the 32 GB card; the library has no Q6_K |
| nvidia/Qwen3.8-27B-NVFP4 | vLLM 0.30.0, NVFP4 W4A4 | 10,714 / 4,564 | 61.0 / 60.6 | — | rejected: no decode gain without MTP |
| nvidia/Qwen3.8-27B-NVFP4 | vLLM 0.30.0, NVFP4 + MTP 2 | 10,292 / 4,275 | 98.6 / ~137 | 7/11 | rejected: misreads digits |
| unsloth/Qwen3.6-27B-NVFP4 | vLLM 0.30.0, NVFP4 + MTP 2 | 8,569 / 4,006 | 97.5 / ~133 | 8/11 | candidate for chat only; the W4A4 format loses digits |
| qwen3.6:27b, thinking on | Ollama CUDA, Q4_K_M, 64k window; the scan reader's JSON schema | — | — | — | rejected for the scan reader: about 25 minutes for the eight pinned cases, unit ranges 1 of 7 and common areas 2 of 7 (it left the optional `annexed` object out); kept only as the retry for an empty stamp (see the scorecard above) |
| qwen3.6:27b, thinking off | Ollama CUDA, Q4_K_M, 64k window; the scan reader's JSON schema | — | — | — | **in use** for the scan reader: 2 minutes 40 seconds for the eight pinned cases, every stamp, phase, unit range, common area, and supersession (September 30, 2026) |
| qwen3.5:9b, filled forms | Ollama 0.35.0 CUDA; `VisionReader`'s prompt and JSON schema; `jason form-lab --benchmark` | — | — / ~1.6 s a page | — | **recommended for handwritten forms**: 0.947 to 0.966 on plain layouts (Tesseract and hints 0.40 to 0.49), 0.79 to 0.82 on combs and character boxes; faithful: 0 of 24 changed answers read as the old value, and 0 of 19 broken answers corrected with the plain prompt (October 1, 2026; [form-design.md](form-design.md)) |
| glm-ocr, filled forms | Ollama 0.35.0; `VisionReader`'s prompt and JSON schema | — | — | — | not for owner answers: 0.957 to 0.978 on the battery (0.70 to 0.83 on combs and character boxes), but it "corrects" what people wrote: 6 of 19 broken emails and phone numbers came back valid with the plain prompt, 17 of 19 when told what was sent, and 13 of 24 changed answers came back as the old value; it looped on 2 of 84 pages; 2.2 GB (October 1, 2026; [form-design.md](form-design.md)) |
| deepseek-ocr:3b, filled forms | Ollama 0.35.0, F16; `VisionReader`'s prompt and JSON schema | — | — | — | rejected for forms: 0.351 to 0.419 on the same battery (October 1, 2026) |
| qwen3-embedding:8b, near copies folded | the sections row's passages; `collapse` before every method's top 10 (`eval_retrieval.py --copies`), relevance also through a folded copy | — | 0.46 s a query (hybrid), 0.31 to 0.43 (dense), with the vectors held in memory | — | **in use** (October 2, 2026; `COLLAPSE_COPIES`): held out, hybrid 0.86 / 0.73 to 0.91 / 0.77, dense 0.72 to 0.79, keyword 0.57 to 0.60; 5 won and 0 lost (hybrid), 9 and 0 (dense), 4 and 0 (keyword); exact 1.00, paraphrase 0.86; gold.json hybrid 0.79 to 0.83 (1 won, 0 lost). Near copies in a top 10 went from 4.3 to 4.8 on average to none; 4 held-out hybrid answers are credited only through a folded copy. Pooled over 140: hybrid 0.89 / 0.76. `data/retrieval/runs/2026-10-02-chunks-2-copies.json` |
| AnythingLLM vector search | AnythingLLM Desktop, its own chunks, the same qwen3-embedding:8b on the system Ollama; `scripts/eval_anythingllm.py` on the 140 gold questions, top 30 a workspace, repeated chunk text folded | — | 2.2 s a query | — | **measured against the hybrid** (October 4, 2026): the shared workspace recall@5 0.47 / MRR@10 0.32 (gold.json 0.50, held out 0.47); the record catalogs alone 0.52; the union of four catalogs by score no better. Of the 62 questions the hybrid answers and AnythingLLM does not, 25 have no answer in its stored text (thin parses, documents never uploaded) and 37 are ranking misses: on the 110 questions whose answer it holds, AnythingLLM 0.60 and the hybrid 0.91. It loses most on exact tokens (recording, rule, and resolution numbers, statute citations), where it has no keyword ranking. `data/retrieval/runs/2026-10-04-anythingllm.json` |
| qwen3-embedding:8b, section passages | the weighted row's fusion, unchanged; `passage_sections.section_passages` (outlines, OCR labels, headings; 220-word cap; tables keep their heading row; the section's path as a ranking prefix) on both gold files (`--chunking sections`) | — | 1.2 s a query (hybrid) before the vectors were held in memory; corpus cut 2.8 s | — | **in use** (October 2, 2026; `CHUNKING`): 3,586 passages for 1,533 windows; held out, hybrid recall@5 / MRR@10 0.80 / 0.69 to 0.86 / 0.73 (12 won, 5 lost: defined terms, section numbers, meetings, and use restrictions up; insurance pages and a resolution down), keyword 0.47 to 0.57 (exact 0.72 to 0.97), dense 0.70 to 0.72; but gold.json hybrid 0.88 / 0.74 to 0.79 / 0.69 (1 won, 3 lost), dense MRR 0.64 to 0.49, as copies of the next rule took the slots. The first cut put a numbered paragraph's opening words in its prefix, repeating them; fixed before this row (captions are a short first sentence or nothing). Embedding 3,586 passages took 119 s and 986 more after the fix 31 s; the cache grew from 2,953 to 7,519 vectors (25 to 63 MB). `data/retrieval/runs/2026-10-02-chunks-1-sections.json` |
| qwen3-embedding:8b, "nothing relevant" score | the copies row; `eval_retrieval.py --no-answer`: the best threshold on the top dense cosine, BM25 score, and BM25 per question word, for the held-out set's 6 questions answered nowhere against its 116 answerable ones | — | — | — | **not used** (October 2, 2026): the absent questions score 0.61 to 0.76 cosine against an answerable median of 0.76 (minimum 0.59); the best cosine threshold flags 3 of 6 with 14 answerable (precision 0.18, recall 0.50), BM25 1 of 6 with 2 (0.33, 0.17). `NO_ANSWER_COSINE` stays unset, and no advisory is shown |
| qwen3-embedding:8b, hybrid weighted, held out | the weighted row's setup; `eval_retrieval.py --gold data/retrieval/gold-heldout.json --fusion 60:1.0` on 116 new questions (40 exact, 76 paraphrase), written after the tuning and never used for it | — | 0.59 s a query (hybrid), 0.45 (dense) | — | **the gain holds** (October 2, 2026): recall@5 / MRR@10, keyword 0.47 / 0.41, dense 0.70 / 0.58, hybrid k10 w1.5 0.80 / 0.69, hybrid k60 w1 0.71 / 0.60; exact 0.90 against 0.88, paraphrase 0.75 against 0.62; 12 questions won and 1 lost (sign test p 0.003). Dense alone still leads on use restrictions and section-number questions; 17 questions every method misses (chunk edges, tables, OCR, repeated copies of a document). Per-question ranks in `data/retrieval/runs/2026-10-02-heldout.json` |
| qwen3-embedding:8b, hybrid weighted | the baseline's setup; RRF k 10 (was 60) and the dense ranking weighed 1.5 (`HYBRID_RRF_K`, `DENSE_WEIGHT`) | — | 0.73 s a query (hybrid) | — | **in use** (October 2, 2026): hybrid recall@5 0.88, MRR@10 0.742; exact 1.00, paraphrase 0.83 (above dense alone, 0.78). Tuned on the same 24 questions, so grow the gold set and measure again before trusting the margin |
| qwen3-embedding:8b, retrieval | Ollama 0.35.0 CUDA, Q4_K_M; `scripts/eval_retrieval.py` on the 24 gold questions, 1,533 passages | — | 0.47 s a query (dense), 0.56 (hybrid); corpus embed 19 s for 118 new passages | — | **baseline** (October 2, 2026): recall@5 / MRR@10, keyword 0.71 / 0.57, dense 0.75 / 0.64, hybrid RRF 0.75 / 0.73; exact questions keyword 1.00, dense 0.67, hybrid 1.00; paraphrase keyword 0.61, dense 0.78, hybrid 0.67 (RRF gives up dense's paraphrase gain). Next: the same model at Q8_0, then a reranker over the top 20, each against this row |
| qwen3.6:27b, filled forms | Ollama | — | — | — | not tried: needs about 25 GB of Windows commit to load and 12 to 14 GB was free; try it when AnythingLLM has it loaded or commit is freed (October 1, 2026) |
| qwen3.5:9b, document duties, free reading | Ollama 0.35.0 CUDA, Q4_K_M, 16k window, thinking off, temperature 0; `duty_model.READ_SCHEMA`; `scripts/eval_duties.py` | — | — / median 1.1 s a passage | — | rejected as the reader: P 0.78, R 0.80 on the 59-passage gold set (the phrase grammar P 1.00, R 0.98); splits a prohibition's clauses, reports statuses and definitions as duties, misses list items ([document-duties.md](document-duties.md), October 2, 2026) |
| qwen3.5:9b, document duties, hybrid | the same, `REVIEW_SCHEMA`: the model rules on the grammar's candidates | — | — / median 1.1 s a passage | — | **in use for bearers only** (`jason duties --documents --fill-bearers`): taking its kinds, P 0.89, R 0.86; taking only the bearers the grammar left unstated, P and R stay the grammar's and bearers right rise from 72% to 93% (fresh set 62% to 83%) (October 2, 2026) |
| qwen3.6:27b, document duties | Ollama | — | — | — | not tried: `preflight` refused it, about 25 GB of commit needed and 17.4 GB free with no model loaded (October 2, 2026); rerun `scripts/eval_duties.py --ask review --model qwen3.6:27b` when commit allows |

OCR post-correction trials (October 2, 2026; [ocr-correction.md](ocr-correction.md)). The test set is the recorded declaration's OCR against the working copy, unamended sections only.

| Model or tool | Engine, format | Prefill text / page | Decode text / OCR | Digits | Verdict |
|---|---|---|---|---|---|
| Tesseract 5.4 command-line tool, `eng` (fast), 300 dpi, its `tsv` words | CPU, about 1.3 s a page | — | — | — | **in use** for scans (`ocr.TesseractCli`, `scan_text`): WER 2.23%, CER 0.46% on the whole declaration, where PyMuPDF's page OCR of the same model read 8.12% and 1.00%, running 784 words together to its 63 |
| Tesseract tool options | 200 and 400 dpi, a 3,481-word legal `--user-words`, label `--user-patterns`, `--psm 6` | — | — | — | no gain on ten pages: 2.49%, 1.84%, 1.82%, 1.80%, 2.08% against 1.82% at the defaults |
| qwen3.5:9b, OCR correction, marked suspects | Ollama 0.35.0 CUDA, 8k window, thinking off, temperature 0; `MARKED_PROMPT`, JSON schema | — | — / median 0.6 s a passage | — | **in use** as the second reader (`jason intake --scan --model`): WER 2.75% from 8.89% on 60 passages; with minimal edits that pass the guard, no harm; the text rules' suggestions it confirms are 96.9% right |
| qwen3.5:9b, OCR correction, explicit expectations | the same, `EXPECTATIONS_PROMPT` with made-up examples; JSON corrections with kind, reason, confidence | — | — / median 2.5 s a passage | — | rejected as a reader: WER 4.88%; 52 corrections quoting words not in the passage; changed the drafter's grammar and a numeral, invented a commission number, replaced a sentence; 3.6 edits to right words per 1,000 on the cleanest passages (the rules 0.4). Its stated confidence is the best of its own signals (AUC 0.82), but self-consistency and agreement with the text rules together separate better (AUC 0.88) |
| qwen3.5:9b, as a scorer | the same, `CHOOSE_PROMPT`; one letter, `logprobs` and `top_logprobs` 10 | — | — / 0.08 s a token | — | candidate: chose right 195 of 212 (the lexicon 194, the product 197); calibrated (0.95 or more, 98% right); never writes a reading it was not given |
| qwen3.5:9b, vision, a word's crop | Ollama 0.35.0, 8k window; `VISION_WORD_PROMPT`, the word and its line at 300 and 200 dpi | — | — / 0.22 s a crop | read a commission number the text rules could not | **recommended** for a guarded word (`jason intake --scan --vision`): 30 of 36 misreads read right, 10 of 10 rare right words kept, 4 of 4 of the copy's run-together slips read as two words; where it and the lexicon agree, 38 of 38 right |
| qwen3.5:9b, vision, anchored | the same, with the OCR's line and the word in doubt (`VISION_ANCHORED_PROMPT`, after olmOCR's document anchoring) | — | — / 0.22 s a crop | — | rejected: 28 of 36; the anchor pulled it toward the OCR's misreading |
| qwen3.6:27b, OCR correction and word crops | Ollama | — | — | — | not tried: `preflight` refused it, 25.1 GB of commit needed and 17.9 GB free with no model loaded (October 2, 2026) |
| Tesseract `tessdata_best` `eng` | the tool | — | — | — | not tried: the model file (about 15 MB, github.com/tesseract-ocr/tessdata_best) is a download a person makes |

Not tried yet:
- NVIDIA's OCR-trained `Nemotron-Nano-12B-v2-VL-NVFP4-QAD` (it needs vLLM).
- Small document models that lead OmniDocBench v1.6:
  - PaddleOCR-VL-1.6 (0.9B, Apache-2.0, 96.34);
  - MinerU2.5-Pro (1.2B, 95.75);
  - GLM-OCR in its own pipeline with PP-DocLayoutV3 (0.9B, MIT, 95.22; the Ollama trial above looped);
  - IBM granite-docling-258M (https://huggingface.co/ibm-granite/granite-docling-258M);
  - olmOCR 2 (7B, faithful transcription; https://olmocr.allenai.org/papers/olmocr.pdf).

  Their value for jason is mostly structure: headings, numbering, and reading order, the outline's weak spot. Survey: https://roboflow.com/blog/best-open-source-ocr-models; https://arxiv.org/abs/2607.08143; https://arxiv.org/abs/2609.03445.
- Scoring a written candidate by its token log-probabilities in context: Ollama's proposed `logprob_tokens` (https://github.com/ollama/ollama/pull/18580). The chooser above approximates it with one letter.

**OCR candidates (September 30, 2026).** The digit test's 11 strings, checked by eye on the scans of two deeds: a PO box, a ZIP, the recorder's receipt number, book, and page on each, and a handwritten reference number. The stamp test is the amendment's cover: document number, date, time, fee, and title company. The values are in the private notes (mystique/notes/document-tools.md).

- qwen3.6:27b through `OllamaVisionOcr` read 11 of 11 and the whole stamp, at 5 to 6 seconds a page, decoding at 73 tok/s (59 in the earlier trial).
- Tesseract (`PyMuPdfTesseract`, 200 dpi) read 5 of 11 in half a second a page.
- DeepSeek-OCR and GLM-OCR are ten times faster at decoding, but neither reads the stamp and the digits together, and GLM-OCR does not stop.
- With qwen3.6:27b and the embedder loaded, about 6 GB of Windows commit is free (the D: page file is system-managed and was 4.75 GB). `preflight` then refuses a third model, even the 2 GB glm-ocr, which loads at 10 GB with its 128k window. The trials unloaded the embedder, or both models, first.
- Decision: OCR stays on qwen3.6:27b. Neither dedicated model complements it as a cross-check: where they disagreed with qwen3.6 on a digit, they were wrong.
- Scripts: `baseline.py`, `trial.py`, and `glm_retest.py` in the session scratchpad.

**NVFP4 trial (September 30, 2026).** `nvidia/Qwen3.8-27B-NVFP4` ran on vLLM 0.30.0 in Docker.

- **Setup.**
  - Docker's data disk is `M:\DockerDesktopWSL`. The weights (21 GB) are in `D:\ai\models\hf`, mounted as the container's Hugging Face cache.
  - Options: a 32k window, an FP8 KV cache, and `--gpu-memory-utilization 0.88`, with Ollama's models unloaded under jason's GPU lock.
- **What vLLM used.**
  - vLLM chose the native FP4 kernel (`FlashInferCutlassNvFp4LinearKernel`), not the Marlin fallback.
  - The weights took 19.9 GB, which left a 124k-token KV cache.
  - Startup took 5 to 6.5 minutes (loading, compile, CUDA graphs, FP4 autotune).
- **Speed, on the prompts the Ollama baseline used:**

| 27B, one request at a time | Ollama Q4_K_M (CUDA) | vLLM NVFP4 | vLLM NVFP4 + MTP (2 tokens) |
|---|---|---|---|
| Text prefill (5.8k tokens) | 2,924 tok/s | 10,714 tok/s | 10,292 tok/s |
| Page-image prefill | 1,443 tok/s | 4,564 tok/s | 4,275 tok/s |
| Decode, summary | 59.7 tok/s | 61.0 tok/s | 98.6 tok/s |
| Decode, OCR transcription | 59.3 tok/s | 60–61 tok/s | 134–140 tok/s |

  - NVFP4 alone speeds prefill three to four times.
  - Decode is limited by memory bandwidth, and the NVFP4 weights are no smaller than Q4_K_M's, so decode stays near 60 tok/s.
  - The speed-up in decode comes from MTP speculative decoding. The checkpoint carries one MTP layer.
- **Accuracy on three deed pages.**
  - Qwen3.8 NVFP4 misread five digits that qwen3.6:27b on Ollama read correctly: in a PO box, a ZIP, a printed recorder's receipt number, and a handwritten reference number. The scans were checked by eye.
  - Tesseract missed some of the same digits.
  - `unsloth/Qwen3.6-27B-NVFP4` (23.4 GB) separates the model from the format: the same Qwen3.6, in NVFP4, on the same vLLM, with MTP.
    - It ran as fast: 8,569 tok/s text prefill, 4,006 page prefill, 97.5 tok/s summary decode, 132–134 tok/s OCR decode.
    - It had the same fault. On the 11 digit strings checked by eye across two deeds, qwen3.6 Q4 on Ollama read 11, Qwen3.6 NVFP4 read 8, and Qwen3.8 NVFP4 read 7.
  - The misreads therefore come from W4A4 NVFP4, which quantizes the activations as well as the weights, not from the model version.
  - vLLM's image resizing is not the cause either: it gave the page more tokens than Ollama did (4,643 against 4,055).
- **Decision.**
  - OCR stays on qwen3.6:27b through Ollama, because a recording number or an amount misread quickly is worse than one read slowly.
  - vLLM with MTP is a candidate for chat and summaries.
  - Two things are unsolved. vLLM holds its memory fraction at startup, so it would need `--gpu-memory-utilization` near 0.68 to leave room for the embedder. It would also be a second server to keep running.
  - **Dropped from the stack (September 30, 2026).** Nothing in jason calls vLLM.
    - The NVFP4 checkpoints were deleted from `D:\ai\models\hf`, along with the nightly and the Qwen3.6-35B image.
    - Only `vllm/vllm-openai:v0.30.0` is kept, for trying the OCR models that are served through vLLM: Chandra OCR 2, PaddleOCR-VL 1.6, and dots.mocr.

**Keeping the catalogs filled.** The association's record set changes as syncs run and pages regenerate, and the law is not the record. `jason anythingllm --sync` keeps three catalogs apart in AnythingLLM's document store, each in its own folder and its own workspace, with every document also in the shared association workspace (`--combined ""` turns that off, `--catalog` limits the run): `authorities` (docAuthor "California Legislature and agencies") is the statute pages `jason export-authorities` wrote from the current session publication through the lawlibrary checkout named by `lawlibrary_home`, one page per article of the Davis-Stirling Act and one per span the duties and lien processes cite, plus the DRE publications once `--fetch-publications` has brought them down; `association-records` (docAuthor the association's name) is the governing, annexation, policy, and resolution PDFs and the public reports from the Drive mirror; `jason-pages` (docAuthor "Jason") is the generated pages (each parcel's history, the market, the solar list, the association's record, the records request, records.md, duties.md) and Jason's own instructions (SKILLS.md, AGENTS.md, the docs), which summarize the other two and are never quoted as either. A title a folder already holds is skipped, unless `--refresh` is passed and the catalog is one Jason writes (`authorities`, `jason-pages`) and the file on disk is newer than the stored copy's published time: then the new copy is uploaded first and the old one removed with `DELETE /v1/system/remove-documents`. The association's records are never replaced. A title held in another folder (the first sync put everything in custom-documents and "My Workspace") is moved with `POST /v1/document/move-files` rather than parsed twice. The store will not move a document a workspace still embeds (it answers "files not moved"), so the sync removes it from every workspace's embeddings first, moves it, and adds it to the catalog's workspace and the shared one with `update-embeddings`; "My Workspace" empties as a result, and the shared association workspace takes its place. Uploads go to `POST /v1/document/upload/{folder}` with `addToWorkspaces` and the metadata (title, description, docAuthor). The image-only PDFs still parse to nothing in AnythingLLM's collector; give them a text layer first (`jason ocr-documents`) or upload the `.pdf.md` extracts the readers wrote.

**Docker MCP Toolkit.** Docker Desktop's catalog runs MCP servers as containers behind one gateway, which is the way to add a third-party OCR or RAG server later without installing it into the venv. Nothing in it is needed for the jobs above yet; it becomes useful when a catalog server does one of them better than the local pieces, or when jason-mcp itself should run as a container for another client.

## The library ingestion chain

`jason library` runs the association's whole PayHOA library through one chain and keeps each file's method (`src/jason/tasks/library.py`):

1. **Name and folder rules.** The specification's `KIND_RULES` match the file name, the PayHOA folder, and the library path, in order. A blank platform template and a photo are classified here so they can be set aside.
2. **Find or fetch.** A file lives in `data/library/files/<library path>`, or a copy of the same name is found under the Drive mirror. With `--fetch`, the rest comes from PayHOA in bulk zips of 40; templates and images are not fetched.
3. **Read once.** The text is cached in `data/library/text/<id>.txt` with its source: a `.pdf.md` extract, the PDF's text layer, an OCR engine for an image-only page when one is installed, a CSV or text file, or a Word document's XML.
4. **Phrase rules** (`src/jason/community/content.py`), for a file no name rule placed. A title pass reads the opening words, and a body pass reads the first pages. An extract's header is dropped first, because it carries the file name.
5. **A local model**, with `--model`, for what the phrase rules leave. It answers from the closed list of kinds, each defined with its near neighbors named, at temperature 0 with a JSON schema. An answer under 0.5 confidence is dropped, and the model never overrides a rule.
6. **Refinements.** Record rules add a Civil Code 5200 record the kind alone does not give, and a period is read from the text when the name gave none.
7. **Store.** Rows go to `data/library/library.db`, read by `library_search`, `library_status`, `library_text`, and the 5200 inventory.

Documents from outside the PayHOA catalog (a prior manager's export, a zip, a Drive folder) go through the same readers and the same chain with `jason ingest SOURCE`, which also dedups by hash, finds versions of the documents jason knows, and proposes each file's book, record, and folder ([onboarding.md](onboarding.md#ingest)). Its `--apply` rows sit in `library.db`'s `ingested` table too, and a `jason library` run copies them back into `documents` after it rebuilds the catalog's rows.

The scorecard (`jason library --score`, with `--model` for the model) measures a text reader against the name rules, which are the answer key where the association's naming exists. A disagreement is a rule to fix or a file misnamed, and the misses list names the files.

| Reader | Files scored | Right when answering | Silent |
| --- | ---: | ---: | ---: |
| phrase rules, first version | 477 | 47% | 161 |
| phrase rules, with the title pass and the extract header dropped | 448 | 94% | 72 |
| qwen3.5:9b, a few kinds defined (two files per kind) | 43 | 63% | 2 |
| qwen3.5:9b, every kind defined with its near neighbors (two files per kind) | 80 | 91% | 0 |
| phrase rules on that same sample | 80 | 84% | 29 |

The model answers every file, at under two seconds each on the RTX 4070 Ti SUPER. The phrase rules are free and exact where a title exists, and silent where it does not. So the chain runs the rules first and the model on what they leave. The model's seven misses were near neighbors: a monthly service agreement read as a proposal, a certificate of insurance read as the policy, an executive-session agenda read as an agenda. The model is released a minute after its last call (`keep_alive`), because a loaded 9B model holds about 9 GB of Windows commit charge, and numpy's allocator failed while one was loaded.

What moved the phrase rules is worth keeping in mind for the next kind.
- **Titles decide before bodies.** A treasurer's report carries a balance sheet, and a collection policy quotes the lien statute.
- **The agenda and the minutes share a heading.** The agenda says the meeting is "to be held", and the minutes say "held" or show a motion carried.
- **A recorded instrument's title follows the recorder's stamp.** Amendment, annexation, and declaration match only when "recording requested by" is also there, so minutes that discuss an amendment stay minutes.

AnythingLLM's records catalog takes the classified library too: each file a member could see, titled by name, with its kind, period, and 5200 records in the description. Confidential files, templates, photos, deeds, and tax bills stay out.

## Keeping the local stack healthy

jason's readers, classifier, and OCR, and AnythingLLM's chat, share one model on the RTX 5090: `qwen3.6:27b` at a 65,536-token context (`DEFAULT_MODEL` in `jason.community.ollama_extractor`), with AnythingLLM's embedder `qwen3-embedding:8b` beside it. Nothing else should be loaded.

**`jason local-ai`** reports the stack and says what is wrong and how to fix it:
- whether Ollama answers, and which devices it found when it last started (from its server log);
- each loaded model, and how much of it is in video memory;
- the AnythingLLM chat and embedding models (only those keys are read from its settings file) and whether it answers;
- Windows' commit limit and use, the page files in use, and the ones set in the registry;
- who holds each of jason's locks.

`--check` exits 1 on any finding, for a scheduled task. `--restart-ollama --yes` restarts the Ollama app so it looks for GPUs again, and stops its model servers too. `--unload NAME|all --yes` frees a model. jason changes no setting of Ollama, AnythingLLM, the driver, or Windows.

**What it catches**, each of which happened on September 30, 2026:
- **Ollama on the CPU after a driver change.** Ollama looks for GPUs only when it starts. Until restarted, the 9B model ran at 12.7 tokens a second instead of 136.
- **A model server whose Ollama is gone.** Stopping `ollama.exe` leaves its `llama-server.exe` running. One held 24 GB of commit that nothing could reach.
- **Commit nearly full.** A model in video memory still counts against Windows' commit limit (RAM plus the page files). Two models at once exhausted it, and the model server died with `std::bad_alloc`.
- **A page file set but not in use.** The setting applies at the next restart.
- **A second chat model.** AnythingLLM and jason on different models swap each other out of the card.

**Before a model job.** `jason.local_ai.preflight` runs before the classifier's first request, before the Ollama reader starts, and when OCR decides whether the vision model is available. It refuses the job when:
- Ollama is down or running without the GPU;
- the model is not pulled;
- loading it would leave less than 4 GB of commit.

The classifier and reader then fail fast, and OCR falls back to Tesseract.

**One model request at a time.** Every jason request that runs a model (`/api/chat`, `/api/generate`, `/api/embed`) holds the GPU lock (`jason.locks`), whether it comes from the CLI, the MCP server, or another agent session. A second request waits, up to its timeout, instead of making Ollama load a second model. The locks are operating-system locks in `%LOCALAPPDATA%\jason\locks` (`JASON_LOCK_DIR`), released when a process ends, even by a crash. The same module locks the board's action items while one process reads, changes, and writes them. AnythingLLM's own requests are outside jason's lock, which is why both must use the same model.

**Keeping them running is Windows' job.** The Ollama and AnythingLLM apps start at sign-in. Ollama's environment variables are set by a person: `OLLAMA_MAX_LOADED_MODELS=2`, `OLLAMA_NUM_PARALLEL=1`, `OLLAMA_KEEP_ALIVE=10m`. After a GPU driver update, restart Ollama.

## What not to do

- Do not pin a fact because a model read it. The scorecard scores readers; a person reads the recital; the pin goes in `mystique` with its source.
- Do not send page images or text to a hosted model without a key deliberately in place; the Claude reader fails fast without one, and the local readers never leave the machine.
- Do not read AnythingLLM's database for its API key; generate one in the app and set it in the environment.
- Do not pull a model or install PyTorch-sized packages as a side effect; each is a command a person runs.


**Tesseract, without an administrator install.** PyMuPDF carries the Tesseract engine and needs only its language data. On September 29, 2026 the UB-Mannheim installer (`winget install UB-Mannheim.TesseractOCR`) was hash-verified by winget and then unpacked with 7-Zip into `%LOCALAPPDATA%\Programs\Tesseract-OCR` instead of run, because the installer's administrator prompt cancels when started from the app. `PyMuPdfTesseract.tessdata()` finds the data there, or through `TESSDATA_PREFIX`, or in a machine install. With it, `jason invoices` OCRs a scanned or glyph-coded attachment once and caches the text by file hash, and `jason library` OCRs an image-only PDF, a scan whose site export is only a header, or an image file. AnythingLLM's collector stays the fallback for documents already uploaded there; it cannot OCR a file without uploading it into AnythingLLM's store.
