import os
import sys
from PyQt5 import QtWidgets, QtCore
from .config.filaments import load_filaments

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AnycubicNFCTaggerQT5")
        self.resize(560, 320)

        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        vbox = QtWidgets.QVBoxLayout(central)

        # --- Step 1: two selection boxes side-by-side ---
        row = QtWidgets.QHBoxLayout()
        vbox.addLayout(row)

        left_box = QtWidgets.QGroupBox("Choose filament")
        right_box = QtWidgets.QGroupBox("Choose color")  # will be implemented in Step 2
        row.addWidget(left_box, 1)
        row.addWidget(right_box, 1)

        # Left: filament combo
        left_layout = QtWidgets.QVBoxLayout(left_box)
        self.combo_filament = QtWidgets.QComboBox()
        left_layout.addWidget(self.combo_filament)

        # Right: color combo (placeholder for Step 2)
        right_layout = QtWidgets.QVBoxLayout(right_box)
        self.combo_color = QtWidgets.QComboBox()
        self.combo_color.setEnabled(False)  # enable in Step 2
        right_layout.addWidget(self.combo_color)

        # Output log
        self.output = QtWidgets.QPlainTextEdit()
        self.output.setReadOnly(True)
        vbox.addWidget(self.output)

        self.statusBar().showMessage("Ready")

        # Load filaments from config
        try:
            self.by_filament, self.by_sku = load_filaments(None)  # packaged file
            # populate filament names (unique, sorted)
            names = sorted(self.by_filament.keys(), key=str.casefold)
            self.combo_filament.addItems(names)
            self.log(f"Loaded {sum(len(v) for v in self.by_filament.values())} entries across {len(names)} filaments.")
        except Exception as e:
            self.log(f"[Error] Failed to load filaments: {e}")

        # Signals
        self.combo_filament.currentTextChanged.connect(self.on_filament_changed)

    def log(self, msg: str):
        self.output.appendPlainText(msg)

    # Step 1 behavior: just log the selected filament (colors come in Step 2)
    def on_filament_changed(self, filament_name: str):
        if not filament_name:
            return
        records = self.by_filament.get(filament_name, [])
        self.log(f"Selected filament: {filament_name} ({len(records)} variants)")
        # Step 2 will populate self.combo_color from 'records'



def run_app():
    # High-DPI tweaks
    QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling, True)
    QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps, True)

    app = QtWidgets.QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())