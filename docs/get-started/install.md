# Install

MPVST ships as one VST3 bundle. Nothing has to be built to use it: the archives carry the plug-in and the MicroPython engine it runs your scripts in.

Download the archive for your platform from the [latest release](https://github.com/PyDevices/mpvst/releases/latest). Each file has a `.sha256` beside it to check it against. Windows and Linux both ship; macOS is not a target.

| Platform | Release file | What to do |
|---|---|---|
| Windows | `MPVST-<version>-windows-x86_64-setup.exe` | Run it. |
| Windows, no installer | `MPVST-<version>-windows-x86_64.zip` | Unpack it and copy `MPVST.vst3` into a VST3 folder, as in [MPVST on Windows](../guides/windows.md#installing-from-the-zip-instead). |
| Linux | `MPVST-<version>-linux-x86_64.tar.gz` | Unpack it and run the `install.sh` inside. |

## Windows

The installer works for the current user, so there is no administrator prompt. It puts the bundle in `%LOCALAPPDATA%\Programs\Common\VST3` unless you point it at another VST3 folder.

That also decides where the uninstaller shows up: Settings, then Apps, then Installed apps. It is not in the old Control Panel "Programs and Features" list, which only shows machine-wide installs.

Close your DAW first. A host that has the plug-in loaded holds its files open.

## Linux

`install.sh` copies the bundle to `~/.vst3` and runs the plug-in scan. `--dir DIR` installs somewhere else, and `--uninstall` removes the bundle again (add the same `--dir` you installed with).

## Rescan in your host

Make it a real rescan, not a restart. A host caches what it found last time against the bundle's contents, and REAPER has been seen holding entries from an earlier build after an install. In REAPER, Preferences, Plug-ins, VST, Re-scan clears it.

The bundle registers a named plug-in for every library instrument and effect (for example **TR-808** under Instrument|Drum and **Tape Delay** under Fx|Delay), plus two generic **MPVST Script Host** classes. `mpvst_scan_plugins.py --list`, run with the bundle's own engine, prints the current set. [MPVST on Windows](../guides/windows.md#rescan-after-adding-a-script-of-your-own) and [MPVST on Linux](../guides/linux.md#rescan-after-adding-a-script-of-your-own) show the command.

Next: [your first program](first-program.md).
