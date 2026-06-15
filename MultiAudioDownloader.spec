# -*- mode: python ; coding: utf-8 -*-
import os
import glob
from PyInstaller.utils.hooks import collect_all

block_cipher = None

# Collect all for imageio_ffmpeg and yt_dlp
ffmpeg_datas, ffmpeg_binaries, ffmpeg_hiddenimports = collect_all('imageio_ffmpeg')
ytdlp_datas, ytdlp_binaries, ytdlp_hiddenimports = collect_all('yt_dlp')

# Find VC Runtime DLLs in PySide6 package
pyside6_dir = os.path.join('.venv', 'Lib', 'site-packages', 'PySide6')
dll_files = glob.glob(os.path.join(pyside6_dir, '*140*.dll'))
vc_binaries = [(dll, '.') for dll in dll_files]

datas = [('node/node.exe', 'node')] + ffmpeg_datas + ytdlp_datas
binaries = vc_binaries + ffmpeg_binaries + ytdlp_binaries
hiddenimports = ['pyinstaller_utils'] + ffmpeg_hiddenimports + ytdlp_hiddenimports

a = Analysis(
    ['src/download_app.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='MultiAudioDownloader',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
