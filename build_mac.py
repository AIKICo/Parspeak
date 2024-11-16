import os
import logging
import shutil
import PyInstaller.__main__

def setup_logging():
    logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')

def run_pyinstaller():
    logging.info('Running PyInstaller...')
    script_name = 'main.py'
    try:
        PyInstaller.__main__.run([
            # Core dependencies
            '--collect-all', 'vosk',
            '--collect-all', 'sounddevice',
            '--collect-all', 'numpy',
            '--collect-all', 'pynput',
            # Additional settings
            '--name', 'VoskTranscriber',
            '--windowed',
            '--onedir',
            '--clean',
            '--noconfirm',
            '--target-arch', 'x86_64',
            '--osx-bundle-identifier', 'com.vosktranscriber.app',
            # Hidden imports
            '--hidden-import', 'vosk',
            '--hidden-import', 'sounddevice',
            '--hidden-import', 'numpy',
            '--hidden-import', 'pynput',
            script_name
        ])
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
