"""A profile's template Docs are generated from the bases; a person's edit is reported, never overwritten."""

from jason.community.identity import LetterheadSpec
from jason.community.templates import DocumentTemplate, TemplateKind
from jason.tasks import template_gen
from jason.tasks.template_gen import Action, base_sha, plan, sha


class _Profile:
    def __init__(self, ids=None):
        ids = ids or {}
        self._rows = [DocumentTemplate(kind, f"Template - {kind.value}", ids.get(kind, "")) for kind in TemplateKind]

    def document_templates(self):
        return self._rows

    def letterhead(self):
        return LetterheadSpec("EXAMPLE", footer="1 Main St", doc_id="letterhead")


def _entry(kind, doc_id, text, *, base=None):
    return {"docId": doc_id, "baseSha": base or base_sha(kind), "docSha": sha(text)}


def _actions(steps):
    return {s.kind: s.action for s in steps}


def test_each_state_of_a_template_doc():
    hearing, decision, agenda, letter = (TemplateKind.HEARING_NOTICE, TemplateKind.DECISION_NOTICE, TemplateKind.AGENDA,
                                         TemplateKind.LETTERHEAD)
    state = {
        hearing.slug: _entry(hearing, "h", "as written"),
        decision.slug: _entry(decision, "d", "as written", base="old base"),
        agenda.slug: _entry(agenda, "a", "as written"),
    }
    texts = {"h": "as written", "d": "as written", "a": "edited by a person"}
    actions = _actions(plan(_Profile(), state, texts))
    assert actions == {hearing: Action.UNCHANGED, decision: Action.UPDATE, agenda: Action.EDITED, letter: Action.CREATE}
    state[agenda.slug]["baseSha"] = "old base"
    assert _actions(plan(_Profile(), state, texts))[agenda] is Action.CONFLICT
    assert _actions(plan(_Profile(), state, {**texts, "h": None}))[hearing] is Action.CREATE    # trashed


def test_a_doc_built_before_the_bases_is_adopted():
    steps = plan(_Profile({TemplateKind.LETTERHEAD: "old"}), {}, {"old": "Mystery text"})
    assert _actions(steps)[TemplateKind.LETTERHEAD] is Action.ADOPT
    assert next(s for s in steps if s.kind is TemplateKind.LETTERHEAD).doc_id == "old"


def test_whitespace_alone_is_not_an_edit():
    assert sha("a  b\n\nc") == sha("a b c")


def test_generate_writes_only_what_the_plan_says_and_records_it(monkeypatch, tmp_path):
    from jason.tasks import letters

    made, rewritten = [], []
    monkeypatch.setattr(letters, "build_template",
                        lambda drive, docs, t, **kw: made.append((t.kind, kw["letterhead_id"])) or {"id": f"new-{t.kind.slug}"})
    monkeypatch.setattr(letters, "rewrite_template", lambda docs, t: rewritten.append(t.drive_id) or {"id": t.drive_id})
    monkeypatch.setattr(letters, "document_text", lambda doc: "written")

    class Docs:
        def get(self, doc_id):
            return {}

    profile = _Profile({TemplateKind.LETTERHEAD: "old"})
    state = {TemplateKind.AGENDA.slug: _entry(TemplateKind.AGENDA, "a", "edited")}
    steps = plan(profile, state, {"old": "x", "a": "edited by a person"})
    done = template_gen.generate(object(), Docs(), profile, steps, state, folder_id="folder")
    assert {d["action"] for d in done} == {"create", "adopt"}
    assert rewritten == ["old"] and all(letterhead == "letterhead" for _, letterhead in made)
    assert state[TemplateKind.AGENDA.slug]["docSha"] == sha("edited")                  # the edited Doc is untouched
    assert state[TemplateKind.LETTERHEAD.slug]["docId"] == "old"

    template_gen.save_state(tmp_path, "example", state)
    found = template_gen.template_for(profile, TemplateKind.HEARING_NOTICE, tmp_path, "example")
    assert found.drive_id == "new-hearing-notice"                                     # filling copies the generated Doc


def test_adopting_says_whether_the_doc_still_reads_as_built():
    from jason.tasks.template_gen import as_built

    profile = _Profile({TemplateKind.LETTERHEAD: "old"})
    built = "LOGO header " + as_built(TemplateKind.LETTERHEAD, profile) + " footer"
    step = next(s for s in plan(profile, {}, {"old": built}) if s.kind is TemplateKind.LETTERHEAD)
    assert "unchanged since" in step.reason
    step = next(s for s in plan(profile, {}, {"old": built.replace("Sincerely", "Warmly")}) if s.kind is TemplateKind.LETTERHEAD)
    assert "may have edited" in step.reason
