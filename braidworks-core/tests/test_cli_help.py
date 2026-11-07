"""`--help` shows what a newcomer needs first; tuning sits under Advanced."""

import pytest
from braidworks.core import cli

ADVANCED_ONLY = (
    "--cache-db",
    "--cache-positive-ttl",
    "--cache-negative-ttl",
    "--cache-max-bytes",
    "--run-db",
    "--run-id",
    "--lease-seconds",
    "--review-policy",
    "--confidence-threshold",
    "--max-expansion",
    "--policy",
)


def _help(capsys, *command):
    with pytest.raises(SystemExit) as exc:
        cli.main([*command, "--help"])
    assert exc.value.code == 0
    return capsys.readouterr().out


@pytest.mark.parametrize("verb", ["get", "weave"])
def test_get_help_puts_common_options_before_advanced(verb, capsys):
    out = _help(capsys, verb)
    first, advanced = out.split("Advanced", 1)
    for flag in ("ID", "--have", "--want", "--in-file", "--format", "--param"):
        assert flag in first
    for flag in ADVANCED_ONLY:
        assert flag not in first, flag
        assert flag in advanced, flag


def test_get_usage_is_one_short_line(capsys):
    usage = _help(capsys, "get").split("\n\n", 1)[0]
    assert usage.startswith("usage: braidworks get ID")
    assert "--have TYPE" in usage and "--want TYPE" in usage
    assert len(usage.splitlines()) == 1
    assert "--cache" not in usage


def test_get_help_ends_with_examples(capsys):
    out = _help(capsys, "get")
    examples = out.split("examples:", 1)[1]
    assert "braidworks get P04637 --have protein.query --want protein.name" in examples
    assert "--in-file" in examples


@pytest.mark.parametrize("command", [("run",), ("resume",), ("runs",), ("path",), ("find",)])
def test_commands_show_examples(command, capsys):
    assert "examples:" in _help(capsys, *command)


@pytest.mark.parametrize("command", [("resume",), ("run",)])
def test_tuning_flags_are_grouped_under_advanced(command, capsys):
    out = _help(capsys, *command)
    first, _, advanced = out.partition("Advanced")
    assert advanced, "expected an Advanced section"
    if "--lease-seconds" in out:
        assert "--lease-seconds" not in first


def test_cache_flags_name_their_unit(capsys):
    out = _help(capsys, "get")
    assert "CACHE_POSITIVE_TTL" not in out
    assert "--cache-positive-ttl SECONDS" in out
    assert "--cache-max-bytes BYTES" in out


def test_every_command_renders_help(capsys):
    for command in ("get", "weave", "runs", "resume", "run", "weavers", "keys", "path", "find"):
        _help(capsys, command)
    for command in ("doctor", "references"):
        _help(capsys, command)
