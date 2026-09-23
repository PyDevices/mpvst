#!/usr/bin/env bash
# Clone the sibling repos the builds need, and ready the MicroPython checkout.
#
#   ./scripts/fetch-sibling-repos.sh
#
# For scripts/build-micropython-engine.sh: micropython-pydevices (the
# vst3-engine variant and preset, the patch series), audiodsp (the
# synthio/audiocore DSP the engine links; its own fetch_deps.sh brings ulab
# and the mp3 decoder), the other module repositories the kitchen-sink preset
# names, and a clone of upstream MicroPython at the pinned tag with the patch
# series applied once. For the plug-in build: audiocomponents (the
# audioinstruments and audioeffects packages src/plugin/CMakeLists.txt stages
# into the bundle). Idempotent - safe to rerun.
#
# Everything lands as a sibling of this repository, matching
# build-micropython-engine.sh's and the plug-in CMake defaults.
# MICROPYTHON_DIR overrides where the MicroPython checkout goes.
#
# Deliberately does NOT force-update an already-cloned sibling (no
# `git reset --hard`): these are commonly hand-edited alongside this repo, and
# a clone that already exists may be sitting on local commits nobody has
# pushed yet. If it's already there, this just fetches and reports how far
# behind/ahead of origin/main it is, and leaves updating it to you.
set -euo pipefail
repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
workspace_dir=$(cd "$repo_dir/.." && pwd)
mp_dir=${MICROPYTHON_DIR:-"$workspace_dir/micropython"}

clone_or_report() {
    local name="$1" url="$2" dir="$3"
    if [[ -d "$dir/.git" ]]; then
        git -C "$dir" fetch --quiet origin main
        local ahead behind
        ahead=$(git -C "$dir" rev-list --count origin/main..HEAD)
        behind=$(git -C "$dir" rev-list --count HEAD..origin/main)
        local dirty=""
        [[ -n "$(git -C "$dir" status --porcelain)" ]] && dirty=" (uncommitted changes)"
        echo "$name: already cloned at $dir - $ahead ahead / $behind behind origin/main$dirty"
    else
        echo "$name: cloning to $dir"
        git clone "$url" "$dir"
    fi
}

# The module repositories the kitchen-sink preset names, plus this one's own
# build carrier. audiocomponents is cloned last: it was private for a while
# and a clone that fails for lack of access should not stop the others.
for name in micropython-pydevices audiodsp audioif displayif cameraif usbif \
            lvgl-micropython lvgl-bindings pygraphics pdwidgets palettes; do
    clone_or_report "$name" "https://github.com/PyDevices/$name.git" "$workspace_dir/$name"
done
if [[ ! -d "$workspace_dir/lvgl-bindings/lvgl/src" ]]; then
    git -C "$workspace_dir/lvgl-bindings" submodule update --init --depth 1 lvgl
fi
# ulab and the mp3 decoder, pinned by audiodsp, into audiodsp/.deps/.
"$workspace_dir/audiodsp/scripts/fetch_deps.sh"

upstream=$(tr -d '[:space:]' < "$workspace_dir/micropython-pydevices/UPSTREAM")
if [[ ! -d "$mp_dir/.git" ]]; then
    echo "micropython: cloning $upstream to $mp_dir"
    git clone --branch "$upstream" https://github.com/micropython/micropython.git "$mp_dir"
fi
"$workspace_dir/micropython-pydevices/tools/prepare-micropython.sh" "$mp_dir"

clone_or_report audiocomponents "https://github.com/PyDevices/audiocomponents.git" "$workspace_dir/audiocomponents"
echo "micropython:      $mp_dir"
echo "audiodsp:         $workspace_dir/audiodsp"
echo "audiocomponents:  $workspace_dir/audiocomponents"
