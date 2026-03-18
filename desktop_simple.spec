# -*- mode: python ; coding: utf-8 -*-

import os

# 确定项目根目录
project_root = os.path.abspath('.')

block_cipher = None

# 收集需要的数据文件
datas = [
    (os.path.join(project_root, 'frontend', 'dist'), 'frontend/dist'),
    (os.path.join(project_root, '.env'), '.'),
    (os.path.join(project_root, 'backend', 'app'), 'app'),
]

# 排除不需要的大型库
excludes = [
    'torch',
    'tensorflow',
    'transformers',
    'sklearn',
    'scipy',
    'pandas',
    'matplotlib',
    'cv2',
    'av',
    'soundfile',
    'imageio',
    'nltk',
    'pygame',
    'PIL._tkinter_finder',
    'tkinter',
    'tornado',
]

a = Analysis(['desktop_app.py'],
             pathex=[project_root, os.path.join(project_root, 'backend')],
             binaries=[],
             datas=datas,
             hiddenimports=[
                 'flask',
                 'flask_cors',
                 'werkzeug.serving',
                 'PyQt5',
                 'PyQt5.QtWebEngineWidgets',
                 'PyQt5.QtWebEngineCore',
                 'PyQt5.QtWebChannel',
                 'PyQt5.QtNetwork',
                 'lxml',
                 'docx',
                 'pymupdf',
                 'openai',
                 'httpx',
                 'pydantic',
                 'jinja2',
                 'requests',
             ],
             hookspath=[],
             runtime_hooks=[],
             excludes=excludes,
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          [],
          name='TraceBack',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          upx_exclude=[],
          runtime_tmpdir=None,
          console=False,  # 不显示控制台窗口
          disable_windowed_traceback=False,
          target_arch=None,
          codesign_identity=None,
          entitlements_file=None,
          icon=None)
