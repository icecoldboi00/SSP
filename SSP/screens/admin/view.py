# screens/admin/view.py

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QHBoxLayout, QFrame,
    QLineEdit, QMessageBox, QGroupBox
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QIntValidator, QPixmap, QPainter

class AdminScreenView(QWidget):
    """The user interface for the Admin Panel. Contains no logic."""
    back_clicked = pyqtSignal()
    view_data_logs_clicked = pyqtSignal()
    update_paper_clicked = pyqtSignal(str)
    reset_paper_clicked = pyqtSignal()

    def __init__(self, background_image_path=None):
        super().__init__()
        self.background_pixmap = QPixmap(background_image_path) if background_image_path else None
        self.setup_ui()

    def paintEvent(self, event):
        painter = QPainter(self)
        if self.background_pixmap:
            painter.drawPixmap(self.rect(), self.background_pixmap)
        else:
            painter.fillRect(self.rect(), Qt.GlobalColor.black)
        super().paintEvent(event)

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(50, 30, 50, 30)
        layout.setSpacing(20)

        title = QLabel("Admin Panel")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("color: white; font-size: 48px; font-weight: bold; text-shadow: 2px 2px 4px #000000;")

        content_frame = self._create_content_frame()
        
        back_button = QPushButton("← Back to Main Screen")
        back_button.setMinimumHeight(60)
        back_button.setCursor(Qt.PointingHandCursor)
        back_button.setStyleSheet("""
            QPushButton {
                background-color: #c83c3c; color: white; font-size: 20px; font-weight: bold;
                border: 1px solid #d85050; border-radius: 10px; padding: 10px;
            }
            QPushButton:hover { background-color: #e05a5a; }
        """)
        back_button.clicked.connect(self.back_clicked.emit)

        layout.addWidget(title)
        layout.addWidget(content_frame, 1)
        layout.addWidget(back_button)

    def _create_content_frame(self):
        frame = QFrame()
        frame.setObjectName("contentFrame")
        frame.setStyleSheet("""
            #contentFrame {
                background-color: rgba(15, 31, 0, 0.85);
                border: 1px solid rgba(42, 93, 26, 0.9);
                border-radius: 20px;
            }
        """)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(25)
        layout.addWidget(self._create_paper_management_group())
        layout.addWidget(self._create_system_data_group())
        return frame

    def _create_paper_management_group(self):
        group = QGroupBox("Paper Management")
        group.setStyleSheet(self._get_groupbox_style())
        layout = QVBoxLayout(group)
        layout.setSpacing(15)

        count_layout = QHBoxLayout()
        count_layout.addWidget(QLabel("Current Paper Count:", styleSheet="color: #e0e0e0; font-size: 18px;"))
        count_layout.addStretch()
        
        self.paper_count_input = QLineEdit()
        self.paper_count_input.setValidator(QIntValidator(0, 100))
        self.paper_count_input.setAlignment(Qt.AlignCenter)
        self.paper_count_input.setFixedWidth(100)
        self.paper_count_input.returnPressed.connect(
            lambda: self.update_paper_clicked.emit(self.paper_count_input.text())
        )
        count_layout.addWidget(self.paper_count_input)
        layout.addLayout(count_layout)

        button_layout = QHBoxLayout()
        update_paper_btn = QPushButton("Update Count", clicked=lambda: self.update_paper_clicked.emit(self.paper_count_input.text()))
        update_paper_btn.setStyleSheet(self._get_button_style("#ff9800", "#f57c00"))
        
        reset_paper_btn = QPushButton("Refill (Reset to 100)", clicked=self.reset_paper_clicked.emit)
        reset_paper_btn.setStyleSheet(self._get_button_style("#1e440a", "#2a5d1a"))
        
        button_layout.addStretch()
        button_layout.addWidget(update_paper_btn)
        button_layout.addWidget(reset_paper_btn)
        button_layout.addStretch()
        layout.addLayout(button_layout)
        
        return group

    def _create_system_data_group(self):
        group = QGroupBox("System & Data")
        group.setStyleSheet(self._get_groupbox_style())
        layout = QVBoxLayout(group)
        layout.setSpacing(15)

        transaction_btn = QPushButton("View System Data Logs", clicked=self.view_data_logs_clicked.emit)
        transaction_btn.setMinimumHeight(50)
        transaction_btn.setStyleSheet(self._get_button_style("#1e440a", "#2a5d1a", font_size="18px"))
        layout.addWidget(transaction_btn)

        ink_layout = QHBoxLayout()
        ink_layout.addWidget(QLabel("Ink Level Status:", styleSheet="color: #e0e0e0; font-size: 18px;"))
        ink_layout.addStretch()
        ink_layout.addWidget(QLabel("Monitoring Not Implemented", styleSheet="color: #999999; font-size: 18px; font-style: italic;"))
        layout.addLayout(ink_layout)
        
        return group

    def update_paper_count_display(self, count: int, color: str):
        """Updates the paper count input field and its style."""
        self.paper_count_input.setText(str(count))
        self.paper_count_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: #1f1f38; color: white; font-size: 18px;
                font-weight: bold; border: 3px solid {color}; border-radius: 8px;
                padding: 5px 10px;
            }}
            QLineEdit:focus {{ border: 3px solid #ff9800; }}
        """)

    def show_message_box(self, title: str, text: str):
        QMessageBox.warning(self, title, text)

    def _get_groupbox_style(self):
        return """ ... """ # Style string from original file

    def _get_button_style(self, bg_color, hover_color, font_size="16px"):
        return f""" ... """ # Style string from original file