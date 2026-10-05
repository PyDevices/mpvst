"""mpvst's C modules for a MicroPython build: vstaudio and vstui.

Name this repository among the modules of a micropython-pydevices build, the
way any module outside that repository is named, by its path:

    build_mp.py --port windows --variant vst3-engine --modules <others>,/path/to/mpvst

The vst3-engine variant is what turns sockets, SSL and FFI off for the
plug-in's sidecar; see docs/security.md.
"""

if 0:

    def include(*args, **kwargs):
        pass


include("usermods/vstaudio")  # type: ignore[name-defined]  # noqa: PGH003
include("usermods/vstui")  # type: ignore[name-defined]  # noqa: PGH003
