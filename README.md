# Nicky Boom // Level Editor — User Manual

*An unofficial level editor for **Nicky Boom** (Microids, DOS, 1992)*

**Version 1.0** · Created by **DarkSoL** (Discord: `darksol41`) · Engine reverse-engineering based on Gregory Montoir's **cyx** reimplementation (`nicky-0.2.0-src`) · Built with the help of the Claude AI (Anthropic)
> If you’d like to support me financially, BTC address: bc1qp476rmcaapl6n6xjvg2la50cfw3kwvxe8sj0m5
---

## What is this?

This is a browser-based editor for **Nicky Boom**'s level files. It lets you:

- Repaint the tile map of any level (`DECORn.CDG` / `DECORn.BLK`)
- Move, edit, add, and delete monsters/items (`POSITn.REF` / `REFn.REF`)
- Preview real in-game sprites for objects (`S0n.SPR` / `S1n.SPR`)
- Export edited files that load back into the **real, original DOS game** running in DOSBox

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
2. Click **OPEN GAME FOLDER** and select the folder containing your extracted game files.
3. Level 1 loads automatically. Use the **Level** dropdown (top left) to switch between levels, including boss (`A`) variants.
4. Edit the map (see below), then click **Export .CDG** / **Export POSIT.REF** to download your changed file(s).
5. Copy the exported file(s) back into your DOSBox game folder (overwrite the original) and launch the game to test.

If you only have some of the files, you can also use **OR PICK FILES MANUALLY** to load whatever you have — the level/folder workflow is just a convenience layer on top of that.

The interface is available in **English, Russian, Spanish, Chinese, French, German, and Portuguese** — pick your language from the dropdown in the top-right corner.

---

## 3. Editing tiles

This is the default mode (**Tiles** tab, top-left of the canvas panel).

- **Brush** — click a tile in the left palette, then click/drag on the map to paint it.
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
- **Click an empty spot** on the map while a type is selected in the left panel to place a **new** object there — but read the warning below first.
- **Delete object** button removes the selected object.

### What does "Visible" actually mean?

Despite the name, this flag does **not** control whether the object is shown on screen. It controls what happens **after the object is destroyed/collected** — for example, whether a breakable block reveals something inside, and/or plays a sound. Most ordinary decorative objects normally have this **off** — that's expected, not a bug.

---

## 5. Exporting

Two export buttons, one per file type. Both rebuild the file using the game's native **sqx** compression format.

**"No compression (safe mode)"** is checked by default — **leave it checked.** See the warnings below for why.

---

## 6. ⚠️ Engine limitations — please read before editing

This game's 1992 engine has some hard, hardware-era constraints that **the editor cannot work around**. They were found through extensive reverse-engineering (including disassembling the original `.EXE`) and real in-game testing. Ignoring them *will* cause crashes, glitches, or broken audio.

| Limitation | Details | Safe? |
|---|---|---|
| **No real compression** | Any genuine LZ match (even a single one) in a `sqx`-compressed file makes the real game hang or render garbage. The editor always falls back to literal-only encoding — bigger files, but the only mode confirmed to work. | Editor handles this automatically |
| **Header permutation must match the original** | Each file's internal byte-order header (`j1,j2,j3,c1`) must stay exactly as the original file had it. Changing it — even with zero compression — has been observed to crash the game. | Editor always preserves the original header |
| **`POSITn.REF` has a hard object-count ceiling** | The game pre-allocates a fixed-size object table. Level 1, for example, is already using all 409 of 409 available slots. **Adding new objects beyond the original count risks corrupting nearby memory** (missing objects, graphical glitches, instability). | Editing, moving, and **deleting** existing objects is always safe |
| **Objects must be sorted by X position** | The engine uses a sliding-window scan across the object list, assuming ascending X order, to decide what's currently visible. The editor **automatically re-sorts by X on export** — you don't need to do anything, just don't bypass the export function. | Handled automatically |
| **Exported `.CDG` files end up larger than the original** (~25KB vs. ~9KB, since compression is unsafe) | This size increase has been linked to a still-unsolved, intermittent **music corruption** issue in some setups (wrong notes, or music going silent) after loading an edited level. Visuals and gameplay are *not* affected — only audio. Increasing DOSBox's memory did **not** fix it in our testing. | Unresolved — see note below |

> **About the music issue:** we have not found a complete fix yet. If you run into it, the level itself remains fully playable — only the music is affected. If you discover something that helps (or makes it worse), feedback is very welcome.

---

## 7. Troubleshooting

- **"Open game folder" does nothing.** Make sure you're using a Chromium-based browser (Chrome/Edge); folder selection support varies in other browsers.
- **A level won't load / files missing.** The editor tells you exactly which filename it expected and couldn't find (check the browser console, or just look at which slot indicators stayed unfilled at the top).
- **An object has no picture, just a `#123` label.** That object type has no static sprite assigned in the game data (`sprite_num = 0`) — this is normal for some types, not a bug.
- **Export warns me about object count.** You've added more objects than the original file had — see the limitations table above. Safe options: don't add new objects, or repurpose/move an existing one instead of creating a new one.

---

## Credits

- **Editor & reverse-engineering:** DarkSoL (Discord: `darksol41`)
- **Engine reimplementation reference:** Gregory Montoir — [`cyx`](https://github.com/cyxx) (`nicky-0.2.0-src`)
- **Built with the assistance of:** Claude (Anthropic)
- **Original game:** *Nicky Boom*, © Microids, 1992

This is an unofficial, fan-made tool for editing your own legally owned copy of the game. Not affiliated with Microids.
