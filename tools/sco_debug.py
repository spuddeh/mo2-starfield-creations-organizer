"""
Starfield Creations Organizer — debug probe.

Drop this file in your MO2 plugins/ directory. It adds a tool called
"SCO Debug" to the Tools menu. Run it and then check mo_interface.log
for the results.
"""

import mobase

try:
    from PyQt5.QtGui import QIcon
except ImportError:
    from PyQt6.QtGui import QIcon

import logging

_log = logging.getLogger("sco_debug")


class SCODebugPlugin(mobase.IPluginTool):

    def __init__(self):
        super().__init__()
        self._organizer = None

    def init(self, organizer: mobase.IOrganizer) -> bool:
        self._organizer = organizer
        return True

    def name(self) -> str:
        return "SCO Debug"

    def author(self) -> str:
        return "Spuddeh"

    def description(self) -> str:
        return "Debug probe for Starfield Creations Organizer."

    def version(self) -> mobase.VersionInfo:
        return mobase.VersionInfo(1, 0, 0, mobase.ReleaseType.ALPHA)

    def displayName(self) -> str:
        return "SCO Debug"

    def tooltip(self) -> str:
        return "Logs referenceFile() and secondaryFiles() output to mo_interface.log"

    def icon(self) -> QIcon:
        return QIcon()

    def setParentWidget(self, widget):
        self._parent = widget

    def settings(self) -> list:
        return []

    def display(self):
        o = self._organizer
        unmanaged = o.gameFeatures().gameFeature(mobase.UnmanagedMods)
        if unmanaged is None:
            _log.error("SCO Debug: UnmanagedMods not available")
            return

        import os
        from pathlib import Path

        data_dir  = Path(o.managedGame().dataDirectory().absolutePath())
        mods_path = Path(o.modsPath())
        over_path = Path(o.overwritePath())

        _log.info(f"SCO Debug: data_dir    = {data_dir}")
        _log.info(f"SCO Debug: mods_path   = {mods_path}")
        _log.info(f"SCO Debug: over_path   = {over_path}")

        all_names = unmanaged.mods(False)
        _log.info(f"SCO Debug: mods(False) returned {len(all_names)} name(s): {all_names}")

        cc = o.managedGame().CCPlugins()
        _log.info(f"SCO Debug: CCPlugins() returned {len(cc)} entry/entries: {cc}")

        for name in all_names:
            display_name = unmanaged.displayName(name)
            ref          = unmanaged.referenceFile(name)
            sec          = unmanaged.secondaryFiles(name)
            ref_path     = Path(ref.absoluteFilePath()) if ref else None
            search_dir   = ref_path.parent if ref_path and ref_path.is_file() else None

            _log.info(f"SCO Debug: --- '{name}' ---")
            _log.info(f"SCO Debug:   displayName()          = {display_name!r}")
            _log.info(f"SCO Debug:   referenceFile path     = {str(ref_path)!r}")
            _log.info(f"SCO Debug:   search_dir (parent)   = {str(search_dir)!r}")
            _log.info(f"SCO Debug:   secondaryFiles(name)   ({len(list(sec))} items) = {list(sec)[:5]}{'...' if len(list(sec)) > 5 else ''}")

        _log.info("SCO Debug: done — check mo_interface.log")


def createPlugin():
    return SCODebugPlugin()
