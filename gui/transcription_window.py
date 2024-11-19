import sys
import time
import queue
import arabic_reshaper
from PyQt6.QtCore import Qt, QTimer, QLocale
from PyQt6.QtGui import QFont, QIcon
from PyQt6.QtWidgets import (
    QApplication, QLabel, QWidget, QSystemTrayIcon, QMenu, QGraphicsDropShadowEffect, QVBoxLayout, QComboBox, QHBoxLayout, QPushButton
)
from .settings_window import SettingsWindow

class TranscriptionWindow(QWidget):
    def __init__(self, transcription_queue, control_event, font_family="Arial"):
        super().__init__()
        # Add icon paths
        self.icon_default = "icon.png"
        self.icon_recording = "icon_rec.png"
        self.transcription_queue = transcription_queue
        self.control_event = control_event
        self.font_family = font_family
        self.selected_device = None
        # Add settings_window instance variable
        self.settings_window = None
        self.init_ui()
        self.init_tray()
        
        # Setup timer for queue processing
        self.timer = QTimer()
        self.timer.timeout.connect(self.process_queue)
        self.timer.start(50)  # 50ms interval
        
        # Start hidden
        self.hide()

    def init_ui(self):
        # Set window flags for transparency and always on top
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.Tool |
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        
        # Create label for transcription text
        self.label = QLabel(self)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Remove the blur effect and just keep the shadow
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(15)
        shadow.setColor(Qt.GlobalColor.black)
        shadow.setOffset(0, 0)
        self.label.setGraphicsEffect(shadow)
        
        # Update stylesheet for frosted glass effect
        self.setStyleSheet("""
            QWidget {
                border-radius: 10px;
                background-color: transparent;
            }
        """)
        
        # Updated label stylesheet with better blur simulation
        self.label.setStyleSheet(f"""
            QLabel {{
                color: white;
                background-color: rgba(40, 40, 40, 80);
                padding: 8px 15px;
                border-radius: 10px;
                width: 100%;
                height: 100%;
                text-align: center;
                qproperty-alignment: AlignCenter;
                font-family: {self.font_family};
                font-size: 14px;
                border: 1px solid rgba(255, 255, 255, 20);
            }}
        """)
        
        # Set locale for Persian text
        locale = QLocale(QLocale.Language.Persian)
        self.setLocale(locale)
        self.label.setLocale(locale)
        
        # Use the loaded font with explicit weight
        font = QFont(self.font_family)
        font.setPointSize(14)
        font.setWeight(QFont.Weight.Medium)
        self.label.setFont(font)
        
        # Set window size and position
        screen = QApplication.primaryScreen().geometry()
        window_width = min(screen.width() // 3, 600)  # Smaller width, max 600px
        window_height = 60  # Reduced height
        
        # Position window at top center
        self.setGeometry(
            (screen.width() - window_width) // 2,
            10,
            window_width,
            window_height
        )
        
        # Make label fill the entire window
        self.label.setGeometry(0, 0, window_width, window_height)

    def init_tray(self):
        # Create system tray icon
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(QIcon(self.icon_default))
        
        # Create tray menu
        tray_menu = QMenu()
        settings_action = tray_menu.addAction("Settings")
        settings_action.triggered.connect(self.show_settings)
        tray_menu.addSeparator()
        quit_action = tray_menu.addAction("Quit")
        quit_action.triggered.connect(self.quit_app)
        
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.show()
        
        # Connect double click to toggle visibility
        self.tray_icon.activated.connect(self.on_tray_activated)

    def show_settings(self):
        # If settings window already exists, show and activate it
        if self.settings_window and self.settings_window.isVisible():
            self.settings_window.raise_()
            self.settings_window.activateWindow()
            return

        # Create new settings window only if it doesn't exist
        if not self.settings_window:
            self.settings_window = SettingsWindow(self)
        
        # Set the selected device if it exists
        self.settings_window.selected_device = self.selected_device
        self.settings_window.populate_devices()  # Repopulate with current selection
        self.settings_window.show()
        self.settings_window.raise_()
        self.settings_window.activateWindow()

    def set_recording_state(self, is_recording):
        """Update tray icon based on recording state"""
        icon_path = self.icon_recording if is_recording else self.icon_default
        self.tray_icon.setIcon(QIcon(icon_path))

    def toggle_visibility(self):
        if self.isVisible():
            self.hide()
        else:
            self.show()

    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.toggle_visibility()

    def quit_app(self):
        # Hide tray icon before quitting
        self.tray_icon.hide()
        # Signal the recording thread to stop
        self.control_event.set()
        # Give the thread a moment to clean up
        time.sleep(0.1)
        # Quit the application
        QApplication.quit()
        # Force exit to ensure all threads are stopped
        sys.exit(0)

    def closeEvent(self, event):
        # Override close event to minimize to tray instead of closing
        event.ignore()
        self.hide()

    def show(self):
        super().show()
        self.raise_()
        self.activateWindow()

    def process_text(self, text):
        # Reshape Arabic/Persian text without using bidi
        return arabic_reshaper.reshape(text)

    def process_queue(self):
        try:
            while True:
                action, message = self.transcription_queue.get_nowait()
                if action == "show":
                    self.show()
                    self.set_recording_state(True)
                elif action == "hide":
                    self.hide()
                    self.label.setText("")
                    self.set_recording_state(False)
                elif action == "update":
                    processed_text = self.process_text(message)
                    self.label.setText(processed_text)
                    if not self.isVisible():
                        self.show()
                elif action == "exit":
                    self.close()  # Change this line
                    QApplication.quit()
                self.transcription_queue.task_done()
        except queue.Empty:
            pass
        return True  # Keep the timer running
