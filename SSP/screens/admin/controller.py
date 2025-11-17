from PyQt5.QtWidgets import QWidget, QGridLayout

from .model import AdminModel
from .view import AdminScreenView

class AdminController(QWidget):
    def __init__(self, main_app, parent=None):
        super().__init__(parent)
        self.main_app = main_app

        self.model = AdminModel()
        self.view = AdminScreenView()

        layout = QGridLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.view, 0, 0)
        
        self._connect_signals()

    # Shortcut calling (admin.db_manager) 
    @property
    def db_manager(self):
        return self.model.db_manager

    def _connect_signals(self):
        self.view.back_clicked.connect(self._go_back)
        self.view.view_data_logs_clicked.connect(self._show_data_viewer)

        self.view.paper_decreased.connect(self.model.decrease_paper_count)
        self.view.paper_increased.connect(self.model.increase_paper_count)
        self.view.reset_paper_clicked.connect(self.model.reset_paper_count)
        self.view.coin_1_decreased.connect(self.model.decrease_coin_1_count)
        self.view.coin_1_increased.connect(self.model.increase_coin_1_count)
        self.view.coin_5_decreased.connect(self.model.decrease_coin_5_count)
        self.view.coin_5_increased.connect(self.model.increase_coin_5_count)
        self.view.reset_coins_clicked.connect(self.model.reset_coin_counts)
        self.view.update_cmyk_clicked.connect(self.model.update_cmyk_levels)
        self.view.reset_cmyk_clicked.connect(self.model.reset_cmyk_levels)
        self.view.refresh_cmyk_clicked.connect(self.model.refresh_cmyk_levels)
        
        self.model.paper_count_changed.connect(self.view.update_paper_count_display)
        self.model.coin_count_changed.connect(self.view.update_coin_count_display)
        self.model.cmyk_levels_changed.connect(self.view.update_cmyk_display)
        self.model.show_message.connect(self.view.show_message_box)
    
    def on_enter(self):
        print("Admin screen entered. Refreshing data.")
        self.model.load_paper_count()
        self.model.load_coin_counts()
        self.model.load_cmyk_levels()
        print(f"Paper count: {self.model.db_manager.get_setting('paper_count', default=100)}")
    
    def get_paper_count(self) -> int: # Used in main_app
        fresh_count = self.model.db_manager.get_setting('paper_count', default=100)
        return fresh_count

    def _go_back(self):
        self.main_app.show_screen('idle')

    def _show_data_viewer(self):
        self.main_app.show_screen('data_viewer')
