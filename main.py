#!/usr/bin/env python3

# prerequisites: as described in https://alphacephei.com/vosk/install and also python module `sounddevice` (simply run command `pip install sounddevice`)
# Example usage using Dutch (nl) recognition model: `python test_microphone.py -m nl`
# For more help run: `python test_microphone.py -h`

import argparse
import queue
import sys
import sounddevice as sd
import threading
from pynput import keyboard
import os
import time  # Import time module for sleep

from vosk import Model, KaldiRecognizer

q = queue.Queue()
full_result = []

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
            print("Press 's' to start/stop the recording")
            print("#" * 80)

            rec = KaldiRecognizer(model, args.samplerate)
            recording = False
            prev_recording = False
            break_loop = False  # Add a flag to exit the loop

            def on_press(key):
                nonlocal recording, break_loop
                try:
                    if key.char == 's':
                        recording = not recording
                        print("Recording started..." if recording else "Recording stopped...")
                    elif key.char == 'q':
                        print("Exiting...")
                        break_loop = True
                        return False  # Stop the listener
                except AttributeError:
                    pass

            listener = keyboard.Listener(on_press=on_press)
            listener.start()  # Start the listener outside the loop

            while not break_loop:
                if recording:
                    data = q.get()
                    if rec.AcceptWaveform(data):
                        full_result.append(rec.Result())
                    else:
                        full_result.append(rec.PartialResult())
                    if dump_fn is not None:
                        dump_fn.write(data)
                else:
                    if prev_recording:
                        # Recording was just stopped
                        full_result.append(rec.FinalResult())
                        transcription = " ".join(full_result)
                        print("Transcription:", transcription)
                        full_result = []
                        rec.Reset()
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