"""The whole command line builds: every command module registers its options without a clash.

Importing ``jason.cli`` does not build the parser; argparse refuses a duplicated option only when the subcommand's
arguments are added, which takes down every command at once. This builds it.
"""

from jason.cli import build_parser


def test_the_parser_builds_and_every_command_answers_help():
    parser = build_parser()
    sub = next(a for a in parser._actions if a.__class__.__name__ == "_SubParsersAction")
    assert len(sub.choices) > 100
    for name, command in sub.choices.items():
        command.format_help()                          # each command's own options render
