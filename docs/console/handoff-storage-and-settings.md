# Handoff: the machine jason runs on

For the design pass on the administrator's view of **the machine itself**: where jason, asspy, and lawlibrary keep their files, how much room each drive has, the settings files that name those places and which one set each value now in effect, data left in an old default folder, the locks jason's processes share, the local model stack, and the passage index's health. The data exists today, in four commands and no screen:

- `jason storage [--check] [--json] [--no-sizes] [--min-free-gb GB]` (`jason.storage.report`): each place with its path, drive, the drive's free space, the size of what jason keeps there, `exists`, and `tiny`; the temp setting (`JASON_TEMP_DIR`, else the system's); `configs`, the three user config files by path and whether each is there, never their contents; `legacy`, data left in an old default folder with where to move it; and `problems`, one line each. `--check` exits 1 when there is one.
- `jason local-ai [--json] [--check]` (`jason.local_ai.status`, `findings`): the model server, the devices it found when it started, the models loaded and how much of each is on the GPU, jason's model and embedder, Windows commit and page files, model servers left running by an Ollama that is gone, and the lock holders. `preflight` is the same check a model job runs before it sends anything.
- `jason index --status` (`passage_index.status`): whether the passage index is built, its size, the embedder, the vectors, the passages with no vector, and each catalog's files and passages by standing.
- `jason.locks.holders()`: who holds which lock, since when, for what.

Behind them: `jason.config` (`user_config_path`, `env_file_values`, `_env_value`, `_anchored`, `resolve_env_path`, `temp_dir_problem`, `apply_temp_dir`), `jason.asspy_home.apply`, asspy's `paths.config_path`, `configured`, `home`, and `legacy_home`, and lawlibrary's `core.config_path`, `data_dir`, and `legacy_data_dir`. The rules are AGENTS.md's Boundaries (the temp folder, the user configs and their order, the locks) and [../setup.md](../setup.md#where-jason-writes) ("Where jason writes"); what an agent's scratch may touch is [../scratch.md](../scratch.md); the model stack and its trials are [../document-tools.md](../document-tools.md). No loader serves any of it yet.

**The neighbours, linked and not repeated.** [screens/status.md](screens/status.md) is the built `#/status`: one community's sources, sign-ins, gates, and failures; this page is the machine under every community and adds no row there but a one-line summary. [handoff-admin-components.md](handoff-admin-components.md) and [handoff-instance-and-integrations.md](handoff-instance-and-integrations.md) own the Instance screens, each integration's reading, the credential line and the vault, the schedules, and the service's heartbeat and job lanes (`ServiceStatus`, `LaneRow`, `TerminalStep`); this page reuses those components and redesigns none. Locking is [architecture.md](architecture.md#locking). Being written in the same wave and named here only: `handoff-context-pack-workbench.md` (searching the index by slice, which this page's index health feeds), `handoff-collection-workspace.md`, and `handoff-as-of-and-quote-check.md`.

These components pair with what the console already has: `Card`, `Tabs`, `DataTable`, `Stat`, `Pill`, `Glyph`, `Seal` (`read`), `Findings`, `Caveats`, `Command`, `EmptyState`, `ErrorNotice`, and `RemoteView`, and the neighbours' `TerminalStep` and `LaneRow`. Build new parts only where the table says so.

## The idea in one line

The machine view **reads where jason writes and why it writes there**: each place on its drive with the room left, each storage setting with the file that set the value now in effect, each lock with its holder, the model stack with what a model job's preflight would say, and the index with what it holds; every problem is one line in the check's own words with the command that shows it in a terminal, and every change (a line in a settings file, a folder moved, a model unloaded) is a person's act at the machine, which the console names and then reads again. It never shows a secret, never shows a settings file's other lines, and writes nothing.

## The components

| Component | Where it renders | Data | States to design |
| --- | --- | --- | --- |
| `MachineProblems` | first on `#/instance/machine`; one line on `#/status` and on `#/instance` | `GET /api/machine/problems` | none ("Every place has at least 20 GB free. The model stack reports no problem."); one or more, ordered by severity word then by place; each with its words verbatim, the check that counts it, and its `Command`; a problem no check counts yet (labelled so); one source unreadable (its note and command in place, the others listed) |
| `DriveRoom` | the Places tab, one a drive | `drives[]` | room (free over the floor); short of room (free under it; the places jason keeps there named); free space unknown (the drive could not be read); the system drive marked as such; the floor and where it comes from |
| `PlaceRow` | inside `DriveRoom` | one `places[]` row | kept here, with what (`note`), its size or "not measured"; not there yet; a child of the data directory (indented under it, from `parent`, not from the name's spaces); tiny (listed apart: "a few bytes; never what fills a drive"); path and drive only (the Google token, the Keeper config); not asked (lawlibrary did not answer; the settings could not be read), with why |
| `TempLine` | top of the Places tab, and inside the `JASON_TEMP_DIR` chain | `temp` | set and usable; unset ("the system's temp folder", with its drive and room); set and unusable on disk now ("stops runs", the check's words verbatim); set, and this server started with another value (restart to use the new one) |
| `ConfigFiles` | the Settings tab, top card | `configs[]` and the project `.env` | each file there or "not there yet: name the folders in it"; named by its pointer variable (`JASON_CONFIG`, `ASSPY_CONFIG`, `LAWLIBRARY_CONFIG`, `JASON_ENV`) rather than the default path; which storage settings it names, by key only; unreadable (a line that does not parse sets nothing, so it reads as naming nothing, labelled) |
| `SettingChain` | the Settings tab, one a storage setting | `settings[]` | the layers in order, each "names it", "not named", "file not there", or "not read by this program"; the first that names it marked "in effect" in words; a lower layer overridden (its value shown, struck in words, not by style alone); named nowhere ("the default stands") with the default; two programs read it differently (`views[]`: jason's and the program's own, each with its value; "jason and asspy read different folders"; the console picks neither); a value that resolves relative (taken from the checkout, never the working directory); changed on disk since this server started |
| `SettingChange` | under a `SettingChain`, opened by "How to change it" | `change` | the file the line goes in, the line, and "then run" with `jason storage --check` as a `Command`; a folder a person types, checked by the server for its drive, room, and usability (nothing created, nothing stored); a value refused (a backslash in double quotes, a missing drive) in the check's own words; a setting that is not a file's (`OLLAMA_MODELS`, `HF_HOME`: the program's own environment, which jason never changes) |
| `LeftBehind` | the Old folders tab; a line in `MachineProblems` | `legacy[]` | files left (the count, "1000 or more" when counting stopped), the old folder and the folder to move them into; the target already holds files (both counts; "move into it with care: the console picks nothing"); no target named; moved (read again: nothing left); this server sees AppData through a packaged application's copy (the caveat) |
| `LockTable` | the Locks tab; the GPU lock's row also inside `ModelStack` | `locks` | none held ("No lock is held. The lock folder is ~/.jason/locks (default)."); held, with resource, key, process, command, purpose, since, and how long; held by another community's process; a note left by a process that ended (if the loader does not prune: decision 5); the lock folder named by a setting, or by the default; the folder unreadable |
| `ModelStack` | the Models tab; a line on `#/instance` | `GET /api/machine/models` | not read yet (the read is a person's action: decision 4); server up, with its version and the devices it found; not answering; running without the GPU; each loaded model "all on the GPU" or "N GB on the GPU, the rest on the CPU"; loaded outside the plan; model servers left running by an Ollama that is gone; the GPU lock held (its `LaneRow` for the job) |
| `PreflightLine` | inside `ModelStack`, one for jason's model and one for the embedder | `preflight[]` | would run; would run (already loaded); would refuse, with the preflight's own sentence (not answering, not pulled, no GPU, short of commit with the two figures) |
| `CommitHeadroom` | inside `ModelStack` | `commit` | the figures as text (committed, limit, free) with the bar repeating them; under jason's warning line ("nearly full"); the page files in use and those set but not in use (a setting that applies at the next restart); not Windows (no commit figures: "not read on this system") |
| `IndexHealth` | the Index tab; a line on `#/instance` | `GET /api/machine/index` | not built (the build command); built, with size, embedder, vectors, and the catalogs by standing; passages with no vector (the count and the command that embeds them); built with another embedder (vectors for the current one: none); building now (the store lock's holder); unreadable; when it was built: "not recorded" until the build stamps it |

### The words

Every state is a word, from the code where the code has one (`storage.lines`, `local_ai.status_lines`, `Resource`, `passage_index.Standing`), and a color only repeats it.

| Word | Where from | Meaning |
| --- | --- | --- |
| kept here | `Place` | a place jason reads or writes, on this drive |
| not there yet | `storage.lines` | the place or the file does not exist; for a user config, "name the folders in it" |
| not measured | `size: null` | the folder was not walked (sizes are on request) |
| free space unknown | `free: null` | the drive could not be read |
| tiny | `Place.tiny` | a lock or a file's path: never what fills a drive |
| short of room | `storage.problems` | the drive has less free than the floor, and jason keeps something there |
| in effect, overridden, not named, file not there, not read by this program, the default stands | the setting's chain | which layer set the value, and what each other layer did |
| left behind | `storage.problems` (legacy) | files in an old default folder that nothing now reads |
| held, since, for | `locks.holders` | a process holds the lock; the note says its command, purpose, and start |
| up, not answering | `local_ai.status_lines` | the model server answered, or did not |
| all on the GPU; N GB on the GPU, the rest on the CPU | `local_ai.status_lines` | where a loaded model sits |
| would run, would refuse | `local_ai.preflight` | what a model job's preflight would say now |
| built, not built, building now | `passage_index.status`, the store lock | the index's state |
| authority, record, reference, page, evidence | `passage_index.Standing` | a catalog's standing in the index |

**Severity words** for `MachineProblems`, proposed, a closed set the server attaches (decision 1), worst first:

| Word | Meaning | From | Counted by |
| --- | --- | --- | --- |
| stops runs | every jason program refuses to start until it is fixed | `temp_dir_problem` (`JASON_TEMP_DIR` names a missing drive, a folder that cannot be written, or a path with a control character) | `jason storage --check`; and every other command, `jason-web`, the worker, and the scripts stop with it (`apply_temp_dir_or_exit`, exit 2) |
| refuses model jobs | a model job's preflight would refuse it | `local_ai.preflight` (not answering, not pulled, no GPU, short of commit); `findings` (not answering, no GPU) | `jason local-ai --check` for the findings; the preflight's own refusals only by the job that meets them |
| short of room | a drive under the floor holds jason's places; Windows commit is nearly full; scratch lands on the small drive | `storage.problems`; `local_ai.findings` (commit) | `jason storage --check`; `jason local-ai --check` |
| left behind | files in an old default folder | `storage.problems` (legacy) | `jason storage --check` |
| worth a look | a model partly on the CPU, a model loaded outside the plan, model servers left by a gone Ollama, a page file set but not in use, passages with no vector, a drive whose free space is unknown | `local_ai.findings`; `passage_index.status`; `free: null` | `jason local-ai --check` for the model lines; **no check counts** the index's or an unreadable drive's (decision 8) |

The problem's own sentence is shown verbatim, as the check prints it: the console never rewrites "JASON_TEMP_DIR is E:/jason-scratch/tmp, but the drive E:\ does not exist" into a summary.

## Data shapes

Made-up machine: a small system drive `C:`, data on `E:`, models on `F:`, the home folder shown as `~`. Every path, size, process, and model below is invented; on the screen they come from the loaders, never from this page.

`GET /api/machine/storage` (proposed; `storage.report(data_dir, sizes=False)` with the `parent` and `omitted` keys added; `?sizes=1` measures, which can take minutes):

```json
{
  "found": true, "asOf": "2099-10-05T14:02:00", "measured": false,
  "floor": {"gb": 20, "from": "the check's default (jason storage --min-free-gb)"},
  "drives": [
    {"drive": "C:", "system": true, "free": 9663676416, "freeWords": "9.0 GB free", "standing": "short of room",
     "places": ["Hugging Face cache (HF_HOME)"]},
    {"drive": "E:", "system": false, "free": 412316860416, "freeWords": "384.0 GB free", "standing": "room",
     "places": ["data directory", "retrieval index (index.db)", "retrieval vectors", "library", "temp (JASON_TEMP_DIR)", "ASSPY_HOME (county index cache)", "lawlibrary archive (LAWLIBRARY_DATA)"]},
    {"drive": "F:", "system": false, "free": null, "freeWords": "free space unknown", "standing": "free space unknown",
     "places": ["Ollama models (OLLAMA_MODELS)"]}
  ],
  "places": [
    {"name": "data directory", "parent": null, "path": "E:/jason-data", "drive": "E:", "free": 412316860416, "size": null, "note": "", "exists": true, "tiny": false},
    {"name": "retrieval index (index.db)", "parent": "data directory", "path": "E:/jason-data/retrieval/index.db", "drive": "E:", "free": 412316860416, "size": null, "note": "", "exists": true, "tiny": false},
    {"name": "temp (JASON_TEMP_DIR)", "parent": null, "path": "E:/jason-scratch/tmp", "drive": "E:", "free": 412316860416, "size": null, "note": "scratch, OCR page images, SQLite spill, pytest", "exists": true, "tiny": false},
    {"name": "Hugging Face cache (HF_HOME)", "parent": null, "path": "~/.cache/huggingface", "drive": "C:", "free": 9663676416, "size": null, "note": "", "exists": true, "tiny": false},
    {"name": "Ollama models (OLLAMA_MODELS)", "parent": null, "path": "F:/models", "drive": "F:", "free": null, "size": null, "note": "", "exists": true, "tiny": false},
    {"name": "locks", "parent": null, "path": "~/.jason/locks", "drive": "C:", "free": 9663676416, "size": null, "note": "held while a model or a store is in use", "exists": true, "tiny": true},
    {"name": "Google token", "parent": null, "path": "E:/jason/secrets/google-token.json", "drive": "E:", "free": 412316860416, "size": null, "note": "path and drive only", "exists": true, "tiny": true}
  ],
  "temp": {"configured": true, "setting": "E:/jason-scratch/tmp", "path": "E:/jason-scratch/tmp", "systemTemp": "~/AppData/Local/Temp",
           "systemTempDrive": "C:", "systemTempFree": 9663676416, "error": "", "startedWith": "E:/jason-scratch/tmp"},
  "configs": [
    {"name": "jason", "path": "~/.jason/.env", "exists": true, "namedBy": ""},
    {"name": "asspy", "path": "~/.asspy/.env", "exists": false, "namedBy": ""},
    {"name": "lawlibrary", "path": "~/.lawlibrary/.env", "exists": true, "namedBy": ""}
  ],
  "legacy": [
    {"name": "asspy", "path": "~/AppData/Local/asspy", "files": 1000, "atLeast": true, "moveTo": "E:/asspy", "targetFiles": 0}
  ],
  "omitted": [],
  "masked": {"home": "~"},
  "commands": {"check": "jason storage --check", "json": "jason storage --json", "sizes": "jason storage"},
  "caveats": ["Read only: no file's contents are read. The secrets folder and the Keeper config are named by path and drive.",
              "These are jason-web's views of the machine. A program launched by a packaged application sees its own copy of AppData; run jason storage --check in a terminal to see the terminal's."]
}
```

`omitted` is a miss named, never a silent gap: `{"place": "lawlibrary archive (LAWLIBRARY_DATA)", "why": "lawlibrary did not answer within 30 seconds", "command": "jason storage"}`, or `{"place": "Google token, Keeper config", "why": "the settings could not be read"}`. Today `storage.report` leaves those places out without saying (decision 9).

`GET /api/machine/settings` (proposed; one row a storage setting from an allowlist, never any other key; the layer that set each value comes from the same function that resolves it):

```json
{
  "found": true, "asOf": "2099-10-05T14:02:00",
  "projectEnv": {"path": "E:/jason/.env", "exists": true, "from": "the checkout's own (JASON_ENV is not set)"},
  "settings": [
    {"key": "JASON_TEMP_DIR", "program": "jason", "what": "scratch, OCR page images, SQLite spill, pytest",
     "chain": [
       {"layer": "environment", "where": "jason-web's process, started 2099-10-05 07:00", "state": "not named"},
       {"layer": "project .env", "file": "E:/jason/.env", "state": "names it", "value": "C:/Temp/jason", "overridden": false},
       {"layer": "user config", "file": "~/.jason/.env", "state": "names it", "value": "E:/jason-scratch/tmp", "overridden": true},
       {"layer": "default", "value": "the system's temp folder", "state": "not reached"}],
     "inEffect": {"layer": "project .env", "value": "C:/Temp/jason", "resolved": "C:/Temp/jason", "drive": "C:", "usable": true},
     "startedWith": "C:/Temp/jason",
     "change": {"file": "~/.jason/.env", "line": "JASON_TEMP_DIR=<a folder on a roomy drive, forward slashes>",
                "also": "remove JASON_TEMP_DIR from E:/jason/.env, which comes first", "then": "jason storage --check"}},
    {"key": "ASSPY_HOME", "program": "asspy", "what": "county index caches, association directories, roll downloads, samples",
     "views": [
       {"who": "jason, which copies its own setting into asspy's environment first (asspy_home.apply)",
        "chain": [{"layer": "environment", "state": "not named"},
                  {"layer": "project .env", "file": "E:/jason/.env", "state": "not named"},
                  {"layer": "jason's user config", "file": "~/.jason/.env", "state": "names it", "value": "E:/asspy"},
                  {"layer": "asspy's user config", "file": "~/.asspy/.env", "state": "file not there"},
                  {"layer": "default", "value": "~/.asspy", "state": "not reached"}],
        "inEffect": {"layer": "jason's user config", "value": "E:/asspy"}},
       {"who": "asspy on its own (a terminal, a scheduled task)",
        "chain": [{"layer": "environment", "state": "not named"},
                  {"layer": "asspy's user config", "file": "~/.asspy/.env", "state": "file not there"},
                  {"layer": "default", "value": "~/.asspy", "state": "in effect"}],
        "inEffect": {"layer": "default", "value": "~/.asspy"}}],
     "agree": false,
     "disagreement": "jason and asspy read different folders: jason E:/asspy, asspy on its own ~/.asspy",
     "change": {"file": "~/.asspy/.env", "line": "ASSPY_HOME=E:/asspy", "then": "jason storage --check"}},
    {"key": "OLLAMA_MODELS", "program": "Ollama", "what": "the model files",
     "chain": [{"layer": "environment", "state": "names it", "value": "F:/models"}, {"layer": "default", "value": "~/.ollama/models", "state": "not reached"}],
     "inEffect": {"layer": "environment", "value": "F:/models"},
     "change": {"file": null, "line": null, "note": "Ollama reads its own environment variable. jason never changes a system or user setting; a person sets it and restarts Ollama."}}
  ],
  "allowlist": ["JASON_TEMP_DIR", "JASON_DATA_DIR", "PAYHOA_CATALOG", "JASON_LOCK_DIR", "LAWLIBRARY_HOME", "ASSPY_HOME", "LAWLIBRARY_DATA", "OLLAMA_MODELS", "HF_HOME"],
  "commands": {"show": "jason storage --settings", "check": "jason storage --check"},
  "caveats": ["Only the storage settings above are read from each file, by key. No other line of any settings file is read into this answer.",
              "Environment means jason-web's own process. A terminal, an agent's shell, or a scheduled task can have another; the files are read the same by all."]
}
```

`POST /api/machine/settings/check` (proposed; behind the write guard because it carries a path, yet it writes nothing and creates no folder): `{"key": "JASON_TEMP_DIR", "value": "G:/scratch/tmp"}` answers `{"resolved": "G:/scratch/tmp", "drive": "G:", "free": null, "usable": false, "problem": "JASON_TEMP_DIR is G:/scratch/tmp, but the drive G:\\ does not exist. Connect it or change JASON_TEMP_DIR in .env; jason will not fall back to the system temp folder.", "line": "JASON_TEMP_DIR=G:/scratch/tmp"}`, the problem in `temp_dir_problem`'s own words. A value that looks like a secret is refused with `intake.secret_reason`'s message and nothing is kept.

`GET /api/machine/locks` (proposed; `locks.holders` without pruning, decision 5):

```json
{
  "found": true, "asOf": "2099-10-05T14:02:00",
  "folder": {"path": "~/.jason/locks", "from": "default (JASON_LOCK_DIR is named nowhere)"},
  "held": [
    {"lock": "gpu", "resource": "gpu", "resourceWords": "the local model server", "key": "", "community": null,
     "pid": 4120, "command": "jason board --minutes 2099-10-01", "purpose": "draft the minutes",
     "since": "2099-10-05T13:58:41+00:00", "heldFor": "3 min"},
    {"lock": "store-retrieval-index", "resource": "store", "resourceWords": "a store jason reads, changes, and writes back", "key": "retrieval-index",
     "community": null, "pid": 5216, "command": "jason index --build", "purpose": "build the passage index",
     "since": "2099-10-05T12:40:03+00:00", "heldFor": "1 h 22 min"},
    {"lock": "payhoa-example", "resource": "payhoa", "resourceWords": "a community's PayHOA session", "key": "example",
     "community": "example", "pid": 6020, "command": "jason sync-catalog --by Jane Example", "purpose": "",
     "since": "2099-10-05T14:01:10+00:00", "heldFor": "1 min"}
  ],
  "leftBehind": [],
  "commands": {"show": "jason local-ai"},
  "caveats": ["The lock is the fact; the note beside it is advice. A lock is released when its process ends, even by a crash.",
              "Nothing here releases a lock. Ending the process that holds it releases it; that is a person's act at the machine."]
}
```

`GET /api/machine/models` (proposed; `local_ai.status` plus a preflight report for jason's model and the embedder that runs the same checks and raises nothing):

```json
{
  "found": true, "readAt": "2099-10-05T14:02:05", "readBy": "A. Admin",
  "server": {"url": "http://127.0.0.1:11434", "up": true, "version": "0.0.0-example",
             "devices": [{"library": "CUDA", "description": "Example GPU 24 GB", "driver": "0.0", "total": "24.0 GiB", "available": "21.5 GiB"}],
             "orphans": []},
  "plan": {"jasonModel": "example-model:27b", "embedModel": "example-embed:8b"},
  "loaded": [{"name": "example-embed:8b", "size": 6442450944, "vram": 6442450944, "where": "all on the GPU", "inPlan": true, "expires": "2099-10-05T14:06:00"}],
  "preflight": [
    {"model": "example-model:27b", "result": "would refuse", "words": "loading example-model:27b needs about 25.0 GB of Windows commit and 18.2 GB is free; unload a model (jason local-ai --unload NAME --yes) or raise the page file",
     "need": 26843545600, "free": 19542101197},
    {"model": "example-embed:8b", "result": "would run", "words": "loaded"}],
  "commit": {"limit": 68719476736, "committed": 49177375539, "free": 19542101197, "nearlyFullBelow": 8589934592, "margin": 4294967296,
             "pageFiles": [{"file": "E:\\pagefile.sys", "size": 34359738368}], "configured": ["E:\\pagefile.sys 32768 32768"]},
  "gpuLock": {"held": true, "lock": "gpu", "pid": 4120, "command": "jason board --minutes 2099-10-01", "since": "2099-10-05T13:58:41+00:00"},
  "findings": [],
  "commands": {"show": "jason local-ai", "check": "jason local-ai --check", "unload": "jason local-ai --unload example-embed:8b --yes",
               "restart": "jason local-ai --restart-ollama --yes"},
  "caveats": ["jason changes no setting of Ollama, the driver, or Windows. Unloading a model and restarting Ollama are a person's commands."]
}
```

`GET /api/machine/index` (proposed; `passage_index.status` opened read-only, the store lock, and the build's own stamp once it writes one):

```json
{
  "found": true, "built": true, "path": "E:/jason-data/retrieval/index.db", "bytes": 2147483648,
  "model": "example-embed:8b", "vectors": 48810, "withoutVector": 312,
  "builtAt": null, "builtAtWords": "not recorded: the index does not stamp its build yet",
  "building": {"lock": "store-retrieval-index", "pid": 5216, "command": "jason index --build", "since": "2099-10-05T12:40:03+00:00"},
  "catalogs": [
    {"catalog": "authorities", "standing": "authority", "files": 412, "passages": 18230},
    {"catalog": "library", "standing": "record", "files": 1204, "passages": 26115},
    {"catalog": "reports", "standing": "page", "files": 88, "passages": 3911},
    {"catalog": "example-case", "standing": "evidence", "files": 61, "passages": 866}
  ],
  "vectorsCache": {"path": "E:/jason-data/retrieval/vectors", "size": null},
  "commands": {"status": "jason index --status", "build": "jason index --build", "plan": "jason index --plan"},
  "caveats": ["A hit is a passage to read, not a finding; a generated page is a summary, never the rule."]
}
```

A catalog of standing `evidence` (a legal case's file) is P3: outside the private view the row reads "a legal case's file (evidence)" with its counts and no name, as the cases are listed elsewhere.

`GET /api/machine/problems` (proposed; one list from the rows the checks already make, each with its kind and severity attached where the line is written):

```json
{
  "found": true, "asOf": "2099-10-05T14:02:05",
  "problems": [
    {"severity": "refuses model jobs", "kind": "preflight-commit", "source": "models",
     "words": "loading example-model:27b needs about 25.0 GB of Windows commit and 18.2 GB is free; unload a model (jason local-ai --unload NAME --yes) or raise the page file",
     "countedBy": "a model job's own preflight", "command": "jason local-ai", "tab": "models"},
    {"severity": "short of room", "kind": "drive-low", "source": "storage",
     "words": "C: has 9.0 GB free, under 20 GB, and jason keeps Hugging Face cache (HF_HOME) there",
     "countedBy": "jason storage --check", "command": "jason storage --check", "tab": "places"},
    {"severity": "left behind", "kind": "legacy", "source": "storage",
     "words": "1000+ files are left in ~/AppData/Local/asspy, an old default folder for asspy that nothing now reads; move it to E:/asspy (docs/setup.md, Where jason writes)",
     "countedBy": "jason storage --check", "command": "jason storage --check", "tab": "left-behind"},
    {"severity": "worth a look", "kind": "drive-unknown", "source": "storage",
     "words": "F: could not be read: its free space is unknown, and jason keeps Ollama models (OLLAMA_MODELS) there",
     "countedBy": "no check counts it yet", "command": "jason storage", "tab": "places"},
    {"severity": "worth a look", "kind": "index-without-vector", "source": "index",
     "words": "312 passages have no vector for example-embed:8b; a dense search does not reach them",
     "countedBy": "no check counts it yet", "command": "jason index --build", "tab": "index"}
  ],
  "unavailable": [],
  "checks": {"storage": {"command": "jason storage --check", "exit": 1}, "models": {"command": "jason local-ai --check", "exit": 0}}
}
```

`checks` says what each check would exit with now, so the screen and the terminal agree; `unavailable` names a source that could not be read, with its note and command, and the rest still list.

## What the design must keep

- **No secret, ever** (principle 6, P4). The Google token and the Keeper config are a path and a drive, never their contents; a settings file is a path and "there" or "not there yet", and the only keys read out of it are the allowlisted storage settings. Key names outside the allowlist are not returned either: the screen never lists what a `.env` holds. No field asks for a secret; the folder check refuses one in `intake.secret_reason`'s words and keeps nothing.
- **The layer that set it, from the function that sets it.** A `SettingChain` is the resolver's own answer (the environment, then the project's `.env`, then the user config, then the default, for jason; asspy's and lawlibrary's own orders for theirs), never a reconstruction on the client. Where two programs read one setting differently (`ASSPY_HOME` as jason runs asspy and as asspy runs alone), both are shown with their values and the console picks neither.
- **jason-web's environment is not the terminal's.** "Environment" is labelled as the server's process, with its start time, and a value read from a file after the server started is shown beside the one it started with ("restart to use it", with the neighbour's `jason daemon stop` and `jason serve` as `TerminalStep`s).
- **The console writes no settings file, moves no folder, releases no lock, and changes no Windows or Ollama setting.** It shows the file, the line, and the command, then reads again (decisions 2, 3, 5, 10). Every such step is a `TerminalStep` naming "a person at the machine" and why it is not a button. If a write is ever built (decision 2), it is a `Confirm` in the signed-in administrator's name, through the write guard, with its CLI equivalent named, and refused for any key outside the allowlist.
- **A move is a person's act, verified after.** `LeftBehind` names the old folder, the folder to move into, and what the target already holds; after the person moves the files, the screen reads again and says "nothing left" or the count still there. Where both folders hold files, the screen says so and suggests no merge.
- **The check's own words.** Each problem, finding, and preflight refusal is rendered verbatim (`Findings`); the severity word is beside it, never in place of it. Each one names the check that counts it, or "no check counts it yet", so the console never reports a problem the terminal would pass silently, or the reverse.
- **No threshold invented.** The floor is the check's (`--min-free-gb`, 20 GB by default) and says so; commit's "nearly full" line is jason's 8 GB, named; a lock held long has its age and no word, since no lock declares a limit.
- **A miss stays a miss** (principle 8). A drive that cannot be read is "free space unknown", never 0 GB; a place not asked (lawlibrary silent, settings unreadable) is named with why; a model server not read yet says so and offers the read, never an empty card; an index not built is "not built" with the build command; "when it was built" is "not recorded" until the build stamps it, never a file's modified time.
- **Reading changes nothing.** The loaders open SQLite read-only, create no lock folder, prune no lock note (decision 5), and walk no folder for sizes unless asked.
- **Administrator only.** Every route answers one of jason's admins signed in as themselves (`jason.web.access.signed_in`, as `GET /api/status` does): 401 with no sign-in, 403 for anyone else, 403 while an admin views as someone else, never in the owner view. An officer sees none of it; `#/status`'s summary line is the admin's too.
- **No color-only meaning.** Every state above is a word; a drive's bar repeats its figures in text; "in effect" is a word on the step, not a highlight.

## Where it goes

- **Instance → Machine** (proposed): `#/instance/machine`, beside Service and Integrations in the Instance group ([handoff-instance-and-integrations.md](handoff-instance-and-integrations.md)), administrator only (`owner: false`, `roles: administrator`). `MachineProblems` first, then `Tabs`: **Places** (`TempLine`, a `DriveRoom` a drive, the tiny places apart), **Settings** (`ConfigFiles`, then a `SettingChain` a setting), **Old folders** (`LeftBehind`; the tab hides when there are none and `MachineProblems` says "no old folder holds files"), **Locks** (`LockTable`), **Models** (`ModelStack`), **Index** (`IndexHealth`). Query: `?tab=places|settings|left-behind|locks|models|index`, `?setting=KEY` (a key from the allowlist), `?sizes=1`. A URL never carries a path ([security-and-privacy.md](security-and-privacy.md#urls)): a path can carry a user name. The header's `Command` is `jason storage --check`.
- **`#/instance`**: one line each from `MachineProblems` ("2 problems: 1 refuses model jobs, 1 short of room"), `ModelStack` ("Model server up; the GPU lock held 3 min by a minutes draft"), and `IndexHealth` ("Index built; 312 passages with no vector"), linking into the tabs.
- **`#/status`** ([screens/status.md](screens/status.md)): one line under its header for an admin, "The machine: 2 problems", linking to `#/instance/machine`, until Instance exists (decision 6). Status keeps its sources, sign-ins, gates, and failures; nothing here moves into it.
- **Instance → Integrations**: the "local models" and "the law library" and "county caches" cards ([handoff-admin-components.md](handoff-admin-components.md)) link to the Models, Settings (`LAWLIBRARY_DATA`), and Places (`ASSPY_HOME`) tabs for where their files live. The connection state stays the card's.
- **Instance → Service**: the GPU lane's `LaneRow` and the GPU lock are one fact seen twice; the lane links to the Locks tab's row, and the lock's row names the job.

**Loaders and writes to add** (all proposed; each wraps a function that exists, except where marked "to write"; none derives a fact of its own):

| Name | Function behind it | Reads | Writes |
| --- | --- | --- | --- |
| `machine-storage` | `jason.storage.report(data_dir, sizes=False)`; with `?sizes=1`, `sizes=True`. To write: `parent` on each place instead of the name's leading spaces, `drives[]` grouped by the server, `omitted[]` for a place not asked and why, `temp.startedWith` (`config.system_temp` and the value `apply_temp_dir` used at start), `legacy[].targetFiles`, and the home folder replaced by `~` | disk only; a child process for lawlibrary (`_lawlibrary_paths`, 30 s) | — |
| `machine-settings` | to write: `config.setting_chain(key)` over an allowlist `config.STORAGE_SETTINGS`, built on `_env_value`'s order and `env_file_values`' files, reading each file once and keeping only the allowlisted keys; asspy's order through a public `asspy.paths.where(key)` (to write in asspy; jason imports no `_` name); lawlibrary's asked of its checkout, as `_lawlibrary_paths` asks today. The CLI twin, `jason storage --settings` (to write), prints the same chains | disk; the server's environment | — |
| write `machine/settings/check` | to write: `config.resolve_temp_dir` and `temp_dir_problem` for the temp setting, `storage.drive_of` and `free_bytes` for any path; `intake.secret_reason` on the value | disk only; creates nothing | nothing (a POST only because it carries a path) |
| `machine-locks` | `locks.holders` with a read-only variant that reports a free lock's note as "left behind" and deletes nothing (to write: `holders(prune=False)`), and a `lock_dir` that does not create the folder on read | the lock folder | — |
| `machine-models` | `local_ai.status`; to write: `local_ai.preflight_report(model)`, the preflight's checks as a dict (`result`, `words`, `need`, `free`) that raises nothing, for `DEFAULT_MODEL` and `EMBED_MODEL`; `findings` with a `kind` each | Ollama's local API (127.0.0.1), its server log, Windows' commit figures and process list, the registry's page file settings | — |
| `machine-index` | `passage_index.status(data_dir)` opened read-only (today it opens through `connect`, which may write its schema row); the store lock `retrieval-index` from `machine-locks`; to write: a `built_at` row in the index's `meta` table at the end of `build` | the index file, the lock folder | — |
| `machine-problems` | to write: `storage.problem_rows` and `local_ai.finding_rows`, the same lines `problems` and `findings` print today, each with `kind` and `severity` attached where it is written; plus the preflight refusals, `free: null`, and the index's `withoutVector` | through the loaders above | — |

There is no write route on this page. Unloading a model, restarting Ollama, editing a settings file, moving a folder, and ending a process are each a `TerminalStep` (decisions 2, 3, 10).

## Accessibility

As [components.md](components.md#accessibility), with these particulars.

- **Problems first, as a list.** `MachineProblems` is a `<ul>` under a heading with the count ("2 problems"), each item starting with its severity word in text, then the check's words, then "counted by" and the `Command`. When the page loads with a "stops runs" problem, that item is also announced once with `role="alert"`; the rest are not.
- **A drive is a `Card` with a heading** ("E: 384.0 GB free"); its bar, if drawn, is `aria-hidden` because the heading and a line of text carry the figures ("384.0 GB free; floor 20 GB; jason keeps 7 places here"). The places are a `DataTable` with columns name, path, size, state; a child place is a row whose name column says "in the data directory", not an indent alone.
- **A `SettingChain` is an ordered list** (`<ol>`), one item a layer in the program's order, each with its state word; the item in effect says "in effect" in text and carries `aria-current="true"`. An overridden value reads "overridden by the project .env", never a strikethrough alone. Two views are two lists under their own headings, with the disagreement as a sentence above them.
- **`SettingChange` is a disclosure** (`<details>`), its summary "How to change JASON_TEMP_DIR". The folder field has a visible label ("A folder on a roomy drive"), the check's answer arrives in `role="status"`, a refusal in `role="alert"` tied to the field with `aria-describedby`. The line and the command are `Command`s with copy buttons whose accessible names say what they copy ("Copy the line for ~/.jason/.env").
- **Locks and loaded models are `DataTable`s** with captions ("Locks held now", "Models loaded"); "held for" is text ("1 h 22 min") beside a `<time>` for "since".
- **`ModelStack`'s read** (decision 4) is a button, "Read the model server now", busy while it runs and then the result in place; nothing reads on its own on a timer.
- **Paths** are in a code face, wrap at slashes inside their cell, and never scroll the page sideways; `~` is read out as "home folder" through an `abbr` with a title, or as text (decision 7).
- **Shortcuts** as [patterns.md](content/patterns.md#keyboard-use); every target 24 by 24 CSS pixels or spaced to pass; nothing needs a drag; nothing times out.

### The phone layout (under 720 px)

- `MachineProblems` stays first, each problem a card: the severity word, the words, then the `Command` full width.
- The tabs become a `select` ("Places, Settings, Old folders, Locks, Models, Index").
- A drive is a card with its free space and floor as two lines of text; its places a list of name, then path, then size, each on its own line; the tiny places under a disclosure ("3 small files").
- A `SettingChain` stays an ordered list, one layer a line, the value under its layer; "How to change it" opens under the chain, its field and the copy buttons full width.
- Locks and loaded models become cards: the lock or model first, then the holder or where it sits, then since.
- "Go to" replaces the nav as `ConsoleShell` does. Nothing scrolls sideways at 320 px.

## Decisions for the design

1. **Severity words.** The five above (stops runs, refuses model jobs, short of room, left behind, worth a look) are a proposal; the checks print plain lines. Decide the set and its glyphs (one meaning a glyph; the overdue and stop glyphs are taken), knowing the server attaches the word where the line is written, so the terminal can print the same word.
2. **Whether the console ever writes a settings file.** Today it shows the file, the line, and the command. A write would be one key in the allowlist, to the program's own user config, as a `Confirm` in the administrator's name through the write guard, after a backup, with a CLI twin (`jason storage --set KEY=VALUE --by NAME`, to write). Against it: the user config is the person's own file in the home folder, a hosted install has no such file, and a setting that moves the data directory under a running server needs a restart anyway. Decide: never, or only for `JASON_TEMP_DIR` and the lock folder, or for the allowlist.
3. **The move.** Decide whether `LeftBehind` shows an operating-system command (a copy that keeps existing files) as a `Command`, or only the two folders in words, since a wrong merge loses data; and whether a person records "moved" as a line in jason's own log, or the re-read alone is the record.
4. **Reading the model server on load.** It is local (127.0.0.1), not a service outside the machine, but it queries Ollama, the process list, and the registry. Decide whether `ModelStack` reads on load, or shows "not read yet" with a button that reads it as a person's action (named in `readBy`).
5. **Lock notes left behind.** `holders()` deletes a note whose lock is free, and `lock_dir()` creates the folder, so a plain read writes. Decide whether the loader prunes as the CLI does (housekeeping, not a person's act) or reports "left behind by a process that ended" and deletes nothing. Either way, no control in the browser releases a held lock; decide whether the screen ever offers to end a holding process (the brief says no).
6. **Where it lives until Instance exists.** Decide whether `#/instance/machine` waits for the Instance group, or ships first as a band of `#/status` with the same components, moving later.
7. **Masking a path that names a person.** A path under the home folder carries the operating system's user name (`C:/Users/<name>/...`), and a lock's command line carries an executable path and a `--by NAME`. The proposal: the server replaces the home folder with `~` everywhere, masks emails and phone numbers in command lines (`jason.approvals.audit.mask`), and shows the rest. Decide whether an administrator can reveal a full path, and if so whether that is logged as a reveal (`access/served.jsonl`).
8. **What the checks count.** An unreadable drive and passages with no vector are counted by no check today. Decide whether `jason storage --check` should count a drive it cannot read, and whether the index needs a check of its own (`jason index --check`, to write) before the console marks either above "worth a look".
9. **Sizes.** Measuring walks every folder and can take minutes on an archive of tens of gigabytes. Decide whether sizes are measured on request only (proposed), cached with the time they were measured, or measured by a scheduled job; a size is never shown without when it was measured.
10. **Model actions.** `jason local-ai --unload NAME --yes` and `--restart-ollama --yes` change what Ollama runs. Decide whether they stay `TerminalStep`s, or become a job a person queues behind `Confirm` (the GPU lane, `jason jobs`), named and logged, never on a timer.
11. **The floor.** It is the check's flag, not a setting. Decide whether the screen lets a person view the page at another floor (the page's own state, not stored, as the event picker does in [handoff-applicability-questions.md](handoff-applicability-questions.md)), and whether the floor becomes a setting (`JASON_MIN_FREE_GB`, to write) so the console and a scheduled check agree.
12. **Several communities on one machine.** The report reads one data directory, the active profile's. Decide whether the Places tab lists every community's data folder under the data root (each with its size), or the machine view shows the data root alone and Instance → Communities shows each folder's size.

## Not part of this pass

- The service, its heartbeat, its lanes, and its start and stop: `ServiceStatus` and `LaneRow` in [handoff-admin-components.md](handoff-admin-components.md).
- Credentials, the vault, and the setup dialogs: [handoff-instance-and-integrations.md](handoff-instance-and-integrations.md). This page names the Google token and the Keeper config by path only.
- The county index cache's coverage (`index_coverage`, `index_survey`, `county_status`): asspy's data and its own screens; this page shows only where `ASSPY_HOME` is and how much room it takes.
- Searching the passage index or building a pack from it: `handoff-context-pack-workbench.md`.
- Changing Windows (page files, `PagefileOnOsVolume`, `setx TEMP`), the GPU driver, or Ollama's own settings: [../setup.md](../setup.md#where-jason-writes) lists what a person may choose to run; jason changes none of it.
- Deleting scratch, a cache, or another program's files: [../scratch.md](../scratch.md) says what may be deleted and by whom; the console deletes nothing.
- Any owner-facing or officer-facing version: the machine is the administrator's at every phase.
- The previews: the design project's authored preview for each component follows the build; fixtures will be `ui/src/components/machineproblems.test.tsx` and its siblings, from the sample data above.
