# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['desktop_run.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('..\\frontend\\dist', 'frontend\\dist'),
        ('app\\data\\licenses.json', 'app\\data')
    ],
    hiddenimports=['requests'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'torch', 'tensorflow', 'scipy', 'sklearn', 'matplotlib', 
        'numpy', 'pandas', 'pygame', 'cv2', 'av', 'transformers',
        'onnxruntime', 'boto3', 'grpc', 'uvicorn', 'nltk', 'pyqt5'
    ],
    noarchive=False,
    optimize=2,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='TraceBackDesktop',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # 隐藏控制台窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)