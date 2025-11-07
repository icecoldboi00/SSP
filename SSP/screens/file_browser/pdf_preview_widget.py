from PyQt5.QtWidgets import QWidget
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QPainter, QColor

class PDFPreviewWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._pixmap = None
        self._borderless = False
        
        self.setStyleSheet("""
            PDFPreviewWidget {
                background-color: #c4c4c4;
                border: 1px solid #ddd;
                border-radius: 4px;
            }
        """)

    def setPixmap(self, pixmap):
        self._pixmap = pixmap
        self.update()

    def clear(self):
        self._pixmap = None
        self.update()

    def setBorderless(self, borderless=True):
        self._borderless = borderless
        if borderless:
            self.setStyleSheet("""
                PDFPreviewWidget {
                    background-color: #c4c4c4;
                    border: none;
                }
            """)
        else:
            self.setStyleSheet("""
                PDFPreviewWidget {
                    background-color: #c4c4c4;
                    border: 1px solid #ddd;
                    border-radius: 4px;
                }
            """)

    def mousePressEvent(self, event):
        # Disable panning: do nothing special on mouse press
        self.setCursor(Qt.ArrowCursor)

    def mouseMoveEvent(self, event):
        # Disable panning: ignore drag and keep cursor default
        self.setCursor(Qt.ArrowCursor)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._is_panning = False
            self.setCursor(Qt.ArrowCursor)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Fill background with container tint so page edges are visible
        painter.fillRect(self.rect(), QColor(196, 196, 196))
        
        if self._pixmap is None:
            return
        
        # Calculate scaled pixmap size to fit entire page to widget
        pixmap_size = self._pixmap.size()
        widget_rect = self.rect()
        scale_w = widget_rect.width() / max(1, pixmap_size.width())
        scale_h = widget_rect.height() / max(1, pixmap_size.height())
        fit_scale = min(scale_w, scale_h)
        scaled_size = QSize(
            int(pixmap_size.width() * fit_scale),
            int(pixmap_size.height() * fit_scale)
        )
        
        # Calculate position to center the pixmap
        x = (widget_rect.width() - scaled_size.width()) // 2
        y = (widget_rect.height() - scaled_size.height()) // 2
        
        # Draw the pixmap
        painter.drawPixmap(x, y, scaled_size.width(), scaled_size.height(), self._pixmap)

    def sizeHint(self):
        """Returns the preferred size of the widget."""
        if self._pixmap:
            return self._pixmap.size()
        # Encourage tall previews so items fill the preview container height
        return QSize(360, 800)
