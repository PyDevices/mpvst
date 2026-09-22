#!/usr/bin/env python3
"""Refuse an engine binary older than the audiodsp checkout it certifies.

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

The check that catches both, and anything else of the kind: every audiodsp
module the engine carries is stamped with `__revision__`, the `git describe` of
the tree it was compiled from. Compare its sha against the sibling checkout's
HEAD. One comparison, no list to maintain, and it cannot be fooled by a change
that adds no new module name.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

# Any audiodsp module carries the stamp; ask three, and require that they
# agree. They are all compiled from one tree, so a disagreement is its own
# finding -- a hand-assembled binary, or a module from somewhere else.
PROBE_MODULES = ("audiobiquad", "audioshaper", "audiodynamics")

# `git describe` output, e.g. v0.0.3-252-g95e58b3 or v0.5.1-1-g95e58b3-dirty.
DESCRIBE = re.compile(r"-g(?P<sha>[0-9a-f]{7,40})(?P<dirty>-dirty)?$")


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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("engine", help="the engine binary the bundle carries")
    parser.add_argument("audiodsp", help="the sibling audiodsp checkout")
    args = parser.parse_args()

    engine = Path(args.engine)
    if not engine.exists():
        print(f"no engine at {engine}", file=sys.stderr)
        return 1

    checkout = Path(args.audiodsp)
    if not (checkout / ".git").exists():
        # No sibling to compare against -- someone building from a release
        # tarball. Say so out loud rather than passing quietly, because a
        # skip that looks like a pass is the failure this test is about.
        print(f"SKIP: no audiodsp git checkout at {checkout}, so the engine's "
              f"provenance cannot be checked. It may be any age.")
        return 0

    head = subprocess.run(["git", "-C", str(checkout), "rev-parse", "HEAD"],
                          capture_output=True, text=True).stdout.strip()
    if not head:
        print(f"SKIP: {checkout} has no HEAD to compare against.")
        return 0

    revisions = engine_revisions(engine)
    missing = [m for m in PROBE_MODULES if m not in revisions]
    if missing:
        print("the engine does not carry these audiodsp modules at all: "
              + ", ".join(missing))
        print("Rebuild it: scripts/build-micropython-engine.sh --port unix")
        return 1
    if len(set(revisions.values())) != 1:
        print("the engine's audiodsp modules disagree about which tree they "
              "came from, which means it was not built in one pass:")
        for name, rev in sorted(revisions.items()):
            print(f"    {name:16} {rev}")
        return 1

    described = next(iter(revisions.values()))
    match = DESCRIBE.search(described)
    if match is None:
        print(f"cannot read a commit out of the engine's __revision__ "
              f"{described!r}; expected a git describe ending in -g<sha>.")
        return 1
    sha = match.group("sha")
    if not head.startswith(sha):
        print(f"the engine was built from audiodsp {described}, and the "
              f"checkout at {checkout} is now at {head[:len(sha)]}.")
        print("Every ctest suite below this one is certifying a DSP core that "
              "is not the one on disk. Rebuild it:")
        print("    scripts/build-micropython-engine.sh --port unix")
        return 1
    if match.group("dirty"):
        print(f"the engine was built from a dirty audiodsp tree ({described}), "
              f"so what it contains is not any commit.")
        return 1

    print(f"engine provenance OK: built from audiodsp {described}, which is "
          f"this checkout's HEAD")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
