import sys
from unittest.mock import MagicMock


class MockSignal:
    def __init__(self, *args, **kwargs):
        pass

    def emit(self, *args, **kwargs):
        pass


class MockThread:
    def __init__(self, *args, **kwargs):
        pass

    def start(self):
        self.run()

    def run(self):
        pass


# Setup mock for QGIS and PyQt modules so we can run tests outside QGIS environment
mock_qtcore = MagicMock()
mock_qtcore.pyqtSignal = MockSignal
mock_qtcore.QThread = MockThread

mock_pyqt = MagicMock()
mock_pyqt.QtCore = mock_qtcore


class MockWidget:
    Ok = 1
    Cancel = 2

    def __init__(self, *args, **kwargs):
        pass

    def __getattr__(self, name):
        if name == "findText":
            return lambda *args, **kwargs: 0
        if name == "critical":
            return lambda *args, **kwargs: None
        return MagicMock()


class MockQtWidgets:
    QDialog = MockWidget
    QFrame = MockWidget
    QHBoxLayout = MockWidget
    QVBoxLayout = MockWidget
    QLabel = MockWidget
    QLineEdit = MockWidget
    QListWidget = MockWidget
    QMessageBox = MockWidget
    QProgressBar = MockWidget
    QPushButton = MockWidget
    QComboBox = MockWidget
    QDialogButtonBox = MockWidget
    QFormLayout = MockWidget
    QAction = MockWidget


mock_pyqt.QtWidgets = MockQtWidgets()
mock_pyqt.QtGui = MagicMock()

mock_qgis = MagicMock()
mock_qgis.PyQt = mock_pyqt
mock_qgis.core = MagicMock()


class MockQgsSettings:
    def value(self, key, default):
        return default


mock_qgis.core.QgsSettings = MockQgsSettings
mock_qgis.gui = MagicMock()
mock_qgis.utils = MagicMock()

sys.modules["qgis"] = mock_qgis
sys.modules["qgis.core"] = mock_qgis.core
sys.modules["qgis.gui"] = mock_qgis.gui
sys.modules["qgis.utils"] = mock_qgis.utils
sys.modules["qgis.PyQt"] = mock_pyqt
sys.modules["qgis.PyQt.QtCore"] = mock_qtcore
sys.modules["qgis.PyQt.QtWidgets"] = mock_pyqt.QtWidgets
sys.modules["qgis.PyQt.QtGui"] = mock_pyqt.QtGui
