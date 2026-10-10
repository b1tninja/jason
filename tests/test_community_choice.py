"""docs/tenancy.md, phase 1: which community a command serves, where that came from, and the line a write prints first."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from jason import cli, tenancy
from jason.community import profile as profiles
from jason.community.profile import CommunityNotChosen, resolve_community

CHOICE_VARS = ("JASON_COMMUNITY", "JASON_PROFILE", "JASON_COMMUNITY_VIA", "JASON_DEFAULT_COMMUNITY_SHIM")


@pytest.fixture
def clean(tmp_path, monkeypatch):
    """No choice anywhere: no environment setting, an empty project .env and user config (both in tmp_path), and the
    notices not yet printed."""
    for name in (*CHOICE_VARS, "JASON_COMMUNITY_NOTICED"):
        monkeypatch.setenv(name, "")                    # recorded, so that a setting the code makes itself
        monkeypatch.delenv(name)                        # (tenancy.choose_community) is undone after the test
    project, user = tmp_path / "project.env", tmp_path / "user.env"
    monkeypatch.setenv("JASON_ENV", str(project))
    monkeypatch.setenv("JASON_CONFIG", str(user))
    return project, user


def installed(monkeypatch, *names: str) -> None:
    rows = [{"name": n, "where": f"/profiles/{n}"} for n in names]
    monkeypatch.setattr(profiles, "installed_profiles", lambda: rows)


# --- the resolver ---------------------------------------------------------------------------------------------------

def test_the_flag_comes_first_then_the_environment_then_the_old_name_then_the_files(clean, monkeypatch):
    project, user = clean
    installed(monkeypatch, "alpha", "beta", "gamma", "delta", "epsilon")
    user.write_text("JASON_COMMUNITY=epsilon\n", encoding="utf-8")
    assert (resolve_community().name, resolve_community().source) == ("epsilon", "user config, JASON_COMMUNITY")
    project.write_text("JASON_PROFILE=delta\n", encoding="utf-8")
    assert (resolve_community().name, resolve_community().source) == ("delta", "project .env, JASON_PROFILE (old name)")
    project.write_text("JASON_PROFILE=delta\nJASON_COMMUNITY=gamma\n", encoding="utf-8")
    assert resolve_community().name == "gamma"                      # the new spelling beats the old one in the same file
    monkeypatch.setenv("JASON_PROFILE", "beta")
    got = resolve_community()
    assert (got.name, got.alias, got.source) == ("beta", True, "JASON_PROFILE (old name)")
    monkeypatch.setenv("JASON_COMMUNITY", "alpha")
    assert (resolve_community().name, resolve_community().source) == ("alpha", "JASON_COMMUNITY")
    tenancy.choose_community("gamma")
    assert (resolve_community().name, resolve_community().source) == ("gamma", "--community flag")
    monkeypatch.undo()


def test_nothing_chosen_uses_the_only_installed_profile_and_says_so(clean, monkeypatch, capsys):
    installed(monkeypatch, "alpha")
    assert profiles.profile_name() == "alpha"
    assert profiles.profile_name() == "alpha"
    err = capsys.readouterr().err
    assert err.count("community: alpha (the only installed profile; set JASON_COMMUNITY or run `jason use KEY`)") == 1


def test_nothing_chosen_among_several_uses_the_built_in_default_with_a_notice(clean, monkeypatch, capsys):
    installed(monkeypatch, "alpha", "beta")
    got = resolve_community()
    assert (got.name, got.source, got.shim) == (profiles.DEFAULT_PROFILE, "built-in default", True)
    assert profiles.profile_name() == profiles.DEFAULT_PROFILE
    assert capsys.readouterr().err == (f"community: {profiles.DEFAULT_PROFILE} (built-in default; set JASON_COMMUNITY or "
                                       "run `jason use KEY`)\n")


@pytest.mark.parametrize("off", ["0", "false", "off", "no"])
def test_with_the_shim_off_and_several_installed_nothing_is_guessed(clean, monkeypatch, off):
    installed(monkeypatch, "beta", "alpha")
    monkeypatch.setenv("JASON_DEFAULT_COMMUNITY_SHIM", off)
    with pytest.raises(CommunityNotChosen, match=r"this machine has 2 \(alpha, beta\)"):
        resolve_community()
    with pytest.raises(CommunityNotChosen):
        profiles.profile_name()
    from jason.config import default_data_dir

    with pytest.raises(CommunityNotChosen):                 # a data folder is never guessed either
        default_data_dir()


def test_the_shim_setting_can_come_from_the_user_config(clean, monkeypatch):
    _, user = clean
    installed(monkeypatch, "alpha", "beta")
    user.write_text("JASON_DEFAULT_COMMUNITY_SHIM=0\n", encoding="utf-8")
    with pytest.raises(CommunityNotChosen):
        resolve_community()


def test_the_old_name_is_noted_once(clean, monkeypatch, capsys):
    installed(monkeypatch, "alpha", "beta")
    monkeypatch.setenv("JASON_PROFILE", "alpha")
    profiles.profile_name()
    profiles.profile_name()
    err = capsys.readouterr().err
    assert err.count("JASON_PROFILE is the old name of JASON_COMMUNITY") == 1


def test_resolving_loads_no_profile(clean, monkeypatch):
    installed(monkeypatch, "alpha", "beta")
    monkeypatch.setenv("JASON_COMMUNITY", "alpha")
    loaded = dict(profiles._LOADED)
    resolve_community()
    assert profiles._LOADED == loaded


def test_a_name_that_is_not_a_profile_name_is_refused(clean, monkeypatch):
    monkeypatch.setenv("JASON_COMMUNITY", "Not A Name")
    with pytest.raises(profiles.ProfileNotFound):
        resolve_community()


# --- the commands -----------------------------------------------------------------------------------------------------

def run(argv: list[str]) -> int:
    with pytest.raises(SystemExit) as stop:
        cli.main(argv)
    return stop.value.code


def test_no_community_chosen_exits_2_before_a_command_runs(clean, monkeypatch, capsys):
    installed(monkeypatch, "beta", "alpha")
    monkeypatch.setenv("JASON_DEFAULT_COMMUNITY_SHIM", "0")
    assert run(["which"]) == 2
    err = capsys.readouterr().err
    assert "no community chosen, and this machine has 2 (alpha, beta)" in err and "jason use KEY" in err
    assert run(["use", "--list"]) == 0                      # and the commands that need no community still run
    assert run(["use", "alpha"]) == 0


def test_the_community_flag_is_read_before_the_subcommand(clean, monkeypatch, capsys):
    installed(monkeypatch, "alpha", "beta")
    monkeypatch.setenv("JASON_DEFAULT_COMMUNITY_SHIM", "0")
    assert tenancy.pull_community_flag(["--community", "beta", "cadence", "--community", "alpha"]) == (
        ["cadence", "--community", "alpha"], "beta")           # a subcommand's own --community is its own
    assert tenancy.pull_community_flag(["--community=beta", "which"]) == (["which"], "beta")
    assert run(["--community", "beta", "which"]) == 0
    out = capsys.readouterr().out
    assert out.splitlines()[0] == "community: beta (from --community flag)"
    assert run(["--community", "zeta", "which"]) == 2
    assert "no profile 'zeta' is installed here (installed: alpha, beta)" in capsys.readouterr().err
    monkeypatch.undo()


def test_use_writes_the_user_config_and_prints_what_it_wrote(clean, monkeypatch, capsys):
    _, user = clean
    installed(monkeypatch, "alpha", "beta")
    monkeypatch.setenv("JASON_DEFAULT_COMMUNITY_SHIM", "0")
    user.write_text("JASON_TEMP_DIR=D:/scratch\nJASON_COMMUNITY=alpha\n# kept\n", encoding="utf-8")
    assert run(["use", "beta"]) == 0
    assert capsys.readouterr().out == f"wrote JASON_COMMUNITY=beta to {user}\n"
    assert user.read_text(encoding="utf-8") == "JASON_TEMP_DIR=D:/scratch\nJASON_COMMUNITY=beta\n# kept\n"
    assert resolve_community().name == "beta"
    assert run(["use"]) == 0
    assert capsys.readouterr().out.splitlines()[0] == "community: beta (from user config, JASON_COMMUNITY)"
    assert run(["use", "--list"]) == 0
    listing = capsys.readouterr().out.splitlines()
    assert listing[0].startswith("  alpha") and listing[1].startswith("* beta")


def test_use_refuses_an_unknown_profile_and_says_what_still_wins(clean, monkeypatch, capsys):
    _, user = clean
    installed(monkeypatch, "alpha", "beta")
    assert run(["use", "zeta"]) == 2
    assert not user.exists()
    assert "no profile 'zeta' is installed here (installed: alpha, beta)" in capsys.readouterr().err
    monkeypatch.setenv("JASON_COMMUNITY", "alpha")
    assert run(["use", "beta"]) == 0
    captured = capsys.readouterr()
    assert "note: alpha is still chosen, from JASON_COMMUNITY" in captured.err


def test_use_without_a_choice_says_so_and_still_lists(clean, monkeypatch, capsys):
    installed(monkeypatch, "alpha", "beta")
    monkeypatch.setenv("JASON_DEFAULT_COMMUNITY_SHIM", "0")
    assert run(["use"]) == 2
    capsys.readouterr()
    assert run(["communities"]) == 0
    assert "no community is chosen: jason use KEY" in capsys.readouterr().out


# --- the line a write prints first --------------------------------------------------------------------------------------

def _through_main(monkeypatch, argv: list[str]) -> list[str]:
    """Run ``cli.main(argv)`` with the command itself replaced, so only what main does before it is seen."""
    real = cli.build_parser

    def build():
        parser = real()
        parse = parser.parse_args

        def parse_args(args=None, namespace=None):
            ns = parse(args, namespace)
            ns.func = lambda a: 0
            return ns

        parser.parse_args = parse_args
        return parser

    monkeypatch.setattr(cli, "build_parser", build)
    assert run(argv) == 0


@pytest.mark.parametrize("argv", [["mailroom", "--cancel", "7", "--yes"],
                                  ["zoom", "--caption", "hello", "--yes"],
                                  ["local-ai", "--restart-ollama", "--yes"]])
def test_a_command_with_yes_prints_the_community_and_data_first(clean, monkeypatch, capsys, argv):
    from jason.config import data_dir

    monkeypatch.setenv("JASON_COMMUNITY", "mystique")
    _through_main(monkeypatch, argv)
    assert capsys.readouterr().err.splitlines()[0] == f"community: mystique (from JASON_COMMUNITY); data: {data_dir()}"


def test_a_command_without_yes_prints_no_banner(clean, monkeypatch, capsys):
    monkeypatch.setenv("JASON_COMMUNITY", "mystique")
    _through_main(monkeypatch, ["mailroom", "--prices"])
    assert "community:" not in capsys.readouterr().err


def test_a_write_with_no_community_chosen_stops_before_it_runs(clean, monkeypatch, capsys):
    installed(monkeypatch, "alpha", "beta")
    monkeypatch.setenv("JASON_DEFAULT_COMMUNITY_SHIM", "0")
    ran: list[int] = []
    real = cli.build_parser

    def build():
        parser = real()
        parse = parser.parse_args

        def parse_args(args=None, namespace=None):
            ns = parse(args, namespace)
            ns.func = lambda a: ran.append(1) or 0
            return ns

        parser.parse_args = parse_args
        return parser

    monkeypatch.setattr(cli, "build_parser", build)
    assert run(["local-ai", "--restart-ollama", "--yes"]) == 2
    assert ran == []


def test_a_web_write_prints_the_banner(clean, monkeypatch, capsys):
    from flask import Flask

    from jason.config import data_dir
    from jason.web import guard

    monkeypatch.setenv("JASON_COMMUNITY", "mystique")
    app = Flask(__name__)
    token = guard.install(app)

    @app.post("/api/thing")
    def thing():
        return {"ok": True}

    client = app.test_client()
    assert client.get("/api/thing").status_code in (404, 405)
    assert "community:" not in capsys.readouterr().err
    res = client.post("/api/thing", base_url="http://localhost", headers={"Origin": "http://localhost", guard.TOKEN_HEADER: token})
    assert res.status_code == 200
    assert capsys.readouterr().err.splitlines()[0] == f"community: mystique (from JASON_COMMUNITY); data: {data_dir()}"


def test_an_mcp_write_prints_the_banner(clean, monkeypatch, capsys, tmp_path):
    from jason.mcp.governance import answer_intake_question

    monkeypatch.setenv("JASON_COMMUNITY", "mystique")
    answer_intake_question("none", "an answer", "A Person", data_dir=tmp_path)
    assert capsys.readouterr().err.splitlines()[0] == f"community: mystique (from JASON_COMMUNITY); data: {tmp_path}"
    answer_intake_question("none", "an answer", "", data_dir=tmp_path)           # refused for want of a name: nothing written
    assert capsys.readouterr().err == ""


# --- the MCP server -----------------------------------------------------------------------------------------------------

def test_the_server_serves_one_named_community(clean, monkeypatch):
    pytest.importorskip("mcp")
    from jason.mcp import server

    monkeypatch.setenv("JASON_COMMUNITY", "mystique")
    built = server.build("board")
    assert built.name == "jason-mystique"
    assert built.instructions.startswith("Community: mystique. This server answers for ")
    assert "No tool takes a community" in built.instructions


def test_tools_names_the_tool_set_and_profile_is_the_deprecated_alias(monkeypatch, capsys):
    from jason.mcp import server

    monkeypatch.delenv("JASON_MCP_PROFILE", raising=False)
    monkeypatch.delenv("JASON_MCP_TOOLS", raising=False)
    monkeypatch.setattr(sys, "argv", ["jason-mcp", "--community", "alpha", "--tools", "governance"])
    assert server._profile() == "governance" and server._community_arg() == "alpha"
    assert capsys.readouterr().err == ""
    monkeypatch.setattr(sys, "argv", ["jason-mcp", "--profile", "board"])
    assert server._profile() == "board"
    assert "--profile names a tool set and is deprecated; use --tools board" in capsys.readouterr().err
    monkeypatch.setattr(sys, "argv", ["jason-mcp"])
    monkeypatch.setenv("JASON_MCP_PROFILE", "onboarding")
    assert server._profile() == "onboarding"


def test_the_server_refuses_a_community_that_is_not_installed(clean, monkeypatch):
    from jason.mcp import server

    installed(monkeypatch, "alpha")
    monkeypatch.setattr(sys, "argv", ["jason-mcp", "--community", "zeta"])
    with pytest.raises(SystemExit, match="no profile 'zeta' is installed here"):
        server.main()


def test_set_user_config_value_keeps_every_other_line(tmp_path, monkeypatch):
    from jason.config import set_user_config_value

    target = tmp_path / "home" / ".jason" / ".env"
    monkeypatch.setenv("JASON_CONFIG", str(target))
    assert set_user_config_value("JASON_COMMUNITY", "alpha") == target
    assert target.read_text(encoding="utf-8") == "JASON_COMMUNITY=alpha\n"
    target.write_text("A=1\nexport JASON_COMMUNITY = old\nB=2", encoding="utf-8")
    set_user_config_value("JASON_COMMUNITY", "beta")
    assert target.read_text(encoding="utf-8") == "A=1\nJASON_COMMUNITY=beta\nB=2\n"
