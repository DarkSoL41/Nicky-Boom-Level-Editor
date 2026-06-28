# Nicky Boom // Level Editor — User Manual

*An unofficial level editor for **Nicky Boom** (Microids, DOS, 1992)*

**Version 1.1** · Created by **DarkSoL** (Discord: `darksol41`) · Engine reverse-engineering based on Gregory Montoir's **cyx** reimplementation (`nicky-0.2.0-src`), plus independent disassembly of the original `NICKY.EXE` · Built with the help of the Claude AI (Anthropic)
> If you’d like to support me financially, BTC address: bc1qp476rmcaapl6n6xjvg2la50cfw3kwvxe8sj0m5
---

## What is this?

This is a browser-based editor for **Nicky Boom**'s level files. It lets you:

- Repaint the tile map of any level (`DECORn.CDG` / `DECORn.BLK`)
- Move, edit, add, and delete monsters/items (`POSITn.REF` / `REFn.REF`)
- Preview real in-game sprites for objects (`S0n.SPR` / `S1n.SPR`)
- Export edited files that load back into the **real, original DOS game** running in DOSBox — with full, real compression, correct music/sound, and no hangs

It's a single `.html` file. No installation, no server, no account — just open it in a modern browser (Chrome, Edge, or Firefox recommended).

> ⚠️ This tool only **edits existing level files** extracted from a legally owned copy of the game. It does not include any game files or assets.

---

## 1. Requirements

| You need | Why |
|---|---|
| A modern desktop browser | Chrome / Edge work best (folder picker support) |
| A copy of *Nicky Boom* (DOS) | To get the original level files |
| DOSBox (or similar) | To actually run the game and test your edits |

### Files the editor looks for

The editor reads the game's own data files directly — nothing needs to be converted first.

| File | Contains | Required? |
|---|---|---|
| `DECORn.CDG` | Tile map of the level | **Required** |
| `DECORn.BLK` | Tile graphics (16×16px) | **Required** |
| `DECORn.REF` | Tile attributes (collision, etc.) | Optional |
| `POSITn.REF` | Monster/item placement | Optional (needed for "Objects" mode) |
| `REFn.REF` | Monster/item *type* definitions | Optional (needed for "Objects" mode) |
| `S0n.SPR` / `S1n.SPR` | Item/monster sprite graphics | Optional (needed for picture previews) |

`n` is the level number (`1`–`4`), with a `1A`/`2A`/`3A`/`4A` variant for boss areas.

There is **no `DECOR.PAL`** in the original game — the colour palette is always reconstructed automatically.

---

## 2. Quick Start

1. Open `nicky_level_editor.html` in your browser.
2. Click **OPEN GAME FOLDER** and select the folder containing your extracted game files. Your browser may show a system warning about access to "all files in the folder" — that's normal directory-picker behaviour, nothing is ever uploaded anywhere; the editor only reads the specific level files it needs and ignores everything else.
3. Level 1 loads automatically. Use the **Level** dropdown (top left) to switch between levels, including boss (`A`) variants.
4. Edit the map (see below), then click **Export .CDG** / **Export POSIT.REF** to download your changed file(s).
5. Copy the exported file(s) back into your DOSBox game folder (overwrite the original) and launch the game to test.

If you only have some of the files, you can also use **OR PICK FILES MANUALLY** to load whatever you have — the level/folder workflow is just a convenience layer on top of that.

The interface is available in **English, Russian, Spanish, Chinese, French, German, and Portuguese** — pick your language from the dropdown in the top-right corner.

---

## 3. Editing tiles

This is the default mode (**Tiles** tab, top-left of the canvas panel).

- **Brush (left-click)** — click a tile in the left palette, then left-click/drag on the map to paint it.
- **Eraser (right-click)** — right-click/drag on the map to erase, painting tile `0` ("sky"). The browser's right-click context menu is suppressed on the map so this works smoothly.
- **Eyedropper** — pick a tile directly from the map (auto-switches back to Brush).
- **Undo** — `Ctrl+Z` or the Undo button (multi-level undo).
- **Grid** — toggle a 16×16 alignment grid over the map.
- **Collisions** — overlay showing which tiles are solid (from `DECORn.REF`).
- **Zoom** — slider in the toolbar; the map is large (6400×800px), so zooming out helps for an overview.

---

## 4. Editing objects (monsters & items)

Switch to the **Objects** tab (needs `POSITn.REF` + `REFn.REF` loaded; sprite files are optional but give you real picture previews instead of plain markers).

- The left panel lists every **object type** defined for the level, with a thumbnail (if sprites are loaded) and its score/lifes stats.
- Existing objects appear as markers directly on the map, positioned exactly like the game renders them.
- **Click** a marker to select it — an inspector panel appears (type, X/Y, `tile_num`, `ref_ref_index`, and the `Visible` flag).
- **Drag** a marker to reposition it.
- **Click an empty spot** on the map while a type is selected in the left panel to place a **new** object there — but read the warning below first. New objects default to **`Visible` unchecked**, matching how most regular objects/monsters are set up in the original levels.
- **Delete object** button removes the selected object.

### What does "Visible" actually mean?

Despite the name, this flag does **not** control whether the object is shown on screen. It controls what happens **after the object is destroyed/collected** — for example, whether a breakable block reveals something inside, and/or plays a sound. Most ordinary decorative objects normally have this **off** — that's expected, not a bug, and is now also the editor's default for newly placed objects.

---

## 5. Exporting

Two export buttons, one per file type. Both rebuild the file using the game's native **sqx** compression format — with **real, full LZ compression** (not a literal-only fallback), producing files close to the original's size (roughly 9-11 KB for a typical `DECORn.CDG`, instead of ~20-25 KB).

You don't need to touch any settings — just click **Export .CDG** / **Export POSIT.REF**. The editor automatically:

- compresses your edited data with real LZ matching,
- keeps the file's native header byte order (`j1,j2,j3,c1`) as loaded,
- recalculates the file's internal buffer-placement offset (the first 2 bytes) to match the exact size of the newly compressed data — this is the fix that makes real compression safe (see the limitations section below for the short version, or `NICKY_FORMAT.md` for the full technical story).

The green **"✓ Full compression (fixed)"** badge in the toolbar is just a reminder that this fix is active — there's nothing to toggle.

---

## 6. ⚠️ Engine limitations — please read before editing

This game's 1992 engine has a couple of hard, hardware-era constraints that **the editor cannot work around**, found through extensive reverse-engineering (including disassembling the original `.EXE`) and real in-game testing.

| Limitation | Details | Safe? |
|---|---|---|
| **`POSITn.REF` has a hard object-count ceiling** | The game pre-allocates a fixed-size object table. Level 1, for example, is already using all 409 of 409 available slots. **Adding new objects beyond the original count risks corrupting nearby memory** (missing objects, graphical glitches, instability) — this is a hard-coded limit in the game's own memory layout, unrelated to the file format. | Editing, moving, and **deleting** existing objects is always safe |
| **Objects must be sorted by X position** | The engine uses a sliding-window scan across the object list, assuming ascending X order, to decide what's currently visible. The editor **automatically re-sorts by X on export** — you don't need to do anything, just don't bypass the export function. | Handled automatically |

That's it — that's the whole list. Earlier versions of this editor had several other "limitations" here (no real compression allowed, header order had to match exactly, exported `.CDG` files were stuck at ~25KB with occasional music corruption). **All of those have been root-caused and fixed in v1.1** — the actual problem was a buffer-placement offset (the file's first 2 bytes) that needs recalculating after every edit, not a fundamental restriction of the format. See `NICKY_FORMAT.md` if you're curious about the technical details.

---

## 7. Troubleshooting

- **"Open game folder" does nothing.** Make sure you're using a Chromium-based browser (Chrome/Edge); folder selection support varies in other browsers.
- **My browser warns about giving access to all files in the folder.** That's a standard browser security notice for picking a whole directory, not specific to this editor — no data is ever uploaded anywhere, everything runs locally in your browser, and the editor only reads the specific level files it needs.
- **A level won't load / files missing.** The editor tells you exactly which filename it expected and couldn't find (check the browser console, or just look at which slot indicators stayed unfilled at the top).
- **An object has no picture, just a `#123` label.** That object type has no static sprite assigned in the game data (`sprite_num = 0`) — this is normal for some types, not a bug.
- **Export warns me about object count.** You've added more objects than the original file had — see the limitations table above. Safe options: don't add new objects, or repurpose/move an existing one instead of creating a new one.
- **Export warns that the compressed body is bigger than the decompressed size.** This can only happen on extremely "random"/noisy maps where real compression can't beat 1:1. Simplify the map (more repeated/uniform tile patterns) and try again.

---

## Credits

- **Editor & reverse-engineering:** DarkSoL (Discord: `darksol41`)
- **Engine reimplementation reference:** Gregory Montoir — [`cyx`](https://github.com/cyxx) (`nicky-0.2.0-src`)
- **Built with the assistance of:** Claude (Anthropic)
- **Original game:** *Nicky Boom*, © Microids, 1992

This is an unofficial, fan-made tool for editing your own legally owned copy of the game. Not affiliated with Microids.
