#!/usr/bin/env bash
# Download a released Windows build of MPVST, check it against its .sha256,
# and install it into the per-user VST3 directory a DAW scans, the same place
# install-plugin-windows.sh puts a build made from this checkout.
#
#   ./scripts/install-release.sh [--download-only] [TAG]
#
# With no TAG it takes the newest release, pre-releases included, so it
# installs the latest dev build. --download-only stops after the checksum
# and leaves the unpacked bundle where it says. Run from WSL with the GitHub
# CLI (gh) signed in. MPVST_RELEASE_REPO names another repository to take
# releases from, and MPVST_VST3_DIR another install directory.
set -euo pipefail

repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
release_repo=${MPVST_RELEASE_REPO:-PyDevices/mpvst}

download_only=0
tag=
for arg in "$@"; do
    case "$arg" in
        --download-only) download_only=1 ;;
        -h|--help) sed -n '2,12p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
        -*) echo "error: unknown option $arg" >&2; exit 2 ;;
        *) [[ -z "$tag" ]] || { echo "error: one tag at most" >&2; exit 2; }
           tag=$arg ;;
    esac
done

command -v gh >/dev/null 2>&1 || { echo "error: the GitHub CLI (gh) is not installed" >&2; exit 1; }

if [[ -z "$tag" ]]; then
    # gh lists the newest first, pre-releases among them.
    tag=$(gh release list -R "$release_repo" --exclude-drafts --limit 1 \
        --json tagName -q '.[0].tagName')
    [[ -n "$tag" ]] || { echo "error: $release_repo has no releases" >&2; exit 1; }
fi
version=${tag#v}
name="MPVST-$version"
archive="$name-windows-x86_64.zip"

work_dir=$(mktemp -d)
trap 'rm -rf -- "$work_dir"' EXIT

echo "downloading $archive from $release_repo $tag"
gh release download "$tag" -R "$release_repo" \
    -p "$archive" -p "$archive.sha256" -D "$work_dir"
(cd "$work_dir" && sha256sum -c "$archive.sha256") \
    || { echo "error: $archive does not match its .sha256" >&2; exit 1; }

python3 -m zipfile -e "$work_dir/$archive" "$work_dir"
bundle_src="$work_dir/$name/MPVST.vst3"
for f in MPVST.vst3 mpvst-engine.exe mpvst_bootstrap.py default_instrument.py; do
    [[ -f "$bundle_src/Contents/x86_64-win/$f" ]] \
        || { echo "error: the archive's bundle has no Contents/x86_64-win/$f" >&2; exit 1; }
done

if [[ "$download_only" == 1 ]]; then
    trap - EXIT
    echo "verified: $bundle_src"
    exit 0
fi

source "$repo_dir/scripts/windows-paths.sh"
mpvst_load_windows_paths || exit 1
vst3_dir=${MPVST_VST3_DIR:-$WIN_LOCALAPPDATA/Programs/Common/VST3}

# A DAW holds the .vst3 DLL open, and each engine holds mpvst-engine.exe
# open, including engines a force-killed host left behind. Any of them makes
# the removal below fail half-way, so stop them all and wait until none is
# left before touching the installed bundle.
running=1
for _ in 1 2 3 4 5; do
    running=$(powershell.exe -NoProfile -Command \
        "Get-Process reaper,mpvst-engine -EA SilentlyContinue | Stop-Process -Force -EA SilentlyContinue; Start-Sleep 3; @(Get-Process reaper,mpvst-engine -EA SilentlyContinue).Count" \
        2>/dev/null | tr -d '\r[:space:]')
    [[ "$running" == 0 ]] && break
done
[[ "$running" == 0 ]] || {
    echo "error: REAPER or an MPVST engine is still running; close it and run this again" >&2
    exit 1
}

mkdir -p "$vst3_dir"
rm -rf "$vst3_dir/MPVST.vst3" || {
    echo "error: could not remove $vst3_dir/MPVST.vst3; a process still holds it" >&2
    exit 1
}
cp -r "$bundle_src" "$vst3_dir/MPVST.vst3"

# Check the copy, file by file, against what was verified.
(cd "$bundle_src" && find . -type f -exec sha256sum {} +) > "$work_dir/bundle.sha256"
(cd "$vst3_dir/MPVST.vst3" && sha256sum --quiet -c "$work_dir/bundle.sha256") \
    || { echo "error: the installed bundle differs from the release" >&2; exit 1; }

echo "installed $name: $vst3_dir/MPVST.vst3"
