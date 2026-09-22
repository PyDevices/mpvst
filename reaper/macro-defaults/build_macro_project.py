#!/usr/bin/env python3
"""One-track MPVST project whose component state is written by hand.

The point is to control the two fields a saved project carries that nobody
can set from a DAW: the state version, and -- from version 3 -- the mask
saying which macros somebody actually chose. matrix_instrument.py renders a
constant level of 0.125 + 0.125 * macro01 while a note is held, and its own
default for macro01 is 0.0, so the rendered sample says exactly which value
reached the script.

    build_macro_project.py <out.RPP> <script.py> <version> <mask> <value>
"""
import base64
import struct
import sys
import uuid


def guid():
    return "{%s}" % str(uuid.uuid4()).upper()


def component_state(script, version, mask, value):
    comp = struct.pack("<ii", version, 0)
    for _ in range(16):
        comp += struct.pack("<f", value)
    comp += struct.pack("<ii", 4, len(script))
    comp += script
    if version >= 3:
        comp += struct.pack("<i", mask)
    return comp


INSTRUMENT_HEADER = [0x35700DF5, 0xFEED5EEE, 0x0,
                     0x2, 0x1, 0x0, 0x2, 0x0,
                     None, 0x1, 0xFFFF]
INSTRUMENT_VST = ('<VST "VST3i: MPVST Script Host" '
                  'MPVST.vst3 0 "" '
                  '896536053{60A40168727C4E7DAAF808B790961DAA} ""')


def chunk_lines(script, version, mask, value):
    comp = component_state(script, version, mask, value)
    data = struct.pack("<II", len(comp), 1) + comp + b"\0" * 8
    words = [len(data) if w is None else w for w in INSTRUMENT_HEADER]
    header = struct.pack("<%dI" % len(words), *words)
    lines = [base64.b64encode(header).decode()]
    encoded = base64.b64encode(data).decode()
    lines += [encoded[i:i + 128] for i in range(0, len(encoded), 128)]
    lines.append(base64.b64encode(b"\0" * 6).decode())
    return lines


def main():
    out, script_path = sys.argv[1], sys.argv[2]
    version, mask, value = int(sys.argv[3]), int(sys.argv[4]), float(sys.argv[5])
    script = open(script_path, "rb").read()

    lines = ['<REAPER_PROJECT 0.1 "7.79" 0',
             "  RIPPLE 0", "  TEMPO 120 4 4", "  SAMPLERATE 48000 0 0",
             "  <TRACK %s" % guid(),
             '    NAME "macro default"',
             "    VOLPAN 1 0 1 -1 1", "    NCHAN 2", "    FX 1",
             "    TRACKID %s" % guid(), "    MAINSEND 1 0",
             "    <FXCHAIN", "      SHOW 0", "      LASTSEL 0",
             "      DOCKED 0", "      BYPASS 0 0 0",
             "      " + INSTRUMENT_VST]
    for line in chunk_lines(script, version, mask, value):
        lines.append("        " + line)
    lines += ["      >", "      FLOATPOS 0 0 0 0",
              "      FXID %s" % guid(), "      WAK 0 0", "    >",
              "    <ITEM", "      POSITION 0", "      LENGTH 3", "      LOOP 0",
              "      IGUID %s" % guid(), "      IID 1", '      NAME "note"',
              "      GUID %s" % guid(),
              "      <SOURCE MIDI", "        HASDATA 1 960 QN",
              "        E 1920 90 3c 64", "        E 1920 80 3c 00",
              "        GUID %s" % guid(), "        IGNTEMPO 0 120 4 4",
              "      >", "    >", "  >", ">"]
    with open(out, "w") as handle:
        handle.write("\n".join(lines) + "\n")
    print("wrote %s  version=%d mask=0x%X value=%.3f" % (out, version, mask, value))


main()
