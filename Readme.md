# Parspeak

Parspeak is a real-time speech recognition application that transcribes speech in Persian (Farsi) using the [Vosk](https://github.com/alphacep/vosk-api) library. It features a PyQt6 GUI for displaying transcriptions and allows users to start and stop recording with a customizable hotkey.

## Features

- Real-time speech recognition in Persian.
- Customizable hotkey for controlling recording.
- System tray integration with quick access to settings.
- GUI overlay for displaying transcribed text on the screen.

## Installation

1. **Clone the repository:**

   ```bash
   git clone https://github.com/omid3098/parspeak.git
   cd parspeak
   ```

2. **Create and activate a virtual environment:**

   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows, use `venv\Scripts\activate`
   ```

3. **Install dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

4. **Download and set up the Vosk model:**
   - You can use the existing model located at 'models/' directory or
      - Download the Persian model from [Vosk Models](https://alphacephei.com/vosk/models).
      - Extract the model into the `models` directory. Ensure to update the path in main.py the path is `models/vosk-model-small-fa-0.42`.


## Video Tutorial:


https://github.com/user-attachments/assets/7a76c177-fd4e-4e0b-8d82-d68e69f6da88



## Licenses

### Vosk Models
The Vosk speech recognition models are licensed under the Apache License 2.0.
For more information, visit: https://github.com/alphacep/vosk-api/blob/master/LICENSE

### PyQt6
PyQt6 is licensed under the GNU General Public License v3.
For more information, visit: https://www.riverbankcomputing.com/software/pyqt/license
