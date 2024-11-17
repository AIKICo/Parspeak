import queue
import sys
import json
import sounddevice as sd
import numpy as np  # Add this import
from pynput import keyboard
import os
import time
from datetime import datetime
import threading
import pyperclip
import arabic_reshaper
from vosk import Model, KaldiRecognizer
from PyQt6.QtWidgets import QApplication, QLabel, QWidget
from PyQt6.QtCore import Qt, QTimer, QLocale
from PyQt6.QtGui import QFont, QFontDatabase


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
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        
        # Create label for transcription text
        self.label = QLabel(self)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # Remove setLayoutDirection as we'll handle RTL in CSS
        
        # Updated stylesheet with correct RTL handling
        self.label.setStyleSheet(f"""
            QLabel {{
                color: white;
                background-color: rgba(0, 0, 0, 150);
                padding: 8px 15px;
                border-radius: 5px;
                width: 100%;
                height: 100%;
                text-align: center;
                qproperty-alignment: AlignCenter;
                font-family: {self.font_family};
                font-size: 14px;
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

def audio_preprocessing(audio_data):
    # Convert bytes to numpy array
    audio = np.frombuffer(audio_data, dtype=np.int16)
    
    # Convert to float32 for processing
    audio = audio.astype(np.float32) / 32768.0
    
    # Boost the signal slightly
    audio = audio * 1.2
    
    # Advanced noise gate with smoothing
    noise_gate = 0.003
    mask = abs(audio) > noise_gate
    audio = audio * mask
    
    # Clip to prevent distortion
    audio = np.clip(audio, -1.0, 1.0)
    
    # Convert back to int16
    audio = (audio * 32768).astype(np.int16)
    return audio.tobytes()

# Keep existing callback function
def callback(indata, frames, time, status):
    if status:
        print(status, file=sys.stderr)
    q.put(bytes(indata))

# Keep existing record function unchanged
def record(transcription_queue, control_event):
    try:
        # Use higher sample rate for better quality
        device_info = sd.query_devices(None, "input")
        samplerate = 16000  # Optimal rate for Vosk small model
        device = None

        # Update model path to point to the extracted folder
        model_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models", "vosk-model-small-fa-0.42")
        if not os.path.exists(model_path):
            print(f"Error: Model not found at {model_path}")
            print("Please download the model from https://alphacephei.com/vosk/models")
            print("Extract it to the 'models' folder in your script directory")
            sys.exit(1)
            
        model = Model(model_path=model_path)

        # Set dump_fn to None
        dump_fn = None

        with sd.RawInputStream(samplerate=samplerate, 
                             blocksize=4000,  # Smaller chunks for more frequent updates
                             device=device,
                             dtype="int16",
                             channels=1,
                             callback=callback):
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
                            processed_data = audio_preprocessing(data)
                            
                            # Accumulate small chunks before processing
                            audio_data.append(processed_data)
                            
                            # Process in larger chunks for better accuracy
                            if len(audio_data) >= 4:  # Process every 4 chunks
                                combined_data = b''.join(audio_data)
                                if rec.AcceptWaveform(combined_data):
                                    result = rec.Result()
                                    if result and len(result) > 2:
                                        result_dict = json.loads(result)
                                        if "text" in result_dict and result_dict["text"]:
                                            transcription_state.full_result.append(result_dict["text"])
                                            transcription = " ".join(filter(None, transcription_state.full_result))
                                            if transcription_state.current_partial:
                                                transcription += " " + transcription_state.current_partial
                                            transcription_queue.put(("update", transcription))
                                audio_data = []  # Clear processed chunks
                            
                            # Only show partial results after minimum duration
                            elif recording_start_time and (datetime.now() - recording_start_time).total_seconds() >= MIN_RECORDING_DURATION:
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
                                dump_fn.write(processed_data)
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
        
        # Get script directory and construct font path
        script_dir = os.path.dirname(os.path.abspath(__file__))
        font_path = os.path.join(script_dir, "fonts", "Vazirmatn-Regular.ttf")
        
        print(f"Looking for font at: {font_path}")
        
        if not os.path.exists(font_path):
            print(f"Error: Font file not found at {font_path}")
            # Try alternative locations
            alt_paths = [
                "./fonts/Vazirmatn-Regular.ttf",
                "../fonts/Vazirmatn-Regular.ttf",
                os.path.expanduser("~/fonts/Vazirmatn-Regular.ttf")
            ]
            
            for alt_path in alt_paths:
                if os.path.exists(alt_path):
                    font_path = alt_path
                    print(f"Found font at alternative location: {font_path}")
                    break
            else:
                print("Using system font as fallback")
                font_family = "Arial"
        
        if 'font_family' not in locals():  # Only load font if we haven't set a fallback
            font_id = QFontDatabase.addApplicationFont(font_path)
            if font_id < 0:
                print(f"Error: Failed to load font from {font_path}")
                font_family = "Arial"
            else:
                font_families = QFontDatabase.applicationFontFamilies(font_id)
                if not font_families:
                    print("Error: No font families found in the font file")
                    font_family = "Arial"
                else:
                    font_family = font_families[0]
                    print(f"Successfully loaded font family: {font_family}")

        # Create window with loaded font
        window = TranscriptionWindow(transcription_queue, control_event, font_family)
        
        # Keep reference to window and app
        app.window = window  # Prevent garbage collection
        
        # Run application
        sys.exit(app.exec())  # Change this line
        
        # Cleanup
        control_event.set()
        recording_thread.join()

        # Check if we have the full model
        model_path = os.path.join(script_dir, "model")
        if not os.path.exists(model_path):
            print("Warning: Full model not found. Please download the complete model for better accuracy.")
            print("Visit https://alphacephei.com/vosk/models and download the Persian model")
            print("Extract it to a 'model' folder in your script directory")

    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)