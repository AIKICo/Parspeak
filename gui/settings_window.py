import sounddevice as sd
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtWidgets import (
    QApplication, QWidget, QGraphicsDropShadowEffect, QVBoxLayout, QComboBox, 
    QHBoxLayout, QPushButton, QLabel, QFrame
)

class SettingsWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.selected_device = None
        self.current_hotkey = set()  # Store current hotkey combination
        self.is_listening_for_hotkey = False
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

        # Device selection section
        device_label = QLabel("Input Device:")
        device_label.setStyleSheet(f"color: white;")
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

        # Hotkey section
        hotkey_label = QLabel("Recording Hotkey:")
        hotkey_label.setStyleSheet(f"color: white;")
        
        hotkey_layout = QHBoxLayout()
        self.hotkey_display = QLabel("Ctrl+Shift+S")
        self.hotkey_display.setStyleSheet("""
            QLabel {
                color: white;
                background-color: rgba(60, 60, 60, 180);
                padding: 8px;
                border-radius: 5px;
                border: 1px solid rgba(255, 255, 255, 20);
            }
        """)
        
        self.hotkey_button = QPushButton("Set Hotkey")
        self.hotkey_button.setStyleSheet("""
            QPushButton {
                color: white;
                background-color: rgba(60, 60, 60, 180);
                padding: 8px 15px;
                border-radius: 5px;
                border: 1px solid rgba(255, 255, 255, 20);
            }
            QPushButton:hover {
                background-color: rgba(80, 80, 80, 180);
            }
        """)
        self.hotkey_button.clicked.connect(self.start_listening_for_hotkey)
        
        hotkey_layout.addWidget(self.hotkey_display)
        hotkey_layout.addWidget(self.hotkey_button)

        # Button layout
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
        container_layout.addWidget(device_label)
        container_layout.addWidget(self.device_combo)
        container_layout.addSpacing(10)
        container_layout.addWidget(hotkey_label)
        container_layout.addLayout(hotkey_layout)
        container_layout.addSpacing(10)
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
        self.resize(300, 200)
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

    def start_listening_for_hotkey(self):
        if self.is_listening_for_hotkey:
            self.stop_listening_for_hotkey()
            return

        self.is_listening_for_hotkey = True
        self.hotkey_button.setText("Press keys... (ESC to cancel)")
        self.current_hotkey.clear()
        self.setFocus()  # Ensure window can receive key events
        self.grabKeyboard()  # Grab keyboard focus

    def stop_listening_for_hotkey(self):
        self.is_listening_for_hotkey = False
        self.hotkey_button.setText("Set Hotkey")
        self.releaseKeyboard()  # Release keyboard focus
        self.update_hotkey_display()

    def keyPressEvent(self, event: QKeyEvent):
        if not self.is_listening_for_hotkey:
            return super().keyPressEvent(event)

        if event.key() == Qt.Key.Key_Escape:
            self.stop_listening_for_hotkey()
            return

        # Convert Qt key to string representation
        key = self._convert_qt_key(event)
        if key:
            self.current_hotkey.add(key)
            self.update_hotkey_display()

    def _convert_qt_key(self, event: QKeyEvent) -> str:
        # Map Qt keys to string representations
        key_map = {
            Qt.Key.Key_Control: "Key.ctrl",
            Qt.Key.Key_Shift: "Key.shift",
            Qt.Key.Key_Alt: "Key.alt",
            Qt.Key.Key_Meta: "Key.cmd",
        }

        # Handle modifier keys
        if event.key() in key_map:
            return key_map[event.key()]

        # Handle regular keys
        key_text = event.text()
        if key_text:
            return key_text.lower()

        return None

    def update_hotkey_display(self):
        if not self.current_hotkey:
            return
        
        # Convert internal key names to display names
        key_map = {
            "Key.ctrl": "Ctrl",
            "Key.shift": "Shift",
            "Key.alt": "Alt",
            "Key.cmd": "Super"
        }
        
        display_keys = []
        for key in sorted(self.current_hotkey):
            display_key = key_map.get(str(key), str(key))
            display_keys.append(display_key)
        
        self.hotkey_display.setText("+".join(display_keys))

    def apply_settings(self):
        self.selected_device = self.device_combo.currentData()
        if self.parent:
            self.parent.selected_device = self.selected_device
            if self.current_hotkey:
                self.parent.update_hotkey(self.current_hotkey)
        self.hide()  # Hide instead of close

    def closeEvent(self, event):
        # Hide instead of close
        event.ignore()
        self.hide()
