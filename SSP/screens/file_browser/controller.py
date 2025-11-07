import os
from PyQt5.QtWidgets import QWidget, QMessageBox
from PyQt5.QtCore import pyqtSignal, QTimer
from .model import FileBrowserModel
from .view import FileBrowserView


class FileBrowserController(QWidget):
    pdf_selected = pyqtSignal(dict)

    def __init__(self, main_app):
        super().__init__()
        self.main_app = main_app

        self.model = FileBrowserModel()
        self.view = FileBrowserView()

        self.timeout_timer = QTimer()
        self.timeout_timer.setSingleShot(True)
        self.timeout_timer.timeout.connect(self._on_timeout)

        self.setLayout(self.view.main_layout)

        self._connect_signals()
        self._load_pdf_files()

    def _connect_signals(self):
        self.view.back_to_idle_clicked.connect(self._go_back_to_idle)
        self.view.continue_button_clicked.connect(self._continue_to_payment)
        self.view.pdf_button_clicked.connect(self.model.select_pdf)

        self.view.single_page_clicked.connect(self._set_single_page_view)
        self.view.multipage_clicked.connect(self._set_multipage_view)
        self.view.select_all_clicked.connect(self._select_all_pages)
        self.view.deselect_all_clicked.connect(self._deselect_all_pages)
        self.view.prev_page_clicked.connect(self._prev_page)
        self.view.next_page_clicked.connect(self._next_page)
        self.view.prev_grid_page_clicked.connect(self._prev_grid_page)
        self.view.next_grid_page_clicked.connect(self._next_grid_page)
        self.view.page_widget_clicked.connect(self._page_widget_clicked)
        self.view.page_checkbox_clicked.connect(self._page_checkbox_clicked)
        self.view.single_page_checkbox_clicked.connect(self._single_page_checkbox_clicked)

        self.view.back_to_idle_clicked.connect(self._reset_timeout)
        self.view.continue_button_clicked.connect(self._reset_timeout)
        self.view.pdf_button_clicked.connect(self._reset_timeout)
        self.view.single_page_clicked.connect(self._reset_timeout)
        self.view.multipage_clicked.connect(self._reset_timeout)
        self.view.select_all_clicked.connect(self._reset_timeout)
        self.view.deselect_all_clicked.connect(self._reset_timeout)
        self.view.prev_page_clicked.connect(self._reset_timeout)
        self.view.next_page_clicked.connect(self._reset_timeout)
        self.view.prev_grid_page_clicked.connect(self._reset_timeout)
        self.view.next_grid_page_clicked.connect(self._reset_timeout)
        self.view.page_widget_clicked.connect(self._reset_timeout)
        self.view.page_checkbox_clicked.connect(self._reset_timeout)
        self.view.single_page_checkbox_clicked.connect(self._reset_timeout)

        self.model.files_loaded.connect(self.view.load_pdf_files)
        self.model.pdf_selected.connect(self.view.select_pdf)
        self.model.error_occurred.connect(self._show_error)

    def _load_pdf_files(self):
        self.model.load_pdf_files()

    def _go_back_to_idle(self):
        self.main_app.show_screen('idle')

    def _continue_to_payment(self):
        print(f"PDF: {self.view.selected_pdf}")

        if not self.view.selected_pdf:
            QMessageBox.warning(self, "No PDF Selected", "Please select a PDF file.")
            return

        selected_pages_list = [page for page, selected in self.view.selected_pages.items() if selected]
        print(f"Selected pages list: {selected_pages_list}")

        if not selected_pages_list:
            QMessageBox.warning(self, "No Pages Selected", "Please select at least one page to print.")
            return

        usb_manager = self.main_app.usb_screen.model.usb_manager

        copied_file = None
        if usb_manager and hasattr(usb_manager, 'verify_file_in_session'):
            current_path = self.view.selected_pdf.get('path') if isinstance(self.view.selected_pdf, dict) else None
            if current_path and usb_manager.verify_file_in_session(current_path):
                print(f"File already in session directory")
                copied_file = dict(self.view.selected_pdf)

        if not copied_file:
            print(f"Copying file: {self.view.selected_pdf['filename']}")
            if usb_manager and hasattr(usb_manager, 'copy_selected_file'):
                copied_file = usb_manager.copy_selected_file(self.view.selected_pdf)
            else:
                QMessageBox.critical(self, "USB Error", "USB manager is not available. Please try again.")
                return

        if not copied_file:
            QMessageBox.critical(self, "File Copy Error", "Failed to copy the selected PDF file.")
            return

        file_path = copied_file.get('path') if isinstance(copied_file, dict) else None
        if not file_path or not os.path.exists(file_path):
            QMessageBox.critical(self, "File Not Found", "The copied PDF file could not be found. Please try again.")
            return

        if usb_manager and hasattr(usb_manager, 'verify_file_in_session'):
            if not usb_manager.verify_file_in_session(file_path):
                QMessageBox.critical(self, "Invalid File", "The copied PDF is not available in the current session.")
                return

        print(f"Calling set_pdf_data using: {copied_file['filename']} and pages: {selected_pages_list}")
        options_screen = self.main_app.printing_options_screen
        options_screen.set_pdf_data(copied_file, selected_pages_list)
        self.main_app.show_screen('printing_options')

    def _show_error(self, error_message):
        QMessageBox.critical(self, "Error", error_message)

    def _set_single_page_view(self):
        self.view.set_single_page_view()

    def _set_multipage_view(self):
        self.view.set_all_pages_view()

    def _select_all_pages(self):
        self.view.select_all_pages()

    def _deselect_all_pages(self):
        self.view.deselect_all_pages()

    def _prev_page(self):
        if self.view.single_page_index > 1:
            self.view.single_page_index -= 1
            self.view.show_single_page()

    def _next_page(self):
        if self.view.selected_pdf and self.view.single_page_index < self.view.selected_pdf['pages']:
            self.view.single_page_index += 1
            self.view.show_single_page()

    def _prev_grid_page(self):
        if self.view.current_grid_page > 1:
            self.view.current_grid_page -= 1
            self.view.show_pdf_preview()

    def _next_grid_page(self):
        if not self.view.selected_pdf:
            return
        total_doc_pages = self.view.selected_pdf['pages']
        total_grid_pages = (total_doc_pages + self.view.ITEMS_PER_GRID_PAGE - 1) // self.view.ITEMS_PER_GRID_PAGE
        if self.view.current_grid_page < total_grid_pages:
            self.view.current_grid_page += 1
            self.view.show_pdf_preview()

    def _page_widget_clicked(self, page_num):
        self.view.single_page_index = page_num
        self.view.set_single_page_view()

    def _page_checkbox_clicked(self, page_num, selected):
        self.view.selected_pages[page_num] = selected
        if self.view.selected_pdf:
            self.view.pdf_page_selections[self.view.selected_pdf['path']] = self.view.selected_pages.copy()
        self.view.update_selected_count()
        if self.view.view_mode == 'single' and page_num == self.view.single_page_index:
            self.view.single_page_checkbox.blockSignals(True)
            self.view.single_page_checkbox.setChecked(selected)
            self.view.single_page_checkbox.blockSignals(False)

    def _single_page_checkbox_clicked(self, selected):
        if self.view.selected_pdf:
            self.view.selected_pages[self.view.single_page_index] = selected
            self.view.pdf_page_selections[self.view.selected_pdf['path']] = self.view.selected_pages.copy()
            self.view.update_selected_count()

    def load_pdf_files(self, pdf_files):
        self.model.load_pdf_files(pdf_files)

    def on_enter(self):
        self.timeout_timer.start(300000)
        print("File browser timeout started (5 minutes)")

    def on_leave(self):
        self.model.cleanup()
        self.timeout_timer.stop()

    def _on_timeout(self):
        print("File browser screen timeout - returning to idle screen")
        self.main_app.show_screen('idle')

    def _reset_timeout(self):
        self.timeout_timer.stop()
        self.timeout_timer.start(300000)
        print("File browser screen timeout reset")
    

