import queue
import sys
import json  # Add this import
import sounddevice as sd
from pynput import keyboard
import os
import time
from datetime import datetime
import tkinter as tk
import threading  # Import threading module

from vosk import Model, KaldiRecognizer

q = queue.Queue()
MIN_RECORDING_DURATION = 0.5  # Minimum recording duration in seconds

def callback(indata, frames, time, status):
    """This is called (from a separate thread) for each audio block."""
    if status:
        print(status, file=sys.stderr)
    q.put(bytes(indata))

def record(transcription_queue, control_event):
    full_result = []  # Moved inside the function
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

            pressed_keys = set()
            def on_press(key):
                nonlocal recording, break_loop, pressed_keys, rec, audio_data, recording_start_time, full_result
                pressed_keys.add(key)
                try:
                    if (keyboard.Key.ctrl in pressed_keys and
                        keyboard.Key.shift in pressed_keys and
                        keyboard.KeyCode.from_char('s') in pressed_keys):
                        recording = not recording
                        if recording:
                            clear_audio_state()
                            rec = KaldiRecognizer(model, samplerate)
                            recording_start_time = datetime.now()
                            print("Recording started...")
                            # Signal the main thread to show the window
                            transcription_queue.put(("show", None))
                        else:
                            print("Recording stopped...")
                            if rec:
                                time.sleep(0.1)  # Small delay before processing
                                try:
                                    final = rec.FinalResult()
                                    if final:
                                        full_result.append(final)
                                        transcription = " ".join(full_result)
                                        print("Transcription:", transcription)
                                        # Save transcription to a file
                                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                                        with open(f"transcription_{timestamp}.txt", "w") as f:
                                            f.write(transcription)
                                        # Send final transcription to the GUI
                                        transcription_queue.put(("update", transcription))
                                except Exception as e:
                                    print("Error processing audio:", str(e))
                                finally:
                                    clear_audio_state()
                                    full_result = []
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
                if recording and rec:  # Check if rec exists
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
                                            full_result.append(result_dict["text"])
                                            transcription = " ".join(full_result)
                                            transcription_queue.put(("update", transcription))
                                else:
                                    partial = rec.PartialResult()
                                    if partial and len(partial) > 2:
                                        partial_dict = json.loads(partial)
                                        if "partial" in partial_dict:
                                            transcription = partial_dict["partial"]
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
                                full_result.append(final_dict["text"])
                                transcription = " ".join(full_result)
                                print("Transcription:", transcription)
                        except Exception as e:
                            print("Error getting final result:", str(e))
                        finally:
                            full_result = []
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
if __name__ == "__main__":
    if os.geteuid() != 0:
        print("Script is not running as root. Attempting to elevate privileges...")
        args = ['sudo', sys.executable] + sys.argv
        os.execvp('sudo', args)
    else:
        # Create a queue to communicate with the GUI
        transcription_queue = queue.Queue()
        control_event = threading.Event()

        # Start the recording function in a separate thread
        recording_thread = threading.Thread(target=record, args=(transcription_queue, control_event))
        recording_thread.start()

        # Initialize Tkinter window in the main thread
        root = tk.Tk()
        root.overrideredirect(True)  # Remove window decorations
        root.attributes("-topmost", True)  # Keep the window on top
        root.configure(bg='black')  # Set background color to black
        root.attributes('-alpha', 0.5)  # Set window opacity to 70%

        # Position the window at the middle top
        screen_width = root.winfo_screenwidth()
        window_width = screen_width // 2
        window_height = 50  # Adjust height as needed
        x_position = (screen_width - window_width) // 2
        y_position = 10  # Slightly below the top edge
        root.geometry(f"{window_width}x{window_height}+{x_position}+{y_position}")

        # Create label to display transcription
        transcription_label = tk.Label(root, text="", font=("Helvetica", 16), fg="white", bg='black')
        transcription_label.pack(expand=True)

        root.withdraw()  # Hide the window initially

        def process_queue():
            try:
                while True:
                    action, message = transcription_queue.get_nowait()
                    if action == "show":
                        root.deiconify()  # Show the window
                    elif action == "hide":
                        root.withdraw()  # Hide the window
                        transcription_label.config(text="")
                    elif action == "update":
                        transcription_label.config(text=message)
                    elif action == "exit":
                        root.destroy()
                        return
                    transcription_queue.task_done()
            except queue.Empty:
                pass
            root.after(50, process_queue)  # Check the queue every 50ms

        # Start processing the queue
        root.after(0, process_queue)
        root.mainloop()

        # Wait for the recording thread to finish
        recording_thread.join()