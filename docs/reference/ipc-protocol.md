# Protocol reference

How the plug-in and its engine process talk. The exact sizes and offsets are the compile-time checks in [`src/protocol/include/mpvst/protocol.h`](../../src/protocol/include/mpvst/protocol.h) and [`ui.h`](../../src/protocol/include/mpvst/ui.h); this page is the rules and the record table. [How it works](../how-it-works/index.md) is the narrative.

## Compatibility

- The magic is the four ASCII bytes `MPV3`. The protocol major version is 1, and an incompatible layout or meaning increments it. The minor version is 2, and readers ignore unknown optional regions.
- Every region carries its byte size and a generation.
- Integers are fixed-width and little-endian. Shared atomics are naturally aligned 32- or 64-bit integers.
- No `bool`, enum-sized field, native pointer, `size_t`, C++ object or implicit padding appears in the wire layout.
- Both MSVC and GCC report the same offsets, sizes and alignments, and the protocol tests check it.

## Regions

The mapping begins with a fixed header holding offsets and sizes for the host-to-engine control ring, the timestamped event and parameter ring, the host-to-engine work slots, the engine-to-host float32 output slots, and the engine status with bounded diagnostics. Every region starts on a 64-byte boundary.

| Record | Bytes | Role |
|---|---:|---|
| `mpvst_shared_header` | 128 | ABI identity, capacities, offsets, generation, lifecycle |
| `mpvst_status` | 128 | heartbeat, counters, event-consumer cursor, bounded diagnostic |
| `mpvst_command` | 64 | non-audio lifecycle and reload commands |
| `mpvst_event` | 32 | absolute-sample event or parameter change |
| `mpvst_work_slot` | 64 | bounded render request and transport context |
| `mpvst_output_slot` | 64 | output metadata, then planar float32 samples |

An output slot is a 64-byte header followed by `max_frames` left samples and `max_frames` right samples, with the stride rounded up to the next 64-byte boundary. Output is planar stereo float32.

VST3 MIDI controller parameters are decoded before they enter the event ring: `channel` keeps the MIDI channel, `data0` the controller number, `value0` is normalized 0 to 1, and pitch bend also carries its bipolar value in `value1`.

## Slots never block the audio thread

Each fixed-capacity slot has an atomic sequence value. A producer owns a slot only when its expected sequence is free, writes the payload, then publishes the completed sequence with release ordering. A consumer acquires it, copies the bounded payload and releases it for the next wrap. Neither side waits for a slot on the audio thread: a full ring means a bounded drop, and late, stale or mismatched output means silence.

Output slots are keyed by absolute start sample and generation. The plug-in accepts one only when generation, start sample, frame count, channel count and format all match what it asked for.

Maximum frames per slot is fixed when the mapping is created, from the host's `maxSamplesPerBlock`. Event payloads have a fixed maximum size. Text diagnostics are fixed UTF-8 buffers with byte counts and truncation flags. Counters saturate rather than wrap.

## Lifecycle

1. Setup chooses the sample rate, maximum block size and latency.
2. Non-audio code creates a unique mapping and the engine process.
3. The engine validates the complete header before marking itself ready.
4. Activation increments the generation and clears the cursors.
5. Audio processing starts with `L` samples of silence.
6. Deactivation closes the generation and asks the engine to shut down.
7. Teardown waits until audio processing has stopped.

## Editor records

The editor uses a second, sibling mapping, so the audio mapping's 128-byte header never had to grow: an engine that doesn't understand the extra argument naming the UI mapping ignores it and plays without an editor.

| Record | Bytes | Role |
|---|---:|---|
| `mpvst_ui_state` | 128 | logical and maximum size, pixel format, editor-open flag, content scale, frame sequence, cursors, UI error, heartbeat |
| `mpvst_ui_rect` | 16 | dirty rectangle tied to a frame sequence |
| `mpvst_ui_input` | 32 | input event: type, buttons, logical x and y, two signed wheel deltas, sequence |
| `mpvst_ui_edit` | 32 | parameter edit: begin, perform or end; parameter ID; normalized float32 value; sequence |
| framebuffer | 1024 x 600 x 2 | RGB565 little-endian pixels at the maximum size; the logical size indexes into the same stride |

The rings hold 64 dirty rectangles, 256 input events and 64 edits. They degrade by counted, bounded loss rather than waiting: a full dirty ring coalesces to one full-frame rectangle, pointer moves coalesce to the latest position, wheel events add their deltas, and a full edit ring drops `perform` records but never a `begin` or `end`.

A frame is published under a sequence lock. The engine sets the sequence odd, writes pixels and rectangles, then sets it even. The view samples the sequence, copies, and re-checks; on a mismatch it discards the copy and retries on its next timer tick. Coordinates are logical pixels everywhere, and the view converts for display scale.

### The `vstui` module

| Call | Role |
|---|---|
| `vstui.open(name)` | Map the region the plug-in named; false when there is none. |
| `vstui.configure(w, h)` | Declare the logical size, once, within the compiled maximum. |
| `vstui.blit(buf, x, y, w, h)` | Copy pixels in and publish, both inside the sequence lock. |
| `vstui.publish(x, y, w, h)` | Publish a rectangle written through `framebuffer()`. |
| `vstui.framebuffer()` | A memoryview of the RGB565 framebuffer. |
| `vstui.poll()` | Drain pending input events. |
| `vstui.edit(kind, id, value)` | Publish one parameter edit. |
| `vstui.editor_open()` | The host's editor-attached flag. |
| `vstui.error(code)` | Report a panel failure for the view to render. |
