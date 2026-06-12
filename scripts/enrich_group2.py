import json

filepath_tags = 'utils/tags.json'
with open(filepath_tags, 'r', encoding='utf-8') as f:
    tags_data = json.load(f)

# Add Modulation tags
tags_data["Modulation"] = {
    "Chorus": {"type": "Efecto", "description": "Duplica la señal, la retrasa y la desafina levemente para crear amplitud y riqueza."},
    "Flanger": {"type": "Efecto", "description": "Retrasos ultracortos con feedback que generan un barrido intenso tipo 'avión jet'."},
    "Phaser": {"type": "Efecto", "description": "Filtros de fase que crean picos de ecualización en movimiento (efecto vocal y burbujeante)."},
    "Tremolo / Vibrato": {"type": "Efecto", "description": "Tremolo altera el volumen rítmicamente. Vibrato altera la afinación rítmicamente."},
    "Rotary": {"type": "Efecto", "description": "Emulación mecánica de un parlante giratorio Leslie (clásico de órganos y blues)."},
    "Analog / BBD": {"type": "Circuito", "description": "Chips analógicos 'Bucket Brigade'. Tono cálido, orgánico y un poco oscuro."},
    "Digital": {"type": "Circuito", "description": "Procesamiento digital. Alta fidelidad, transparente y ultrapreciso."}
}

# Add Pitch/Synth tags
tags_data["Pitch/Synth"] = {
    "Octaver": {"type": "Efecto", "description": "Añade notas una o dos octavas exactas por encima o por debajo de lo que tocás."},
    "Harmonizer": {"type": "Efecto", "description": "Permite sumar intervalos musicales (3ras, 5tas). Muchos son inteligentes y siguen la escala."},
    "Whammy": {"type": "Efecto", "description": "Alteración extrema de la afinación controlada en tiempo real por un pedal de expresión."},
    "Synth": {"type": "Efecto", "description": "Generadores de sintetizador puro (ondas cuadradas/sierra) disparados por la guitarra."}
}

with open(filepath_tags, 'w', encoding='utf-8') as f:
    json.dump(tags_data, f, indent=2, ensure_ascii=False)


filepath_catalog = 'utils/helix_catalog.json'
with open(filepath_catalog, 'r', encoding='utf-8') as f:
    catalog = json.load(f)

# --- Modulation Logic ---
def get_mod_data(name, based_on):
    n = name.lower()
    b = based_on.lower() if based_on else ""
    
    tags = []
    instruments = ["Universal"]
    desc = ""

    # Effect Type
    if "chorus" in n or "chorus" in b or "dimension" in b or "ce-1" in b:
        tags.append("Chorus")
        desc = "Efecto de coro que ensancha la señal para un sonido más rico y estéreo."
    elif "flanger" in n or "flange" in n or "a/da" in b or "electric mistress" in b:
        tags.append("Flanger")
        desc = "Barrido tipo jet clásico creado por retrasos en fase y retroalimentación."
    elif "phase" in n or "stone" in b or "univibe" in b or "vibe" in n:
        if "univibe" in b or "vibe" in n:
            tags.extend(["Phaser", "Tremolo / Vibrato"])
            desc = "Clásico efecto Univibe. Combina phasing profundo con vibrato sutil."
        else:
            tags.append("Phaser")
            desc = "Filtro de fase oscilante para tonos líquidos y funk."
    elif "tremolo" in n or "trem" in n or "vibrato" in n or "opto" in b or "bias" in b or "panner" in n or "pan" in b:
        tags.append("Tremolo / Vibrato")
        desc = "Modulación de amplitud (volumen) o tono, aportando movimiento rítmico."
    elif "rotary" in n or "leslie" in b or "vibratone" in b:
        tags.append("Rotary")
        desc = "Simulación del legendario altavoz rotatorio mecánico."
    else:
        tags.append("Chorus")
        desc = f"Simulación de modulación {based_on if based_on else n}."

    # Circuit
    if "boss" in b or "mxr" in b or "electro-harmonix" in b or "analog" in n or "bucket" in b or "ce-1" in b:
        tags.append("Analog / BBD")
    elif "digital" in n or "tc electronic" in b or "studio" in n or "rack" in b:
        tags.append("Digital")
    else:
        # Most legacy line 6 mods are digital or emulate digital
        if "line 6" in b and "analog" not in n:
            tags.append("Digital")
        elif not any(t in tags for t in ["Analog / BBD", "Digital"]):
            tags.append("Analog / BBD") # default assumption for vintage stomps

    # Bass specific
    if "bass" in n or "ebs" in b:
        instruments = ["Bass"]

    return {"tags": list(dict.fromkeys(tags)), "instruments": instruments, "description": desc}


# --- Pitch/Synth Logic ---
def get_pitch_data(name, based_on):
    n = name.lower()
    b = based_on.lower() if based_on else ""
    
    tags = []
    instruments = ["Universal"]
    desc = ""

    # Effect Type
    if "octav" in n or "octav" in b or "oc-2" in b or "pog" in b or "up" in n or "down" in n:
        tags.append("Octaver")
        desc = "Generador de octavas para engrosar riffs o emular sintetizadores graves."
        if "pog" in b: tags.append("Digital")
        else: tags.append("Analog / BBD")
    elif "whammy" in n or "wham" in n or "bend" in n:
        tags.extend(["Whammy", "Digital"])
        desc = "Alteración extrema de tono controlada por expresión, popularizada por Tom Morello y Dimebag."
    elif "synth" in n or "synth" in b or "string" in n or "oscillator" in n or "generator" in n or "growl" in n:
        tags.extend(["Synth", "Digital"])
        desc = "Sintetizador disparado por la nota del instrumento. Genera ondas cuadradas, sierra, etc."
    elif "harmony" in n or "harmonizer" in b or "pitch" in n or "shift" in n or "eventide" in b or "h3000" in b:
        tags.extend(["Harmonizer", "Digital"])
        desc = "Pitch shifter que permite añadir intervalos armónicos fijos o inteligentes a tu interpretación."
        if "eventide" in b:
            tags.append("Studio")
    else:
        tags.extend(["Synth", "Digital"])
        desc = f"Simulación de Pitch/Synth {based_on if based_on else n}."
        
    # Bass
    if "bass" in n or "ebs" in b or "oc-2" in b:
        if "oc-2" in b: instruments = ["Guitar", "Bass"]
        else: instruments = ["Bass"]

    return {"tags": list(dict.fromkeys(tags)), "instruments": instruments, "description": desc}


updated_count = 0

# Process Modulation
for m in catalog['catalog'].get('Modulation', []):
    data = get_mod_data(m['name'], m.get('based_on', ''))
    m['tags'] = data['tags']
    m['instruments'] = data['instruments']
    m['description'] = data['description']
    updated_count += 1

# Process Pitch/Synth
for m in catalog['catalog'].get('Pitch/Synth', []):
    data = get_pitch_data(m['name'], m.get('based_on', ''))
    m['tags'] = data['tags']
    m['instruments'] = data['instruments']
    m['description'] = data['description']
    updated_count += 1


with open(filepath_catalog, 'w', encoding='utf-8') as f:
    json.dump(catalog, f, indent=2, ensure_ascii=False)

print(f"Group 2 (Modulation, Pitch/Synth) successfully enriched! ({updated_count} models total)")
