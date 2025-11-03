from PyQt5.QtCore import QObject, pyqtSignal

class IdleModel(QObject):
    def __init__(self):
        super().__init__()

    # If touch is on admin button, don't start the process. Admin button has its own click handler
    def validate_touch_interaction(self, event_pos, admin_button_geometry):
        if admin_button_geometry and admin_button_geometry.contains(event_pos):
            return False
        return True
