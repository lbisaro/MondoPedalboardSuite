import json

filepath_tags = 'utils/tags.json'
with open(filepath_tags, 'r', encoding='utf-8') as f:
    tags_data = json.load(f)

# Add Dynamic tags
tags_data["Dynamic"] = {
    "Compressor": {"type": "Efecto", "description": "Reduce el rango dinámico, nivela picos y sube señales débiles."},
    "Noise Gate": {"type": "Efecto", "description": "Cierra el paso de audio cuando no se toca, eliminando ruido."},
    "Limiter": {"type": "Efecto", "description": "Compresor extremo, evita que la señal pase de cierto límite."},
    "Sustainer": {"type": "Efecto", "description": "Optimizado para prolongar las notas al máximo sin perder el ataque inicial."},
    "Stompbox": {"type": "Formato", "description": "Emula pedales de piso clásicos. Suelen agregar color y frecuencias medias."},
    "Studio": {"type": "Formato", "description": "Emula procesadores de rack de estudio. Más limpios, precisos y con alta fidelidad."},
    "Optical": {"type": "Circuito", "description": "Circuito óptico. Suave, extremadamente musical y con un ataque más redondeado."},
    "FET": {"type": "Circuito", "description": "Transistores de Efecto de Campo. Ataque híper rápido, agresivo y percusivo."},
    "VCA": {"type": "Circuito", "description": "Controlado por Voltaje. El estándar moderno: rápido, punchy y transparente."},
    "OTA": {"type": "Circuito", "description": "Circuito clásico de pedales antiguos. Tono aplastado ('squishy') que suele colorear bastante."}
}

with open(filepath_tags, 'w', encoding='utf-8') as f:
    json.dump(tags_data, f, indent=2, ensure_ascii=False)

filepath_catalog = 'utils/helix_catalog.json'
with open(filepath_catalog, 'r', encoding='utf-8') as f:
    catalog = json.load(f)

def get_dynamic_data(name, based_on):
    n = name.lower()
    b = based_on.lower() if based_on else ""
    
    tags = []
    instruments = ["Guitar", "Bass"]
    desc = ""

    # Effect Type
    if "gate" in n or "gate" in b or "noise" in n:
        tags.append("Noise Gate")
        tags.append("Studio") # Usually gates in Helix are transparent
        desc = "Eliminador de ruido diseñado para limpiar el silencio entre notas."
    elif "limit" in n or "limit" in b:
        tags.append("Limiter")
        tags.append("Studio")
        desc = "Limitador de pared de ladrillo. Evita recortes (clipping) en la señal."
    elif "sustainer" in n or "sust" in b or "cs-3" in b:
        tags.append("Sustainer")
        tags.append("Stompbox")
        desc = "Diseñado para emparejar el nivel y prolongar la vibración natural de la nota."
    else:
        tags.append("Compressor")
        
    # Format & Circuit
    if "la-2a" in b or "la studio" in n or "teletronix" in b:
        tags.extend(["Studio", "Optical"])
        instruments = ["Universal"]
        desc = "Basado en el Teletronix LA-2A. Clásico de estudio, cálido y muy musical. Ideal general y bajo."
    elif "1176" in b or "fet" in b or "urei" in b or "1176" in n:
        tags.extend(["Studio", "FET"])
        instruments = ["Universal"]
        desc = "Basado en el Urei 1176. Ataque rapidísimo, muy agresivo y cortante."
    elif "dyna comp" in b or "red squeeze" in n or "ross" in b or "mxr" in b:
        tags.extend(["Stompbox", "OTA"])
        desc = "Clásico compresor percusivo de pedal, colorea la señal con un tono retro."
    elif "kinky" in n or "xotic" in b or "sp comp" in b:
        tags.extend(["Stompbox", "OTA"])
        desc = "Compresor de pedal tipo OTA pero con capacidades de mezcla paralela (blend)."
    elif "dbx" in b or "ashly" in b or "rochester" in n or "vca" in b:
        tags.extend(["Studio", "VCA"])
        instruments = ["Universal"]
        desc = "Compresor VCA de rack, muy rápido, punchy y altamente transparente."
    elif "line 6" in b or "deluxe comp" in n or "3-band" in n or "original" in b or "auto swell" in n:
        if "auto swell" in n:
            tags = ["Noise Gate"]
            desc = "Diseño original que simula el uso del control de volumen de la guitarra para eliminar el ataque de la púa."
        else:
            tags.extend(["Studio", "VCA"])
            desc = "Diseño original hipertransparente. Excelente para no alterar el tono base del instrumento."
        
    # Bass specific
    if "ebs" in b or "multicomp" in b or "darkglass" in b or "bass" in n:
        instruments = ["Bass"]
        desc = "Compresor optimizado especialmente para las bajas frecuencias del bajo eléctrico."
        if "ebs" in b: tags.extend(["Stompbox", "VCA"])
        
    # Fallback
    if not desc:
        desc = f"Simulación de procesamiento dinámico {based_on if based_on else n}."
        if "Noise Gate" not in tags and "Compressor" not in tags: tags.append("Compressor")
        if "Stompbox" not in tags and "Studio" not in tags: tags.append("Stompbox")

    # Remove duplicates
    tags = list(dict.fromkeys(tags))
    
    return {"tags": tags, "instruments": instruments, "description": desc}

updated_count = 0
for m in catalog['catalog'].get('Dynamic', []):
    data = get_dynamic_data(m['name'], m.get('based_on', ''))
    m['tags'] = data['tags']
    m['instruments'] = data['instruments']
    m['description'] = data['description']
    updated_count += 1

with open(filepath_catalog, 'w', encoding='utf-8') as f:
    json.dump(catalog, f, indent=2, ensure_ascii=False)

print(f"Dynamics successfully enriched! ({updated_count} models)")
