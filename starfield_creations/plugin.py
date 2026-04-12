try:
    from PyQt5.QtGui import QIcon
    from PyQt5.QtWidgets import QApplication
except ImportError:
    from PyQt6.QtGui import QIcon
    from PyQt6.QtWidgets import QApplication

import mobase

from .dialog import CreationsDialog
from ._version import VERSION


class StarfieldCreationsPlugin(mobase.IPluginTool):

    def __init__(self):
        super().__init__()
        self._organizer = None

    def init(self, organizer: mobase.IOrganizer) -> bool:
        self._organizer = organizer
        return True

    def name(self) -> str:
        return "Starfield Creations Organizer"

    def author(self) -> str:
        return "Spuddeh"

    def description(self) -> str:
        return "Moves Starfield Creations from the game Data directory into individual MO2-managed mod folders."

    def version(self) -> mobase.VersionInfo:
        major, minor, patch = (int(x) for x in VERSION.split("."))
        return mobase.VersionInfo(major, minor, patch, mobase.ReleaseType.ALPHA)

    def displayName(self) -> str:
        return "Starfield Creations Organizer"

    def tooltip(self) -> str:
        return "Organize Starfield Creations into individual MO2 mod folders"

    def icon(self) -> QIcon:
        return QIcon()

    def setParentWidget(self, widget):
        self._parent = widget

    def settings(self) -> list:
        return [
            mobase.PluginSetting("prefix", "Text to prepend to each Creation mod name", "[Creations] "),
            mobase.PluginSetting("suffix", "Text to append to each Creation mod name", ""),
        ]

    def display(self):
        prefix = self._organizer.pluginSetting(self.name(), "prefix")
        suffix = self._organizer.pluginSetting(self.name(), "suffix")
        if prefix is None:
            prefix = "[Creations] "
        if suffix is None:
            suffix = ""

        dialog = CreationsDialog(self._organizer, str(prefix), str(suffix), self._parent)
        if dialog.exec():
            new_prefix, new_suffix = dialog.getSettings()
            self._organizer.setPluginSetting(self.name(), "prefix", new_prefix)
            self._organizer.setPluginSetting(self.name(), "suffix", new_suffix)
