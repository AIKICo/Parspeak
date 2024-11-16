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

from kivy.app import App
from kivy.uix.label import Label
from kivy.uix.widget import Widget
from kivy.core.window import Window
from kivy.clock import Clock
from kivy.properties import StringProperty
from kivy.lang import Builder

from vosk import Model, KaldiRecognizer

# Update the Kivy UI string
Builder.load_string('''
<TranscriptionWidget>:
    FloatLayout:
        Label:
            text: root.transcription_text
            size_hint: 1, 1
            pos_hint: {'center_x': 0.5, 'center_y': 0.5}
            color: 1, 1, 1, 1
            font_size: '16sp'
''')

class TranscriptionWidget(Widget):
    transcription_text = StringProperty("")

class TranscriptionApp(App):
    def __init__(self, transcription_queue, control_event, **kwargs):
        super().__init__(**kwargs)
        self.transcription_queue = transcription_queue
        self.control_event = control_event
        self.widget = None
        self.window_visible = False  # Add this line
        
    def build(self):
        # Create widget first
        self.widget = TranscriptionWidget()
        
        # Configure window after creation
        Window.borderless = True
        Window.always_on_top = True
        
        # Calculate window size and position
        screen_width = Window.system_size[0]
        window_width = screen_width // 2
        Window.size = (window_width, 50)
        
        # Position window at top center
        Window.top = 10
        Window.left = (screen_width - window_width) // 2
        
        # Set window properties
        Window.clearcolor = (0, 0, 0, 0.5)
        
        # Hide window initially
        self._hide_window()
        
        # Schedule queue processing
        Clock.schedule_interval(self.process_queue, 0.05)
        
        return self.widget

    def _show_window(self):
        if not self.window_visible:
            Window.show()
            self.window_visible = True

    def _hide_window(self):
        if self.window_visible:
            Window.hide()
            self.window_visible = False

    def process_queue(self, dt):
        try:
            while True:
                action, message = self.transcription_queue.get_nowait()
                if action == "show":
                    self._show_window()
                elif action == "hide":
                    self._hide_window()
                    self.widget.transcription_text = ""
                elif action == "update":
                    self.widget.transcription_text = message
                elif action == "exit":
                    self._hide_window()
                    self.stop()
                    return False
                self.transcription_queue.task_done()
        except queue.Empty:
            pass
        return True

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

# Main thread code
if __name__ == '__main__':
    if os.geteuid() != 0:
        print("Script is not running as root. Attempting to elevate privileges...")
        args = ['sudo', sys.executable] + sys.argv
        os.execvp('sudo', args)
    else:
        transcription_queue = queue.Queue()
        control_event = threading.Event()

        # Start the recording function in a separate thread
        recording_thread = threading.Thread(target=record, args=(transcription_queue, control_event))
        recording_thread.start()

        # Run the Kivy application
        app = TranscriptionApp(transcription_queue, control_event)
        app.run()

        # Wait for the recording thread to finish
        recording_thread.join()