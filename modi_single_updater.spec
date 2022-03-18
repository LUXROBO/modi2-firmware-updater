# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['execute_single_updater.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('modi2_firmware_updater/assets', 'modi2_firmware_updater/assets'),
        ('version.txt', '.')
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False
)

pyz = PYZ(
    a.pure, a.zipped_data, cipher=block_cipher
)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='MODI+ Firmware Updater',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    icon='network_module.ico',
)

app = BUNDLE(
    exe,
    name='MODI+ Firmware Updater.app',
    icon='network_module.ico',
    bundle_identifier=None,
)