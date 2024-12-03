# Parspeak

Parspeak is a real-time speech recognition application that transcribes speech in Persian (Farsi) using the [Vosk](https://github.com/alphacep/vosk-api) library. It features a PyQt6 GUI for displaying transcriptions and allows users to start and stop recording with a customizable hotkey.

## Features

- Real-time speech recognition in Persian.
- Customizable hotkey for controlling recording.
- System tray integration with quick access to settings.
- GUI overlay for displaying transcribed text on the screen.

## Prerequisites

- Python 3.7 or higher.
- [Vosk API](https://github.com/alphacep/vosk-api) installed.
- The Vosk Persian model placed in the `models` directory.
- Required Python packages listed in `requirements.txt`.

## Installation

1. **Clone the repository:**

   ```bash
   git clone https://github.com/yourusername/parspeak.git
   cd parspeak
   ```

2. **Create and activate a virtual environment:**

   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
   ```

3. **Install dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

4. **Download and set up the Vosk model:**

   - Download the Persian model from [Vosk Models](https://alphacephei.com/vosk/models).
   - Extract the model into the `models` directory. Ensure the path is `models/vosk-model-small-fa-0.42`.