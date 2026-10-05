# Scratch

Where an agent or a script puts what it makes only for a check, and what it must leave alone. The system drive is small; the data drive is not. Nothing temporary goes to the system drive.

## Where scratch goes

- **One folder per task on the data drive**: `D:\scratch\jason\<name>\` (a made-up drive and name; use the drive `JASON_TEMP_DIR` names). Put in it every copy, probe, log, and experiment. Temp files too: `tmp\` inside it.
- **Python's temp folder, SQLite's spill, and a child's temp files all follow `TEMP` and `TMP`.** `tempfile` reads them, a sort or index build that overflows SQLite's cache writes `etilqs_*` files into them, and every child process (a browser profile, Tesseract, the lawlibrary worker) inherits them. On Windows `SQLITE_TMPDIR` is ignored: setting it alone leaves the spill on the system drive. `TMPDIR` is for other systems. Set `TEMP` and `TMP` (and the other two, harmlessly) before the work starts.
- **Where jason chooses a place itself**, outside the data directory: the process locks (`JASON_LOCK_DIR`; tiny), the Keeper device config (`keeper_config`, `KEEPER_CONFIG_PATH`), and asspy's county files (`ASSPY_HOME`, in the environment or in `.env`; caches, association directories, roll downloads, browser samples, and they grow into gigabytes). Name each on the data drive.

## How a script sets its own

```bash
SCRATCH=D:/scratch/jason/<name>; mkdir -p "$SCRATCH/tmp"
export TEMP="$SCRATCH/tmp" TMP="$SCRATCH/tmp" TMPDIR="$SCRATCH/tmp" SQLITE_TMPDIR="$SCRATCH/tmp"
```

```powershell
$s = "D:\scratch\jason\<name>"; New-Item -ItemType Directory -Force "$s\tmp" | Out-Null
$env:TEMP = $env:TMP = "$s\tmp"
```

```python
import os
os.environ["TEMP"] = os.environ["TMP"] = r"D:\scratch\jason\<name>\tmp"     # before tempfile or sqlite3 first make a file
```

A build or an experiment against a store works on a copy under the scratch folder, with `JASON_DATA_DIR` pointing at it, never at the real data directory.

## What may be deleted, and what must not

- **Delete when the task is done**: the task's own scratch folder, its `tmp\`, and any copy it made.
- **A confidential copy** (a copy of the data directory, of a store, or of a file marked confidential) is removed when the check ends, or kept only on the data drive. Never on the system drive, in the user's temp folder, or in a shared folder.
- **Never delete the data directory** or anything in it as scratch. `data/retrieval/vectors` is a cache worth keeping: embedding is slow, and a build copies from it. `data/retrieval/index.db` is rebuilt from the files and the vectors, but only slowly.
- **Not jason's, so not ours to delete**: another session's folder, another application's data, an installer's cache. Report what is large and where it came from; the person decides.
