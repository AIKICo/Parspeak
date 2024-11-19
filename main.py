import os
import sys
import time
import queue
import json
import threading
from datetime import datetime

import numpy as np
import sounddevice as sd
import pyperclip
from vosk import Model, KaldiRecognizer
from pynput import keyboard
from PyQt6.QtGui import QFontDatabase
from PyQt6.QtWidgets import (
    QApplication
)

from gui.transcription_window import TranscriptionWindow


# Keep existing queue and TranscriptionState class
q = queue.Queue()
MIN_RECORDING_DURATION = 0.5

class TranscriptionState:
    def __init__(self):
        self.full_result = []
        self.current_partial = ""
        # Change default hotkey format to be consistent
        self.hotkey_combination = {'ctrl', 'shift', 's'}

    def update_hotkey(self, new_combination):
        # Convert combination to lowercase set for consistent comparison
        self.hotkey_combination = {k.lower() for k in new_combination}

def normalize_key(key):
    """Convert key to standardized string format"""
    try:
        # Handle special keys
        if hasattr(key, 'char'):
            if key.char == '\x03':
                return 'ctrl'
            return key.char.lower()
        # Handle modifier and special keys
        if hasattr(key, 'name'):
            return key.name.lower()
        # Handle normal character keys
        return str(key).lower()
    except AttributeError:
        return str(key).lower()

transcription_state = TranscriptionState()

def check_hotkey_match(pressed_keys, target_combination):
    # Normalize all pressed keys
    pressed_str = {normalize_key(k) for k in pressed_keys}
    print(f"Pressed keys: {pressed_str}")  # Debug print
    print(f"Target combination: {target_combination}")  # Debug print
    return pressed_str == target_combination

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

        # Get the window instance from QApplication
        window = QApplication.instance().window
        device = window.selected_device if window.selected_device is not None else None

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
                key_str = normalize_key(key)
                print(f"Key pressed: {key_str}")  # Debug print
                pressed_keys.add(key)
                
                try:
                    if check_hotkey_match(pressed_keys, transcription_state.hotkey_combination):
                        print("Hotkey match detected!")  # Debug print
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
                            current_rec = rec  # Store current recognizer
                            if current_rec is not None:  # Check if rec exists
                                time.sleep(0.2)  # Slightly longer delay before processing
                                try:
                                    # Process any remaining audio in the queue
                                    while not q.empty():
                                        data = q.get()
                                        current_rec.AcceptWaveform(data)
                                    
                                    final = current_rec.FinalResult()
                                    final_dict = json.loads(final)
                                    if final_dict.get("text"):
                                        transcription_state.full_result.append(final_dict["text"])
                                    transcription = " ".join(filter(None, transcription_state.full_result))
                                    if transcription:  # Only process if we have text
                                        print("Transcription:", transcription)
                                        # Send transcription to GUI thread for clipboard operation
                                        transcription_queue.put(("copy", transcription))
                                        # Send final transcription to the GUI
                                        transcription_queue.put(("update", transcription))
                                except Exception as e:
                                    print("Error processing final audio:", str(e))
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

            try:
                while not control_event.is_set():  # Change break_loop to use control_event
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
            finally:
                # Stop keyboard listener when recording stops
                listener.stop()

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
                if (os.path.exists(alt_path)):
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