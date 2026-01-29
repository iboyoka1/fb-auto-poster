"""
PyInstaller build configuration for FB Auto-Poster Windows EXE
"""

import sys
import os
from pathlib import Path

# Get project root
PROJECT_ROOT = Path(__file__).parent

spec = {
    'name': 'fb-auto-poster',
    'version': '1.0.0',
    'author': 'FB Auto-Poster Team',
    'script': str(PROJECT_ROOT / 'run_server.py'),
    'icon': None,  # You can add an icon file path here
    'console': True,  # Show console window
    'windowed': False,
    'collect_all': {
        'flask': True,
        'playwright': True,
        'security': True,
    },
    'hidden_imports': [
        'flask',
        'werkzeug',
        'jinja2',
        'bcrypt',
        'jwt',
        'cryptography',
        'security',
        'setup_wizard',
        'configs',
    ],
    'exclude_modules': [
        'matplotlib',
        'numpy',
        'pandas',
        'scipy',
    ],
    'data_files': [
        ('static', str(PROJECT_ROOT / 'static')),
        ('templates', str(PROJECT_ROOT / 'templates')),
        ('requirements.txt', str(PROJECT_ROOT / 'requirements.txt')),
    ]
}

# PyInstaller command line
# pyinstaller --onefile --windowed --icon=icon.ico --name="FB Auto-Poster" run_server.py
