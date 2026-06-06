"""
utils/modules.py — Cargador de la base de datos de módulos de la Helix LT.

La fuente de datos es utils/modules.json (editable, extensible).
Este módulo expone dos interfaces:

  modules        — dict legado {hex_id: [category, 'Name (variant)']}
                   Mantenido para compatibilidad con preset_parser.py.

  modules_full   — dict enriquecido {hex_id: {...campos completos...}}
                   Para uso futuro en la interfaz gráfica y la API.

  get_module(hex_id) → dict | None
                   Devuelve el registro completo de un módulo por su ID.
"""

from __future__ import annotations

import json
import os
from typing import Optional

# ── Ruta al archivo JSON (mismo directorio que este módulo) ──────────────────
_JSON_PATH = os.path.join(os.path.dirname(__file__), "modules.json")

# Diccionarios de datos principales
_models_db: dict[str, dict] = {}
_usb_mapping: dict[str, dict] = {}

def _load_db() -> None:
    """Carga modules.json y puebla las bases de datos."""
    global _models_db, _usb_mapping
    try:
        with open(_JSON_PATH, encoding="utf-8") as f:
            data = json.load(f)
        _models_db = data.get("models", {})
        _usb_mapping = data.get("usb_mapping", {})
    except (FileNotFoundError, json.JSONDecodeError):
        _models_db = {}
        _usb_mapping = {}

def _build_legacy_name(model: dict, variant: Optional[str]) -> str:
    """Reconstruye 'Name (variant)' desde el modelo genérico."""
    name = model.get("name", "Unknown")
    if variant:
        return f"{name} ({variant})"
    return name

# ── Carga inicial ────────────────────────────────────────────────────────────
_load_db()

# Interfaz legada: {hex_id: [category, 'Name (variant)']}
# Mantenido para compatibilidad con preset_parser.py
modules: dict[str, list] = {}
modules_full: dict[str, dict] = {}

def _rebuild_interfaces() -> None:
    """Reconstruye los diccionarios legados modules y modules_full a partir del mapeo USB."""
    global modules, modules_full
    modules.clear()
    modules_full.clear()
    
    for hex_id, mapping in _usb_mapping.items():
        model_id = mapping.get("model_id")
        variant = mapping.get("variant")
        model = _models_db.get(model_id)
        
        if model:
            # Diccionario legado (usado por preset_parser)
            category = model.get("category", "Unknown")
            name_with_variant = _build_legacy_name(model, variant)
            modules[hex_id] = [category, name_with_variant]
            
            # Diccionario completo
            modules_full[hex_id] = {
                **model,
                "variant": variant,
                "model_id": model_id,
                "hex_id": hex_id
            }

# Construir interfaces al inicio
_rebuild_interfaces()


def get_module(hex_id: str) -> Optional[dict]:
    """
    Devuelve el registro completo de un módulo dado su ID hexadecimal.
    Retorna None si el ID no existe en la base de datos de mapeo USB.

    Ejemplo:
        >>> get_module('cd0200')
        {'name': 'Grammatico GSG', 'category': 'Amp', 'variant': 'mono', 'hex_id': 'cd0200', ...}
    """
    return modules_full.get(hex_id)


def reload() -> None:
    """
    Recarga la base de datos desde modules.json en tiempo de ejecución.
    Actualiza los diccionarios in-place para que las referencias sigan siendo válidas.
    """
    _load_db()
    _rebuild_interfaces()


def save_module(hex_id: str, subcategory: str, model_id: str, model_data: dict) -> bool:
    """
    Actualiza o crea un módulo en la nueva base de datos relacional.
    """
    try:
        with open(_JSON_PATH, "r", encoding="utf-8") as f:
            full_data = json.load(f)
            
        if "models" not in full_data:
            full_data["models"] = {}
        if "usb_mapping" not in full_data:
            full_data["usb_mapping"] = {}
            
        # Actualizar/Crear el modelo genérico
        full_data["models"][model_id] = model_data
        
        # Crear/Actualizar el mapeo USB
        full_data["usb_mapping"][hex_id] = {
            "model_id": model_id,
            "variant": subcategory
        }
        
        # Escribir al disco
        with open(_JSON_PATH, "w", encoding="utf-8") as f:
            json.dump(full_data, f, indent=2, ensure_ascii=False)
            
        # Recargar en memoria
        reload()
        return True
    except Exception as e:
        print(f"Error al guardar módulo en modules.json: {e}")
        return False

def get_categories() -> dict:
    """Devuelve el diccionario de categorías y subcategorías."""
    try:
        with open(_JSON_PATH, encoding="utf-8") as f:
            data = json.load(f)
        return data.get("categories", {})
    except:
        return {}

