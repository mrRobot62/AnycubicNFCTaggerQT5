# src/anycubic_nfc_qt5/app.py
import sys
from pathlib import Path
from PyQt5 import QtWidgets, QtGui, QtCore
from .config.filaments import load_filaments
from importlib import resources

PLACEHOLDER_FILAMENT = "select filament"
PLACEHOLDER_COLOR = "select color"

def set_placeholder(combo: QtWidgets.QComboBox, text: str):
    """Insert a disabled, non-selectable first item as placeholder."""
    combo.clear()
    combo.addItem(text)
    # disable/select-block the placeholder row
    m = combo.model()
    idx = m.index(0, 0)
    m.setData(idx, 0, QtCore.Qt.UserRole - 1)  # disable
    # If using QStandardItemModel, also:
    it = m.item(0)
    if it:
        it.setEnabled(False)
        it.setSelectable(False)
    combo.setCurrentIndex(0)
class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AnycubicNFCTaggerQT5")
        self.resize(580, 360)

        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        layout = QtWidgets.QVBoxLayout(central)

        # === NFC Icon ===
        self.icon_label = QtWidgets.QLabel(alignment=QtCore.Qt.AlignCenter)
        self.icon_label.setMinimumHeight(120)
        layout.addWidget(self.icon_label)

        # Load all three icons from packaged resources
        self.icons = {}
        for state, fname in {
            "red": "nfc_red.png",
            "green": "nfc_green.png",
         }.items():
            try:
                data = resources.files("anycubic_nfc_qt5.ui.resources").joinpath(fname).read_bytes()
                pm = QtGui.QPixmap()
                pm.loadFromData(data)
                self.icons[state] = pm
            except Exception as e:
                print(f"[WARN] Could not load {fname}: {e}")

        self.set_reader_connected(False)  # start: disconnected (red)

        # === Selection row ===
        row = QtWidgets.QHBoxLayout()
        layout.addLayout(row)
        # (rest of your combo boxes and buttons as before)
        left_box = QtWidgets.QGroupBox("Choose filament")
        right_box = QtWidgets.QGroupBox("Choose color")
        row.addWidget(left_box, 1)
        row.addWidget(right_box, 1)

        self.combo_filament = QtWidgets.QComboBox()
        self.combo_color = QtWidgets.QComboBox()
        self.combo_color.setEnabled(False)

        v_left = QtWidgets.QVBoxLayout(left_box)
        v_left.addWidget(self.combo_filament)
        v_right = QtWidgets.QVBoxLayout(right_box)
        v_right.addWidget(self.combo_color)

        # === Buttons row ===
        btn_row = QtWidgets.QHBoxLayout()
        layout.addLayout(btn_row)
        self.btn_read = QtWidgets.QPushButton("READ NFC")
        self.btn_write = QtWidgets.QPushButton("WRITE NFC")
        btn_row.addStretch()
        btn_row.addWidget(self.btn_read)
        btn_row.addWidget(self.btn_write)
        btn_row.addStretch()

        # === Log output ===
        self.output = QtWidgets.QPlainTextEdit()
        self.output.setReadOnly(True)
        layout.addWidget(self.output)

        # placeholders first
        set_placeholder(self.combo_filament, PLACEHOLDER_FILAMENT)
        set_placeholder(self.combo_color, PLACEHOLDER_COLOR)
        self.combo_color.setEnabled(False)


        self.statusBar().showMessage("Ready")

        # Load filaments
        try:
            self.by_filament, self.by_sku = load_filaments(None)
            names = sorted(self.by_filament.keys(), key=str.casefold)
            self.combo_filament.addItems(names)

            # keep placeholder at index 0, append real items after it
            for name in names:
                self.combo_filament.addItem(name)

            self.log(f"Loaded {sum(len(v) for v in self.by_filament.values())} filament records.")
        except Exception as e:
            self.log(f"[Error] Failed to load filaments: {e}")

        # --- Signals ---
        self.combo_filament.currentTextChanged.connect(self.on_filament_changed)
        self.btn_read.clicked.connect(self.on_read)
        self.btn_write.clicked.connect(self.on_write)

        # --- Timer: simulate reader state ---
        self.reader_connected = False
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self._check_reader_state)
        self.timer.start(2000)  # every 2 s check (dummy for now)

    # === UI Helpers ===
    def set_reader_connected(self, state: bool):
        """Show the correct colored NFC icon."""
        pix = self.icons.get("green" if state else "red")
        if not pix or pix.isNull():
            self.icon_label.setText("[missing icon]")
            return
        self.icon_label.setPixmap(pix.scaledToWidth(100, QtCore.Qt.SmoothTransformation))

    def _check_reader_state(self):
        """Simulate: toggle connection status (for now)."""
        self.reader_connected = not self.reader_connected
        self.set_reader_connected(self.reader_connected)
        self.statusBar().showMessage("Reader connected" if self.reader_connected else "Reader disconnected")

    def log(self, msg: str):
        self.output.appendPlainText(msg)

    def _update_actions(self):
        """Enable/disable buttons based on selection state."""
        filament_ok = self.combo_filament.currentIndex() > 0
        color_ok = self.combo_color.isEnabled() and self.combo_color.currentIndex() > 0
        self.btn_write.setEnabled(filament_ok and color_ok)
        self.btn_read.setEnabled(True)

    def on_filament_changed(self, filament_name: str):
        """Handle filament selection change."""
        if self.combo_filament.currentIndex() == 0 or filament_name == PLACEHOLDER_FILAMENT:
            set_placeholder(self.combo_color, PLACEHOLDER_COLOR)
            self.combo_color.setEnabled(False)
            self._update_actions()
            return

        records = self.by_filament.get(filament_name, [])
        self.log(f"Selected filament: {filament_name} ({len(records)} variants)")

        # prepare color combo (for Step 2)
        set_placeholder(self.combo_color, PLACEHOLDER_COLOR)
        self.combo_color.setEnabled(True)
        for rec in records:
            self.combo_color.addItem(rec.color, rec.sku)

        self._update_actions()

    # === Step 2 placeholder buttons ===
    def on_read(self):
        self.log("[INFO] READ NFC clicked")

    def on_write(self):
        self.log("[INFO] WRITE NFC clicked")


def run_app():
    QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling, True)
    QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps, True)
    app = QtWidgets.QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())