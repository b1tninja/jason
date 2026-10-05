"""No dataclass in src/jason shows a secret in its repr (lesson ``credential-repr-showed-secrets``).

A field whose name says it holds a secret (a password, a secret, a TOTP code or seed, an API key, a private key, a
refresh, access, or other token) and whose type is a string must be ``field(repr=False)``, unless its class writes its
own ``__repr__``. The scan reads the source (``ast``), so it finds a new dataclass the day it is written. A field whose
name only looks like one (a parsed text token, a random seed that is an int) is skipped by its type, or listed in
``NOT_SECRETS`` with why.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src" / "jason"

SECRET_WORDS = frozenset({"password", "passwd", "passphrase", "secret", "totp", "seed", "apikey", "token"})
SECRET_PARTS = ("api_key", "private_key", "client_secret")
STRING = re.compile(r"(str|str \| None|None \| str|Optional\[str\])")

# Reviewed: string fields named like a secret that hold none.
NOT_SECRETS = {
    "community/section_refs.py:Ref.token": "a section reference's text as written",
    "community/section_refs.py:Embedded.token": "a section reference's text as written",
    "tasks/meeting_notice.py:Recital.token": "a template token's name",
    "tasks/section_refs.py:Proposal.token": "a section reference's text as written",
}


def _secret_named(name: str) -> bool:
    lowered = name.lower()
    return bool(SECRET_WORDS & set(lowered.split("_"))) or any(part in lowered for part in SECRET_PARTS)


def _is_dataclass(node: ast.ClassDef) -> bool:
    return any("dataclass" in ast.unparse(d) for d in node.decorator_list)


def _findings() -> list[str]:
    found = []
    for path in sorted(SRC.rglob("*.py")):
        rel = path.relative_to(SRC).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=rel)
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef) or not _is_dataclass(node):
                continue
            if any(isinstance(b, ast.FunctionDef) and b.name == "__repr__" for b in node.body):
                continue
            for stmt in node.body:
                if not (isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name)):
                    continue
                name = stmt.target.id
                if not _secret_named(name) or not STRING.fullmatch(ast.unparse(stmt.annotation)):
                    continue
                if stmt.value is not None and "repr=False" in ast.unparse(stmt.value):
                    continue
                key = f"{rel}:{node.name}.{name}"
                if key not in NOT_SECRETS:
                    found.append(f"{key} (line {stmt.lineno})")
    return found


def test_no_dataclass_shows_a_secret_in_its_repr():
    assert _findings() == [], "a secret-named string field without field(repr=False)"


def test_the_reviewed_exceptions_still_exist():
    """An entry in NOT_SECRETS whose field is gone is removed, so the list never grows stale."""
    seen = set()
    for path in sorted(SRC.rglob("*.py")):
        rel = path.relative_to(SRC).as_posix()
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ClassDef) and _is_dataclass(node):
                seen |= {f"{rel}:{node.name}.{s.target.id}" for s in node.body
                         if isinstance(s, ast.AnnAssign) and isinstance(s.target, ast.Name)}
    assert set(NOT_SECRETS) <= seen


def test_the_scan_catches_a_secret_and_passes_a_hidden_one():
    assert _secret_named("client_secret") and _secret_named("refresh_token") and _secret_named("totp_code")
    assert _secret_named("api_key") and _secret_named("keeper_password") and _secret_named("seed")
    assert not _secret_named("tokens") and not _secret_named("link_tokens")
    assert _secret_named("secret_ballot")              # named like one; a bool, so its type skips it
    assert not STRING.fullmatch("bool") and not STRING.fullmatch("tuple[str, ...]") and STRING.fullmatch("str | None")
    from jason.config import Settings
    from jason.secrets import LoginCredentials
    from jason.web.signin import Client

    made_up = "made-up-secret-value"
    assert made_up not in repr(Client("an-id", made_up))
    assert made_up not in repr(LoginCredentials("someone", made_up, "123456"))
    settings = Settings(keeper_username="someone", payhoa_record_uid="", smud_record_uid="", idoxs_record_uid="",
                        keeper_password=made_up, payhoa_org_id=1, smud_category_id=None, idoxs_category_id=None)
    assert made_up not in repr(settings)
