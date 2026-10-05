"""Score the duty readers against the hand-labelled gold sets in data/duties/gold (gold.json, gold-fresh.json).

    python scripts/eval_duties.py                          # the grammar on every gold set; sends nothing anywhere
    python scripts/eval_duties.py --ask read --model qwen3.5:9b     # ask the local model for the gold passages first
    python scripts/eval_duties.py --ask review --model qwen3.5:9b   # the hybrid: the model reviews the grammar's candidates
    python scripts/eval_duties.py --model qwen3.5:9b       # score grammar, model, hybrid, and hybrid-fill from the cache
    python scripts/eval_duties.py --errors                 # also print each miss, extra, and wrong field

A model answer is cached by passage and words in data/duties/model/, so a rerun only scores. A model request holds
the GPU lock and runs jason.local_ai.preflight first; --unload releases the model afterwards (keep_alive 0), which a
pytest run on this machine needs. Split: in gold.json the even-numbered passages were used to tune the grammar (dev)
and the odd ones were held out (test); gold-fresh.json was drawn and labelled after the grammar was frozen.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from jason.tasks.document_duties import evaluate, gold_texts, model_run, readings


def main(argv: list[str] | None = None) -> int:
    from jason.config import apply_temp_dir_or_exit

    apply_temp_dir_or_exit()          # JASON_TEMP_DIR: scratch off the system drive
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default="data")
    parser.add_argument("--model", default="")
    parser.add_argument("--ask", choices=["read", "review"], help="ask the model for every gold passage not cached")
    parser.add_argument("--again", action="store_true", help="with --ask: ask again even when cached")
    parser.add_argument("--keep-alive", default="2m")
    parser.add_argument("--num-ctx", type=int, default=0, help="the context window (default: the shared model's)")
    parser.add_argument("--unload", action="store_true", help="unload the model when done")
    parser.add_argument("--errors", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")
    data = Path(args.data)
    sets = {}
    for name in ("gold.json", "gold-fresh.json"):
        path = data / "duties" / "gold" / name
        if path.is_file():
            sets[name] = json.loads(path.read_text(encoding="utf-8"))["passages"]
    if not sets:
        print("no gold sets in data/duties/gold", file=sys.stderr)
        return 1
    if args.ask:
        from jason.community.duty_model import DutyModel

        reader = DutyModel(model=args.model, keep_alive=args.keep_alive, num_ctx=args.num_ctx)
        ids = [e["id"] for entries in sets.values() for e in entries]
        try:
            model_run(data, ids, strategy=args.ask, reader=reader, again=args.again)
        finally:
            if args.unload:
                from jason.local_ai import unload

                unload(reader.model)
    strategies = ["grammar"] + (["model", "hybrid", "hybrid-fill"] if args.model else [])
    report: dict[str, dict[str, object]] = {}
    for name, entries in sets.items():
        texts = gold_texts(data, entries)
        splits = {"all": entries}
        if name == "gold.json":
            splits.update({"dev": entries[0::2], "test": entries[1::2]})
        for strategy in strategies:
            found = readings(data, [e["id"] for e in entries], strategy, model=args.model)
            for split, part in splits.items():
                result = evaluate(part, found, texts)
                report[f"{name} {split} {strategy}"] = result
                if not args.json:
                    print(f"{name:16} {split:5} {strategy:12} passages {result['passages']:3}  P {result['precision']:.2f}  "
                          f"R {result['recall']:.2f}  F1 {result['f1']:.2f}  (tp {result['tp']}, fp {result['fp']}, "
                          f"fn {result['fn']})  " + "  ".join(f"{k} {v}" for k, v in result["fields"].items()))
                if args.errors and split == "all" and not args.json:
                    for line in result["errors"]:
                        print(f"    {line}")
    if args.json:
        print(json.dumps(report, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
