import queue
import sys
import json
import sounddevice as sd
from pynput import keyboard
import os
import time
from datetime import datetime
import threading
import pyperclip
import arabic_reshaper
from vosk import Model, KaldiRecognizer
from bidi.algorithm import get_display
from PyQt6.QtWidgets import QApplication, QLabel, QWidget
from PyQt6.QtCore import Qt, QTimer, QLocale
from PyQt6.QtGui import QFont, QFontDatabase

# ...existing imports and queue/state definitions...

class TranscriptionWindow(QWidget):
    def __init__(self, transcription_queue, control_event, font_family="Arial"):
        super().__init__()
        self.transcription_queue = transcription_queue
        self.control_event = control_event
        self.font_family = font_family
        self.init_ui()
        
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
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)  # Add this line
        
        # Create label for transcription text with RTL support
        self.label = QLabel(self)
        self.label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.label.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.label.setTextFormat(Qt.TextFormat.PlainText)
        self.label.setStyleSheet("""
            QLabel {
                color: white;
                background-color: rgba(0, 0, 0, 150);
                padding: 10px;
                border-radius: 5px;
                width: 100%;
                height: 100%;
                text-align: right;
                direction: rtl;
            }
        """)
        
        # Set locale for RTL text
        locale = QLocale(QLocale.Language.Persian)
        self.setLocale(locale)
        self.label.setLocale(locale)
        
        # Use the loaded font
        font = QFont(self.font_family, 12)
        self.label.setFont(font)
        
        # Set window size and position
        screen = QApplication.primaryScreen().geometry()
        window_width = screen.width() // 2
        window_height = 100
        
        # Position window at top center
        self.setGeometry(
            (screen.width() - window_width) // 2,
            10,
            window_width,
            window_height
        )
        
        # Make label fill the entire window
        self.label.setGeometry(0, 0, window_width, window_height)

    def show(self):
        super().show()
        self.raise_()
        self.activateWindow()

    def process_text(self, text):
        # Only reshape, don't use bidi as Qt handles text direction
        return arabic_reshaper.reshape(text)

    def process_queue(self):
        try:
            while True:
                action, message = self.transcription_queue.get_nowait()
                if action == "show":
                    self.show()
                elif action == "hide":
                    self.hide()
                    self.label.setText("")
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

# Keep existing queue and TranscriptionState class
q = queue.Queue()
MIN_RECORDING_DURATION = 0.5

class TranscriptionState:
    def __init__(self):
        self.full_result = []
        self.current_partial = ""

transcription_state = TranscriptionState()

# Keep existing callback function
def callback(indata, frames, time, status):
    if status:
        print(status, file=sys.stderr)
    q.put(bytes(indata))

# Keep existing record function unchanged
def record(transcription_queue, control_event):
    try:
        # Use default device and sample rate
        device_info = sd.query_devices(None, "input")
        samplerate = int(device_info["default_samplerate"])
        device = None

        # Set the default language model to "fa"
        model = Model(lang="fa")

        # Set dump_fn to None
        dump_fn = None

        with sd.RawInputStream(samplerate=samplerate, blocksize = 8000, device=device,
                dtype="int16", channels=1, callback=callback):
            print("#" * 80)
            print("Press 'Ctrl+Shift+S' to start/stop the recording")
            print("#" * 80)

            rec = None  # Move recognizer outside the recording logic
            recording = False
            prev_recording = False
            break_loop = False  # Add a flag to exit the loop
            audio_data = []  # Add buffer for audio data
            recording_start_time = None

            def clear_audio_state():
                nonlocal rec, audio_data, recording_start_time
                while not q.empty():
                    _ = q.get()  # Clear the queue
                rec = None
                audio_data = []
                recording_start_time = None
                # Don't clear full_result here anymore

            pressed_keys = set()
            def on_press(key):
                nonlocal recording, break_loop, pressed_keys, rec, audio_data, recording_start_time
                pressed_keys.add(key)
                try:
                    if (keyboard.Key.ctrl in pressed_keys and
                        keyboard.Key.shift in pressed_keys and
                        keyboard.KeyCode.from_char('s') in pressed_keys):
                        recording = not recording
                        if recording:
                            # Only clear full_result when starting a new recording
                            transcription_state.full_result = []
                            transcription_state.current_partial = ""
                            clear_audio_state()
                            rec = KaldiRecognizer(model, samplerate)
                            recording_start_time = datetime.now()
                            print("Recording started...")
                            # Signal the main thread to show the window
                            transcription_queue.put(("show", None))
                        else:
                            print("Recording stopped...")
                            if rec is not None:  # Check if rec exists
                                time.sleep(0.1)  # Small delay before processing
                                try:
                                    final = rec.FinalResult()
                                    if final:
                                        final_dict = json.loads(final)
                                        if final_dict.get("text"):
                                            transcription_state.full_result.append(final_dict["text"])
                                        transcription = " ".join(filter(None, transcription_state.full_result))
                                        print("Transcription:", transcription)
                                        # Copy transcription to clipboard instead of saving to file
                                        try:
                                            pyperclip.copy(transcription)
                                            print("Transcription copied to clipboard!")
                                        except Exception as e:
                                            print("Error copying to clipboard:", str(e))
                                        # Send final transcription to the GUI
                                        transcription_queue.put(("update", transcription))
                                except Exception as e:
                                    print("Error processing audio:", str(e))
                                finally:
                                    clear_audio_state()
                            # Signal the main thread to hide the window
                            transcription_queue.put(("hide", None))
                    elif (keyboard.KeyCode.from_char('q') in pressed_keys):
                        print("Exiting...")
                        break_loop = True
                        # Signal the main thread to close the window
                        transcription_queue.put(("exit", None))
                        return False  # Stop the listener
                except AttributeError:
                    pass

            def on_release(key):
                if key in pressed_keys:
                    pressed_keys.remove(key)

            listener = keyboard.Listener(on_press=on_press, on_release=on_release)
            listener.start()  # Start the listener outside the loop

            while not break_loop:
                if recording and rec is not None:  # Ensure rec exists
                    try:
                        if not q.empty():
                            data = q.get()
                            audio_data.append(data)  # Store audio data
                            
                            # Only process audio after minimum duration
                            if recording_start_time and (datetime.now() - recording_start_time).total_seconds() >= MIN_RECORDING_DURATION:
                                if rec.AcceptWaveform(data):
                                    result = rec.Result()
                                    if result and len(result) > 2:
                                        result_dict = json.loads(result)
                                        if "text" in result_dict and result_dict["text"]:
                                            transcription_state.full_result.append(result_dict["text"])
                                            transcription = " ".join(filter(None, transcription_state.full_result))
                                            if transcription_state.current_partial:
                                                transcription += " " + transcription_state.current_partial
                                            transcription_queue.put(("update", transcription))
                                else:
                                    partial = rec.PartialResult()
                                    if partial and len(partial) > 2:
                                        partial_dict = json.loads(partial)
                                        if "partial" in partial_dict:
                                            transcription_state.current_partial = partial_dict["partial"]
                                            transcription = " ".join(filter(None, transcription_state.full_result))
                                            if transcription_state.current_partial:
                                                transcription += " " + transcription_state.current_partial
                                            transcription_queue.put(("update", transcription))
                            
                            if dump_fn is not None:
                                dump_fn.write(data)
                    except Exception as e:
                        print("Error processing audio frame:", str(e))
                else:
                    if prev_recording and rec and audio_data:
                        try:
                            final_result = rec.FinalResult()
                            final_dict = json.loads(final_result)
                            if "text" in final_dict and final_dict["text"]:
                                transcription_state.full_result.append(final_dict["text"])
                                transcription = " ".join(filter(None, transcription_state.full_result))
                                print("Transcription:", transcription)
                        except Exception as e:
                            print("Error getting final result:", str(e))
                        finally:
                            audio_data = []
                            rec = None
                    time.sleep(0.1)  # Pause briefly to prevent high CPU usage
                prev_recording = recording

    except KeyboardInterrupt:
        print("\nDone")
        sys.exit(0)
    except Exception as e:
        sys.exit(type(e).__name__ + ": " + str(e))

    # Signal the control event to stop the main loop
    control_event.set()

# Update the main section to use PyQt instead of Kivy
if __name__ == '__main__':
    try:
        transcription_queue = queue.Queue()
        control_event = threading.Event()

        # Check audio devices
        try:
            device_info = sd.query_devices(None, "input")
            if device_info is None:
                print("Error: No input device found")
                sys.exit(1)
        except sd.PortAudioError as e:
            print(f"Error initializing audio: {e}")
            sys.exit(1)

        # Start recording thread
        recording_thread = threading.Thread(target=record, args=(transcription_queue, control_event))
        recording_thread.start()

        # Start Qt application
        app = QApplication(sys.argv)
        
        # Load Vazir font
        font_id = QFontDatabase.addApplicationFont("fonts/Vazirmatn-Regular.ttf")
        if font_id < 0:
            print("Warning: Could not load Vazir font, falling back to system font")
            font_family = "Arial"  # Fallback font
        else:
            font_family = QFontDatabase.applicationFontFamilies(font_id)[0]
            print(f"Loaded font family: {font_family}")

        # Create and setup window
        window = TranscriptionWindow(transcription_queue, control_event, font_family)
        
        # Keep reference to window and app
        app.window = window  # Prevent garbage collection
        
        # Run application
        sys.exit(app.exec())  # Change this line
        
        # Cleanup
        control_event.set()
        recording_thread.join()

    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)