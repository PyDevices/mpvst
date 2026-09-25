#!/usr/bin/env python3
"""Stamp the sidecar engine with what it was built from, and refuse a stale one.

    engine-provenance.py write ENGINE --port unix|windows
    engine-provenance.py check ENGINE AUDIODSP_CHECKOUT

`scripts/build-micropython-engine.sh` runs `write` after every build, and the
`mpvst_engine_provenance` ctest runs `check`.

The sidecar engine is a *prebuilt* artifact: `scripts/build-micropython-engine.sh`
writes `.deps/engine/mpvst-engine`, and every later `cmake --build` copies
whatever is sitting there into the bundle without asking how old it is. So the
whole ctest suite can run green against a DSP core that no longer exists.

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
  the running binary's own claim, so it cannot be fooled by a stamp file that
  was copied from somewhere else.
- **vstaudio and vstui**, the C++ usermods in this repository, carry no Python
  stamp, so the stamp file beside the engine records which commit of this
  repository they were linked from. It records audiodsp too, so the engine
  has to pass both questions.

Either way the question is whether the code that goes INTO the engine moved,
not whether the repository did (mpvst#18). audiodsp commits that only touch
READMEs or a workflow used to refuse the engine and block a release until it
was rebuilt for nothing; a check that is red for no reason stops being read.
`ENGINE_PATHS` names what the build reads.

The stamper lives here rather than in the workspace so a public clone gets a
stamped engine too (mpvst#16). A source that is not a git checkout -- a
tarball -- is recorded as "unknown", and the check says so out loud.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
WORKSPACE = REPO.parent

#: What each checked source contributes to the engine, relative to the
#: repository it lives in. A commit that touches none of these cannot change
#: the binary, so it must not refuse it. audiodsp: the C sources, both build
#: glues, the freeze manifest (it names the C modules and ulab), VERSION
#: (compiled in as __version__) and DEPENDENCIES.lock (ulab's and the mp3
#: decoder's pins). Not its docs, tests, workflows, Python lib/ or CircuitPython
#: patches.
ENGINE_PATHS = {
    "vstaudio": ("usermods/vstaudio",),
    "vstui": ("usermods/vstui",),
    "audiodsp": ("src", "micropython.mk", "micropython.cmake", "manifest.py",
                 "VERSION", "DEPENDENCIES.lock"),
}

REBUILD = "scripts/build-micropython-engine.sh --port {port}"

# Any audiodsp module carries the stamp; ask three, and require that they
# agree. They are all compiled from one tree, so a disagreement is its own
# finding -- a hand-assembled binary, or a module from somewhere else.
PROBE_MODULES = ("audiobiquad", "audioshaper", "audiodynamics")

# `git describe` output, e.g. v0.0.3-252-g95e58b3 or v0.5.1-1-g95e58b3-dirty.
DESCRIBE = re.compile(r"-g(?P<sha>[0-9a-f]{7,40})(?P<dirty>-dirty)?$")

FORMAT = 1


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


def describe(repo: Path, paths: tuple[str, ...] = ()) -> dict:
    """A source's commit, or "unknown" when it is not a git checkout."""
    head = _out(repo, "rev-parse", "HEAD")
    if head is None:
        return {"path": str(repo), "head": None, "describe": "unknown",
                "dirty": None, "paths": list(paths)}
    # Dirty means a path that goes into the engine has uncommitted changes. A
    # scratch file or an edited README beside them does not make the build
    # any less a commit.
    status = _out(repo, "status", "--porcelain", "--ignore-submodules=dirty",
                  "--", *paths) if paths else _out(repo, "status", "--porcelain")
    return {
        "path": str(repo),
        "head": head,
        "describe": _out(repo, "describe", "--always", "--dirty", "--abbrev=7") or head[:7],
        "dirty": bool(status),
        "paths": list(paths),
    }


def source_repos(audiodsp: Path) -> dict[str, Path]:
    return {"vstaudio": REPO, "vstui": REPO, "audiodsp": audiodsp}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stamp_path(engine: Path) -> Path:
    return engine.with_name(engine.name + ".provenance")


def cmd_write(args: argparse.Namespace) -> int:
    engine = Path(args.engine).resolve()
    if not engine.exists():
        print(f"no such engine: {engine}", file=sys.stderr)
        return 1
    sources = {name: describe(repo, ENGINE_PATHS[name])
               for name, repo in source_repos(Path(args.audiodsp).resolve()).items()}
    # Recorded for whoever reads the stamp later; not checked, because the
    # build carries them whole and they have no path list here.
    sources["micropython"] = describe(Path(args.micropython).resolve())
    sources["micropython-pydevices"] = describe(WORKSPACE / "micropython-pydevices")
    record = {
        "format": FORMAT,
        "stamper": "mpvst/tools/engine-provenance.py",
        "target": f"mpvst-engine-{args.port}",
        "port": args.port,
        "stamped": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        "binary": {"name": engine.name, "sha256": sha256(engine),
                   "size": engine.stat().st_size},
        "sources": sources,
    }
    out = stamp_path(engine)
    out.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    unknown = sorted(n for n, s in sources.items() if s["head"] is None)
    dirty = sorted(n for n, s in sources.items() if s["dirty"])
    print(f"Stamped {out}"
          + (f" (dirty: {', '.join(dirty)})" if dirty else "")
          + (f" (unknown, not git checkouts: {', '.join(unknown)})" if unknown else ""))
    return 0


def check_stamp(engine: Path, audiodsp: Path) -> list[str]:
    """Problems with the stamp beside the engine; notes are printed here."""
    stamp = stamp_path(engine)
    if not stamp.is_file():
        return [f"no provenance stamp beside {engine.name}. An engine without one "
                f"predates the stamp itself, so what it contains cannot be "
                f"established."]
    record = json.loads(stamp.read_text(encoding="utf-8"))
    if record.get("format") != FORMAT:
        return [f"{stamp.name} is format {record.get('format')!r}; this script "
                f"reads {FORMAT}."]
    problems = []
    if sha256(engine) != record["binary"]["sha256"]:
        problems.append(f"{engine.name} is not the binary that was stamped: "
                        f"something replaced it without stamping it.")
    # audiodsp is asked of the running binary instead (check_revision): the
    # stamp records it, but asking twice would only say the same thing twice.
    for name in ("vstaudio", "vstui"):
        repo = source_repos(audiodsp)[name]
        paths = ENGINE_PATHS[name]
        stamped = record["sources"].get(name)
        if stamped is None:
            problems.append(f"the stamp says nothing about {name}.")
            continue
        head = _out(repo, "rev-parse", "HEAD")
        if stamped["head"] is None:
            if head is None:
                print(f"SKIP: {name} was not a git checkout when the engine was "
                      f"built and is not one now, so its age is unknown.")
            else:
                problems.append(f"{name} was recorded as unknown (not a git "
                                f"checkout) when the engine was built, so "
                                f"whether it holds {repo}'s code cannot be told.")
            continue
        if head is None:
            print(f"SKIP: {repo} is not a git checkout, so {name} cannot be "
                  f"compared. The engine may be any age.")
            continue
        if stamped["dirty"]:
            print(f"  note: {name} was built from uncommitted changes to "
                  f"{', '.join(paths)} ({stamped['describe']}).")
        if head == stamped["head"]:
            continue
        change = moved(repo, stamped["head"], head, paths)
        if change is None:
            problems.append(f"{name}: the engine was built from "
                            f"{stamped['describe']}, which this checkout does "
                            f"not know, so what it contains cannot be compared.")
        elif change:
            problems.append(f"{name}: {_some(change)} changed since the engine "
                            f"was built from {stamped['describe']}.")
        else:
            print(f"  note: {name}: {stamped['head'][:7]} -> {head[:7]} "
                  f"touched nothing that goes into the engine.")
    return problems


def engine_revisions(engine: Path) -> dict[str, str]:
    script = ";".join(
        f"import {m};print('{m}',{m}.__revision__)" for m in PROBE_MODULES
    )
    proc = subprocess.run([str(engine), "-c", script],
                          capture_output=True, text=True, timeout=60)
    if proc.returncode != 0:
        raise SystemExit(
            f"the engine could not report its provenance:\n{proc.stderr.strip()}\n"
            "An engine with no __revision__ predates the stamp and is certainly "
            "stale; rebuild it with scripts/build-micropython-engine.sh."
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
    audiodsp = Path(args.audiodsp).resolve()
    if not engine.exists():
        print(f"no engine at {engine}", file=sys.stderr)
        return 1
    port = "windows" if engine.suffix == ".exe" else "unix"
    hint = REBUILD.format(port=port)
    problems = check_stamp(engine, audiodsp)
    revision_problems, ok = check_revision(engine, audiodsp)
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
    write = sub.add_parser("write", help="stamp an engine that was just built")
    write.add_argument("engine")
    write.add_argument("--port", required=True, choices=("unix", "windows"))
    write.add_argument("--audiodsp", default=str(WORKSPACE / "audiodsp"),
                       help="the audiodsp checkout the build read (default: the sibling)")
    write.add_argument("--micropython", default=str(WORKSPACE / "micropython"),
                       help="the MicroPython checkout the build used (default: the sibling)")
    write.set_defaults(func=cmd_write)
    check = sub.add_parser("check", help="refuse an engine older than its sources")
    check.add_argument("engine", help="the engine binary the bundle carries")
    check.add_argument("audiodsp", help="the sibling audiodsp checkout")
    check.set_defaults(func=cmd_check)
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
