# Nicky Boom level file format (DOS, Microids 1992)

Reverse-engineered through binary analysis, cross-checked against the engine
reimplementation source `nicky-0.2.0-src` (Gregory Montoir / cyx,
http://cyxdown.free.fr/nicky/), and finally confirmed against the real
`NICKY.EXE` (own UPX-unpacking + disassembly of the original DOS executable).
The same compression algorithm (`sqx`) is used for **every** resource file
type: `.CDG`, `.BLK`, `.REF`, `.SQX`.

## 1. Common header and "sqx" compression

Every file on disk is laid out like this:

```
bytes 0-1   : buffer placement offset — see "IMPORTANT" note below!
              (NOT ignored by the real game, even though sqx_decode()
              itself never reads them — see explanation further down)
byte   2    : j1
byte   3    : j2          j1,j2,j3 — a permutation of {0,1,2}
byte   4    : j3
byte   5    : c1          shift parameter for long-match offsets (varies per file, e.g. 3..6)
bytes 6..   : compressed stream
```

The decompressed size is **not stored in the file** — it's engine know-how
(see the `pc_datafiles_table__v1` table in `fileio_std.c`):

| File           | Compressed size (level 1) | Decompressed |
|----------------|----------------------------|----------------|
| DECOR1.BLK     | 25,040                     | 32,768         |
| DECOR1.CDG     | 9,032                       | 20,000         |
| DECOR1.REF     | 163                          | 2,048          |
| POSIT1.REF     | 2,184                        | 4,100          |
| REF1.REF       | 2,839                        | 16,728         |

### ⚠️ IMPORTANT: bytes 0-1 are a buffer placement offset, NOT padding!

This was the actual root cause of months of "compression breaks the game"
mysteries, confirmed by disassembling the real DOS loader code:

```
first_2_bytes = decompressed_size − compressed_body_size
```
(`compressed_body_size` = file size minus the 6-byte header)

Verified exactly on the original files:
- CDG: 20000 − 9026 = **10974** ✓ (matches the file byte-for-byte)
- BLK: 32768 − 25034 = **7734** ✓ (matches the file byte-for-byte)

**Why this exists.** The game allocates one fixed-size buffer per resource
and loads the compressed file into it at an offset, not at the very start.
Decompression then writes the output starting from the buffer's beginning
(growing forward) while reading compressed input that sits further into the
*same* buffer. The offset must be tuned so that:
1. the file read itself doesn't write past the end of the buffer, and
2. the growing decompressed output never catches up to the still-unread
   compressed input within the buffer.

Both constraints together pin the offset down to essentially this one
formula, with only a few bytes of slack (an internal `+0x20` margin in the
loader plus the 4 header bytes consumed by `sqx_decode`).

**What used to go wrong:** earlier versions of the encoder/editor copied
these 2 bytes verbatim from the original file. That's only correct for the
*original* compressed size. As soon as the level is edited, the compressed
body size changes, but the old (now wrong) offset stays — and depending on
the direction of the mismatch this caused either a buffer overrun while
reading the file (→ corrupts adjacent memory → **hang**), or output
overtaking input *inside* the buffer during decompression (→ **garbled
tiles**, but no crash). It also explains why sound/music sometimes broke:
the corrupted adjacent memory could easily be something the sound engine
uses.

**The fix** (implemented in `sqx_encoder.py` / `nicky_level_editor.html`):
recompute these 2 bytes on every export, based on the *actual* size of the
freshly compressed body — never copy them from the original file. With this
fix, real LZ compression (not just a literal-only fallback) works
completely reliably: correct tiles, no hangs, intact music.

### The sqx algorithm itself (LZ family, bit-level control)

Control bits are read from a 16-bit `code` register, refilled from the
stream (little-endian words) as it empties out via shifts (`shr`/`rcr`/`rcl`
— classic assembly rotate-with-carry idioms). Each operation is one of
three types, and the order in which bits select a type is given by the
permutation `(j1, j2, j3)` read from that file's header:

- **Literal** — copy 1 byte verbatim.
- **Short match** — a copy from **-1..-256** bytes back, length 2..5; the
  offset is a single byte (`0xFF00 | byte`).
- **Long match** — offset and length are packed into one 16-bit word using
  the `c1` shift parameter, allowing much longer back-references; if the
  resulting length field is 0, an extra length byte follows, and a zero
  length byte there marks **end of stream**.

A complete working implementation lives in `sqx_codec.py` (decoder) and
`sqx_encoder.py` (encoder), both a direct, debugger-verified port of the
real game's behaviour.

## 2. DECORn.CDG — level tile map

- Decompressed size: **20000 bytes** = `400 × 50` (width × height in tiles).
- One byte per cell = tile index (0..255).
- **Layout is COLUMN-MAJOR**, not row-major!
  `index = col * 50 + row`, i.e. all 50 rows of the first column, then all
  50 rows of the second column, etc. (confirmed against `game.c`/
  `op_logic.c`: `offset = (x >> 4) * _screen_cdg_tile_map_h + ...`, where
  `_screen_cdg_tile_map_h = 50`).
- Each tile is `16×16` px → the full level image is `6400 × 800` px.

## 3. DECORn.BLK — tile graphics

- Decompressed size: **32768 bytes** = 256 tiles × 128 bytes/tile.
- Each tile is `16×16` pixels, 4 bits/pixel (16 colors), **planar** format
  (separate bitplanes), same as Amiga/EGA.
- Per-tile byte layout (`decode_bitplane_tile` in `systemstub_sdl.c`): for
  each of the 16 rows, 8 bytes are read — 4 planes for the left half of the
  row (8 px) then 4 planes for the right half (8 px), interleaved as:
  `P0_left, P0_right, P1_left, P1_right, P2_left, P2_right, P3_left, P3_right`.
  Pixel value = bit from plane `p` (0..3) shifted by `p`; bits are read
  MSB-first within each byte.

## 4. DECORn.PAL — palette (16 colors)

- 16 colors × 2 bytes (big-endian), Amiga 12-bit RGB format:
  `r = (word>>8)&0xF, g=(word>>4)&0xF, b=word&0xF`, then each channel is
  duplicated into the low nibble (`r | r<<4`) to get an 8-bit channel.
- **We don't have this file** — the `decode_nicky_level.py` pipeline
  reconstructs it via median color sampling from the reference screenshot
  (if available), otherwise falls back to a grayscale ramp. If a real
  `DECOR1.PAL` is supplied, it's decoded directly (see
  `palette_from_pal_file`).

## 5. DECORn.REF — tile attributes

- Decompressed size: **2048 bytes** = 256 tiles × 8 bytes/record.
- Indexed as `res_decor_ref[tile_id * 8 + N]`.
- Byte 0 — bit flags (at least bit `0x01` = solid tile/collision, bits
  `0x10`/`0x20` = special swap/animation behaviour).
- Bytes 5/6 — alternate tile id (used when the tile animates/swaps at
  runtime, e.g. breakable blocks).
- Remaining bytes drive less obvious effects (see `game.c` around lines
  2160-2185, 2980-3005).

## 6. POSITn.REF — monster/item placement

- Record size: **10 bytes**; the list ends with a record whose first
  16-bit word has the high bit set (`0x8000` or above, in practice
  `0xFFFF`). Coordinates before the terminator are in pixels, in the same
  coordinate system as the whole map (0..6399 on X, 0..799 on Y).
- Confirmed via `game_init_objects_from_positref()` in `game.c`: the first
  field (`num`) is a **direct index** into the `res_ref_ref` array (the
  `REFn.REF` table), i.e. `anim_data = res_ref_ref[num]`.
- `(map_x, map_y)` are passed straight through as the **top-left corner**
  of the sprite at draw time (`draw_sprite`), not the center.

```
offset    type       field
0         u16 LE     num (anim_num)  — index into REFn.REF (object type)
2         u16 LE     map_x           — X position, pixels (0..6399)
4         u16 LE     map_y           — Y position, pixels (0..799)
6         u16 LE     ref_ref_index   — separate secondary reference into REFn.REF
8         u8         visible
9         u8         tile_num
```

### ⚠️ Hard constraint #1: records must be sorted by ascending map_x

`game_update_cur_objects_ptr()` in `game.c` determines which objects are
currently on screen using a **sliding window**: it advances a pointer
through the object array until `map_pos_x` falls within
`[camera_x − 280, camera_x + screen_width + 280]`, and stops as soon as
`map_pos_x` exceeds the right edge. This optimization **requires** that
objects in the file are strictly sorted by ascending `map_x` — if the order
is broken (e.g. an object was dragged in the editor without re-sorting the
list), the sliding window "skips past" it, and the object stops being
rendered/processed even though it's technically still present in the file.
**The editor sorts objects by X automatically on export** — you don't need
to worry about this manually, but keep it in mind if you edit the file by
other means.

### ⚠️ Hard constraint #2: fixed object count limit

In `game_init_level()` (`game.c`, NICKY1 branch) the regular-object buffer
boundary is `objects_table_ptr2 = &objects_table[410]`, and
`game_init_objects_from_positref()` checks
`assert(os < objects_table_ptr2)`. This means **a maximum of 409 objects +
1 terminator = 410 slots**. Level 1 already uses exactly 409 objects — the
buffer is completely full, and adding even one more object overruns this
specific buffer and clobbers adjacent engine memory (reserved for bullets/
other purposes) — hence vanishing objects, graphical glitches, and
instability when adding new objects. Removing and moving/editing existing
objects is safe. **This is a separate, genuinely hard-coded limit in the
game's own memory layout — unrelated to file compression, and not fixable
through data files alone (would require patching the executable).**

## 7. REFn.REF — monster/item "type" table

- Record size: **0x44 = 68 bytes** (`anim_data_t`, see `load_ref_ref__v1`
  in `resource.c`). For level 1: `16728 / 68 = 246` records. This is a
  table of TEMPLATES/types (stats), NOT placement — placement comes from
  `POSITn.REF`, which references an index into this table.

```
offset    type       field
0         int8       unk0            (used as the "displayed" flag)
1         int8       lifes
2         int8       cycles
3         int8       unk3
4-6       u8 x3      unk4, unk5, unk6
7         u8         init_sprite_num — frame index into .SPR for preview/initial look
8         u8         colliding_opcode — collision behaviour type
9         u8         logic_opcode     — logic/AI type
10        int8       sound_num
11        u8         rnd
12-13     u16 LE      sprite_num
14-15     u16 LE      sprite_flags     (0x80 usually means "level" sprite, not "monster")
16-17     u16 LE      default_sprite_num
18-19     u16 LE      default_sprite_flags
20-21     u16 LE      anim_w
22-23     u16 LE      anim_h
24-25     u16 LE      score            — points awarded for the object
26-27     u16 LE      bounding_box_x1
28-29     u16 LE      bounding_box_x2
30-31     u16 LE      bounding_box_y1
32-33     u16 LE      bounding_box_y2
34-35     u16 LE      move (index into the movement table), 36-37 padding (2 bytes)
38-39     u16 LE      distance_dx
40-41     u16 LE      distance_dy
42-43     u16 LE      anim_data1 (index), 44-45 padding
46-47     u16 LE      anim_data2 (index), 48-49 padding
50-51     u16 LE      anim_data3 (index), 52-53 padding
54-55     u16 LE      dx
56-57     u16 LE      dy
58-59     u16 LE      anim_data4 (index), 60-61 padding
62-63     u16 LE      dx2
64-65     u16 LE      dy2
66-67     —           padding (Nicky 2-only fields, unused in v1)
```

## 8. S0n.SPR / S1n.SPR / NICKY.SPR — sprites (monster/item/Nicky graphics)

Format confirmed via `display_sprite_list()` / `draw_sprite()` /
`sys_get_sprite_dim()` in `systemstub_sdl.c`:

- The file starts with an **offset table** — an array of `u16 LE`, one
  entry per sprite number (`sprite_num`/`init_sprite_num` from `REFn.REF`
  indexes straight into this table). The value is an offset (from the
  start of the file) to that frame's data. The table's size is derived as
  the minimum of the offsets themselves (frame data starts right after the
  table).
- At each frame's offset: `u16 LE width`, `u16 LE height`, then pixels in
  the same 4bpp planar format as tiles (`DECORn.BLK`): per row,
  `ceil(width/8)` groups of 4 bytes (one byte per bitplane), 8 pixels per
  group, bits MSB→LSB.
- Color `0` is the sprite's background/transparency (not drawn on screen).
- Uses ONE of TWO sprite palettes (`sys_set_palette_spr(...,1)`) — not
  necessarily the same as the level's tile palette.

## 9. The encoder (sqx_encoder.py / embedded in nicky_level_editor.html)

A round-trip-safe encoder was needed for the level editor's save feature —
it must produce bytes that the real game's `sqx_decode` turns back into
exactly the intended data.

**Main difficulty:** the decoder reads 16-bit control words "lazily" — in
full, the moment their first bit is needed — then hands out bits one at a
time, interleaved with direct reads of data bytes (literals/offsets/
lengths) from that same stream. So a control word's position in the output
file is determined by *when its first bit was first needed*, not by when
the encoder happened to accumulate all 16 of its bits (which can come from
several different operations).

Solution — a two-pass assembly:

1. **Pass 1.** Walk the operation list (literal / short match / long match
   / terminator) in order; for each, generate its control bits (operation
   choice per the header's `j1,j2,j3` permutation, plus internal length
   bits if needed) and data bytes. Accumulate one flat list of all control
   bits, plus a list of `(end_index_in_flat_list, [data_bytes])` per
   operation.
2. **Pass 2.** Slice the flat bit list into 16-bit words — these are the
   stream's actual control words. Then, for each operation in order: first
   emit any not-yet-emitted control words whose bits it needs
   (`word_index*16 < operation_end`), then emit its data bytes. This
   reproduces exactly the moment the decoder would have loaded that word.

Supports literal, short-match and long-match operations (full LZ77, window
up to 8192 bytes back, length 3..257 bytes, overlapping copies allowed —
the real loop appears to use blocked/overlapping copies too, and this is
**not** an issue once the buffer-offset fix from section 1 is applied).

**Verified byte-for-byte round trip** on all 5 level-1 files (BLK/CDG/REF/
POSIT/animation REF) — compress+decompress reproduces the original data
exactly, with compression close to the original packer's ratio:

| File       | Size  | Our compressed | Original compressed |
|------------|-------|----------------:|----------------------:|
| DECOR1.BLK | 32768 | ~25-26K (≈0.78-0.80) | 25040 (0.764) |
| DECOR1.CDG | 20000 | ~9.6-9.7K (≈0.48-0.49) | 9032 (0.452) |
| DECOR1.REF | 2048  | ~190 (≈0.09)    | 163 (0.080)   |
| POSIT1.REF | 4100  | ~2.3-2.4K (≈0.56-0.58) | 2184 (0.533) |
| REF1.REF   | 16728 | ~3.3K (≈0.20)   | 2839 (0.170)  |

Also verified the full edit cycle "tile edit → rebuild .CDG → load →
render": after recompression the decoder reconstructs the edited data
byte-for-byte, and the rendered level shows the edit in the right place —
**in the real game**, not just in our own decoder, now that the buffer
offset (section 1) is computed correctly.

Implementations: `sqx_encoder.py` (Python) and the embedded JS port in
`nicky_level_editor.html` — both kept in sync and produce byte-identical
output on the same input (cross-checked in Node.js).

## Sources

- `nicky-0.2.0-src.zip` — Gregory Montoir (cyx), engine reimplementation of
  Nicky Boum/Nicky 2; files `sqx_decoder.c`, `fileio_std.c`, `resource.c`,
  `systemstub_sdl.c`, `game.c`, `op_logic.c`.
- Independent UPX unpacking + disassembly of the real `NICKY.EXE` (original
  1992 DOS executable) — used to confirm the format against the actual
  game code, including the buffer-offset mechanism in section 1, which the
  cyx reimplementation doesn't need to replicate (it isn't a real-mode DOS
  program with a fixed-size buffer constraint).
- Reference screenshot of level 1: `964_map0.png` (Hall of Light,
  hol.abime.net/964).
