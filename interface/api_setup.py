import sys
from PySide6.QtWidgets import QApplication, QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton, QHBoxLayout
from PySide6.QtCore import Qt

class ApiSetupDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("VICTOR - API Configuration")
        self.setFixedSize(450, 150)
        self.setStyleSheet("background-color: #0f0f14; color: white;")
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        
        lbl = QLabel("Enter your Gemini API Key to activate VICTOR:")
        lbl.setStyleSheet("font-size: 14px; font-weight: bold; color: #00f0ff;")
        layout.addWidget(lbl)
        
        self.key_input = QLineEdit()
        self.key_input.setPlaceholderText("AIzaSy...")
        self.key_input.setStyleSheet("padding: 8px; border-radius: 4px; background: #1a1a24; border: 1px solid #00f0ff; color: white;")
        layout.addWidget(self.key_input)
        
        btn_layout = QHBoxLayout()
        self.save_btn = QPushButton("Save & Launch")
        self.save_btn.setStyleSheet("padding: 8px 16px; background: #00f0ff; color: black; border-radius: 4px; font-weight: bold;")
        self.save_btn.clicked.connect(self.accept)
        
        btn_layout.addStretch()
        btn_layout.addWidget(self.save_btn)
        layout.addLayout(btn_layout)
        
    def get_key(self):
        return self.key_input.text().strip()

def get_api_key():
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)
    
    dialog = ApiSetupDialog()
    if dialog.exec() == QDialog.Accepted:
        return dialog.get_key()
    return None
