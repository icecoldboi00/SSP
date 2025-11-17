from PyQt5.QtWidgets import QWidget, QGridLayout, QDialog
from .model import IdleModel
from .view import IdleScreenView
from screens.dialogs.pin_dialog import PinDialogController as PinDialog

class IdleController(QWidget):
    def __init__(self, main_app):
        super().__init__()
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
    
    def _handle_screen_touch(self, event):
        admin_button_geometry = self.view.get_admin_button_geometry()
        
        if self.model.validate_touch_interaction(event.pos(), admin_button_geometry):
            self.main_app.show_screen('usb')
    
    def _go_to_admin(self):
        print("Opening PIN dialog.")
        dialog = PinDialog(self)
        result = dialog.exec_()
        if result == QDialog.Accepted:
            print("PIN accepted")
            self.main_app.show_screen('admin')
        else:
            print("Incorrect PIN.")

    def on_enter(self):
        print("Idle screen entered.")
        if self.main_app.check_paper_count_and_redirect(): # Check paper count or go to error screen if kulang
            return 
