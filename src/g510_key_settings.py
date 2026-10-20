from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import (
    QComboBox, QFormLayout, QLabel, QMessageBox, QPushButton, QVBoxLayout, QWidget,
)

from g510_screen_keys import (
    action_labels, load_screens, load_bindings, save_bindings, show_screen, CLOCK_ACTIONS,
    DESIGN_ACTIONS, SCREEN_DESIGNS,
)


class ScreenKeysTab(QWidget):
    bindings_changed = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.bindings = None
        layout = QVBoxLayout(self)
        note = QLabel(
            "L1 blättert durch die vorhandenen Bildschirme und alle eigenen Screens.\n"
            "L2–L5 führen die Aktionen des aktiven Bildschirms aus. "
            "Die manuelle Bildschirmwahl hat Vorrang vor der Medien-Automatik "
            "bis die Wiedergabe mindestens fünf Sekunden beendet ist.\n"
            "Play/ Pause/ Titelwechsel benötigen einen MPRIS-Player. Webradio ohne "
            "MPRIS ist sichtbar, lässt sich darüber aber nicht steuern.\n"
            "Uhr: L2 = vorheriges Layout, L3 = nächstes Layout (20 Designs). "
            "Die letzte Auswahl bleibt gespeichert; die Belegung ist hier änderbar."
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        self.screen = QComboBox()
        layout.addWidget(self.screen)
        form = QFormLayout()
        self.combos = {}
        for key in ("L2", "L3", "L4", "L5"):
            combo = QComboBox()
            combo.activated.connect(self.save)
            form.addRow(key, combo)
            self.combos[key] = combo
        layout.addLayout(form)
        self.status = QLabel()
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        show = QPushButton("Bildschirm jetzt auf dem LCD anzeigen")
        show.clicked.connect(self.show_selected)
        layout.addWidget(show)
        reload_button = QPushButton("Belegung neu laden")
        reload_button.clicked.connect(self.reload)
        layout.addWidget(reload_button)
        layout.addStretch()
        self.screen.currentIndexChanged.connect(self.select_screen)
        self.reload()

    def reload(self):
        try:
            current = self.screen.currentData()
            screens = load_screens()
            actions = action_labels()
            self.bindings = load_bindings()
            self.screen.blockSignals(True)
            self.screen.clear()
            for key, name in screens.items():
                self.screen.addItem(name, key)
            index = self.screen.findData(current)
            self.screen.setCurrentIndex(index if index >= 0 else 0)
            self.screen.blockSignals(False)
            for combo in self.combos.values():
                combo.clear()
                for action, label in actions.items():
                    combo.addItem(label, action)
            self.status.setText("Belegung geladen.")
        except (OSError, ValueError) as error:
            self.bindings = None
            self.status.setText(f"Belegung konnte nicht geladen werden: {error}")
        self.select_screen()

    def select_screen(self):
        for key, combo in self.combos.items():
            combo.setEnabled(self.bindings is not None)
            if self.bindings is not None:
                combo.setCurrentIndex(combo.findData(
                    self.bindings[str(self.screen.currentData())][key]))
            for action in CLOCK_ACTIONS:
                item = combo.model().item(combo.findData(action))
                if item is not None:
                    item.setEnabled(self.screen.currentData() == 1)
            for action in DESIGN_ACTIONS:
                item = combo.model().item(combo.findData(action))
                if item is not None:
                    item.setEnabled(self.screen.currentData() in SCREEN_DESIGNS)

    def save(self):
        if self.bindings is None:
            return
        screen = str(self.screen.currentData())
        previous = dict(self.bindings[screen])
        self.bindings[screen] = {key: combo.currentData()
                                 for key, combo in self.combos.items()}
        try:
            save_bindings(self.bindings)
        except OSError as error:
            self.bindings[screen] = previous
            self.select_screen()
            QMessageBox.critical(self, "LCD-Tasten", f"Speichern fehlgeschlagen: {error}")
            return
        self.status.setText("Belegung gespeichert. Sie gilt ab dem nächsten Tastendruck.")
        self.bindings_changed.emit()

    def show_selected(self):
        try:
            show_screen(self.screen.currentData())
        except (OSError, ValueError) as error:
            QMessageBox.warning(self, "Bildschirmwechsel", str(error))
