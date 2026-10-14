# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec - PDF Analyzer 0.26.0-m4a, Windows 64-bit, onedir.
# Onedir (nu onefile) si fara UPX: reduce alarmele false din Windows Defender.

from pathlib import Path

ROOT = Path(SPECPATH).parent
TESSERACT_DIR = ROOT / "runtime" / "Tesseract-OCR"

# text_engine.py cauta Tesseract in Path(__file__).parents[1] / "runtime",
# adica in folderul _internal al build-ului -> se copiaza acolo.
datas = []
if (TESSERACT_DIR / "tesseract.exe").is_file():
    datas.append((str(TESSERACT_DIR), "runtime/Tesseract-OCR"))

a = Analysis(
    [str(ROOT / "app.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter"],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="PDF Analyzer",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    version=str(Path(SPECPATH) / "version_info.txt"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="PDF Analyzer",
)
