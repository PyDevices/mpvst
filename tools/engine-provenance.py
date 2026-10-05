#!/usr/bin/env python3
"""Refuse a sidecar engine older than the code that goes into it.

    engine-provenance.py check ENGINE

The `mpvst_engine_provenance` ctest runs it on the engine the bundle stages.

The engine is built by micropython-pydevices' `build_mp.py` (the command is in
docs/development.md), into that repository's `builds/<port>/vst3-engine/`,
and every later `cmake --build` copies whatever is sitting there into the
bundle without asking how old it is. So the whole ctest suite can run green
against a DSP core that no longer exists.

It is not hypothetical. On 2026-09-21 the Linux engine was four days stale and
three suites had been red long enough to stop being a signal (mpvst#12):

    acoustickit did not import: no module named 'audiomodal'   (landed 09-15)
    Bitcrusher  AttributeError: audioshaper has no SampleHold  (landed 09-17)

Neither said "stale engine". The catalog said one plug-in would not import and
the effects probe said two rendered silence, which reads exactly like broken
DSP -- and a module-level import check would have caught the first and missed
the second, because `import audioshaper` succeeded and only the attribute was
gone.

Two questions, asked two ways:

- **audiodsp**: every audiodsp module the engine carries is stamped with
  `__revision__`, the `git describe` of the tree it was compiled from. That is
  the running binary's own claim, so it cannot be fooled by a record that was
  copied from somewhere else.
- **this repository's vstaudio and vstui, and audiocomponents' packages**
  (frozen into the engine): `build_mp.py` writes `pydevices-build.json`
  beside every build, naming the commit of each module that went in. The
  engine has to pass both questions.

Either way the question is whether the code that goes INTO the engine moved,
not whether the repository did (mpvst#18). audiodsp commits that only touch
READMEs or a workflow used to refuse the engine and block a release until it
was rebuilt for nothing; a check that is red for no reason stops being read.
`ENGINE_PATHS` names what the build reads. A module recorded as not a git
checkout -- a tarball -- is said so out loud.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

#: What each checked module contributes to the engine, relative to its
#: repository. A commit that touches none of these cannot change the binary,
#: so it must not refuse it. audiodsp: the C sources, both build glues, the
#: freeze manifest and VERSION (compiled in as __version__) and
#: DEPENDENCIES.lock (the mp3 decoder's pin); not its docs, tests, workflows,
#: Python lib/ or CircuitPython patches. mpvst: the two usermods and the
#: manifest that names them. audiocomponents and pydevices: the packages they
#: freeze.
ENGINE_PATHS = {
    "mpvst": ("usermods/vstaudio", "usermods/vstui", "manifest.py"),
    "audiodsp": ("src", "micropython.mk", "micropython.cmake", "manifest.py",
                 "VERSION", "DEPENDENCIES.lock"),
    "audiocomponents": ("lib", "manifest.py"),
    "pydevices": ("lib", "manifest.py"),
}

#: The record build_mp.py writes beside every build.
RECORD = "pydevices-build.json"

REBUILD = ("../micropython-pydevices/build_mp.py --port {port} --variant vst3-engine "
           "--modules audiocomponents,audiodsp,audioif,lvgl-micropython,pydevices,ulab,{repo}{extra}")

# Any audiodsp module carries the stamp; ask three, and require that they
# agree. They are all compiled from one tree, so a disagreement is its own
# finding -- a hand-assembled binary, or a module from somewhere else.
PROBE_MODULES = ("audiobiquad", "audioshaper", "audiodynamics")

# `git describe` output, e.g. v0.0.3-252-g95e58b3 or v0.5.1-1-g95e58b3-dirty.
DESCRIBE = re.compile(r"-g(?P<sha>[0-9a-f]{7,40})(?P<dirty>-dirty)?$")

def _git(repo: Path, *args: str) -> subprocess.CompletedProcess | None:
    try:
        return subprocess.run(["git", "-C", str(repo), *args],
                              capture_output=True, text=True, timeout=60)
    except OSError:
        return None


def _out(repo: Path, *args: str) -> str | None:
    done = _git(repo, *args)
    if done is None or done.returncode != 0:
        return None
    return done.stdout.strip()


def moved(repo: Path, old: str, new: str, paths: tuple[str, ...]) -> list[str] | None:
    """The files under `paths` that differ between two commits; None if unknowable."""
    done = _git(repo, "diff", "--name-only", old, new, "--", *paths)
    if done is None or done.returncode != 0:
        return None
    return done.stdout.split()


def _some(files: list[str]) -> str:
    return ", ".join(files[:3]) + (f" and {len(files) - 3} more" if len(files) > 3 else "")


def record_problems(engine: Path) -> tuple[list[str], dict[str, Path]]:
    """Problems with the build record beside the engine; notes are printed here.

    Also returns where each checked module was read from, so the audiodsp
    question asks the same checkout the build did."""
    record_path = engine.with_name(RECORD)
    if not record_path.is_file():
        return [f"no {RECORD} beside {engine.name}, so what it was built from "
                f"cannot be established."], {}
    record = json.loads(record_path.read_text(encoding="utf-8"))
    if not record.get("complete"):
        return [f"{RECORD} says the build that made {engine.name} did not finish."], {}
    modules = record.get("module_revisions", {})
    # mpvst is named by its path, so find it by path, not by name.
    by_path = {Path(m["path"]).resolve(): m for m in modules.values()}
    entries = {"mpvst": by_path.get(REPO),
               "audiodsp": modules.get("audiodsp"),
               "audiocomponents": modules.get("audiocomponents"),
               "pydevices": modules.get("pydevices")}
    problems, sources = [], {}
    for name, entry in entries.items():
        if entry is None:
            problems.append(f"the engine was built without {name}"
                            + (f" (this checkout, {REPO})" if name == "mpvst" else "") + ".")
            continue
        repo = Path(entry["path"])
        sources[name] = repo
        paths = ENGINE_PATHS[name]
        head = _out(repo, "rev-parse", "HEAD")
        built = entry.get("commit")
        if built is None:
            print(f"SKIP: {name} was not a git checkout when the engine was built, "
                  f"so its age is unknown.")
            continue
        if head is None:
            print(f"SKIP: {repo} is not a git checkout now, so {name} cannot be "
                  f"compared. The engine may be any age.")
            continue
        if entry.get("dirty"):
            print(f"  note: {name} was built from uncommitted changes ({entry['revision']}).")
        if head == built:
            continue
        change = moved(repo, built, head, paths)
        if change is None:
            problems.append(f"{name}: the engine was built from {entry['revision']}, "
                            f"which {repo} does not know, so what it contains cannot "
                            f"be compared.")
        elif change:
            problems.append(f"{name}: {_some(change)} changed since the engine was "
                            f"built from {entry['revision']}.")
        else:
            print(f"  note: {name}: {built[:7]} -> {head[:7]} touched nothing that "
                  f"goes into the engine.")
    return problems, sources


def engine_revisions(engine: Path) -> dict[str, str]:
    script = ";".join(
        f"import {m};print('{m}',{m}.__revision__)" for m in PROBE_MODULES
    )
    proc = subprocess.run([str(engine), "-c", script],
                          capture_output=True, text=True, timeout=60)
    if proc.returncode != 0:
        raise SystemExit(
            f"the engine could not report its provenance:\n{proc.stderr.strip()}\n"
            "An engine with no __revision__ is certainly stale; rebuild it "
            "(docs/development.md)."
        )
    found = {}
    for line in proc.stdout.split("\n"):
        parts = line.split()
        if len(parts) == 2:
            found[parts[0]] = parts[1]
    return found


def check_revision(engine: Path, audiodsp: Path) -> tuple[list[str], str | None]:
    """Problems with the engine's own audiodsp __revision__, and a success line."""
    head = _out(audiodsp, "rev-parse", "HEAD")
    if head is None:
        # Someone building from a release tarball. Say so out loud rather
        # than passing quietly, because a skip that looks like a pass is the
        # failure this test is about.
        print(f"SKIP: no audiodsp git checkout at {audiodsp}, so the engine's "
              f"audiodsp revision cannot be checked. It may be any age.")
        return [], None
    revisions = engine_revisions(engine)
    missing = [m for m in PROBE_MODULES if m not in revisions]
    if missing:
        return [f"the engine does not carry these audiodsp modules at all: "
                f"{', '.join(missing)}"], None
    if len(set(revisions.values())) != 1:
        return ["the engine's audiodsp modules disagree about which tree they "
                "came from, which means it was not built in one pass: "
                + ", ".join(f"{n} {r}" for n, r in sorted(revisions.items()))], None
    described = next(iter(revisions.values()))
    match = DESCRIBE.search(described)
    if match is None:
        return [f"cannot read a commit out of the engine's __revision__ "
                f"{described!r}; expected a git describe ending in -g<sha>."], None
    if match.group("dirty"):
        return [f"the engine was built from a dirty audiodsp tree ({described}), "
                f"so what it contains is not any commit."], None
    sha = match.group("sha")
    if head.startswith(sha):
        return [], f"built from audiodsp {described}, which is this checkout's HEAD"
    change = moved(audiodsp, sha, head, ENGINE_PATHS["audiodsp"])
    if change is None:
        return [f"the engine was built from audiodsp {described}, a commit the "
                f"checkout at {audiodsp} does not have."], None
    if change:
        return [f"the engine was built from audiodsp {described}, and "
                f"{_some(change)} changed since (the checkout is at {head[:7]}). Every ctest suite below this "
                f"one is certifying a DSP core that is not the one on disk."], None
    return [], (f"built from audiodsp {described}; the checkout is at {head[:7]}, "
                f"but nothing that goes into the engine changed between them")


def cmd_check(args: argparse.Namespace) -> int:
    engine = Path(args.engine)
    if not engine.exists():
        print(f"no engine at {engine}", file=sys.stderr)
        return 1
    port = "windows" if engine.suffix == ".exe" else "unix"
    extra = f" ENGINE_ICON={REPO}/installer/art/mpvst.ico" if port == "windows" else ""
    hint = REBUILD.format(port=port, repo=REPO, extra=extra)
    problems, sources = record_problems(engine)
    ok = None
    if "audiodsp" in sources:
        revision_problems, ok = check_revision(engine, sources["audiodsp"])
        problems += revision_problems
    if problems:
        print(f"REFUSED: {engine.name} is older than the code it would certify.")
        for problem in problems:
            print(f"  - {problem}")
        print(f"Rebuild it:\n    {hint}")
        return 1
    print("engine provenance OK" + (f": {ok}" if ok else ""))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("check", help="refuse an engine older than its sources")
    check.add_argument("engine", help="the engine binary the bundle stages")
    check.set_defaults(func=cmd_check)
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
