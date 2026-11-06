"""Run the README quickstart exactly as a newcomer would copy it.

The commands come from the first ```bash block under "## Try one query" in README.md,
so the check and the documentation cannot drift apart. ``git clone`` and ``cd`` lines
are skipped (CI is already inside a checkout).

    python tools/check_quickstart.py            # offline: get → path (route only)
    python tools/check_quickstart.py --live     # run every command as written

Offline mode rewrites each ``braidworks get ID --have T --want W`` (or the ``weave``
alias, or ``--have T=V``) into
``braidworks path --from T --to W``: it proves the documented route plans with the
documented install, without depending on third-party APIs. The live workflow runs the
real queries.
"""

from __future__ import annotations

import argparse
import re
import shlex
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SECTION = "## Try one query"
SKIP_PREFIXES = ("git clone", "cd ")


def quickstart_commands(readme: str) -> list[str]:
    """The README quickstart's shell commands, with continuation lines joined."""
    start = readme.index(SECTION)
    block = re.search(r"```bash\n(.*?)```", readme[start:], re.DOTALL)
    if block is None:
        raise ValueError(f"no ```bash block under {SECTION!r}")
    joined = re.sub(r"\\\n\s*", "", block.group(1))
    commands = [line.strip() for line in joined.splitlines()]
    return [c for c in commands if c and not c.startswith("#") and not c.startswith(SKIP_PREFIXES)]


QUERY_VERBS = ("get", "weave")


def offline_variant(command: str) -> str:
    """Turn a ``get``/``weave`` into the equivalent ``path`` preview; leave others unchanged.

    ``--have TYPE`` (typing positional IDs) and ``--have TYPE=VALUE`` both name a start type.
    """
    argv = shlex.split(command)
    verb = next((word for word in argv if word in QUERY_VERBS), None)
    if verb is None:
        return command
    head = argv[: argv.index(verb)]
    rest = argv[argv.index(verb) + 1 :]
    have: list[str] = []
    want: list[str] = []
    i = 0
    while i < len(rest):
        flag = rest[i]
        value = rest[i + 1] if i + 1 < len(rest) else ""
        if flag == "--have":
            have.append(value.split("=", 1)[0])
        elif flag == "--want":
            want.append(value)
        i += 2 if flag.startswith("--") and not value.startswith("--") else 1
    if not have or not want:
        raise ValueError(f"cannot derive a route from: {command}")
    return shlex.join([*head, "path", "--from", ",".join(have), "--to", ",".join(want)])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--live", action="store_true", help="run get commands for real")
    args = parser.parse_args(argv)

    commands = quickstart_commands((ROOT / "README.md").read_text(encoding="utf-8"))
    for command in commands:
        run = command if args.live else offline_variant(command)
        print(f"$ {run}", flush=True)
        completed = subprocess.run(run, shell=True, cwd=ROOT, check=False)
        if completed.returncode != 0:
            print(f"README quickstart command failed ({completed.returncode}): {run}")
            return 1
    print(
        f"README quickstart OK ({len(commands)} command(s), {'live' if args.live else 'offline'})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
