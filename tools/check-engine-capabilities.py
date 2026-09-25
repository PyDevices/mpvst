#!/usr/bin/env python3
"""Refuse an engine that can reach the network or native code.

docs/security.md promises that the shipped sidecar engine has no sockets, no
TLS and no FFI, so a piece someone downloaded cannot reach the network or load
a native library whatever it contains. That promise lives in a build variant in
another repository (micropython-pydevices' `vst3-engine`), and nothing here
used to check it held.

It did not. The Windows engine built for 0.3.0, and again for 0.3.1, could
`import socket`: the variant switched sockets off on the make line, but the
windows port's C header switched them on regardless, and the make switch never
reached the compiler. The Linux engine was fine, so every test on Linux stayed
green.

So this asks each engine directly: run it, try every forbidden import, and fail
if any succeeds. It also imports `sys` as a control, so an engine that cannot
run at all, or prints nothing, fails instead of reading as "refused all five".

    check-engine-capabilities.py ENGINE [--also OTHER_ENGINE ...]

ENGINE is the engine for this platform and must run. Each --also engine is
checked when it exists and this machine can execute it (a Windows engine runs
under WSL), and is reported as not checked otherwise, since the ctest run on
its own platform covers it.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

# The capabilities the engine must not have. `ssl` on its own can be a frozen
# Python module that fails on its first line (`from tls import *`), so `tls` is
# the one that decides; both are asked. The u-prefixed names are asked too:
# MicroPython resolves `import usocket` to a built-in `socket`.
FORBIDDEN = ("socket", "usocket", "ssl", "tls", "ffi", "uffi", "network")

# Printed per module by the probe below. A module the engine refuses must
# raise ImportError; anything else it raises (the frozen `ssl` hitting an
# OSError, say) is reported as it is, rather than guessed at.
PROBE = """
import sys
print('control', 'ok' if sys.implementation.name == 'micropython' else 'bad')
for name in %r:
    try:
        __import__(name)
        print(name, 'IMPORTS')
    except ImportError:
        print(name, 'refused')
    except Exception as e:
        print(name, 'raised', type(e).__name__)
""" % (FORBIDDEN,)


def probe(engine: Path) -> tuple[dict[str, str] | None, str]:
    """Run the probe; return (result per module, or None if it cannot run)."""
    try:
        proc = subprocess.run([str(engine), "-c", PROBE],
                              capture_output=True, text=True, timeout=60)
    except OSError as e:
        return None, f"cannot execute: {e}"
    found = {}
    for line in proc.stdout.replace("\r", "").split("\n"):
        parts = line.split(None, 1)
        if len(parts) == 2:
            found[parts[0]] = parts[1]
    if found.get("control") != "ok" or proc.returncode != 0:
        return None, (f"the probe did not run (exit {proc.returncode}):\n"
                      f"{(proc.stdout + proc.stderr).strip()}")
    return found, ""


def check(engine: Path, required: bool) -> int:
    if not engine.exists():
        if required:
            print(f"FAIL {engine}: no engine there")
            return 1
        print(f"not checked: {engine} (none built)")
        return 0
    found, why = probe(engine)
    if found is None:
        if required:
            print(f"FAIL {engine}: {why}")
            return 1
        print(f"not checked: {engine} ({why.splitlines()[0]}); the ctest run "
              f"on its own platform covers it")
        return 0
    bad = [m for m in FORBIDDEN if found.get(m) != "refused"]
    summary = ", ".join(f"{m} {found.get(m, 'MISSING FROM PROBE')}"
                        for m in FORBIDDEN)
    if bad:
        print(f"FAIL {engine}: {summary}")
        print("    The engine must refuse all of these (docs/security.md). "
              "The vst3-engine variant in micropython-pydevices switches them "
              "off; rebuild with scripts/build-micropython-engine.sh.")
        return 1
    print(f"ok {engine}: {summary}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("engine", type=Path,
                        help="this platform's engine; must exist and run")
    parser.add_argument("--also", type=Path, action="append", default=[],
                        help="another port's engine, checked if it can run here")
    args = parser.parse_args()
    rc = check(args.engine, required=True)
    for other in args.also:
        rc |= check(other, required=False)
    return rc


if __name__ == "__main__":
    sys.exit(main())
