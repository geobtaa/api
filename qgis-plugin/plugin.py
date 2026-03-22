import os
from qgis.PyQt.QtWidgets import QAction
from qgis.PyQt.QtGui import QIcon
from .ui_dialog import GeodataSearchDialog

class GeodataSearchPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.action = None
        
    def initGui(self):
        icon_path = os.path.join(os.path.dirname(__file__), 'icon.png')
        self.action = QAction(
            QIcon(icon_path),
            "BTAA Geoportal Search",
            self.iface.mainWindow()
        )
        self.action.triggered.connect(self.run)
        
        try:
            self.iface.addToolBarIcon(self.action)
        except AttributeError:
            pass
        self.iface.addPluginToMenu("BTAA Geoportal Search", self.action)
        
    def unload(self):
        if self.action:
            self.iface.removePluginMenu("BTAA Geoportal Search", self.action)
            try:
                self.iface.removeToolBarIcon(self.action)
            except AttributeError:
                pass
            
    def run(self):
        dialog = GeodataSearchDialog(self.iface)
        dialog.exec_()
