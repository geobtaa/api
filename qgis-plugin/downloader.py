import os

import certifi
import requests
from qgis.PyQt.QtCore import QThread, pyqtSignal


class DataLoader(QThread):
    """Worker thread for downloading and loading data"""

    progress = pyqtSignal(int)
    finished = pyqtSignal(str, bool)

    def __init__(self, url, output_path, verify_ssl=True):
        super().__init__()
        self.url = url
        self.output_path = output_path
        self.verify_ssl = verify_ssl

    def run(self):
        try:
            response = requests.get(
                self.url,
                stream=True,
                verify=certifi.where() if self.verify_ssl else False,
                timeout=30,
            )
            response.raise_for_status()

            total_size = int(response.headers.get("content-length", 0))
            block_size = 1024
            downloaded = 0

            os.makedirs(os.path.dirname(self.output_path), exist_ok=True)

            with open(self.output_path, "wb") as f:
                for data in response.iter_content(block_size):
                    downloaded += len(data)
                    f.write(data)
                    if total_size:
                        percent = int((downloaded / total_size) * 100)
                        self.progress.emit(percent)

            self.finished.emit(self.output_path, True)

        except requests.exceptions.SSLError:
            self.finished.emit("SSL Certificate Verification Failed", False)
        except requests.exceptions.RequestException as e:
            self.finished.emit(f"Download failed: {str(e)}", False)
        except Exception as e:
            self.finished.emit(f"Error: {str(e)}", False)
