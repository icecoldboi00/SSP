from PyQt5.QtWidgets import QWidget
from PyQt5.QtCore import Qt, QSize, QPoint, QPointF
from PyQt5.QtGui import QPainter, QPixmap, QColor, QTransform

class PDFPreviewWidget(QWidget):
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
        self._pixmap = pixmap
        # Reset zoom and pan when new pixmap is set
        self._zoom_factor = 1.0
        self._pan_offset = QPointF(0, 0)
        self.update()

    def clear(self):
        self._pixmap = None
        self._zoom_factor = 1.0
        self._pan_offset = QPointF(0, 0)
        self.update()

    def setBorderless(self, borderless=True):
        """Enable/disable borderless mode for maximum content area"""
        self._borderless = borderless
        if borderless:
            self.setStyleSheet("""
                PDFPreviewWidget {
                    background-color: white;
                    border: none;
                    border-radius: 0px;
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
        self.update()

    def zoomIn(self):
        """Zoom in by 25%"""
        self._zoom_factor = min(self._zoom_factor * 1.25, self._max_zoom)
        self._constrain_pan()
        self.update()

    def zoomOut(self):
        """Zoom out by 25%"""
        self._zoom_factor = max(self._zoom_factor / 1.25, self._min_zoom)
        self._constrain_pan()
        self.update()

    def resetZoom(self):
        """Reset zoom to fit the widget"""
        self._zoom_factor = 1.0
        self._pan_offset = QPointF(0, 0)
        self.update()

    def setZoomFactor(self, factor):
        """Set zoom factor directly"""
        self._zoom_factor = max(self._min_zoom, min(factor, self._max_zoom))
        self._constrain_pan()
        self.update()

    def getZoomFactor(self):
        """Get current zoom factor"""
        return self._zoom_factor

    def _constrain_pan(self):
        """Constrain pan offset to keep content visible"""
        if not self._pixmap:
            self._pan_offset = QPointF(0, 0)
            return

        widget_rect = self.rect()
        pixmap_size = self._pixmap.size()
        
        if self._borderless:
            content_rect = widget_rect
        else:
            padding = 15
            content_rect = widget_rect.adjusted(padding, padding, -padding, -padding)
        
        # Calculate the scaled pixmap size
        base_scale_x = content_rect.width() / pixmap_size.width()
        base_scale_y = content_rect.height() / pixmap_size.height()
        base_scale = min(base_scale_x, base_scale_y)
        
        final_scale = base_scale * self._zoom_factor
        
        scaled_width = pixmap_size.width() * final_scale
        scaled_height = pixmap_size.height() * final_scale
        
        # Calculate maximum pan offsets
        max_x_offset = max(0, (scaled_width - content_rect.width()) / 2)
        max_y_offset = max(0, (scaled_height - content_rect.height()) / 2)
        
        # Constrain pan offset
        self._pan_offset.setX(max(-max_x_offset, min(max_x_offset, self._pan_offset.x())))
        self._pan_offset.setY(max(-max_y_offset, min(max_y_offset, self._pan_offset.y())))

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self._pixmap:
            self._is_panning = True
            self._last_pan_point = event.pos()
            self.setCursor(Qt.ClosedHandCursor)

    def mouseMoveEvent(self, event):
        if self._is_panning and self._pixmap:
            delta = event.pos() - self._last_pan_point
            self._pan_offset += QPointF(delta.x(), delta.y())
            self._constrain_pan()
            self._last_pan_point = event.pos()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._is_panning = False
            self.setCursor(Qt.ArrowCursor)

    def enterEvent(self, event):
        if self._pixmap and self._zoom_factor > 1.0:
            self.setCursor(Qt.OpenHandCursor)

    def leaveEvent(self, event):
        self.setCursor(Qt.ArrowCursor)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        painter.setRenderHint(QPainter.Antialiasing)
        
        if self._borderless:
            # Borderless mode: fill with white background, no padding
            painter.fillRect(self.rect(), QColor("white"))
            
            if self._pixmap:
                widget_rect = self.rect()
                pixmap_size = self._pixmap.size()
                
                # No padding in borderless mode - use full widget area
                content_rect = widget_rect
                
                # Calculate base scaling to fit the pixmap in the full widget area
                base_scale_x = content_rect.width() / pixmap_size.width()
                base_scale_y = content_rect.height() / pixmap_size.height()
                base_scale = min(base_scale_x, base_scale_y)
                
                # Apply zoom factor
                final_scale = base_scale * self._zoom_factor
                
                # Calculate new dimensions
                new_width = int(pixmap_size.width() * final_scale)
                new_height = int(pixmap_size.height() * final_scale)
                
                # Center the pixmap in the widget and apply pan offset
                x = (content_rect.width() - new_width) // 2 + self._pan_offset.x()
                y = (content_rect.height() - new_height) // 2 + self._pan_offset.y()
                
                # Create clipping region to prevent drawing outside widget
                painter.setClipRect(content_rect)
                
                # Draw the pixmap
                painter.drawPixmap(int(x), int(y), new_width, new_height, self._pixmap)
                
            else:
                # Draw placeholder text when no pixmap
                painter.setPen(QColor("#888888"))
                painter.drawText(self.rect(), Qt.AlignCenter, "No preview available")
        else:
            # Original bordered mode with zoom support
            painter.fillRect(self.rect(), QColor("#f9f9f9"))
            
            if self._pixmap:
                widget_rect = self.rect()
                pixmap_size = self._pixmap.size()
                
                # Use padding for bordered mode
                padding = 15
                content_rect = widget_rect.adjusted(padding, padding, -padding, -padding)
                
                # Calculate base scaling to fit the pixmap in the content area
                safety_margin = 0.90  # Use 90% of available space
                
                base_scale_x = (content_rect.width() * safety_margin) / pixmap_size.width()
                base_scale_y = (content_rect.height() * safety_margin) / pixmap_size.height()
                base_scale = min(base_scale_x, base_scale_y)
                
                # Apply zoom factor
                final_scale = base_scale * self._zoom_factor
                
                # Calculate new dimensions
                new_width = int(pixmap_size.width() * final_scale)
                new_height = int(pixmap_size.height() * final_scale)
                
                # Center the pixmap in the content area and apply pan offset
                x = content_rect.x() + (content_rect.width() - new_width) // 2 + self._pan_offset.x()
                y = content_rect.y() + (content_rect.height() - new_height) // 2 + self._pan_offset.y()
                
                # Create clipping region to prevent drawing outside content area
                painter.setClipRect(content_rect)
                
                # Draw the pixmap
                painter.drawPixmap(int(x), int(y), new_width, new_height, self._pixmap)
                
            else:
                # Draw placeholder text when no pixmap
                painter.setPen(QColor("#888888"))
                painter.drawText(self.rect(), Qt.AlignCenter, "No preview available")
            
            # Draw border only in bordered mode
            painter.setClipping(False)  # Disable clipping for border
            painter.setPen(QColor("#cccccc"))
            painter.drawRect(self.rect().adjusted(0, 0, -1, -1))

    def sizeHint(self):
        return QSize(400, 500)