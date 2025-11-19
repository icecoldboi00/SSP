from PyQt5.QtCore import QObject, pyqtSignal
from managers.usb_file_manager import USBFileManager


class FileBrowserModel(QObject):
    files_loaded = pyqtSignal(list)
    pdf_selected = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.usb_manager = USBFileManager()
        self.pdf_files = []
        self.selected_pdf = None
        self._locked_path = None

    def load_pdf_files(self, pdf_files=None):
        try:
            if pdf_files is not None:
                self.pdf_files = pdf_files
                print(f"Loaded {len(pdf_files)} PDF files from external source")
            else:
                self.pdf_files = []
                print("Awaiting PDF files from USB controller")

            self.files_loaded.emit(self.pdf_files)
        except Exception as exc:
            self.error_occurred.emit(f"Error loading PDF files: {exc}")

    def select_pdf(self, pdf_data):
        self.selected_pdf = pdf_data
        self.pdf_selected.emit(pdf_data)

        path = pdf_data.get('path')
        if path:
            self.usb_manager.mark_file_in_use(path)
            self._locked_path = path

    def cleanup(self):
        if self._locked_path:
            try:
                self.usb_manager.mark_file_complete(self._locked_path)
            finally:
                self._locked_path = None