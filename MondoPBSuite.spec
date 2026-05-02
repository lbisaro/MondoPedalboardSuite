# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec - Mondo PedalBoard Suite
# Modo: onefile -> genera un unico MondoPBSuite.exe en la raiz del proyecto

import sys
from PyInstaller.utils.hooks import collect_data_files

qtawesome_datas  = collect_data_files('qtawesome')
pyqtgraph_datas  = collect_data_files('pyqtgraph')

all_datas = qtawesome_datas + pyqtgraph_datas + [
    ('docs/MondoPBSuite_Logo.png', 'docs'),
]

block_cipher = None

a = Analysis(
    ['MondoPBSuite.py'],
    pathex=['.'],
    binaries=[],
    datas=all_datas,
    hiddenimports=[
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',
        'PySide6.QtOpenGL',
        'PySide6.QtOpenGLWidgets',
        'pyqtgraph',
        'pyqtgraph.graphicsItems',
        'pyqtgraph.widgets',
        'sounddevice',
        '_sounddevice_data',
        'soundfile',
        'numpy',
        'scipy',
        'scipy.signal',
        'scipy.fft',
        'pyloudnorm',
        'qtawesome',
        'styles',
        'eq_analyzer_widget',
        'preset_compare_widget',
        'device_connection',
        'audio_comparator',
        'ui_utils',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'IPython', 'jupyter'],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# Modo onefile: todo empaquetado en un solo ejecutable
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    exclude_binaries=False,   # onefile: incluir todo en el exe
    name='MondoPBSuite',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='docs/MondoPBSuite_logo.ico',
)
# Sin bloque COLLECT -> no genera carpeta dist\MondoPBSuite\_internal
