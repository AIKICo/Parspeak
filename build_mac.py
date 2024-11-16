import os
import logging
import shutil
import platform
import PyInstaller.__main__

def setup_logging():
    logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')

def run_pyinstaller():
    logging.info('Running PyInstaller...')
    script_name = 'main.py'
    try:
        # Get the virtual environment path
        venv_path = os.path.join(os.getcwd(), '.venv')
        site_packages = os.path.join(venv_path, 'lib', 'python3.11', 'site-packages')
        kivy_path = os.path.join(site_packages, 'kivy')
        
        # Basic PyInstaller arguments
        pyinstaller_args = [
            # Core dependencies
            '--collect-all', 'vosk',
            '--collect-all', 'pynput',
            '--collect-all', 'pyperclip',
            '--collect-all', '_sounddevice_data',  # Add sounddevice data
            # Kivy-specific settings
            '--add-data', f'{kivy_path}:kivy',
            # Additional settings
            '--name', 'VoskTranscriber',
            '--windowed',
            '--onedir',
            '--clean',
            '--noconfirm',
            '--osx-bundle-identifier', 'com.vosktranscriber.app',
            # Hidden imports
            '--hidden-import', 'sounddevice',
            '--hidden-import', '_sounddevice_data',
            '--hidden-import', 'sounddevice_build_info',
            '--hidden-import', 'kivy.core.window.window_sdl2',
            '--hidden-import', 'kivy.core.text.text_sdl2',
            '--hidden-import', 'kivy.core.text.markup',
            '--hidden-import', 'kivy.core.image',
            '--hidden-import', 'kivy.core.clipboard.clipboard_sdl2',
            '--hidden-import', 'kivy.uix.widget',
            '--hidden-import', 'kivy.uix.label',
            '--hidden-import', 'kivy.uix.floatlayout',
            '--hidden-import', 'kivy.lang',
            '--hidden-import', 'kivy.input.providers.mouse',
            '--hidden-import', 'kivy.input.providers.mactouch',
            '--hidden-import', 'vosk',
            '--hidden-import', 'pynput.keyboard._darwin',
            '--hidden-import', 'pyperclip',
        ]

        # Remove architecture-specific settings and let PyInstaller auto-detect
        PyInstaller.__main__.run(pyinstaller_args + [script_name])
        
    except Exception as e:
        logging.error(f'PyInstaller failed: {e}')
        raise

def clean_build():
    logging.info('Cleaning build directories...')
    dirs_to_clean = ['build', 'dist', '__pycache__']
    for dir_name in dirs_to_clean:
        if os.path.exists(dir_name):
            shutil.rmtree(dir_name)
            logging.info(f'Deleted {dir_name}')

def create_app_bundle():
    logging.info('Creating macOS app bundle...')
    try:
        info_plist_path = 'dist/VoskTranscriber.app/Contents/Info.plist'
        if os.path.exists(info_plist_path):
            with open(info_plist_path, 'a') as f:
                f.write('''
                <key>NSMicrophoneUsageDescription</key>
                <string>This app needs access to the microphone for audio recording.</string>
                <key>CFBundleDisplayName</key>
                <string>VoskTranscriber</string>
                <key>CFBundleGetInfoString</key>
                <string>Real-time Speech Recognition Tool</string>
                <key>CFBundleIdentifier</key>
                <string>com.vosktranscriber.app</string>
                <key>CFBundleName</key>
                <string>VoskTranscriber</string>
                <key>CFBundleShortVersionString</key>
                <string>1.0.0</string>
                <key>NSHighResolutionCapable</key>
                <true/>
                <key>LSApplicationCategoryType</key>
                <string>public.app-category.productivity</string>
                ''')
    except Exception as e:
        logging.error(f'Failed to create app bundle: {e}')
        raise

def main():
    setup_logging()
    try:
        clean_build()
        run_pyinstaller()
        create_app_bundle()
        logging.info('Build process completed successfully.')
    except Exception as e:
        logging.error(f'Build process failed: {e}')
        exit(1)

if __name__ == '__main__':
    main()
