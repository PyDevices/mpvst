#!/usr/bin/env bash
# Does a script's own macro default survive a project load?
#
#   ./reaper/macro-defaults/run-macro-defaults.sh [--platform windows|linux]
#
# Renders three projects that differ only in the two fields no DAW can set --
# the component state's version, and from version 3 the mask saying which
# macros somebody actually chose -- and reads the level back out of the PCM.
#
#   A  v3, mask 0x0000   ->  0.1250   the script's own default survived
#   B  v3, mask 0xFFFF   ->  0.1875   0.5 was replayed over it
#   C  v2 legacy         ->  0.1875   an old project does not move
#
# B is the failure reproduced deliberately. Without it, A on its own proves
# only that something rendered; a harness that can only pass is not evidence.
#
# The instrument is reaper/matrix/matrix_instrument.py, which renders a
# constant 0.125 + 0.125 * macro01 while a note is held and defaults macro01
# to 0.0, so one sample names the value that reached the script.
#
# Needs the plug-in installed -- ~/.vst3 on Linux, the per-user VST3 folder on
# Windows -- and rebuilt after any change to the state code. PyDevices/mpvst#7.
set -euo pipefail

# Defaults to linux and is chosen explicitly, exactly as run-reaper-matrix.sh
# does. Both platforms are driven from WSL here, so sniffing the environment
# would guess wrong half the time -- and a `[[ ... ]] && var=x` that evaluates
# false returns 1, which under `set -e` aborts the script it was meant to
# configure.
platform=linux
while [[ $# -gt 0 ]]; do
    case "$1" in
        --platform) platform="$2"; shift 2 ;;
        *) echo "usage: $0 [--platform windows|linux]" >&2; exit 2 ;;
    esac
done

here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
repo_dir=$(cd "$here/../.." && pwd)
instrument="$repo_dir/reaper/matrix/matrix_instrument.py"

if [[ "$platform" == windows ]]; then
    source "$repo_dir/scripts/windows-paths.sh"
    mpvst_load_windows_paths || exit 1
    reaper_exe=${REAPER_EXE:-$WIN_USERPROFILE/REAPER/reaper.exe}
    # A portable REAPER keeps its resource directory beside reaper.exe, and
    # %APPDATA%\REAPER is then silently ignored -- which looks exactly like a
    # modal dialog, because the startup script simply never runs.
    if [[ -n "${REAPER_RESOURCE:-}" ]]; then
        reaper_resource=$REAPER_RESOURCE
    elif [[ -f "$(dirname "$reaper_exe")/reaper.ini" ]]; then
        reaper_resource=$(dirname "$reaper_exe")
    else
        reaper_resource=$WIN_APPDATA/REAPER
    fi
    work_unix=${WORK_DIR:-$WIN_TEMP/mpvst-macro-defaults}
    sep='\'
    to_native() { wslpath -w "$1"; }
else
    reaper_exe=${REAPER_EXE:-$HOME/opt/REAPER/reaper}
    reaper_resource=${REAPER_RESOURCE:-$HOME/.config/REAPER}
    work_unix=${WORK_DIR:-/tmp/mpvst-macro-defaults}
    sep='/'
    to_native() { printf '%s' "$1"; }
fi

test -x "$reaper_exe" || chmod +x "$reaper_exe"
rm -rf "$work_unix"; mkdir -p "$work_unix"
work_native=$(to_native "$work_unix")

python3 "$here/build_macro_project.py" "$work_unix/A_v3_unknown.RPP" "$instrument" 3 0     0.5
python3 "$here/build_macro_project.py" "$work_unix/B_v3_known.RPP"   "$instrument" 3 65535 0.5
python3 "$here/build_macro_project.py" "$work_unix/C_v2_legacy.RPP"  "$instrument" 2 0     0.5

# REAPER reopens its last project and shows a modal error if it is gone, which
# would block the startup script forever. Always hand it an explicit one.
cat > "$work_unix/empty.RPP" <<'RPP'
<REAPER_PROJECT 0.1 "7.79" 0
  RIPPLE 0
  TEMPO 120 4 4
>
RPP

# Leaving __startup.lua behind would quit REAPER the next time a human opened
# it, so removing it is part of the run and not a tidy-up someone may skip.
cleanup() {
    rm -f "$reaper_resource/Scripts/__startup.lua"
    if [[ "$platform" == windows ]]; then
        powershell.exe -NoProfile -Command \
            "Get-Process reaper,mpvst-engine,micropython-vst-engine -EA SilentlyContinue | Stop-Process -Force -EA SilentlyContinue" \
            >/dev/null 2>&1 || true
    else
        pkill -x reaper >/dev/null 2>&1 || true
    fi
}
trap cleanup EXIT

mkdir -p "$reaper_resource/Scripts"
cp "$here/render.lua" "$reaper_resource/Scripts/__startup.lua"
if [[ "$platform" == windows ]]; then
    powershell.exe -NoProfile -Command \
        "Get-Process reaper -EA SilentlyContinue | Stop-Process -Force -EA SilentlyContinue" \
        >/dev/null 2>&1 || true
else
    pkill -x reaper >/dev/null 2>&1 || true
fi
sleep 3

echo "Rendering three macro-default projects on $platform..."
if [[ "$platform" == windows ]]; then
    launcher="$work_unix/run.ps1"
    cat > "$launcher" <<PS1
\$env:MPVST_MACRO_WORKDIR = "$work_native"
\$env:MPVST_MACRO_SEP = "\\"
\$env:MPVST_TEST_LOG = "$work_native${sep}script_log.txt"
Start-Process -FilePath "$(to_native "$reaper_exe")" -ArgumentList "-ignoreerrors","$work_native${sep}empty.RPP"
PS1
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$(to_native "$launcher")" \
        >/dev/null 2>&1 || true
else
    MPVST_MACRO_WORKDIR="$work_unix" MPVST_MACRO_SEP="/" \
    MPVST_TEST_LOG="$work_unix/script_log.txt" \
        nohup "$reaper_exe" -ignoreerrors "$work_unix/empty.RPP" >/dev/null 2>&1 &
fi

deadline=$(( $(date +%s) + ${MACRO_TIMEOUT:-300} ))
while [ "$(date +%s)" -lt "$deadline" ]; do
    if [ -f "$work_unix/report.txt" ] && grep -q '^DONE' "$work_unix/report.txt" 2>/dev/null; then
        break
    fi
    sleep 5
done

if ! grep -q '^DONE' "$work_unix/report.txt" 2>/dev/null; then
    echo "no report produced. Capture the REAPER window before assuming a modal" >&2
    echo "dialog: the usual cause is the startup script never running, because" >&2
    echo "the resource directory is not where this script guessed." >&2
    exit 1
fi

echo
python3 "$here/check_renders.py" "$work_unix"/*.wav
