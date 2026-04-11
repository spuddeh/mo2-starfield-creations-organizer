# Starfield Creations Organizer

**Note:** This plugin was built with assistance from an LLM (Claude). The code has been reviewed and tested, but keep that in mind.

An MO2 plugin that moves your installed Starfield Creations into individual MO2-managed mod folders, so you can enable, disable, and prioritise them like any other mod.

## The Problem

Creations are downloaded from inside the game and their files land in one of two places:

- The game's `Data/` directory, if you launched Starfield outside of MO2
- MO2's **Overwrite** folder, if you launched through MO2

Either way they show up as unmanaged "Non-MO" entries in the modlist. You can't toggle them, set priorities, or manage them properly. On top of that, some Creations (like Trackers Alliance) ship as multiple plugin files and show up as duplicate entries.

## What it does

The plugin uses the Creation data MO2 already has from `ContentCatalog.txt`. No Bethesda API needed. It scans both the game Data directory and the Overwrite folder, then moves each Creation's files into its own MO2 mod folder. Creations with multiple plugin files get merged into a single folder.

## Requirements

- Mod Organizer 2 **2.5.x** or later
- Starfield game support (`game_starfield.dll`), included with MO2

## Installation

Copy the `starfield_creations/` folder into your MO2 `plugins/` directory:

```
<MO2 install>\plugins\starfield_creations\
```

Restart MO2. The tool will appear in the **Tools** menu.

## Usage

1. Open **Tools > Starfield Creations Organizer**
2. Set a **Prefix** and/or **Suffix** if you want (default prefix is `[Creations]` followed by a space)
3. Uncheck anything you want to skip
4. Click **Organize**

MO2 will refresh and your Creations will show up as normal managed mods.

## Notes

- **Files are moved, not copied.** The originals are removed from the Data directory or Overwrite folder. MO2 handles linking them back when you launch the game through it. If you launch Starfield directly outside of MO2, those Creations won't load.
- **Safe to re-run.** Creations already in an MO2 mod folder are skipped automatically.
- **Creations you own but haven't downloaded** won't appear in the list.
- **DLC is excluded.** Shattered Space and Constellation are treated as DLC by MO2 and won't show up.
- Prefix/Suffix settings are saved between sessions.

## Compatibility

- No Bethesda API calls
- Works alongside Root Builder (files go in the mod root, not a `Root/` subfolder)
- Tested on MO2 2.5.2, 2.5.3beta2, and 2.5.3beta3

## License

MIT
