#!/usr/bin/env bash
# Build the MicroPython sidecar engine.
#
#   ./scripts/build-micropython-engine.sh [--port windows|unix]
#
# Defaults to the Windows engine, which is the shipping product. The unix port
# builds the same module set for the Linux bundle.
#
# The build is upstream MicroPython's own make with the vst3-engine variant
# and preset that micropython-pydevices carries: the variant turns sockets,
# SSL and FFI off (the engine is a deliberately narrow scripting core -
# compositions and racks are code, and mpvst_scan_plugins.py runs at DAW scan
# time, so the shipped interpreter must not reach the network or arbitrary
# native code; the mpvst_engine_capabilities ctest checks it held, on each
# port's engine), and the preset names every module the workspace builds plus
# this repository's vstaudio and vstui. Nothing here is copied or linked into
# the MicroPython checkout.
#
# Layout: this repository, micropython-pydevices, audiodsp (and the other
# module repositories the preset names) and a MicroPython checkout are
# siblings under one directory. scripts/fetch-sibling-repos.sh lays that out
# and readies the checkout. MICROPYTHON_DIR overrides where the checkout is.
set -euo pipefail

port=windows
while [[ $# -gt 0 ]]; do
    case "$1" in
        --port) port="$2"; shift 2 ;;
        *) echo "usage: $0 [--port windows|unix]" >&2; exit 2 ;;
    esac
done

repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
workspace_dir=$(cd "$repo_dir/.." && pwd)
mp_dir=${MICROPYTHON_DIR:-"$workspace_dir/micropython"}
pyd_dir="$workspace_dir/micropython-pydevices"
output_dir="$repo_dir/.deps/engine"
jobs=${JOBS:-$(nproc)}

# The windows executable wears our icon rather than MicroPython's. One .ico
# serves both Windows surfaces: this, and the bundle folder icon the VST3 SDK
# would otherwise fill with Steinberg's logo (see src/plugin/CMakeLists.txt).
# Placeholder art - installer/art/README.md says what it is and how to replace it.
make_extra=()
case "$port" in
    # mkrules.mk appends .exe itself for mingw targets, so the variant's PROG is
    # the bare name; the installed artifact still carries the extension.
    windows) engine_name=mpvst-engine.exe
             make_extra+=(CROSS_COMPILE=x86_64-w64-mingw32- ENGINE_ICON="$repo_dir/installer/art/mpvst.ico") ;;
    unix)    engine_name=mpvst-engine ;;
    *) echo "error: unsupported port '$port'" >&2; exit 2 ;;
esac

variant_dir="$pyd_dir/variants/$port/vst3-engine"
if [[ ! -f "$mp_dir/ports/$port/Makefile" ]]; then
    echo "error: no Makefile at $mp_dir/ports/$port - the sibling micropython checkout" \
        "is missing or incomplete. Run scripts/fetch-sibling-repos.sh, or point" \
        "MICROPYTHON_DIR at an existing checkout." >&2
    exit 1
fi
if [[ ! -f "$variant_dir/mpconfigvariant.mk" ]]; then
    echo "error: no vst3-engine variant at $variant_dir - the sibling" \
        "micropython-pydevices checkout is missing or old. Run scripts/fetch-sibling-repos.sh." >&2
    exit 1
fi
if [[ ! -f "$workspace_dir/audiodsp/micropython.mk" ]]; then
    echo "error: no micropython.mk at $workspace_dir/audiodsp - the sibling audiodsp" \
        "checkout is missing or incomplete. Run scripts/fetch-sibling-repos.sh." >&2
    exit 1
fi
overlay_mark="The PyDevices overlay applied to $(tr -d '[:space:]' < "$pyd_dir/UPSTREAM")"
if [[ "$(git -C "$mp_dir" log -1 --format=%s 2>/dev/null)" != "$overlay_mark"* ]]; then
    echo "error: $mp_dir does not carry the PyDevices overlay; run" \
        "$pyd_dir/tools/prepare-micropython.sh $mp_dir" >&2
    exit 1
fi

mkdir -p "$output_dir"

make -C "$mp_dir/mpy-cross" -j "$jobs"
# VARIANT_DIR is taken relative to the port directory; the build lands in
# build-vst3-engine (the variant's own name), beside the port's other builds.
make -C "$mp_dir/ports/$port" -j "$jobs" \
    VARIANT_DIR="$variant_dir" "${make_extra[@]}"

install -m 755 \
    "$mp_dir/ports/$port/build-vst3-engine/$engine_name" \
    "$output_dir/$engine_name"

# Stamp it with what it was built from. The engine is a PREBUILT artifact:
# every later `cmake --build` copies whatever is sitting in .deps/engine into
# the bundle without asking how old it is, so the whole ctest suite can run
# green against a core that no longer exists (mpvst#12, four days of it). The
# stamp records the commits of this repo's own vstaudio/vstui and of audiodsp,
# so tools/engine-provenance.py can refuse an engine once the code that goes
# into it moves. The stamper is this repository's own, so a public clone gets
# a stamped engine too (mpvst#16).
python3 "$repo_dir/tools/engine-provenance.py" write "$output_dir/$engine_name" \
    --port "$port" --audiodsp "$workspace_dir/audiodsp" --micropython "$mp_dir"

echo "Built $output_dir/$engine_name"
