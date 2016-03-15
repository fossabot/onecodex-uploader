# -*- mode: python -*-

block_cipher = None
ASSET_DIR = 'onecodex_uploader/icons/'
execfile('onecodex_uploader/version.py')

import os
from subprocess import call

call(['pyside-uic', 'onecodex_uploader/mainwindow.ui'],
     stdout=open('onecodex_uploader/mainwindow_ui.py', 'w'))

a = Analysis(
    ['uploader.py'],
    pathex=['C:\\Users\\Roderick\\Documents\\onecodex-uploader'],
    binaries=None,
    datas=None,
    hiddenimports=['HTMLParser'],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher
)

for fdir, _, fnames in os.walk(ASSET_DIR):
    d = os.path.normpath(os.path.relpath(fdir, ASSET_DIR))
    for fname in fnames:
        if fname.endswith(('.png', '.ico')):
            a.datas.append((os.path.join('icons', d, fname),
                            os.path.join(ASSET_DIR, d, fname), 'DATA'))

pyz = PYZ(
    a.pure,
    a.zipped_data,
    cipher=block_cipher
)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    name='One Codex Uploader',
    debug=False,
    strip=False,
    upx=True,
    console=False,
    icon='onecodex_uploader\\icons\\win_logo.ico'
)
