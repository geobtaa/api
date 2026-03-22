from qgis.PyQt.QtWidgets import QDialog, QVBoxLayout, QFormLayout, QLineEdit, QDialogButtonBox
from qgis.core import QgsSettings

class BtaaSettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("BTAA Geoportal Plugin Settings")
        
        self.settings = QgsSettings()
        
        layout = QVBoxLayout()
        form_layout = QFormLayout()
        
        self.url_input = QLineEdit()
        default_url = self.settings.value("btaa_plugin/api_url", "https://lib-btaageoapi-dev-app-01.oit.umn.edu/api/v1")
        self.url_input.setText(default_url)
        form_layout.addRow("API Base URL:", self.url_input)
        
        layout.addLayout(form_layout)
        
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        
        self.setLayout(layout)
        
    def accept(self):
        self.settings.setValue("btaa_plugin/api_url", self.url_input.text().strip())
        super().accept()
