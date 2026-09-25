# What the shipped engine cannot do

Compositions, instruments, and racks are Python code, and some of it —
`mpvst_scan_plugins.py` reading module declarations — runs at plugin-scan time,
before you consciously play anything. Because people share pieces, the shipped
sidecar engine is built without **sockets, SSL or FFI**, so that a piece you
downloaded cannot reach the network whatever it contains. A hostile script
has no exfiltration
channel and no route to arbitrary native code; its blast radius is the
file I/O the engine legitimately needs for its own library.

This is a safe default, not a sandbox. You can rebuild the engine with
networking or FFI enabled and drop it into the bundle — at that point the
capability was your informed choice as the builder, which is exactly the
line this default draws: nothing a downloaded piece can switch on by
itself. Do not redistribute bundles containing a widened engine without
saying so.

The engine is built without those three at the source, on both platforms,
by the `vst3-engine` variant in
[micropython-pydevices](https://github.com/PyDevices/micropython-pydevices/tree/main/variants)
that [`scripts/build-micropython-engine.sh`](../scripts/build-micropython-engine.sh)
builds with. The ctest `mpvst_engine_capabilities`
([tools/check-engine-capabilities.py](../tools/check-engine-capabilities.py))
runs each engine and fails if it can import `socket`, `ssl`, `tls`, `ffi` or
`network`. It exists because the Windows engines shipped in 0.3.0 and 0.3.1
could import `socket` while every Linux test passed.
