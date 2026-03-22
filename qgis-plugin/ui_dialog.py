import json
import os
import tempfile
import webbrowser
import zipfile
from qgis.PyQt.QtWidgets import (QDialog, QVBoxLayout, QLineEdit, QListWidget, 
                                QPushButton, QHBoxLayout, QLabel, QComboBox,
                                QProgressBar, QMessageBox, QFrame, QGridLayout)
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QPixmap, QIcon
from qgis.core import QgsRasterLayer, QgsVectorLayer, QgsProject, Qgis, QgsSettings

from .api_client import BtaaApiClient
from .downloader import DataLoader
from .settings_dialog import BtaaSettingsDialog

class GeodataSearchDialog(QDialog):
    def __init__(self, iface, parent=None):
        super().__init__(parent)
        self.iface = iface
        self.setWindowTitle("BTAA Geoportal Search")
        self.resize(900, 600)
        
        icon_path = os.path.join(os.path.dirname(__file__), 'icon.png')
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        
        self.settings = QgsSettings()
        self.api_url = self.settings.value("btaa_plugin/api_url", "https://lib-btaageoapi-dev-app-01.oit.umn.edu/api/v1")
        self.api_client = BtaaApiClient(self.api_url)
        
        # UI Setup
        layout = QVBoxLayout()
        
        # Banner Logo
        self.banner_label = QLabel()
        if os.path.exists(icon_path):
            pixmap = QPixmap(icon_path)
            scaled_pixmap = pixmap.scaledToWidth(250, Qt.SmoothTransformation)
            self.banner_label.setPixmap(scaled_pixmap)
            self.banner_label.setAlignment(Qt.AlignCenter)
            layout.addWidget(self.banner_label)
            
        search_layout = QGridLayout()
        
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Enter search terms...")
        self.search_box.returnPressed.connect(self.perform_search)
        search_layout.addWidget(QLabel("Search:"), 0, 0)
        search_layout.addWidget(self.search_box, 0, 1, 1, 2)
        
        self.resource_type_combo = QComboBox()
        self.resource_type_combo.addItem("All Types")
        search_layout.addWidget(QLabel("Resource Type:"), 1, 0)
        search_layout.addWidget(self.resource_type_combo, 1, 1)
        
        self.format_combo = QComboBox()
        self.format_combo.addItem("All Formats")
        search_layout.addWidget(QLabel("Format:"), 1, 2)
        search_layout.addWidget(self.format_combo, 1, 3)
        
        self.search_button = QPushButton("Search")
        self.search_button.clicked.connect(self.perform_search)
        search_layout.addWidget(self.search_button, 0, 3)
        
        self.settings_button = QPushButton("Settings")
        self.settings_button.clicked.connect(self.open_settings)
        search_layout.addWidget(self.settings_button, 0, 4)
        
        layout.addLayout(search_layout)
        
        results_layout = QHBoxLayout()
        
        results_frame = QFrame()
        results_frame.setFrameStyle(QFrame.StyledPanel)
        results_layout_inner = QVBoxLayout()
        
        self.results_list = QListWidget()
        self.results_list.itemClicked.connect(self.show_preview)
        self.results_list.itemDoubleClicked.connect(self.load_selected_layer)
        results_layout_inner.addWidget(self.results_list)
        
        pagination_layout = QHBoxLayout()
        self.prev_button = QPushButton("Previous")
        self.prev_button.clicked.connect(self.prev_page)
        self.next_button = QPushButton("Next")
        self.next_button.clicked.connect(self.next_page)
        self.page_label = QLabel("Page 1")
        pagination_layout.addWidget(self.prev_button)
        pagination_layout.addWidget(self.page_label)
        pagination_layout.addWidget(self.next_button)
        results_layout_inner.addLayout(pagination_layout)
        
        results_frame.setLayout(results_layout_inner)
        results_layout.addWidget(results_frame)
        
        preview_frame = QFrame()
        preview_frame.setFrameStyle(QFrame.StyledPanel)
        preview_layout = QVBoxLayout()
        
        self.preview_image = QLabel()
        self.preview_image.setAlignment(Qt.AlignCenter)
        self.preview_image.setMinimumSize(250, 250)
        
        self.open_browser_button = QPushButton("View at BTAA Geoportal")
        self.open_browser_button.hide()
        self.open_browser_button.clicked.connect(self.open_current_in_browser)
        
        self.preview_text = QLabel()
        self.preview_text.setWordWrap(True)
        
        preview_layout.addWidget(self.preview_image)
        preview_layout.addWidget(self.open_browser_button)
        preview_layout.addWidget(self.preview_text)
        preview_layout.addStretch()
        preview_frame.setLayout(preview_layout)
        
        results_layout.addWidget(preview_frame)
        layout.addLayout(results_layout)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.hide()
        layout.addWidget(self.progress_bar)
        
        self.setLayout(layout)
        
        self.current_results = []
        self.current_page = 1
        self.total_pages = 1
        self.per_page = 10
        
        self.load_facets()

    def open_settings(self):
        dialog = BtaaSettingsDialog(self)
        if dialog.exec_():
            self.api_url = self.settings.value("btaa_plugin/api_url", "https://lib-btaageoapi-dev-app-01.oit.umn.edu/api/v1")
            self.api_client = BtaaApiClient(self.api_url)
            self.load_facets()

    def load_facets(self):
        try:
            data = self.api_client.get_facets()
            resource_types = []
            formats = []
            for facet in data.get("included", []):
                if facet["id"] == "gbl_resourceClass_sm":
                    resource_types = [item[0] 
                                   for item in facet["attributes"]["items"] if item and len(item) > 0]
                elif facet["id"] == "gbl_resourceType_sm":
                    formats = [item[0] 
                                   for item in facet["attributes"]["items"] if item and len(item) > 0]
            
            self.resource_type_combo.blockSignals(True)
            self.resource_type_combo.clear()
            self.resource_type_combo.addItem("All Types")
            self.resource_type_combo.addItems(resource_types)
            self.resource_type_combo.blockSignals(False)
            
            self.format_combo.blockSignals(True)
            self.format_combo.clear()
            self.format_combo.addItem("All Formats")
            self.format_combo.addItems(formats)
            self.format_combo.blockSignals(False)
        except Exception as e:
            self.show_error("Error loading facets", str(e))

    def perform_search(self):
        self.current_page = 1
        self.search()
        
    def search(self):
        search_term = self.search_box.text()
        if not search_term:
            return
            
        self.progress_bar.setRange(0, 0)
        self.progress_bar.show()
        self.search_button.setEnabled(False)
        
        params = {
            "q": search_term,
            "page": self.current_page,
            "per_page": self.per_page
        }
        
        resource_type = self.resource_type_combo.currentText()
        if resource_type != "All Types":
            params["include_filters[gbl_resourceClass_sm][]"] = resource_type
            
        format_type = self.format_combo.currentText()
        if format_type != "All Formats":
            params["include_filters[gbl_resourceType_sm][]"] = format_type
            
        try:
            data = self.api_client.search(params)
            
            meta = data.get("meta", {}).get("pages", {})
            self.total_pages = meta.get("total_pages", 1)
            self.page_label.setText(f"Page {self.current_page} of {self.total_pages}")
            self.prev_button.setEnabled(self.current_page > 1)
            self.next_button.setEnabled(self.current_page < self.total_pages)
            
            self.results_list.clear()
            self.current_results = []
            
            for item in data.get("data", []):
                attributes = item.get("attributes", {}).get("ogm", {})
                title = attributes.get("dct_title_s", "Untitled")
                format_str = attributes.get("dct_format_s", "")
                if format_str:
                    title = f"{title} ({format_str})"
                self.results_list.addItem(title)
                self.current_results.append(item)
                
        except Exception as e:
            self.show_error("Search Error", str(e))
        finally:
            self.progress_bar.hide()
            self.search_button.setEnabled(True)

    def show_preview(self, item_widget):
        index = self.results_list.row(item_widget)
        if index < 0 or index >= len(self.current_results):
            return
            
        item = self.current_results[index]
        attributes = item.get("attributes", {}).get("ogm", {})
        meta_ui = item.get("meta", {}).get("ui", {})
        
        thumbnail_url = meta_ui.get("thumbnail_url")
        if thumbnail_url:
            try:
                content = self.api_client.get_thumbnail(thumbnail_url)
                pixmap = QPixmap()
                pixmap.loadFromData(content)
                scaled_pixmap = pixmap.scaled(250, 250, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.preview_image.setPixmap(scaled_pixmap)
            except:
                self.preview_image.clear()
        else:
            self.preview_image.clear()
            
        self.open_browser_button.show()
            
        preview_text = []
        preview_text.append(f"<b>Title:</b> {attributes.get('dct_title_s', '')}")
        preview_text.append(f"<b>Format:</b> {attributes.get('dct_format_s', '')}")
        desc_list = attributes.get('dct_description_sm', [])
        desc = desc_list[0] if desc_list else ""
        preview_text.append(f"<b>Description:</b> {desc}")
        
        self.preview_text.setText("<br>".join(preview_text))

    def load_selected_layer(self, item_widget):
        index = self.results_list.row(item_widget)
        if index < 0 or index >= len(self.current_results):
            return
            
        item = self.current_results[index]
        attributes = item.get("attributes", {}).get("ogm", {})
        meta_ui = item.get("meta", {}).get("ui", {})
        
        try:
            references = json.loads(attributes.get("dct_references_s", "{}"))
        except:
            references = {}
            
        def get_reference_url(key):
            if not isinstance(references, dict):
                return None
                
            ref = references.get(key)
            if not ref:
                return None
            if isinstance(ref, str):
                return ref
            if isinstance(ref, list) and len(ref) > 0:
                if isinstance(ref[0], dict):
                    return ref[0].get("url")
            if isinstance(ref, dict):
                return ref.get("url")
            return None
            
        # Try returning WMS
        wms_url = get_reference_url("http://www.opengis.net/def/serviceType/ogc/wms")
        if wms_url:
            layer_name = attributes.get("gbl_wxsidentifier_s", "")
            if layer_name:
                self.load_wms_layer(wms_url, layer_name, attributes.get("dct_title_s", ""))
                return
                
        wfs_url = get_reference_url("http://www.opengis.net/def/serviceType/ogc/wfs")
        if wfs_url:
            layer_name = attributes.get("gbl_wxsidentifier_s", "")
            if layer_name:
                self.load_wfs_layer(wfs_url, layer_name, attributes.get("dct_title_s", ""))
                return
                
        # Try Downloads array (GeoPackage or Shapefile)
        downloads = meta_ui.get("downloads", [])
        download_url = None
        
        for dl in downloads:
            label = dl.get("label", "").lower()
            if "geopackage" in label:
                download_url = dl.get("url")
                break
                
        if not download_url:
            for dl in downloads:
                label = dl.get("label", "").lower()
                if "shapefile" in label:
                    download_url = dl.get("url")
                    break
                    
        if download_url:
            self.download_and_load_shapefile(download_url, attributes.get("dct_title_s", ""))
            return
            
        # Fallback to Shapefile reference
        shapefile_url = get_reference_url("http://schema.org/downloadUrl")
        if shapefile_url and attributes.get("dct_format_s") == "Shapefile":
            self.download_and_load_shapefile(shapefile_url, attributes.get("dct_title_s", ""))
            return
            
        # Fallback to browser
        if self.iface:
            self.iface.messageBar().pushMessage("Information", "This dataset cannot be loaded directly as a layer. Opening in web browser instead.", level=Qgis.Info)
        self.open_current_in_browser(item_widget)

    def open_current_in_browser(self, item_widget=None):
        if not item_widget:
            item_widget = self.results_list.currentItem()
        if not item_widget:
            return
        index = self.results_list.row(item_widget)
        if index < 0 or index >= len(self.current_results):
            return
            
        item = self.current_results[index]
        item_id = item.get("id")
        
        if item_id:
            # Construct URL to the resource
            catalog_base = self.api_url.replace('/api/v1', '/resources')
            url = f"{catalog_base}/{item_id}"
            webbrowser.open(url)
        else:
            self.show_error("Error", "Could not find resource ID to open.")

    def load_wms_layer(self, url, layer_name, title):
        layer = QgsRasterLayer(
            f"url={url}&layers={layer_name}",
            title,
            "wms"
        )
        if layer.isValid():
            QgsProject.instance().addMapLayer(layer)
            self.show_success("Layer loaded successfully")
        else:
            self.show_error("WMS Error", "Failed to load WMS layer")

    def load_wfs_layer(self, url, layer_name, title):
        layer = QgsVectorLayer(
            f"url={url}&typename={layer_name}",
            title,
            "WFS"
        )
        if layer.isValid():
            QgsProject.instance().addMapLayer(layer)
            self.show_success("WFS Layer loaded successfully")
        else:
            self.show_error("WFS Error", "Failed to load WFS layer")

    def download_and_load_shapefile(self, url, title):
        temp_dir = tempfile.mkdtemp()
        zip_path = os.path.join(temp_dir, "data.zip")
        self.try_download(url, zip_path, temp_dir, title, verify_ssl=self.api_client.session.verify)

    def try_download(self, url, zip_path, temp_dir, title, verify_ssl=True):
        self.downloader = DataLoader(url, zip_path, verify_ssl=verify_ssl)
        self.downloader.progress.connect(self.progress_bar.setValue)
        self.downloader.finished.connect(lambda path, success: 
            self.handle_shapefile_download(path, success, temp_dir, title, url, verify_ssl))
        
        self.progress_bar.setRange(0, 100)
        self.progress_bar.show()
        self.downloader.start()

    def handle_shapefile_download(self, path, success, temp_dir, title, url, verify_ssl):
        self.progress_bar.hide()
        
        if not success:
            error_msg = path
            if verify_ssl and "SSL" in error_msg:
                reply = QMessageBox.question(
                    self,
                    "SSL Certificate Error",
                    "Failed to verify SSL certificate. Would you like to try downloading without SSL verification?",
                    QMessageBox.Yes | QMessageBox.No
                )
                if reply == QMessageBox.Yes:
                    self.try_download(url, os.path.join(temp_dir, "data.zip"), temp_dir, title, verify_ssl=False)
                    return
            self.show_error("Download Error", error_msg)
            return
            
        try:
            with zipfile.ZipFile(path, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)
                
            data_file = None
            for file in os.listdir(temp_dir):
                if file.endswith(".shp") or file.endswith(".gpkg"):
                    data_file = os.path.join(temp_dir, file)
                    break
                    
            if not data_file:
                raise Exception("No map data found in download")
                
            layer = QgsVectorLayer(data_file, title, "ogr")
            if layer.isValid():
                QgsProject.instance().addMapLayer(layer)
                self.show_success("Shapefile loaded successfully")
            else:
                raise Exception("Invalid shapefile")
                
        except Exception as e:
            self.show_error("Shapefile Error", str(e))
            try:
                import shutil
                shutil.rmtree(temp_dir)
            except:
                pass

    def prev_page(self):
        if self.current_page > 1:
            self.current_page -= 1
            self.search()
            
    def next_page(self):
        if self.current_page < self.total_pages:
            self.current_page += 1
            self.search()

    def show_error(self, title, message):
        QMessageBox.critical(self, title, message)
        
    def show_success(self, message):
        if self.iface:
            self.iface.messageBar().pushMessage("Success", message, level=Qgis.Success)
