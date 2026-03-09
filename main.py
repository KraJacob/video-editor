import sys
import warnings
warnings.filterwarnings("ignore", message=".*bytes wanted but.*bytes read.*")

from PyQt6.QtWidgets import QApplication

from ui.main_window import MainWindow
from ui.style import DARK_QSS


def main() -> None:
    app = QApplication(sys.argv)
    app.setStyleSheet(DARK_QSS)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
