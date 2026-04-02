import logging
import re
import shutil
from pathlib import Path

import mobase

# Characters that are illegal in Windows directory names
_ILLEGAL_CHARS = re.compile(r'[\\/:*?"<>|]')

_log = logging.getLogger("starfield_creations")


def scan_creations(organizer: mobase.IOrganizer) -> list[dict]:
    """
    Returns a list of unmanaged Creations that have not yet been moved into
    an MO2 mod folder.

    Searches both the game Data directory (via MO2's UnmanagedMods API) and
    the MO2 Overwrite directory (for Creations downloaded while launching
    the game through MO2).

    Each entry: {
        "display_name": str,  # human-readable name from ContentCatalog
        "files": [Path],      # existing file paths on disk (esm/esl + ba2s)
    }
    """
    unmanaged = organizer.gameFeatures().gameFeature(mobase.UnmanagedMods)
    if unmanaged is None:
        _log.warning("Starfield Creations Organizer: UnmanagedMods feature not available")
        return []

    mods_path = Path(organizer.modsPath())
    overwrite_path = Path(organizer.overwritePath())

    # CCPlugins() is built from ContentCatalog.txt — the authoritative list of
    # actual Creations. DLC (Constellation, Shattered Space) are hardcoded in
    # primaryPlugins()/DLCPlugins() and are NOT present here.
    cc_filenames = organizer.managedGame().CCPlugins()
    _log.debug(f"Starfield Creations Organizer: CCPlugins() returned {len(cc_filenames)} entries")

    cc_plugin_names = [Path(p).stem for p in cc_filenames]

    # Build a display name lookup and initialise the merged dict up front so
    # overwrite files can be added even if referenceFile() finds nothing.
    plugin_display: dict[str, str] = {}
    merged: dict[str, dict] = {}

    for plugin_name in cc_plugin_names:
        display_name = unmanaged.displayName(plugin_name)
        plugin_display[plugin_name] = display_name
        # Pre-create entry so overwrite scan can populate it even when
        # the game Data directory has no files for this creation.
        if display_name not in merged:
            merged[display_name] = {
                "display_name": display_name,
                "files": [],
                "_seen": set(),
            }

    # --- Pass 1: game Data directory via UnmanagedMods API ---
    for plugin_name, display_name in plugin_display.items():
        ref = unmanaged.referenceFile(plugin_name)
        secondary = unmanaged.secondaryFiles(plugin_name)

        raw_paths = [ref] + list(secondary)

        # is_file() rejects directories and non-existent paths (handles the
        # case where referenceFile() returns '.' for undownloaded creations).
        files = [Path(p) for p in raw_paths if p and Path(p).is_file()]

        # Exclude files already inside the MO2 mods directory
        files = [f for f in files if not _is_under(f, mods_path)]

        if files:
            _log.debug(f"Starfield Creations Organizer: API found {len(files)} file(s) for '{display_name}'")

        entry = merged[display_name]
        for f in files:
            if f.name not in entry["_seen"]:
                entry["files"].append(f)
                entry["_seen"].add(f.name)

    # --- Pass 2: MO2 Overwrite directory ---
    # When the game is launched through MO2, Creations downloaded in-session
    # land in Overwrite rather than the game's Data directory.
    # The UnmanagedMods API may not cover this location, so we scan it directly.
    overwrite_files = _scan_overwrite(overwrite_path, cc_plugin_names)

    for plugin_name, ow_files in overwrite_files.items():
        display_name = plugin_display[plugin_name]
        entry = merged[display_name]
        added = 0
        for f in ow_files:
            if not _is_under(f, mods_path) and f.name not in entry["_seen"]:
                entry["files"].append(f)
                entry["_seen"].add(f.name)
                added += 1
        if added:
            _log.debug(f"Starfield Creations Organizer: Overwrite found {added} file(s) for '{display_name}'")

    # Remove entries with no files (owned but not downloaded)
    empty = [dn for dn, e in merged.items() if not e["files"]]
    for dn in empty:
        _log.debug(f"Starfield Creations Organizer: skipping '{dn}' — no files found on disk")
        del merged[dn]

    # Strip internal tracking sets before returning
    for entry in merged.values():
        del entry["_seen"]

    _log.info(f"Starfield Creations Organizer: found {len(merged)} Creation(s) to organise")
    return list(merged.values())


def organize_creations(
    organizer: mobase.IOrganizer,
    creations: list[dict],
    prefix: str,
    suffix: str,
) -> int:
    """
    Moves each Creation's files into a new MO2-managed mod folder.
    Returns the number of mods successfully created.
    """
    created = 0

    for creation in creations:
        display_name = creation["display_name"]
        files = creation["files"]

        safe_name = _ILLEGAL_CHARS.sub("-", display_name).strip()
        mod_name = f"{prefix}{safe_name}{suffix}"

        _log.info(f"Starfield Creations Organizer: organising '{display_name}' → '{mod_name}'")

        guessed = mobase.GuessedString(mod_name, mobase.GuessQuality.USER)
        mod = organizer.createMod(guessed)
        if mod is None:
            _log.warning(f"Starfield Creations Organizer: createMod() returned None for '{mod_name}' — skipping")
            continue

        mod_path = Path(mod.absolutePath())
        moved = 0

        for src in files:
            if not src.is_file():
                _log.warning(f"Starfield Creations Organizer: source no longer a file, skipping: {src}")
                continue

            dest = mod_path / src.name

            if dest.exists():
                _log.warning(f"Starfield Creations Organizer: destination already exists, skipping: {dest}")
                continue

            try:
                shutil.move(str(src), str(dest))
                _log.debug(f"Starfield Creations Organizer: moved {src.name}")
                moved += 1
            except Exception as e:
                _log.error(f"Starfield Creations Organizer: failed to move {src.name}: {e}")

        _log.info(f"Starfield Creations Organizer: '{mod_name}' — {moved}/{len(files)} file(s) moved")
        created += 1

    if created > 0:
        organizer.refresh()

    return created


def _scan_overwrite(overwrite_path: Path, cc_plugin_names: list[str]) -> dict[str, list[Path]]:
    """
    Scans the MO2 Overwrite directory for Creation files.

    Bethesda Creation filenames follow the convention:
      <plugin_name>.esm / .esl / .esp
      <plugin_name> - <descriptor>.ba2

    Returns a dict mapping plugin_name → list[Path].
    """
    result: dict[str, list[Path]] = {}

    if not overwrite_path.is_dir():
        return result

    # Build a lower-case lookup for fast matching
    lower_names = {n.lower(): n for n in cc_plugin_names}

    for f in overwrite_path.rglob("*"):
        if not f.is_file():
            continue

        stem = f.stem.lower()

        # Exact match covers .esm/.esl/.esp plugin files
        if stem in lower_names:
            plugin_name = lower_names[stem]
            result.setdefault(plugin_name, []).append(f)
            continue

        # Prefix match covers BA2 archives: "<plugin> - Main.ba2" etc.
        # Require the next character to be a space to avoid false matches
        # between e.g. "ccbgsfe001-foo" and "ccbgsfe001-foobar".
        for lower_name, plugin_name in lower_names.items():
            if stem.startswith(lower_name + " "):
                result.setdefault(plugin_name, []).append(f)
                break

    if result:
        total = sum(len(v) for v in result.values())
        _log.info(f"Starfield Creations Organizer: Overwrite scan found {total} file(s) across {len(result)} Creation(s)")
    else:
        _log.debug("Starfield Creations Organizer: Overwrite scan found no Creation files")

    return result


def _is_under(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False
