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


def _load_db() -> dict:
    """Carga modules.json y devuelve el dict 'modules'."""
    with open(_JSON_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("modules", {})


def _build_legacy_name(entry: dict) -> str:
    """Reconstruye 'Name (variant)' desde los campos separados del JSON."""
    name    = entry.get("name", "Unknown")
    variant = entry.get("variant")
    if variant:
        return f"{name} ({variant})"
    return name


# ── Carga inicial ────────────────────────────────────────────────────────────
_db: dict[str, dict] = _load_db()

# Interfaz legada: {hex_id: [category, 'Name (variant)']}
modules: dict[str, list] = {
    hex_id: [entry["category"], _build_legacy_name(entry)]
    for hex_id, entry in _db.items()
}

# Interfaz enriquecida: {hex_id: {todos los campos}}
modules_full: dict[str, dict] = {
    hex_id: {**entry, "id": hex_id}
    for hex_id, entry in _db.items()
}


def get_module(hex_id: str) -> Optional[dict]:
    """
    Devuelve el registro completo de un módulo dado su ID hexadecimal.
    Retorna None si el ID no existe en la base de datos.

    Ejemplo:
        >>> get_module('cd032b')
        {'id': 'cd032b', 'category': 'Cab', 'name': '4x10 US Super', ...}
    """
    entry = _db.get(hex_id)
    if entry is None:
        return None
    return {**entry, "id": hex_id}


def reload() -> None:
    """
    Recarga la base de datos desde modules.json en tiempo de ejecución.
    Útil cuando la interfaz gráfica modifica el JSON y se quiere
    reflejar el cambio sin reiniciar la aplicación.
    """
    global _db, modules, modules_full
    _db = _load_db()
    modules = {
        hex_id: [entry["category"], _build_legacy_name(entry)]
        for hex_id, entry in _db.items()
    }
    modules_full = {
        hex_id: {**entry, "id": hex_id}
        for hex_id, entry in _db.items()
    }
