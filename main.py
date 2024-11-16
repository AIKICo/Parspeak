import argparse
import queue
import sys
import sounddevice as sd
from pynput import keyboard
import os
import time  # Import time module for sleep
from datetime import datetime

from vosk import Model, KaldiRecognizer

q = queue.Queue()
full_result = []
MIN_RECORDING_DURATION = 0.5  # Minimum recording duration in seconds

def int_or_str(text):
    """Helper function for argument parsing."""
    try:
        return int(text)
    except ValueError:
        return text

def callback(indata, frames, time, status):
    """This is called (from a separate thread) for each audio block."""
    if status:
        print(status, file=sys.stderr)
    q.put(bytes(indata))

def record():
    global full_result
    try:
        if args.samplerate is None:
            device_info = sd.query_devices(args.device, "input")
            # soundfile expects an int, sounddevice provides a float:
            args.samplerate = int(device_info["default_samplerate"])
        
        if args.model is None:
            model = Model(lang="fa")
        else:
            model = Model(lang=args.model)

        if args.filename:
            dump_fn = open(args.filename, "wb")
        else:
            dump_fn = None

        with sd.RawInputStream(samplerate=args.samplerate, blocksize = 8000, device=args.device,
                dtype="int16", channels=1, callback=callback):
            print("#" * 80)
            print("Press 'Ctrl+Cmd+S' to start/stop the recording")
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
                nonlocal recording, break_loop, pressed_keys, rec, audio_data, recording_start_time  # Add rec and audio_data to nonlocal
                global full_result  # Add this line
                pressed_keys.add(key)
                try:
                    if (keyboard.Key.ctrl in pressed_keys and
                        keyboard.Key.cmd in pressed_keys and
                        keyboard.KeyCode.from_char('s') in pressed_keys):
                        recording = not recording
                        if recording:
                            clear_audio_state()
                            rec = KaldiRecognizer(model, args.samplerate)
                            recording_start_time = datetime.now()
                            print("Recording started...")
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
                                except Exception as e:
                                    print("Error processing audio:", str(e))
                                finally:
                                    clear_audio_state()
                                    full_result = []
                    elif (keyboard.KeyCode.from_char('q') in pressed_keys):
                        print("Exiting...")
                        break_loop = True
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
                                    if result and len(result) > 2:  # Check if result is not empty json '{}'
                                        full_result.append(result)
                                else:
                                    partial = rec.PartialResult()
                                    if partial and len(partial) > 2:
                                        full_result.append(partial)
                            
                            if dump_fn is not None:
                                dump_fn.write(data)
                    except Exception as e:
                        print("Error processing audio frame:", str(e))
                else:
                    if prev_recording and rec and audio_data:
                        try:
                            full_result.append(rec.FinalResult())
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
        parser.exit(0)
    except Exception as e:
        parser.exit(type(e).__name__ + ": " + str(e))

parser = argparse.ArgumentParser(add_help=False)
parser.add_argument(
    "-l", "--list-devices", action="store_true",
    help="show list of audio devices and exit")
args, remaining = parser.parse_known_args()
if args.list_devices:
    print(sd.query_devices())
    parser.exit(0)
parser = argparse.ArgumentParser(
    description=__doc__,
    formatter_class=argparse.RawDescriptionHelpFormatter,
    parents=[parser])
parser.add_argument(
    "-f", "--filename", type=str, metavar="FILENAME",
    help="audio file to store recording to")
parser.add_argument(
    "-d", "--device", type=int_or_str,
    help="input device (numeric ID or substring)")
parser.add_argument(
    "-r", "--samplerate", type=int, help="sampling rate")
parser.add_argument(
    "-m", "--model", type=str, help="language model; e.g. en-us, fr, nl; default is en-us")
args = parser.parse_args(remaining)

if __name__ == "__main__":
    if os.geteuid() != 0:
        print("Script is not running as root. Attempting to elevate privileges...")
        args = ['sudo', sys.executable] + sys.argv
        os.execvp('sudo', args)
    else:
        record()
        print("Full result:", " ".join(full_result))