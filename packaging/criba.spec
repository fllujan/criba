# PyInstaller: Criba.app (macOS) y la carpeta Criba\ con Criba.exe (Windows).
# Uso, desde la raíz del repositorio: uv run pyinstaller packaging/criba.spec --noconfirm
# ruff: noqa  (lo ejecuta PyInstaller, con sus propios nombres globales)
import re
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

ROOT = Path(SPECPATH).parent
SRC = ROOT / "src"
VERSION = re.search(
    r'__version__ = "([^"]+)"', (SRC / "criba" / "__init__.py").read_text(encoding="utf-8")
)[1]
MAC = sys.platform == "darwin"

# Qt que Criba no usa: PyInstaller solo empaqueta lo importado, pero algunas dependencias
# opcionales arrastran estos módulos.
QT_UNUSED = [
    "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineQuick",
    "PySide6.QtWebEngineWidgets",
    "PySide6.QtWebView",
    "PySide6.QtMultimedia",
    "PySide6.QtQuick3D",
    "PySide6.Qt3DCore",
    "PySide6.QtCharts",
    "PySide6.QtGraphs",
    "PySide6.QtDataVisualization",
    "PySide6.QtLocation",
    "PySide6.QtPositioning",
    "PySide6.QtBluetooth",
    "PySide6.QtNfc",
    "PySide6.QtSensors",
    "PySide6.QtSerialPort",
    "PySide6.QtWidgets",
    "PySide6.QtDesigner",
    "PySide6.QtUiTools",
]

a = Analysis(
    [str(SRC / "criba" / "__main__.py")],
    pathex=[str(SRC)],
    # QML, fuentes, iconos y prompts (todo lo que no es .py dentro del paquete).
    datas=collect_data_files("criba", excludes=["**/*.ts", "**/.gitkeep"]),
    hiddenimports=[*collect_submodules("keyring.backends"), "criba.gui.selftest"],
    excludes=["tkinter", "pytest", "mypy", "ruff", *QT_UNUSED],
    noarchive=False,
    optimize=0,  # pydantic y los docstrings de la CLI los necesitan
)

# PyInstaller recoge todos los plugins QML aunque no se usen (WebEngine solo pesa 224 MB).
# El QML de Criba solo importa QtQuick, Controls.Basic, Dialogs, Layouts y Shapes.
QT_UNUSED_FILES = re.compile(
    r"WebEngine|WebView|WebChannel|WebSockets|Quick3D|Qt3D|Multimedia|SpatialAudio|Charts"
    r"|Graphs|DataVisualization|Location|Positioning|Sensors|TextToSpeech|RemoteObjects"
    r"|Scxml|StateMachine|QtTest|Qt5Compat|VirtualKeyboard|Qt6?Pdf|qpdf|QtQuick/Pdf"
    r"|Controls/(Material|Universal|Imagine|Fusion|FluentWinUI3|iOS|macOS|Windows)\b",
    re.IGNORECASE,
)


def _used(entry):
    dest, src, kind = entry[0].replace("\\", "/"), str(entry[1]), entry[2]
    if kind == "SYMLINK":  # p. ej. Resources/QtWebView -> el framework que se quita
        return not QT_UNUSED_FILES.search(dest + " " + src)
    return not (dest.startswith("PySide6/") and QT_UNUSED_FILES.search(dest))


a.binaries = [e for e in a.binaries if _used(e)]
a.datas = [e for e in a.datas if _used(e)]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Criba",
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,  # la del Python que construye: arm64 o x86_64
    codesign_identity=None,  # firma ad hoc; con Developer ID se firma después
    entitlements_file=None,
    icon=str(ROOT / "packaging" / ("macos/criba.icns" if MAC else "windows/criba.ico")),
    upx=False,
)

coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="Criba")

if MAC:
    app = BUNDLE(
        coll,
        name="Criba.app",
        icon=str(ROOT / "packaging" / "macos" / "criba.icns"),
        bundle_identifier="io.github.fllujan.criba",
        version=VERSION,
        info_plist={
            "CFBundleName": "Criba",
            "CFBundleDisplayName": "Criba",
            "CFBundleShortVersionString": VERSION,
            "CFBundleVersion": VERSION,
            "CFBundleDevelopmentRegion": "es",
            "LSMinimumSystemVersion": "14.0",  # lo que exige Qt 6.12
            "LSApplicationCategoryType": "public.app-category.education",
            "NSHighResolutionCapable": True,
            "NSRequiresAquaSystemAppearance": False,  # modo oscuro automático
            "NSHumanReadableCopyright": "© Félix Luján",
        },
    )
