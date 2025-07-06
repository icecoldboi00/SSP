from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QFrame, QGridLayout, QLineEdit,
                             QComboBox, QSpacerItem, QSizePolicy, QMessageBox,
                             QProgressBar)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QFont, QPixmap, QPainter

class PaymentCalculationDialog(QDialog):
    """Dialog for calculating printing costs and handling payment"""
    payment_completed = pyqtSignal(dict)  # Emits payment info when completed
    
    def __init__(self, pdf_data, parent=None):
        super().__init__(parent)
        self.pdf_data = pdf_data
        self.total_cost = 0
        self.setup_ui()
        self.calculate_cost()
        
    def setup_ui(self):
        self.setWindowTitle("Print Cost Calculator")
        self.setModal(True)
        self.setFixedSize(500, 600)
        self.setStyleSheet("""
            QDialog {
                background-color: #2b2b2b;
                color: white;
            }
        """)
        
        layout = QVBoxLayout()
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 30)
        
        # Header
        header = QLabel("📄 PRINT COST CALCULATION")
        header.setAlignment(Qt.AlignCenter)
        header.setStyleSheet("""
            QLabel {
                color: #4CAF50;
                font-size: 24px;
                font-weight: bold;
                margin: 10px 0;
                padding: 15px;
                border: 2px solid #4CAF50;
                border-radius: 10px;
                background-color: rgba(76, 175, 80, 0.1);
            }
        """)
        layout.addWidget(header)
        
        # PDF Info Section
        info_frame = QFrame()
        info_frame.setStyleSheet("""
            QFrame {
                background-color: #333;
                border-radius: 8px;
                padding: 15px;
            }
        """)
        info_layout = QVBoxLayout(info_frame)
        
        # File name
        filename_label = QLabel(f"📁 File: {self.pdf_data['filename']}")
        filename_label.setStyleSheet("color: white; font-size: 16px; font-weight: bold; margin: 5px 0;")
        filename_label.setWordWrap(True)
        
        # File size
        size_mb = self.pdf_data.get('size', 0) / (1024 * 1024)
        size_label = QLabel(f"💾 Size: {size_mb:.2f} MB")
        size_label.setStyleSheet("color: #ccc; font-size: 14px; margin: 5px 0;")
        
        # Page count
        self.pages_label = QLabel(f"📄 Pages: {self.pdf_data['pages']} pages")
        self.pages_label.setStyleSheet("color: #ccc; font-size: 14px; margin: 5px 0;")
        
        info_layout.addWidget(filename_label)
        info_layout.addWidget(size_label)
        info_layout.addWidget(self.pages_label)
        
        layout.addWidget(info_frame)
        
        # Pricing Options
        pricing_frame = QFrame()
        pricing_frame.setStyleSheet("""
            QFrame {
                background-color: #333;
                border-radius: 8px;
                padding: 15px;
            }
        """)
        pricing_layout = QVBoxLayout(pricing_frame)
        
        pricing_title = QLabel("💰 PRICING OPTIONS")
        pricing_title.setStyleSheet("color: #FFD700; font-size: 18px; font-weight: bold; margin-bottom: 10px;")
        pricing_layout.addWidget(pricing_title)
        
        # Print type selection
        print_type_layout = QHBoxLayout()
        print_type_label = QLabel("Print Type:")
        print_type_label.setStyleSheet("color: white; font-size: 14px;")
        
        self.print_type_combo = QComboBox()
        self.print_type_combo.addItems([
            "Black & White - ₱2.00 per page",
            "Color - ₱5.00 per page",
            "Premium Color - ₱8.00 per page"
        ])
        self.print_type_combo.setStyleSheet("""
            QComboBox {
                background-color: #444;
                color: white;
                border: 1px solid #666;
                border-radius: 4px;
                padding: 8px;
                font-size: 14px;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 5px solid white;
            }
        """)
        self.print_type_combo.currentTextChanged.connect(self.calculate_cost)
        
        print_type_layout.addWidget(print_type_label)
        print_type_layout.addWidget(self.print_type_combo)
        pricing_layout.addLayout(print_type_layout)
        
        # Paper size selection
        paper_size_layout = QHBoxLayout()
        paper_size_label = QLabel("Paper Size:")
        paper_size_label.setStyleSheet("color: white; font-size: 14px;")
        
        self.paper_size_combo = QComboBox()
        self.paper_size_combo.addItems([
            "A4 (Standard) - No extra charge",
            "Legal - +₱0.50 per page",
            "A3 - +₱2.00 per page"
        ])
        self.paper_size_combo.setStyleSheet("""
            QComboBox {
                background-color: #444;
                color: white;
                border: 1px solid #666;
                border-radius: 4px;
                padding: 8px;
                font-size: 14px;
            }
        """)
        self.paper_size_combo.currentTextChanged.connect(self.calculate_cost)
        
        paper_size_layout.addWidget(paper_size_label)
        paper_size_layout.addWidget(self.paper_size_combo)
        pricing_layout.addLayout(paper_size_layout)
        
        # Copies
        copies_layout = QHBoxLayout()
        copies_label = QLabel("Copies:")
        copies_label.setStyleSheet("color: white; font-size: 14px;")
        
        self.copies_input = QLineEdit("1")
        self.copies_input.setStyleSheet("""
            QLineEdit {
                background-color: #444;
                color: white;
                border: 1px solid #666;
                border-radius: 4px;
                padding: 8px;
                font-size: 14px;
            }
        """)
        self.copies_input.textChanged.connect(self.calculate_cost)
        
        copies_layout.addWidget(copies_label)
        copies_layout.addWidget(self.copies_input)
        pricing_layout.addLayout(copies_layout)
        
        layout.addWidget(pricing_frame)
        
        # Cost Breakdown
        cost_frame = QFrame()
        cost_frame.setStyleSheet("""
            QFrame {
                background-color: #1a4d1a;
                border: 2px solid #4CAF50;
                border-radius: 8px;
                padding: 15px;
            }
        """)
        cost_layout = QVBoxLayout(cost_frame)
        
        cost_title = QLabel("💵 COST BREAKDOWN")
        cost_title.setStyleSheet("color: #4CAF50; font-size: 18px; font-weight: bold; margin-bottom: 10px;")
        cost_layout.addWidget(cost_title)
        
        self.cost_details = QLabel()
        self.cost_details.setStyleSheet("color: white; font-size: 14px; line-height: 1.5;")
        cost_layout.addWidget(self.cost_details)
        
        self.total_label = QLabel()
        self.total_label.setStyleSheet("""
            QLabel {
                color: #FFD700;
                font-size: 20px;
                font-weight: bold;
                margin-top: 10px;
                padding: 10px;
                border: 2px solid #FFD700;
                border-radius: 6px;
                background-color: rgba(255, 215, 0, 0.1);
            }
        """)
        cost_layout.addWidget(self.total_label)
        
        layout.addWidget(cost_frame)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(15)
        
        cancel_btn = QPushButton("❌ Cancel")
        cancel_btn.setMinimumHeight(45)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #d32f2f;
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 16px;
                font-weight: bold;
                padding: 10px 20px;
            }
            QPushButton:hover {
                background-color: #f44336;
            }
        """)
        cancel_btn.clicked.connect(self.reject)
        
        self.proceed_btn = QPushButton("💳 Proceed to Payment")
        self.proceed_btn.setMinimumHeight(45)
        self.proceed_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 16px;
                font-weight: bold;
                padding: 10px 20px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        self.proceed_btn.clicked.connect(self.proceed_to_payment)
        
        button_layout.addWidget(cancel_btn)
        button_layout.addWidget(self.proceed_btn)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)
    
    def calculate_cost(self):
        """Calculate the total printing cost"""
        try:
            # Get values
            pages = self.pdf_data['pages']
            copies = int(self.copies_input.text() or "1")
            
            # Base cost per page
            print_type = self.print_type_combo.currentText()
            if "Black & White" in print_type:
                base_cost = 2.00
            elif "Color" in print_type and "Premium" not in print_type:
                base_cost = 5.00
            else:  # Premium Color
                base_cost = 8.00
            
            # Paper size additional cost
            paper_size = self.paper_size_combo.currentText()
            paper_cost = 0.00
            if "Legal" in paper_size:
                paper_cost = 0.50
            elif "A3" in paper_size:
                paper_cost = 2.00
            
            # Calculate totals
            cost_per_page = base_cost + paper_cost
            subtotal = pages * cost_per_page * copies
            
            # Add service fee (5%)
            service_fee = subtotal * 0.05
            self.total_cost = subtotal + service_fee
            
            # Update display
            cost_breakdown = f"""
📄 Pages: {pages} pages
🔢 Copies: {copies}
💰 Cost per page: ₱{cost_per_page:.2f}
➖➖➖➖➖➖➖➖➖➖➖➖
📊 Subtotal: ₱{subtotal:.2f}
🔧 Service Fee (5%): ₱{service_fee:.2f}
            """.strip()
            
            self.cost_details.setText(cost_breakdown)
            self.total_label.setText(f"💵 TOTAL AMOUNT: ₱{self.total_cost:.2f}")
            
        except ValueError:
            self.cost_details.setText("Please enter a valid number of copies")
            self.total_label.setText("💵 TOTAL AMOUNT: ₱0.00")
            self.total_cost = 0
    
    def proceed_to_payment(self):
        """Proceed to payment processing"""
        if self.total_cost <= 0:
            QMessageBox.warning(self, "Invalid Amount", "Please check your input values.")
            return
        
        # Create payment info
        payment_info = {
            'pdf_data': self.pdf_data,
            'print_type': self.print_type_combo.currentText(),
            'paper_size': self.paper_size_combo.currentText(),
            'copies': int(self.copies_input.text() or "1"),
            'total_cost': self.total_cost
        }
        
        # Show payment processing dialog
        payment_dialog = PaymentProcessingDialog(payment_info, self)
        if payment_dialog.exec_() == QDialog.Accepted:
            self.payment_completed.emit(payment_info)
            self.accept()

class PaymentProcessingDialog(QDialog):
    """Dialog for processing payment"""
    
    def __init__(self, payment_info, parent=None):
        super().__init__(parent)
        self.payment_info = payment_info
        self.setup_ui()
        self.start_payment_simulation()
    
    def setup_ui(self):
        self.setWindowTitle("Payment Processing")
        self.setModal(True)
        self.setFixedSize(450, 500)
        self.setStyleSheet("""
            QDialog {
                background-color: #2b2b2b;
                color: white;
            }
        """)
        
        layout = QVBoxLayout()
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 30)
        
        # Header
        header = QLabel("💳 PAYMENT PROCESSING")
        header.setAlignment(Qt.AlignCenter)
        header.setStyleSheet("""
            QLabel {
                color: #2196F3;
                font-size: 24px;
                font-weight: bold;
                margin: 10px 0;
                padding: 15px;
                border: 2px solid #2196F3;
                border-radius: 10px;
                background-color: rgba(33, 150, 243, 0.1);
            }
        """)
        layout.addWidget(header)
        
        # Payment Summary
        summary_frame = QFrame()
        summary_frame.setStyleSheet("""
            QFrame {
                background-color: #333;
                border-radius: 8px;
                padding: 15px;
            }
        """)
        summary_layout = QVBoxLayout(summary_frame)
        
        summary_title = QLabel("📋 PAYMENT SUMMARY")
        summary_title.setStyleSheet("color: #FFD700; font-size: 18px; font-weight: bold; margin-bottom: 10px;")
        summary_layout.addWidget(summary_title)
        
        # Payment details
        details_text = f"""
📄 File: {self.payment_info['pdf_data']['filename']}
🖨️ Print Type: {self.payment_info['print_type'].split(' - ')[0]}
📏 Paper Size: {self.payment_info['paper_size'].split(' - ')[0]}
🔢 Copies: {self.payment_info['copies']}
💰 Total Amount: ₱{self.payment_info['total_cost']:.2f}
        """.strip()
        
        details_label = QLabel(details_text)
        details_label.setStyleSheet("color: white; font-size: 14px; line-height: 1.5;")
        summary_layout.addWidget(details_label)
        
        layout.addWidget(summary_frame)
        
        # Payment Method Selection
        method_frame = QFrame()
        method_frame.setStyleSheet("""
            QFrame {
                background-color: #333;
                border-radius: 8px;
                padding: 15px;
            }
        """)
        method_layout = QVBoxLayout(method_frame)
        
        method_title = QLabel("💳 SELECT PAYMENT METHOD")
        method_title.setStyleSheet("color: #4CAF50; font-size: 16px; font-weight: bold; margin-bottom: 10px;")
        method_layout.addWidget(method_title)
        
        self.payment_method = QComboBox()
        self.payment_method.addItems([
            "💵 Cash Payment",
            "💳 Credit/Debit Card",
            "📱 GCash",
            "📱 PayMaya",
            "🏦 Bank Transfer"
        ])
        self.payment_method.setStyleSheet("""
            QComboBox {
                background-color: #444;
                color: white;
                border: 1px solid #666;
                border-radius: 4px;
                padding: 10px;
                font-size: 14px;
            }
        """)
        method_layout.addWidget(self.payment_method)
        
        layout.addWidget(method_frame)
        
        # Processing Status
        self.status_label = QLabel("Ready to process payment...")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("""
            QLabel {
                color: #FFD700;
                font-size: 16px;
                font-weight: bold;
                margin: 15px 0;
                padding: 10px;
                border: 2px solid #FFD700;
                border-radius: 6px;
                background-color: rgba(255, 215, 0, 0.1);
            }
        """)
        layout.addWidget(self.status_label)
        
        # Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid #555;
                border-radius: 5px;
                text-align: center;
                background-color: #333;
                color: white;
                font-weight: bold;
            }
            QProgressBar::chunk {
                background-color: #4CAF50;
                border-radius: 3px;
            }
        """)
        layout.addWidget(self.progress_bar)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(15)
        
        self.cancel_btn = QPushButton("❌ Cancel Payment")
        self.cancel_btn.setMinimumHeight(45)
        self.cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #d32f2f;
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 14px;
                font-weight: bold;
                padding: 10px 20px;
            }
            QPushButton:hover {
                background-color: #f44336;
            }
        """)
        self.cancel_btn.clicked.connect(self.reject)
        
        self.pay_btn = QPushButton("💰 Process Payment")
        self.pay_btn.setMinimumHeight(45)
        self.pay_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 14px;
                font-weight: bold;
                padding: 10px 20px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        self.pay_btn.clicked.connect(self.process_payment)
        
        button_layout.addWidget(self.cancel_btn)
        button_layout.addWidget(self.pay_btn)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)
    
    def start_payment_simulation(self):
        """Initialize payment simulation"""
        pass
    
    def process_payment(self):
        """Process the payment"""
        # Disable buttons during processing
        self.pay_btn.setEnabled(False)
        self.cancel_btn.setEnabled(False)
        
        # Show progress
        self.progress_bar.setVisible(True)
        self.status_label.setText("Processing payment...")
        
        # Simulate payment processing
        self.progress_bar.setValue(0)
        
        # Step 1: Validating payment method
        QTimer.singleShot(500, lambda: self.update_progress(20, "Validating payment method..."))
        QTimer.singleShot(1000, lambda: self.update_progress(40, "Connecting to payment gateway..."))
        QTimer.singleShot(1500, lambda: self.update_progress(60, "Processing transaction..."))
        QTimer.singleShot(2000, lambda: self.update_progress(80, "Confirming payment..."))
        QTimer.singleShot(2500, lambda: self.update_progress(100, "Payment successful!"))
        QTimer.singleShot(3000, self.payment_success)
    
    def update_progress(self, value, message):
        """Update progress bar and status"""
        self.progress_bar.setValue(value)
        self.status_label.setText(message)
    
    def payment_success(self):
        """Handle successful payment"""
        self.status_label.setText("✅ Payment completed successfully!")
        self.status_label.setStyleSheet("""
            QLabel {
                color: #4CAF50;
                font-size: 16px;
                font-weight: bold;
                margin: 15px 0;
                padding: 10px;
                border: 2px solid #4CAF50;
                border-radius: 6px;
                background-color: rgba(76, 175, 80, 0.1);
            }
        """)
        
        # Show success message
        QMessageBox.information(self, "Payment Successful", 
                              f"Payment of ₱{self.payment_info['total_cost']:.2f} has been processed successfully!\n\n"
                              f"Your PDF will now be prepared for printing.")
        
        self.accept()
