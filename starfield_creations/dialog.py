try:
    from PyQt5.QtCore import Qt
    from PyQt5.QtWidgets import (
        QDialog, QDialogButtonBox, QLabel, QLineEdit,
        QListWidget, QListWidgetItem, QVBoxLayout, QHBoxLayout,
        QWidget, QMessageBox,
    )
except ImportError:
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import (
        QDialog, QDialogButtonBox, QLabel, QLineEdit,
        QListWidget, QListWidgetItem, QVBoxLayout, QHBoxLayout,
        QWidget, QMessageBox,
    )

import mobase

from .organizer import scan_creations, organize_creations
from ._version import VERSION

_EXAMPLE_NAME = "Trackers Alliance: The Complete Bounty Series"


class CreationsDialog(QDialog):

    def __init__(self, organizer: mobase.IOrganizer, prefix: str, suffix: str, parent=None):
        super().__init__(parent)
        self._organizer = organizer
        self._creations = []

        self.setWindowTitle(f"Starfield Creations Organizer v{VERSION}")
        self.setMinimumWidth(500)

        layout = QVBoxLayout(self)

        # --- Naming settings ---
        naming_layout = QHBoxLayout()
        naming_layout.addWidget(QLabel("Prefix:"))
        self._prefix_edit = QLineEdit(prefix)
        naming_layout.addWidget(self._prefix_edit)
        naming_layout.addSpacing(16)
        naming_layout.addWidget(QLabel("Suffix:"))
        self._suffix_edit = QLineEdit(suffix)
        naming_layout.addWidget(self._suffix_edit)
        layout.addLayout(naming_layout)

        # Preview label
        self._preview_label = QLabel()
        self._preview_label.setWordWrap(True)
        layout.addWidget(self._preview_label)

        self._prefix_edit.textChanged.connect(self._update_preview)
        self._suffix_edit.textChanged.connect(self._update_preview)

        # --- Creation list ---
        self._status_label = QLabel("Scanning for Creations...")
        layout.addWidget(self._status_label)

        self._list = QListWidget()
        layout.addWidget(self._list)

        # --- Buttons ---
        buttons = QDialogButtonBox()
        self._organize_btn = buttons.addButton("Organize", QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.addButton("Cancel", QDialogButtonBox.ButtonRole.RejectRole)
        buttons.accepted.connect(self._on_organize)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._update_preview()
        self._load_creations()

    def _update_preview(self):
        prefix = self._prefix_edit.text()
        suffix = self._suffix_edit.text()
        self._preview_label.setText(f"<i>Preview: {prefix}{_EXAMPLE_NAME}{suffix}</i>")

    def _load_creations(self):
        self._creations = scan_creations(self._organizer)
        self._list.clear()

        if not self._creations:
            self._status_label.setText("No unmanaged Creations found.")
            self._organize_btn.setEnabled(False)
            return

        self._status_label.setText(f"Found {len(self._creations)} Creation(s):")
        for creation in self._creations:
            file_count = len(creation["files"])
            item = QListWidgetItem(
                f"{creation['display_name']}  ({file_count} file{'s' if file_count != 1 else ''})"
            )
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)
            self._list.addItem(item)

    def _on_organize(self):
        selected = [
            self._creations[i]
            for i in range(self._list.count())
            if self._list.item(i).checkState() == Qt.CheckState.Checked
        ]

        if not selected:
            QMessageBox.information(self, "Nothing selected", "No Creations were selected.")
            return

        prefix = self._prefix_edit.text()
        suffix = self._suffix_edit.text()
        count = organize_creations(self._organizer, selected, prefix, suffix)

        QMessageBox.information(
            self,
            "Done",
            f"Organized {count} Creation{'s' if count != 1 else ''} into MO2 mod folders.",
        )
        self.accept()

    def getSettings(self) -> tuple[str, str]:
        return self._prefix_edit.text(), self._suffix_edit.text()
