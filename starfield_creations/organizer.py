import json
import logging
import os
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

    Compatible with MO2 2.5.2 through 2.5.3beta4+. The UnmanagedMods API
    changed in beta4 — mods() now returns human-readable Title names instead
    of raw plugin filenames, and referenceFile()/secondaryFiles() now take
    Title names as input. We use CCPlugins() as a stem-based whitelist to
    filter out DLC/base game entries, which works across all versions.

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

    # CCPlugins() returns plugin filenames for all ContentCatalog entries
    # across all MO2 versions. Used as a whitelist to exclude DLC/base game
    # entries that also appear in mods().
    cc_filenames = organizer.managedGame().CCPlugins()
    cc_stems = {Path(f).stem.lower() for f in cc_filenames}
    _log.debug(f"Starfield Creations Organizer: CCPlugins() returned {len(cc_filenames)} entries")

    # mods(False) returns all unmanaged mod names. In beta4+ these are
    # human-readable Title names from ContentCatalog; in earlier versions
    # they are raw plugin filename stems.
    all_names = unmanaged.mods(False)
    _log.debug(f"Starfield Creations Organizer: mods() returned {len(all_names)} entries")

    merged: dict[str, dict] = {}

    # Pre-populate stem->display_name from ContentCatalog.txt so the overwrite
    # scan can attribute files even when referenceFile() finds nothing.
    stem_to_display: dict[str, str] = _stem_map_from_catalog(organizer)

    for name in all_names:
        display_name = unmanaged.displayName(name)

        # referenceFile() returns a QFileInfo object, not a string.
        # Call .absoluteFilePath() to get the actual path.
        ref_info = unmanaged.referenceFile(name)
        ref_str = ref_info.absoluteFilePath() if ref_info else ""
        ref_path = Path(ref_str) if ref_str else None

        # secondaryFiles() returns bare filenames from ContentCatalog when the
        # mod is in the catalog (e.g. "sfta01 - Main.ba2"), or full paths via
        # the directory-scan fallback for non-catalog entries.
        secondary = unmanaged.secondaryFiles(name)

        # Filter out DLC/base game: ref_path stem must be a known CC plugin.
        if ref_path and ref_path.stem.lower() not in cc_stems:
            _log.debug(f"Starfield Creations Organizer: skipping '{display_name}' — not in CCPlugins (DLC/base game)")
            continue

        # Derive the search directory from the reference file's location.
        # This handles multiple data directories (game install vs documents)
        # without needing to enumerate them explicitly.
        search_dirs: list[Path] = []
        if ref_path and ref_path.is_file():
            search_dirs.append(ref_path.parent)
        search_dirs.append(overwrite_path)

        files: list[Path] = []
        seen: set[str] = set()

        # Add reference file first
        if ref_path and ref_path.is_file() and not _is_under(ref_path, mods_path):
            files.append(ref_path)
            seen.add(ref_path.name.lower())

        for p in secondary:
            if not p:
                continue
            path = Path(p)
            if path.is_absolute():
                # Non-catalog fallback already gives full paths
                if path.is_file() and not _is_under(path, mods_path) and path.name.lower() not in seen:
                    files.append(path)
                    seen.add(path.name.lower())
            else:
                # Bare filename — search the reference file's directory then overwrite
                for search_dir in search_dirs:
                    candidate = search_dir / path.name
                    if candidate.is_file() and not _is_under(candidate, mods_path):
                        if candidate.name.lower() not in seen:
                            files.append(candidate)
                            seen.add(candidate.name.lower())
                        break

            stem_to_display[path.stem.lower()] = display_name

        if not files:
            _log.debug(f"Starfield Creations Organizer: no Data files for '{display_name}'")

        if display_name not in merged:
            merged[display_name] = {
                "display_name": display_name,
                "files": [],
                "_seen": set(),
            }

        entry = merged[display_name]
        for f in files:
            if f.name not in entry["_seen"]:
                entry["files"].append(f)
                entry["_seen"].add(f.name)

    # --- Pass 2: MO2 Overwrite directory ---
    # When the game is launched through MO2, Creations downloaded in-session
    # land in Overwrite rather than the game's Data directory.
    overwrite_map = _scan_overwrite(overwrite_path, stem_to_display)

    for display_name, ow_files in overwrite_map.items():
        if display_name not in merged:
            merged[display_name] = {
                "display_name": display_name,
                "files": [],
                "_seen": set(),
            }
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

        _log.info(f"Starfield Creations Organizer: organising '{display_name}' -> '{mod_name}'")

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


def _scan_overwrite(overwrite_path: Path, stem_to_display: dict[str, str]) -> dict[str, list[Path]]:
    """
    Scans the MO2 Overwrite directory for Creation files.

    stem_to_display maps lowercase file stems to display names, built from
    referenceFile()/secondaryFiles() during the main scan pass.

    Returns a dict mapping display_name -> list[Path].
    """
    result: dict[str, list[Path]] = {}

    if not overwrite_path.is_dir():
        return result

    for f in overwrite_path.rglob("*"):
        if not f.is_file():
            continue

        stem = f.stem.lower()

        # Exact match covers .esm/.esl/.esp plugin files
        if stem in stem_to_display:
            display_name = stem_to_display[stem]
            result.setdefault(display_name, []).append(f)
            continue

        # Prefix + space match covers BA2 archives: "<plugin> - Main.ba2"
        for known_stem, display_name in stem_to_display.items():
            if stem.startswith(known_stem + " "):
                result.setdefault(display_name, []).append(f)
                break

    if result:
        total = sum(len(v) for v in result.values())
        _log.info(f"Starfield Creations Organizer: Overwrite scan found {total} file(s) across {len(result)} Creation(s)")
    else:
        _log.debug("Starfield Creations Organizer: Overwrite scan found no Creation files")

    return result


def _stem_map_from_catalog(organizer: mobase.IOrganizer) -> dict[str, str]:
    """
    Parses ContentCatalog.txt directly to build a complete mapping of
    lowercase plugin filename stems to their human-readable Title names.

    This is used to pre-populate stem_to_display before the main scan so
    the overwrite scan can attribute files even when referenceFile() returns
    nothing (which happens when files are only in the Overwrite directory and
    not in the game's Data directory).
    """
    local_appdata = os.environ.get("LOCALAPPDATA", "")
    game_name = organizer.managedGame().gameShortName()
    catalog_path = Path(local_appdata) / game_name / "ContentCatalog.txt"

    if not catalog_path.is_file():
        _log.warning(f"Starfield Creations Organizer: ContentCatalog.txt not found at {catalog_path}")
        return {}

    try:
        with open(catalog_path, encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        _log.warning(f"Starfield Creations Organizer: failed to parse ContentCatalog.txt: {e}")
        return {}

    result: dict[str, str] = {}
    for key, value in data.items():
        if key == "ContentCatalog" or not isinstance(value, dict):
            continue
        title = value.get("Title", key)
        for filename in value.get("Files", []):
            stem = Path(filename).stem.lower()
            result[stem] = title

    _log.debug(f"Starfield Creations Organizer: ContentCatalog mapped {len(result)} file stem(s)")
    return result


def _is_under(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False
