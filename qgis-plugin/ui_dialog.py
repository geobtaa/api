import json
import os
import tempfile
import webbrowser
import zipfile

from qgis.core import Qgis, QgsProject, QgsRasterLayer, QgsSettings, QgsVectorLayer
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QIcon, QPixmap
from qgis.PyQt.QtWidgets import (
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

try:
    from .api_client import BtaaApiClient
    from .downloader import DataLoader
    from .settings_dialog import BtaaSettingsDialog
except ImportError:
    from api_client import BtaaApiClient
    from downloader import DataLoader
    from settings_dialog import BtaaSettingsDialog


class GeodataSearchDialog(QDialog):
    def __init__(self, iface, parent=None):
        super().__init__(parent)
        self.iface = iface
        self.setWindowTitle("BTAA Geoportal Search")
        self.resize(900, 600)

        icon_path = os.path.join(os.path.dirname(__file__), "icon.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self.settings = QgsSettings()
        self.api_url = self.settings.value(
            "btaa_plugin/api_url", "https://lib-btaageoapi-dev-app-01.oit.umn.edu/api/v1"
        )
        self.api_client = BtaaApiClient(self.api_url)

        # UI Setup
        self.setStyleSheet("""
            QDialog { background-color: #f7f9fa; }
            QFrame { background-color: #ffffff; border: 1px solid #e1e4e8; border-radius: 6px; }
            QLabel { border: none; }
            QPushButton { background-color: #0366d6; color: white; border: none; padding: 6px 16px; border-radius: 6px; font-weight: bold; }
            QPushButton:hover { background-color: #005cc5; }
            QPushButton:disabled { background-color: #94d3a2; color: #ffffff; }
            QLineEdit, QComboBox { padding: 6px; border: 1px solid #d1d5da; border-radius: 4px; background-color: white; color: black; }
            QComboBox QAbstractItemView { background-color: white; color: black; selection-background-color: #0366d6; selection-color: white; }
            QListWidget { border: none; outline: none; }
            QListWidget::item { padding: 8px; border-bottom: 1px solid #eaecef; color: black; }
            QListWidget::item:selected { background-color: #f1f8ff; color: #0366d6; font-weight: bold; }
        """)

        layout = QVBoxLayout()

        # Top Header (Search bar, settings)
        header_frame = QFrame()
        header_frame.setStyleSheet(
            "QFrame { background-color: #002855; border-radius: 4px; padding: 4px; } "
            "QLabel { color: white; font-weight: bold; font-size: 16px; border: None; } "
            "QLineEdit { padding: 6px; border-radius: 12px; font-weight: normal; color: black; background: white; border: None; }"
        )

        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(10, 10, 10, 10)

        self.banner_label = QLabel()
        icon_path = os.path.join(os.path.dirname(__file__), "btaa-logo.png")
        if os.path.exists(icon_path):
            pixmap = QPixmap(icon_path)
            scaled_pixmap = pixmap.scaledToHeight(45, Qt.SmoothTransformation)
            self.banner_label.setPixmap(scaled_pixmap)
            self.banner_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        header_layout.addWidget(self.banner_label)

        self.header_title = QLabel(" Geoportal")
        header_layout.addWidget(self.header_title)

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search for geospatial data (e.g., Minnesota)")
        self.search_box.returnPressed.connect(self.perform_search)
        header_layout.addWidget(self.search_box, 1)

        self.search_button = QPushButton("Search")
        self.search_button.setStyleSheet(
            "QPushButton { background-color: white; color: #002855; border-radius: 12px; font-weight: bold; padding: 6px 16px; } QPushButton:hover { background-color: #e0e0e0; }"
        )
        self.search_button.clicked.connect(self.perform_search)
        header_layout.addWidget(self.search_button)

        self.settings_button = QPushButton("⚙️ Settings")
        self.settings_button.setStyleSheet(
            "QPushButton { background-color: transparent; color: white; border-radius: 12px; font-weight: normal; padding: 6px 12px; } QPushButton:hover { background-color: #004080; }"
        )
        self.settings_button.clicked.connect(self.open_settings)
        header_layout.addWidget(self.settings_button)

        header_frame.setLayout(header_layout)
        layout.addWidget(header_frame)

        # Active Constraints
        self.active_filters_box = QFrame()
        self.active_filters_box.setStyleSheet(
            "QFrame { background: #f0f4f8; border: 1px solid #dcdcdc; border-radius: 4px; } QLabel { color: #333; font-size: 12px;}"
        )
        active_filters_layout = QHBoxLayout()
        active_filters_layout.setContentsMargins(10, 6, 10, 6)
        self.active_filters_label = QLabel("<b>Active Filters:</b> None")
        active_filters_layout.addWidget(self.active_filters_label)
        self.active_filters_box.setLayout(active_filters_layout)
        self.active_filters_box.hide()
        layout.addWidget(self.active_filters_box)

        # Main Body
        main_layout = QHBoxLayout()

        # Left Panel (Facets)
        facets_frame = QFrame()
        facets_layout = QVBoxLayout()
        facets_layout.setContentsMargins(15, 15, 15, 15)

        facets_label = QLabel("<b>Filters</b>")
        facets_layout.addWidget(facets_label)

        self.place_combo = QComboBox()
        self.place_combo.addItem("All Places")
        self.place_combo.currentIndexChanged.connect(self.perform_search)
        facets_layout.addWidget(QLabel("Place:"))
        facets_layout.addWidget(self.place_combo)

        self.resource_class_combo = QComboBox()
        self.resource_class_combo.addItem("All Resource Classes")
        self.resource_class_combo.currentIndexChanged.connect(self.perform_search)
        facets_layout.addWidget(QLabel("Resource Class:"))
        facets_layout.addWidget(self.resource_class_combo)

        self.resource_type_combo = QComboBox()
        self.resource_type_combo.addItem("All Resource Types")
        self.resource_type_combo.currentIndexChanged.connect(self.perform_search)
        facets_layout.addWidget(QLabel("Resource Type:"))
        facets_layout.addWidget(self.resource_type_combo)

        self.language_combo = QComboBox()
        self.language_combo.addItem("All Languages")
        self.language_combo.currentIndexChanged.connect(self.perform_search)
        facets_layout.addWidget(QLabel("Language:"))
        facets_layout.addWidget(self.language_combo)

        self.creator_combo = QComboBox()
        self.creator_combo.addItem("All Creators")
        self.creator_combo.currentIndexChanged.connect(self.perform_search)
        facets_layout.addWidget(QLabel("Creator:"))
        facets_layout.addWidget(self.creator_combo)

        self.publisher_combo = QComboBox()
        self.publisher_combo.addItem("All Publishers")
        self.publisher_combo.currentIndexChanged.connect(self.perform_search)
        facets_layout.addWidget(QLabel("Publisher:"))
        facets_layout.addWidget(self.publisher_combo)

        self.provider_combo = QComboBox()
        self.provider_combo.addItem("All Providers")
        self.provider_combo.currentIndexChanged.connect(self.perform_search)
        facets_layout.addWidget(QLabel("Provider:"))
        facets_layout.addWidget(self.provider_combo)

        facets_layout.addStretch()
        facets_frame.setLayout(facets_layout)
        facets_frame.setFixedWidth(220)
        main_layout.addWidget(facets_frame)

        # Middle Panel (Results)
        results_frame = QFrame()
        results_layout_inner = QVBoxLayout()
        results_layout_inner.setContentsMargins(0, 0, 0, 0)

        results_top_layout = QHBoxLayout()
        results_top_layout.setContentsMargins(15, 10, 15, 10)
        self.result_count_label = QLabel("<b>0 results</b>")
        results_top_layout.addWidget(self.result_count_label)

        results_top_layout.addStretch()

        self.sort_combo = QComboBox()
        self.sort_combo.addItems(
            [
                "Relevance",
                "Year (Newest first)",
                "Year (Oldest first)",
                "Title (A-Z)",
                "Title (Z-A)",
            ]
        )
        self.sort_combo.currentIndexChanged.connect(self.perform_search)
        results_top_layout.addWidget(QLabel("Sort by:"))
        results_top_layout.addWidget(self.sort_combo)

        results_layout_inner.addLayout(results_top_layout)

        self.results_list = QListWidget()
        self.results_list.itemClicked.connect(self.show_preview)
        self.results_list.itemDoubleClicked.connect(self.load_selected_layer)
        results_layout_inner.addWidget(self.results_list, 1)  # stretch 1

        pagination_layout = QHBoxLayout()
        pagination_layout.setContentsMargins(15, 10, 15, 15)
        self.prev_button = QPushButton("Previous")
        self.prev_button.clicked.connect(self.prev_page)
        self.next_button = QPushButton("Next")
        self.next_button.clicked.connect(self.next_page)
        self.page_label = QLabel("Page 1")
        self.page_label.setAlignment(Qt.AlignCenter)
        pagination_layout.addWidget(self.prev_button)
        pagination_layout.addWidget(self.page_label, 1)
        pagination_layout.addWidget(self.next_button)
        results_layout_inner.addLayout(pagination_layout)

        results_frame.setLayout(results_layout_inner)
        main_layout.addWidget(results_frame, 2)  # stretch 2

        # Right Panel (Preview)
        preview_frame = QFrame()
        preview_layout = QVBoxLayout()
        preview_layout.setContentsMargins(15, 15, 15, 15)

        self.preview_image = QLabel()
        self.preview_image.setAlignment(Qt.AlignCenter)
        self.preview_image.setMinimumSize(250, 250)

        self.open_browser_button = QPushButton("View at BTAA Geoportal")
        self.open_browser_button.hide()
        self.open_browser_button.clicked.connect(self.open_current_in_browser)

        self.preview_text = QLabel()
        self.preview_text.setWordWrap(True)
        self.preview_text.setAlignment(Qt.AlignTop)

        preview_layout.addWidget(self.preview_image)
        preview_layout.addWidget(self.open_browser_button)
        preview_layout.addWidget(self.preview_text)
        preview_layout.addStretch()
        preview_frame.setLayout(preview_layout)
        preview_frame.setFixedWidth(300)
        main_layout.addWidget(preview_frame)

        layout.addLayout(main_layout, 1)

        self.progress_bar = QProgressBar()
        self.progress_bar.hide()
        layout.addWidget(self.progress_bar)

        self.setLayout(layout)

        self.current_results = []
        self.current_page = 1
        self.total_pages = 1
        self.per_page = 20

        # Load facets slightly delayed to ensure UI is visible if used outside __init__ or synchronously
        self.load_facets()

    def open_settings(self):
        dialog = BtaaSettingsDialog(self)
        if dialog.exec_():
            self.api_url = self.settings.value(
                "btaa_plugin/api_url", "https://lib-btaageoapi-dev-app-01.oit.umn.edu/api/v1"
            )
            self.api_client = BtaaApiClient(self.api_url)
            self.load_facets()

    def update_facets_from_data(self, included_data):
        try:
            places = []
            resource_classes = []
            resource_types = []
            languages = []
            creators = []
            publishers = []
            providers = []
            for facet in included_data:
                if facet.get("id") == "dct_spatial_sm":
                    places = [
                        item[0] for item in facet.get("attributes", {}).get("items", []) if item
                    ]
                elif facet.get("id") == "gbl_resourceClass_sm":
                    resource_classes = [
                        item[0] for item in facet.get("attributes", {}).get("items", []) if item
                    ]
                elif facet.get("id") == "gbl_resourceType_sm":
                    resource_types = [
                        item[0] for item in facet.get("attributes", {}).get("items", []) if item
                    ]
                elif facet.get("id") == "dct_language_sm":
                    languages = [
                        item[0] for item in facet.get("attributes", {}).get("items", []) if item
                    ]
                elif facet.get("id") == "dct_creator_sm":
                    creators = [
                        item[0] for item in facet.get("attributes", {}).get("items", []) if item
                    ]
                elif facet.get("id") == "dct_publisher_sm":
                    publishers = [
                        item[0] for item in facet.get("attributes", {}).get("items", []) if item
                    ]
                elif facet.get("id") == "schema_provider_s":
                    providers = [
                        item[0] for item in facet.get("attributes", {}).get("items", []) if item
                    ]

            def populate_combo(combo, default_text, items):
                current_selection = combo.currentText()
                combo.blockSignals(True)
                combo.clear()
                combo.addItem(default_text)

                # Make sure the current selection is kept if it was already filtering things
                if current_selection != default_text and current_selection not in items:
                    combo.addItem(current_selection)

                combo.addItems(items)

                index = combo.findText(current_selection)
                if index >= 0:
                    combo.setCurrentIndex(index)
                else:
                    combo.setCurrentIndex(0)

                combo.blockSignals(False)

            populate_combo(self.place_combo, "All Places", places)
            populate_combo(self.resource_class_combo, "All Resource Classes", resource_classes)
            populate_combo(self.resource_type_combo, "All Resource Types", resource_types)
            populate_combo(self.language_combo, "All Languages", languages)
            populate_combo(self.creator_combo, "All Creators", creators)
            populate_combo(self.publisher_combo, "All Publishers", publishers)
            populate_combo(self.provider_combo, "All Providers", providers)

        except Exception as e:
            self.show_error("Error loading facets", str(e))

    def load_facets(self):
        try:
            data = self.api_client.get_facets()
            self.update_facets_from_data(data.get("included", []))
        except Exception as e:
            self.show_error("Error loading facets", str(e))

    def perform_search(self):
        self.current_page = 1
        self.search()

    def search(self):
        search_term = self.search_box.text()

        self.progress_bar.setRange(0, 0)
        self.progress_bar.show()
        self.search_button.setEnabled(False)

        params = {"q": search_term, "page": self.current_page, "per_page": self.per_page}

        active_filters = []
        if search_term:
            active_filters.append(f"Search: <b>'{search_term}'</b>")

        place = self.place_combo.currentText()
        if place != "All Places":
            params["include_filters[dct_spatial_sm][]"] = place
            active_filters.append(f"Place: {place}")

        resource_class = self.resource_class_combo.currentText()
        if resource_class != "All Resource Classes":
            params["include_filters[gbl_resourceClass_sm][]"] = resource_class
            active_filters.append(f"Resource Class: {resource_class}")

        resource_type = self.resource_type_combo.currentText()
        if resource_type != "All Resource Types":
            params["include_filters[gbl_resourceType_sm][]"] = resource_type
            active_filters.append(f"Resource Type: {resource_type}")

        language = self.language_combo.currentText()
        if language != "All Languages":
            params["include_filters[dct_language_sm][]"] = language
            active_filters.append(f"Language: {language}")

        creator = self.creator_combo.currentText()
        if creator != "All Creators":
            params["include_filters[dct_creator_sm][]"] = creator
            active_filters.append(f"Creator: {creator}")

        publisher = self.publisher_combo.currentText()
        if publisher != "All Publishers":
            params["include_filters[dct_publisher_sm][]"] = publisher
            active_filters.append(f"Publisher: {publisher}")

        provider = self.provider_combo.currentText()
        if provider != "All Providers":
            params["include_filters[schema_provider_s][]"] = provider
            active_filters.append(f"Provider: {provider}")

        sort_choice = self.sort_combo.currentText()
        if sort_choice == "Year (Newest first)":
            params["sort"] = "year_desc"
        elif sort_choice == "Year (Oldest first)":
            params["sort"] = "year_asc"
        elif sort_choice == "Title (A-Z)":
            params["sort"] = "title_asc"
        elif sort_choice == "Title (Z-A)":
            params["sort"] = "title_desc"
        else:
            params["sort"] = "relevance"

        if active_filters:
            self.active_filters_box.show()
            self.active_filters_label.setText(
                "<b>Active Filters:</b> " + " | ".join(active_filters)
            )
        else:
            self.active_filters_box.hide()

        try:
            data = self.api_client.search(params)

            # Dynamically push refreshed facets from current search query back to combo boxes
            self.update_facets_from_data(data.get("included", []))

            meta = data.get("meta", {})
            self.total_pages = meta.get("totalPages", 1)
            total_count = meta.get("totalCount", 0)

            self.result_count_label.setText(f"<b>{total_count:,} results</b>")
            self.page_label.setText(f"Page {self.current_page} of {self.total_pages}")
            self.prev_button.setEnabled(self.current_page > 1)
            self.next_button.setEnabled(self.current_page < self.total_pages)

            self.results_list.clear()
            self.current_results = []

            for item in data.get("data", []):
                attributes = item.get("attributes", {}).get("ogm", {})
                title = attributes.get("dct_title_s", "Untitled")
                if isinstance(title, list):
                    title = title[0] if title else "Untitled"
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
        desc_list = attributes.get("dct_description_sm", [])
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
            self.iface.messageBar().pushMessage(
                "Information",
                "This dataset cannot be loaded directly as a layer. Opening in web browser instead.",
                level=Qgis.Info,
            )
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
            catalog_base = self.api_url.replace("/api/v1", "/resources")
            url = f"{catalog_base}/{item_id}"
            webbrowser.open(url)
        else:
            self.show_error("Error", "Could not find resource ID to open.")

    def load_wms_layer(self, url, layer_name, title):
        layer = QgsRasterLayer(f"url={url}&layers={layer_name}", title, "wms")
        if layer.isValid():
            QgsProject.instance().addMapLayer(layer)
            self.show_success("Layer loaded successfully")
        else:
            self.show_error("WMS Error", "Failed to load WMS layer")

    def load_wfs_layer(self, url, layer_name, title):
        layer = QgsVectorLayer(f"url={url}&typename={layer_name}", title, "WFS")
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
        self.downloader.finished.connect(
            lambda path, success: self.handle_shapefile_download(
                path, success, temp_dir, title, url, verify_ssl
            )
        )

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
                    QMessageBox.Yes | QMessageBox.No,
                )
                if reply == QMessageBox.Yes:
                    self.try_download(
                        url, os.path.join(temp_dir, "data.zip"), temp_dir, title, verify_ssl=False
                    )
                    return
            self.show_error("Download Error", error_msg)
            return

        try:
            with zipfile.ZipFile(path, "r") as zip_ref:
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
