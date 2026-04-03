import sys
from PySide6.QtWidgets import QApplication
from ui import MainWindow

class App:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.window = MainWindow()

    def run(self):
        self.window.show()
        return self.app.exec()
