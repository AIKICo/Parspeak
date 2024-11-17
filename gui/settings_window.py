import sounddevice as sd
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication, QWidget, QGraphicsDropShadowEffect, QVBoxLayout, QComboBox, QHBoxLayout, QPushButton
)

class SettingsWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.selected_device = None
        # Replace the window modality setting
        self.setWindowModality(Qt.WindowModality.NonModal)
        self.init_ui()

    def init_ui(self):
        # Common styles
        BACKGROUND_COLOR = "rgba(40, 40, 40, 200)"
        ELEMENT_BACKGROUND = "rgba(60, 60, 60, 180)"
        BORDER_COLOR = "rgba(255, 255, 255, 20)"
        TEXT_COLOR = "white"

        # Update window flags and attributes
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # Create main layout for the window
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Create background container widget
        self.container = QWidget()
        self.container.setStyleSheet(f"""
            QWidget {{
                background-color: {BACKGROUND_COLOR};
                border-radius: 10px;
                border: 1px solid {BORDER_COLOR};
            }}
        """)
        
        # Create layout for container
        container_layout = QVBoxLayout(self.container)
        container_layout.setContentsMargins(15, 15, 15, 15)
        
        # Create and style the combo box
        self.device_combo = QComboBox()
        self.device_combo.setStyleSheet(f"""
            QComboBox {{
                color: {TEXT_COLOR};
                background-color: {ELEMENT_BACKGROUND};
                padding: 8px;
                border-radius: 5px;
                border: 1px solid {BORDER_COLOR};
            }}
            QComboBox::drop-down {{
                border: none;
            }}
            QComboBox::down-arrow {{
                image: none;
            }}
            QComboBox QAbstractItemView {{
                color: {TEXT_COLOR};
                background-color: {BACKGROUND_COLOR};
                selection-background-color: {ELEMENT_BACKGROUND};
                border: 1px solid {BORDER_COLOR};
            }}
        """)
        self.populate_devices()
        
        # Create button layout and buttons
        button_layout = QHBoxLayout()
        apply_button = QPushButton("Apply")
        close_button = QPushButton("Close")
        
        button_style = f"""
            QPushButton {{
                color: {TEXT_COLOR};
                background-color: {ELEMENT_BACKGROUND};
                padding: 8px 15px;
                border-radius: 5px;
                border: 1px solid {BORDER_COLOR};
            }}
            QPushButton:hover {{
                background-color: rgba(80, 80, 80, 180);
            }}
        """
        apply_button.setStyleSheet(button_style)
        close_button.setStyleSheet(button_style)
        
        # Connect buttons
        apply_button.clicked.connect(self.apply_settings)
        close_button.clicked.connect(self.close)
        
        # Add buttons to button layout
        button_layout.addWidget(apply_button)
        button_layout.addWidget(close_button)
        
        # Add widgets to container layout
        container_layout.addWidget(self.device_combo)
        container_layout.addLayout(button_layout)
        
        # Add container to main layout
        main_layout.addWidget(self.container)
        
        # Add shadow effect to container
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(15)
        shadow.setColor(Qt.GlobalColor.black)
        shadow.setOffset(0, 0)
        self.container.setGraphicsEffect(shadow)
        
        # Set window size
        self.resize(300, 120)
        self.center_on_screen()

    def center_on_screen(self):
        screen = QApplication.primaryScreen().geometry()
        self.move(
            (screen.width() - self.width()) // 2,
            (screen.height() - self.height()) // 2
        )

    def populate_devices(self):
        self.device_combo.clear()
        devices = sd.query_devices()
        for i, device in enumerate(devices):
            if device['max_input_channels'] > 0:
                self.device_combo.addItem(f"{device['name']}", i)
        
        # Select current device if set
        if self.selected_device is not None:
            index = self.device_combo.findData(self.selected_device)
            if index >= 0:
                self.device_combo.setCurrentIndex(index)

    def apply_settings(self):
        self.selected_device = self.device_combo.currentData()
        if self.parent:
            self.parent.selected_device = self.selected_device
        self.hide()  # Hide instead of close

    def closeEvent(self, event):
        # Hide instead of close
        event.ignore()
        self.hide()
