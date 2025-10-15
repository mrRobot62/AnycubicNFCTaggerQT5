import sys
from PyQt5 import QtWidgets, QtGui, QtCore


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PyQt5 Beispiel")
        self.resize(420, 220)

        # ---- Zentraler Inhalt ----
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        main_layout = QtWidgets.QVBoxLayout(central)

        self.label = QtWidgets.QLabel("Gib deinen Namen ein:")
        main_layout.addWidget(self.label)

        self.name_input = QtWidgets.QLineEdit()
        self.name_input.setPlaceholderText("Name hier …")
        main_layout.addWidget(self.name_input)

        btn_row = QtWidgets.QHBoxLayout()
        main_layout.addLayout(btn_row)

        self.btn_hello = QtWidgets.QPushButton("Sag Hallo")
        self.btn_clear = QtWidgets.QPushButton("Leeren")
        btn_row.addWidget(self.btn_hello)
        btn_row.addWidget(self.btn_clear)

        # ---- Statusleiste ----
        self.status = self.statusBar()
        self.status.showMessage("Bereit")

        # ---- Aktionen (für Menü & Toolbar) ----
        act_hello = QtWidgets.QAction("Hallo", self)
        act_hello.setShortcut(QtGui.QKeySequence("Ctrl+H"))
        act_hello.triggered.connect(self.say_hello)

        act_clear = QtWidgets.QAction("Leeren", self)
        act_clear.setShortcut(QtGui.QKeySequence("Esc"))
        act_clear.triggered.connect(self.clear_input)

        act_quit = QtWidgets.QAction("Beenden", self)
        act_quit.setShortcut(QtGui.QKeySequence.Quit)
        act_quit.triggered.connect(QtWidgets.qApp.quit)

        # ---- Menüleiste ----
        menu_file = self.menuBar().addMenu("&Datei")
        menu_file.addAction(act_hello)
        menu_file.addAction(act_clear)
        menu_file.addSeparator()
        menu_file.addAction(act_quit)

        # ---- Toolbar ----
        tb = self.addToolBar("Aktionen")
        tb.setMovable(False)
        tb.addAction(act_hello)
        tb.addAction(act_clear)

        # ---- Buttons verbinden ----
        self.btn_hello.clicked.connect(self.say_hello)
        self.btn_clear.clicked.connect(self.clear_input)

    def say_hello(self):
        name = self.name_input.text().strip()
        if name:
            QtWidgets.QMessageBox.information(self, "Begrüßung", f"Hallo {name} 👋")
            self.status.showMessage(f"Hallo an {name}", 2000)
        else:
            QtWidgets.QMessageBox.warning(self, "Hinweis", "Bitte gib zuerst deinen Namen ein!")
            self.status.showMessage("Kein Name eingegeben", 2000)

    def clear_input(self):
        self.name_input.clear()
        self.name_input.setFocus()
        self.status.showMessage("Eingabe geleert", 1500)


if __name__ == "__main__":
    # Optional bessere DPI-Unterstützung
    QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling, True)
    QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps, True)

    app = QtWidgets.QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())