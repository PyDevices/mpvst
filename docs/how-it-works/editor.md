# The editor

Every instance can show a panel of its own, laid out like a hardware instrument. It has sixteen patch pads in eight banks, an encoder with a ring of LEDs for each macro, a dot-matrix display, an engine light, and FINE, BYPASS and RELOAD buttons, labelled with whatever the script declares. This page is how that panel works and what happens when it breaks. It is one generic panel, the `controlpanel` package, frozen into the engine. Per-script panels, meters and resizable editors aren't built.

## Who draws what

The panel runs in the same MicroPython process as your script and is written with LVGL. It draws into a shared RGB565 framebuffer, and the plug-in's native view copies that framebuffer into a window your host provides. The view doesn't interpret widgets or rebuild the UI. Python paints pixels; native code presents pixels.

The panel's logical size is fixed for the life of the engine and declared once from Python, up to 1024 by 600 pixels; the stock panel uses 800 by 480. The view scales it for your display rather than the engine re-laying anything out.

When no editor is open the engine does no UI work at all: no timers, no painting, no input polling. When one is open, the engine ticks the panel only when audio is ahead of its deadline, at about 30 Hz, so under load the frame rate drops and the audio doesn't.

## Input

The panel takes pointer and wheel input, not keyboard. Drag an encoder up or right to turn it up. Click a control to focus it: the wheel (or a trackpad swipe) acts on the focused control, sideways adjusting it (rightward increasing) and up and down moving focus to the previous or next control. Double-click an encoder to return it to the value the patch gave it. FINE makes drags and the wheel finer. A pad picks a patch; the bank buttons show another bank's pads.

## Gestures become automation

An encoder drag is reported to your host as one begin, a stream of changes, and one end, so it records as a single automation edit. A burst of wheel notches on a focused control is one gesture too: it begins on the first notch and ends after a short quiet. The host echoes each change back through the normal parameter path, and the panel treats the host's value as the truth.

The panel edits the patch, the 16 macros, bypass and reload. When the patch changes from the host, every encoder and LED ring moves to the new patch's macros, and nothing is sent back. All of them are ordinary automatable parameters your host's generic editor shows as well.

## When the panel fails

A Python error in the panel is caught, the panel is torn down, and audio is unaffected. The view draws "Editor unavailable" instead of freezing, and the instance keeps playing. A host that provides no run loop (on Linux) gets no editor, and the generic parameter editor still works.

If the engine restarts, the view picks up the new framebuffer and the panel rebuilds from the replayed macro values.

Opening the editor doesn't change what's rendered: the output is identical with and without one attached, and the cross-platform parity check enforces that.

The shared-memory records behind all this are in the [protocol reference](../reference/ipc-protocol.md#editor-records).
