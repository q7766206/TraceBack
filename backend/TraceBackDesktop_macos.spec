# -*- mode: python ; coding: utf-8 -*-

import sys
sys.setrecursionlimit(5000)

a = Analysis(
    ['desktop_run.py'],
    pathex=[],
    binaries=[],
    datas=[('../frontend/dist', 'frontend/dist'), ('app/data/licenses.json', 'app/data')],
    hiddenimports=[
        'requests',
        'PyQt5',
        'PyQt5.QtCore',
        'PyQt5.QtGui',
        'PyQt5.QtWidgets',
        'PyQt5.QtWebEngineWidgets',
        'werkzeug',
        'flask',
        'jinja2',
        'markupsafe',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='TraceBackDesktop',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # macOS 通常不使用控制台
    disable_windowed_traceback=False,
    argv_emulation=True,  # macOS 需要启用
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='TraceBackDesktop',
)

# macOS .app bundle 配置
app = BUNDLE(
    coll,
    name='TraceBackDesktop.app',
    icon=None,
    bundle_identifier='com.mirofish.traceback',
    info_plist={
        'CFBundleShortVersionString': '0.1.0',
        'CFBundleVersion': '0.1.0',
        'NSHighResolutionCapable': 'True',
        'LSBackgroundOnly': 'False',
    },
)
