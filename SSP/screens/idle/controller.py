from PyQt5.QtWidgets import QWidget, QGridLayout, QDialog
from PyQt5.QtCore import Qt

from .model import IdleModel
from .view import IdleScreenView
from screens.dialogs.pin_dialog import PinDialogController as PinDialog

class IdleController(QWidget):
    def __init__(self, main_app, parent=None):
        super().__init__(parent)
        self.main_app = main_app
        
        self.model = IdleModel()
        self.view = IdleScreenView()
        
        layout = QGridLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.view, 0, 0)
        
        self._connect_signals()
    
    def _connect_signals(self):

        self.view.screen_touched.connect(self._handle_screen_touch)
        self.view.admin_button_clicked.connect(self._go_to_admin)
        
        self.model.background_image_loaded.connect(self.view.set_background_image)
        self.model.show_message.connect(self._show_message)
    
    def _handle_screen_touch(self, event):
        admin_button_geometry = self.view.get_admin_button_geometry()
        
        if self.model.validate_touch_interaction(event.pos(), admin_button_geometry):
            self._start_printing()
    
    def _start_printing(self):
        self.main_app.show_screen('usb')
    
    def _go_to_admin(self):
        try:
            print("Opening PIN dialog.")
            dialog = PinDialog(self)
            result = dialog.exec_()
            if result == QDialog.Accepted:
                print("PIN accepted")
                self.main_app.show_screen('admin')
            else:
                print("Incorrect PIN.")
        except Exception as e:
            print(f"Error in admin PIN dialog: {e}")

    def _show_message(self, title, text):
        print(f"{title}: {text}")
    
    def on_enter(self):
        print("Idle screen entered.")
        if self.main_app.check_paper_count_and_redirect():
            return 
    
    def on_leave(self):
        print("Idle screen left.")
