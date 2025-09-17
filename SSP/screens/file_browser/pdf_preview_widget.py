from PyQt5.QtWidgets import QWidget
from PyQt5.QtCore import Qt, QSize, QPoint, QPointF
from PyQt5.QtGui import QPainter, QPixmap, QColor, QTransform

class PDFPreviewWidget(QWidget):
    """Widget for displaying PDF previews with zoom and pan functionality."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._pixmap = None
        self._borderless = False
        
        # Zoom and pan properties
        self._zoom_factor = 1.0
        self._min_zoom = 0.5
        self._max_zoom = 5.0
        self._pan_offset = QPointF(0, 0)
        self._last_pan_point = QPoint()
        self._is_panning = False
        
        # Touch/mouse tracking
        self.setMouseTracking(True)
        
        self.setStyleSheet("""
            PDFPreviewWidget {
                background-color: #f9f9f9;
                border: 1px solid #ddd;
                border-radius: 4px;
            }
        """)

    def setPixmap(self, pixmap):
        """Sets the pixmap to display."""
        self._pixmap = pixmap
        # Reset zoom and pan when new pixmap is set
        self._zoom_factor = 1.0
        self._pan_offset = QPointF(0, 0)
        self.update()

    def clear(self):
        """Clears the current pixmap."""
        self._pixmap = None
        self._zoom_factor = 1.0
        self._pan_offset = QPointF(0, 0)
        self.update()

    def setBorderless(self, borderless=True):
        """Enable/disable borderless mode for maximum content area."""
        self._borderless = borderless
        if borderless:
            self.setStyleSheet("""
                PDFPreviewWidget {
                    background-color: white;
                    border: none;
                }
            """)
        else:
            self.setStyleSheet("""
                PDFPreviewWidget {
                    background-color: #f9f9f9;
                    border: 1px solid #ddd;
                    border-radius: 4px;
                }
            """)

    def zoomIn(self):
        """Zooms in by 25%."""
        self._zoom_factor = min(self._zoom_factor * 1.25, self._max_zoom)
        self.update()

    def zoomOut(self):
        """Zooms out by 25%."""
        self._zoom_factor = max(self._zoom_factor / 1.25, self._min_zoom)
        self.update()

    def resetZoom(self):
        """Resets zoom to 100%."""
        self._zoom_factor = 1.0
        self._pan_offset = QPointF(0, 0)
        self.update()

    def wheelEvent(self, event):
        """Handles mouse wheel events for zooming."""
        if event.angleDelta().y() > 0:
            self.zoomIn()
        else:
            self.zoomOut()
        event.accept()

    def mousePressEvent(self, event):
        """Handles mouse press events for panning."""
        if event.button() == Qt.LeftButton:
            self._is_panning = True
            self._last_pan_point = event.pos()
            self.setCursor(Qt.ClosedHandCursor)

    def mouseMoveEvent(self, event):
        """Handles mouse move events for panning."""
        if self._is_panning:
            delta = event.pos() - self._last_pan_point
            self._pan_offset += delta
            self._last_pan_point = event.pos()
            self.update()
        else:
            self.setCursor(Qt.OpenHandCursor)

    def mouseReleaseEvent(self, event):
        """Handles mouse release events."""
        if event.button() == Qt.LeftButton:
            self._is_panning = False
            self.setCursor(Qt.ArrowCursor)

    def paintEvent(self, event):
        """Paints the widget with the current pixmap."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Fill background
        if self._borderless:
            painter.fillRect(self.rect(), QColor(255, 255, 255))
        else:
            painter.fillRect(self.rect(), QColor(249, 249, 249))
        
        if self._pixmap is None:
            return
        
        # Calculate scaled pixmap size
        pixmap_size = self._pixmap.size()
        scaled_size = QSize(
            int(pixmap_size.width() * self._zoom_factor),
            int(pixmap_size.height() * self._zoom_factor)
        )
        
        # Calculate position to center the pixmap
        widget_rect = self.rect()
        x = (widget_rect.width() - scaled_size.width()) // 2 + int(self._pan_offset.x())
        y = (widget_rect.height() - scaled_size.height()) // 2 + int(self._pan_offset.y())
        
        # Draw the pixmap
        painter.drawPixmap(x, y, scaled_size.width(), scaled_size.height(), self._pixmap)

    def getZoomFactor(self):
        """Returns the current zoom factor."""
        return self._zoom_factor

    def sizeHint(self):
        """Returns the preferred size of the widget."""
        if self._pixmap:
            return self._pixmap.size()
        return QSize(400, 600)
