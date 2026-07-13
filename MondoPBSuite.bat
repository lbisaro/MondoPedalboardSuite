@echo off
:: Cambiar el directorio de trabajo al directorio donde está guardado este archivo .bat
cd /d "C:\Users\lbisa\OneDrive\Documentos\soft\Line 6\MondoPedalboardSuite"

:: Activar el entorno virtual (.venv)
call .venv\Scripts\activate.bat

:: Ejecutar el script de Python
python MondoPBSuite.py

:: Desactivar el entorno virtual al cerrar
call deactivate
