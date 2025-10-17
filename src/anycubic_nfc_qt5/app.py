# src/anycubic_nfc_qt5/app.py
import sys, traceback
from PyQt5 import QtWidgets, QtCore
from .ui.main_window import MainWindow

def run_app():
    APP_TITLE = "AnycubicNFCTaggerQT5"
    UI_VERSION = "V0.3"

    QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling, True)
    QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps, True)
    app = QtWidgets.QApplication(sys.argv)
    win = MainWindow(APP_TITLE, UI_VERSION)
    win.show()
    sys.exit(app.exec_())


def _global_excepthook(exctype, value, tb):
    text = "".join(traceback.format_exception(exctype, value, tb))
    # Terminal
    print(text, file=sys.stderr)
    # Optional: in eine Datei schreiben
    with open("qt_error.log", "a", encoding="utf-8") as f:
        f.write(text + "\n")

sys.excepthook = _global_excepthook
if __name__ == "__main__":
    run_app()