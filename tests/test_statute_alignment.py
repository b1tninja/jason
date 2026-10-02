"""The statute aligner on synthetic text: no model, no lawlibrary, no statute words."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from jason.community import statute_alignment as sa
from jason.sources.lawlibrary import Edition, OutlineNode, Section
from jason.tasks import statute_align as task

OLD_7 = """The words before the list.

(a) The keeper shall ring the copper bell at dawn every market day.

(b) A visitor may borrow a lantern from the keeper for three evenings.

(1) The lantern returns clean.

(A) With its wick trimmed.

(i) And its glass unbroken.

(c) The keeper shall publish the tower schedule on the gate fifteen days ahead."""

NEW_A = "On every market day the copper bell shall be rung at dawn by the keeper."
NEW_B = "A visitor may borrow a lantern from the keeper for three evenings."
NEW_C = "(a) The keeper shall publish the tower schedule on the gate fourteen days ahead.\n\n(b) The schedule names the bell ringer."


def test_subdivisions_keep_nested_labels_inside():
    units = sa.subdivisions("7", OLD_7, group="ARTICLE 1. Towers")
    assert [u.id for u in units] == ["7(intro)", "7(a)", "7(b)", "7(c)"]
    assert "(i) And its glass unbroken." in units[2].text      # a roman numeral under (A) is not a new subdivision
    assert units[0].group == "ARTICLE 1. Towers"
    one = sa.subdivisions("8", "A single rule with no list at all in it.")
    assert [u.id for u in one] == ["8"]


def test_subdivisions_letter_i_after_h_is_top_level():
    text = "\n\n".join(f"({c}) Rule number {c} about the lantern and the bell." for c in "abcdefghij")
    assert [u.label for u in sa.subdivisions("9", text)][-3:] == ["(h)", "(i)", "(j)"]


def test_gold_unit_labels():
    assert sa.gold_unit_labels("(e)(1)-(2)") == ["(e)"]
    assert sa.gold_unit_labels("(a)-(c)") == ["(a)", "(b)", "(c)"]
    assert sa.gold_unit_labels("(intro. cl.)") == ["(intro)"]
    assert sa.gold_unit_labels("") == [""]
    assert sa.gold_unit_labels("(last para)") == []


def test_quote_found_folds_and_refuses_short():
    text = "The keeper’s bell  shall ring\nat dawn."
    assert sa.quote_found("the keeper's bell shall ring at dawn", text)
    assert not sa.quote_found("bell", text)
    assert not sa.quote_found("the keeper shall sing at dusk", text)
    assert sa.quote_found("keeper's bell ... at dawn", text)


def _units():
    old = list(sa.subdivisions("7", OLD_7, group="ARTICLE 1. Towers"))
    new = [*sa.subdivisions("70", NEW_A, group="ARTICLE 1. Bells"), *sa.subdivisions("71", NEW_B, group="ARTICLE 2. Lanterns"),
           *sa.subdivisions("72", NEW_C, group="ARTICLE 1. Bells")]
    return old, new


def test_candidates_and_similarity_baseline():
    old, new = _units()
    tf = sa.Tfidf([u.text for u in old + new])
    smap = sa.structure_map(old, new, tf, gold_pairs=[("7", "70")], exclude_section="7")
    assert smap.targets("ARTICLE 1. Towers")                 # the outline maps the heading even with its own rows left out
    cs = sa.candidates(old, new, tf, smap, top_k=2)
    assert {c.id for c in cs.candidates} >= {"70", "71", "72(a)"}
    found = {(m.former, m.current) for m in sa.similarity_matches(cs, method="lexical", floor=0.2)}
    assert ("7(b)", "71") in found


def _fake_post(answers):
    calls = []

    def post(url, payload):
        calls.append(payload)
        assert payload["think"] is False and payload["options"]["temperature"] == 0
        prompt = payload["messages"][0]["content"]
        for key, matches in answers.items():
            if f") {key}:" in prompt:
                return {"message": {"content": json.dumps({"matches": matches})}, "eval_count": 10}
        return {"message": {"content": json.dumps({"matches": []})}}
    return post, calls


def _m(candidate, relation, fq, cq, change="", cf="", cc=""):
    return {"candidate": candidate, "relation": relation, "former_quote": fq, "current_quote": cq, "change": change,
            "change_former": cf, "change_current": cc}


def test_judge_keeps_only_grounded_answers():
    old, new = _units()
    tf = sa.Tfidf([u.text for u in old + new])
    cs = sa.candidates(old, new, tf, sa.structure_map(old, new, tf), top_k=3)
    post, calls = _fake_post({
        "7(a)": [_m("70", "continued_without_substantive_change", "ring the copper bell at dawn", "the copper bell shall be rung at dawn")],
        "7(b)": [_m("71", "continued_without_substantive_change", "borrow a lantern from the keeper", "a lantern made of gold")],
        "7(c)": [_m("72(a)", "continued_with_changes", "publish the tower schedule on the gate", "publish the tower schedule on the gate",
                    "notice 15 days -> 14 days", "fifteen days ahead", "fourteen days ahead")],
    })
    judge = sa.OllamaJudge(post=post)
    result = sa.judge_section(cs, judge, former_edition="old", current_edition="new")
    kept = {(m.former, m.current): m for m in result["matches"]}
    assert ("7(a)", "70") in kept and ("7(c)", "72(a)") in kept
    assert ("7(b)", "71") not in kept                         # its current quote is not in the text
    assert result["dropped"][0]["why"] == "current quote not found"
    assert kept[("7(c)", "72(a)")].change == "notice 15 days -> 14 days" and kept[("7(c)", "72(a)")].change_verified
    assert len(calls) == len(old)                            # one request per former unit, the candidates shared
    rows = {r["former"]: r for r in sa.per_former(old, result["matches"])}
    assert rows["7(b)"]["relation"] == "not_continued"
    current = {r["section"]: r for r in sa.per_current(new, result["matches"])}
    assert current["71"]["relation"] == "new" and current["72"]["changes"] == ["notice 15 days -> 14 days"]


def test_unverified_change_phrase_is_dropped():
    old, new = _units()
    by_id = {u.id: u for u in new}
    kept, _ = sa.verify(old[3], [_m("72(a)", "continued_with_changes", "publish the tower schedule", "publish the tower schedule",
                                    "notice 30 days -> 10 days", "thirty days", "ten days")], by_id)
    assert kept and kept[0].change == "" and not kept[0].change_verified and kept[0].confidence == "low"


def _gold_doc():
    def row(part, targets, source="disposition_table", succession="continued"):
        return {"act": "davis-stirling", "source": source, "succession": succession,
                "former": {"citation": f"CIV 7{part}", "section": "7", "part": part},
                "targets": [{"citation": f"CIV {t}", "section": t.split("(")[0], "part": t[len(t.split("(")[0]):]} for t in targets]}
    return {"sections": [{"section": "7", "rows": [
        row("(intro)", []), row("(a)", ["70"]), row("(b)", ["71"]), row("(c)", ["72(a)"]),
        row("(a)", ["70"], "commission_comment", "continued_without_substantive_change"),
        row("(c)", ["72(a)"], "commission_comment", "continued_with_changes")]}]}


def test_read_gold_and_evaluate():
    old, new = _units()
    gold = sa.read_gold(_gold_doc(), old)
    assert ("7(c)", "72") in gold.unit_pairs and "7(intro)" in gold.omitted_units
    matches = [sa.Match("7(a)", "70", "continued_without_substantive_change", "llm"),
               sa.Match("7(c)", "72(a)", "continued_with_changes", "llm"),
               sa.Match("7(intro)", "71", "continued_with_changes", "llm")]
    e = sa.evaluate(matches, gold, ["7"], current_scope=[u.section for u in new])
    assert e["section"]["tp"] == 3 and e["section"]["predicted"] == 3 and e["section"]["gold"] == 3
    assert e["unit"]["recall"] == round(2 / 3, 3)
    assert e["current_subdivision"] == {"named_by_table": 1, "matched": 1}
    assert e["omitted_units"] == {"gold": 1, "left_unmatched": 0}
    assert e["relation"]["accuracy"] == 1.0 and e["relation"]["with_changes"]["recall"] == 1.0
    assert e["new"]["gold"] == 0


class FakeLibrary:
    """lawlibrary's ``editions`` with synthetic text, counting the calls."""

    def __init__(self, texts):
        self.texts = texts
        self.calls = 0

    def editions(self, wanted):
        self.calls += 1
        out = []
        for code, start, end, session in wanted:
            sections = tuple(Section(f"{code} {n}", code, n, "", text, ("PART 5", heading), session)
                             for n, (heading, text) in self.texts.get(session, {}).items() if float(start) <= float(n) <= float(end))
            nodes = tuple(OutlineNode("article", h, n, n, 1) for n, (h, _) in self.texts.get(session, {}).items())
            out.append(Edition(code, start, end, session, sections, nodes))
        return tuple(out)


def test_recodification_end_to_end(tmp_path, monkeypatch):
    monkeypatch.setattr(task, "FORMER_SPAN", ("CIV", "1", "9", "2011"))
    monkeypatch.setattr(task, "CURRENT_SPAN", ("CIV", "10", "99", "2013"))
    hist = tmp_path / "authorities" / "history"
    hist.mkdir(parents=True)
    (hist / "former-sections.json").write_text(json.dumps(_gold_doc()), encoding="utf-8")
    lib = FakeLibrary({"2011": {"7": ("ARTICLE 1. Towers", OLD_7)},
                       "2013": {"70": ("ARTICLE 1. Bells", NEW_A), "71": ("ARTICLE 2. Lanterns", NEW_B), "72": ("ARTICLE 1. Bells", NEW_C)}})
    post, _ = _fake_post({"7(a)": [_m("70", "continued_without_substantive_change", "ring the copper bell at dawn",
                                      "the copper bell shall be rung at dawn")]})
    result = task.recodification(tmp_path, lib, judge=sa.OllamaJudge(post=post, model="fake"), label="t")
    assert Path(result["written"]).is_file(), result

    assert result["evaluation"]["llm"]["section"]["tp"] == 1
    assert {"structure", "lexical", "llm"} <= set(result["evaluation"])
    again = task.recodification(tmp_path, lib, judge=sa.OllamaJudge(post=lambda u, p: 1 / 0, model="fake"), write=False)
    assert again["sections"][0].get("cached")                  # the judged section is read back, not asked again
    assert lib.calls == 2                                       # the editions are kept on disk after the first fetch


def test_amendment_moves_letters_by_identity_and_asks_for_the_rest():
    old = sa.subdivisions("50", "(a) The keeper rings the bell.\n\n(b) The keeper decides within fifteen days.\n\n"
                                "(c) A visitor may appeal the keeper's decision to the council.", session="2023")
    new = sa.subdivisions("50", "(a) The keeper rings the bell.\n\n(b) A visitor may be heard first.\n\n"
                                "(c) The keeper decides within fourteen days.\n\n"
                                "(d) A visitor may appeal the keeper's decision to the council.", session="2025")
    post, calls = _fake_post({"50(b)": [_m("50(c)", "continued_with_changes", "The keeper decides within", "The keeper decides within",
                                           "decision 15 days -> 14 days", "fifteen days", "fourteen days")]})
    res = task.align_amendment(old, new, sa.OllamaJudge(post=post), before="2023", after="2025")
    pairs = {(m.former, m.current): m for m in res["matches"]}
    assert pairs[("50(a)", "50(a)")].source == "text_identity"
    assert pairs[("50(c)", "50(d)")].source == "text_identity"      # moved, words unchanged
    assert pairs[("50(b)", "50(c)")].source == "model" and pairs[("50(b)", "50(c)")].change == "decision 15 days -> 14 days"
    assert len(calls) == 1


def test_cli_registers():
    from jason.commands import statute_align

    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command")
    statute_align.register(sub, lambda p: p.add_argument("--env", default=".env"), lambda a: None)
    args = parser.parse_args(["statute-align", "--amended", "5855", "--before", "2023", "--after", "2025", "--no-model"])
    assert args.amended == "5855" and args.no_model and args.func
