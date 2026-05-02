"""
make_ico.py - Convierte el logo PNG a formato ICO para PyInstaller.
Se ejecuta automáticamente desde build.ps1 antes de compilar.
Requiere: Pillow  (pip install Pillow)
"""
import os
import sys

try:
    from PIL import Image
except ImportError:
    print("ERROR: Pillow no está instalado. Ejecuta: pip install Pillow")
    sys.exit(1)

root  = os.path.dirname(os.path.abspath(__file__))
png   = os.path.join(root, "docs", "MondoPBSuite_Logo.png")
ico   = os.path.join(root, "docs", "MondoPBSuite_logo.ico")

if not os.path.exists(png):
    print(f"ERROR: No se encontró el logo en: {png}")
    sys.exit(1)

img = Image.open(png).convert("RGBA")
img.save(ico, format="ICO", sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
print(f"ICO generado correctamente: {ico}")
