# Nicky Boom — Level Editor v1.1

A level editor for the DOS game **Nicky Boom** (Microids, 1992, ported from
Amiga). Author: DarkSoL, with help from Claude (Anthropic).
Discord: darksol41

## What's new in v1.1

### 🎉 Headline fix: the real cause of hangs/garbled tiles/broken music, found and fixed

For a long time it seemed impossible to rebuild a compressed level
(`DECORn.CDG`) after edits without side effects: the game would either
hang, the map would turn into garbage, or the music/sound would stop
working. Many hypotheses were tried — overlapping copies, the order of
operations in the header, different compression strategies (including
mimicking the original Amiga packer's "column-aware" strategy) — none of
it reliably fixed things.

**The real cause turned out to be the first 2 bytes of the file**, which
were previously assumed to be unused/ignorable padding (the `sqx_decode`
decoder itself genuinely never reads them). In reality they're a **buffer
placement offset** that tells the game where, inside a fixed-size memory
buffer, to place the compressed data before decompressing it:

```
first_2_bytes = decompressed_size − compressed_body_size
```

The game allocates a fixed-size buffer per resource and reads the
compressed file into it starting at an offset given by these 2 bytes — not
at the very beginning of the buffer — so that decompression (which writes
from the start of the buffer and grows forward) never catches up to the
still-unread compressed data sitting further along in the same buffer, and
so the compressed data itself doesn't run past the end of the buffer
during the file read.

Older versions of the exporter **copied these 2 bytes from the original
file** — which is only correct for the original compressed size. Any edit
changes the compressed body size, while the old (now wrong) offset stayed
the same — hence:
- if the new body is **larger** than the original — the file read
  overflows the buffer → corrupts adjacent memory → **hang**;
- if the offset happens to be small — the file read itself fits fine, but
  decompression's output catches up to its own input **inside** the
  buffer → **garbled tiles**, but no crash;
- corrupting adjacent memory could also clobber whatever the **sound
  engine** uses, which is why music/sound broke too.

**The fix**: on every `.CDG` and `.POSIT.REF` export, the editor now
**recomputes these 2 bytes** based on the actual size of the resulting
compressed body. No more limitations — real compression (~9-11 KB instead
of ~25 KB), any tile/object edits, no garbling, no hangs, working music.

### Other fixes in v1.1

- The "Full compression (fixed)" status badge is now translated into all
  supported languages (it used to be Russian-only).
- Right-click on the map no longer opens the browser's context menu —
  it's now an **eraser** (paints tile 0 / "sky"). Left-click still paints
  with the selected tile, as before.
- Added a tooltip explaining the browser's system warning when picking the
  game folder (this is standard browser behaviour for directory pickers,
  not an editor bug — the editor already automatically finds and opens
  only the needed level files, ignoring everything else in the folder and
  its subfolders).
- Editor version bumped: 1.0 → 1.1.
- New objects placed on the map now default to **"Visible" unchecked**
  (most regular objects/monsters in the original levels have this off).

## Known limitation that is NOT fixed

**The 409-object limit** in `POSITn.REF` (monsters/items) is a hard-coded
array size in the game itself (`objects_table[410]` in the code) — it's
unrelated to the file format and can't be worked around by editing data
alone. Moving/editing/removing existing objects is fine; adding more than
409 requires patching the executable itself.

## Requirements

- Level files: `DECORn.CDG`, `DECORn.BLK`, `DECORn.REF`, `POSITn.REF`,
  `REFn.REF`, `S0n.SPR`/`S1n.SPR` (for the level `n` you want, or `nA` for
  a boss level).
- A modern browser (Chrome/Edge/Firefox) — the editor runs entirely
  locally, nothing is ever sent to a server.

## Quick start

1. Open `Nicky_level_editor 1.1.html` in your browser.
2. Click **"OPEN GAME FOLDER"** and pick the folder with your game files —
   the editor automatically finds the needed files and loads level 1.
3. Switch levels using the dropdown at the top.
4. **Tiles mode**: left-click to paint with the selected tile, right-click
   to erase (tile 0), `Ctrl+Z` to undo.
5. **Objects mode**: pick a type on the left, click the map to place/select
   an object, drag to move it, "Delete" button to remove it.
6. **"Export .CDG"** / **"Export POSIT.REF"** save the file in the format
   the game expects (real compression, correct buffer offset).
7. Drop the exported files into your game folder in place of the
   originals and run the game through DOSBox.

## Sources

- `nicky-0.2.0-src.zip` — Gregory Montoir (cyx), engine reimplementation of
  Nicky Boum/Nicky 2 (`sqx_decoder.c`, `fileio_std.c`, `resource.c`,
  `game.c`).
- Independent UPX unpacking and disassembly of `NICKY.EXE` (the original
  DOS version) — used to confirm the format against the real assembly
  code of the game.
- Reference screenshot of level 1: `964_map0.png` (Hall of Light,
  hol.abime.net/964).

## Legal

This is an unofficial, free, non-commercial fan tool for editing your own legally
owned copy of the game. It is not affiliated with or endorsed by Microids.
*Nicky Boom* © 1992 Microids; the game, its name, graphics and levels belong to
their owners. This package does not include any game files or assets.

The `sqx` decoder in this package is a port of `sqx_decode()` from *Nicky - Nicky Boum
engine rewrite*, Copyright (C) 2006-2007 Gregory Montoir (`nicky-0.2.0-src`), used with
attribution. That project is his work; everything else here is written independently.

No warranty of any kind. Keep a backup of your original game files.
If you are a rights holder and want something changed or removed, contact me on Discord (`darksol41`) and I will do it.
