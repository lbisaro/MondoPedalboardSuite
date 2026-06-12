import json

filepath_tags = 'utils/tags.json'
with open(filepath_tags, 'r', encoding='utf-8') as f:
    tags_data = json.load(f)

# Update the previous Analog / BBD to just Analog
if "Modulation" in tags_data and "Analog / BBD" in tags_data["Modulation"]:
    tags_data["Modulation"]["Analog"] = tags_data["Modulation"].pop("Analog / BBD")
if "Pitch/Synth" in tags_data and "Analog / BBD" in tags_data["Pitch/Synth"]:
    tags_data["Pitch/Synth"]["Analog"] = tags_data["Pitch/Synth"].pop("Analog / BBD")

# Add Delay tags
tags_data["Delay"] = {
    "Analog": {"type": "Tipo de Delay", "description": "Delays construidos con chips BBD. Repeticiones oscuras, cálidas y orgánicas."},
    "Tape": {"type": "Tipo de Delay", "description": "Emulaciones de retardo en cinta o tambor magnético. Saturación y leve modulación natural."},
    "Digital": {"type": "Tipo de Delay", "description": "Delays cristalinos y limpios. Las repeticiones son copias exactas de la señal."},
    "Modulated": {"type": "Tipo de Delay", "description": "Delays que añaden efecto de chorus o vibrato a sus colas de repetición."}
}

# Add Reverb tags
tags_data["Reverb"] = {
    "Spring": {"type": "Tipo de Reverb", "description": "Reverb física de resortes. El clásico sonido 'boing' de los amplificadores de los 60s."},
    "Plate": {"type": "Tipo de Reverb", "description": "Reverb de placa de metal de estudio. Muy densa y brillante, ideal para leads."},
    "Ambient": {"type": "Tipo de Reverb", "description": "Recreación de espacios acústicos reales como cuartos, iglesias o grandes salas de concierto."},
    "Synth": {"type": "Tipo de Reverb", "description": "Reverbs modernas que incluyen octavas o pitch-shifting en la cola para crear colchones espaciales."}
}

with open(filepath_tags, 'w', encoding='utf-8') as f:
    json.dump(tags_data, f, indent=2, ensure_ascii=False)


filepath_catalog = 'utils/helix_catalog.json'
with open(filepath_catalog, 'r', encoding='utf-8') as f:
    catalog = json.load(f)

# Rename 'Analog / BBD' to 'Analog' in previous groups
for group in ["Modulation", "Pitch/Synth"]:
    for m in catalog['catalog'].get(group, []):
        if "Analog / BBD" in m.get("tags", []):
            m["tags"].remove("Analog / BBD")
            m["tags"].append("Analog")

# --- Delay Logic ---
def get_delay_data(name, based_on):
    n = name.lower()
    b = based_on.lower() if based_on else ""
    
    tags = []
    instruments = ["Universal"]
    desc = ""

    if "analog" in n or "bucket" in b or "memory man" in b or "dm-2" in b or "carbon copy" in b or "bbd" in b:
        tags.append("Analog")
        desc = "Delay analógico tradicional. Repeticiones cálidas que se funden bellamente en el fondo de la mezcla."
        if "memory man" in b or "mod" in n: tags.append("Modulated")
    elif "tape" in n or "echo" in n or "echo" in b or "echoplex" in b or "binson" in b or "drum" in n:
        tags.append("Tape")
        desc = "Emulación de retardo magnético. Añade el clásico 'wow and flutter' e imperfecciones de la cinta."
    elif "digital" in n or "tc electronic" in b or "2290" in b or "dd-7" in b:
        tags.append("Digital")
        desc = "Delay digital de alta fidelidad. Repeticiones limpias, claras y exactas."
    elif "mod" in n or "chorus" in n:
        tags.append("Modulated")
        desc = "Delay con un fuerte componente de modulación en sus ecos."
        if not any(t in tags for t in ["Analog", "Tape", "Digital"]): tags.append("Digital")
    else:
        tags.append("Digital")
        desc = f"Simulación de Delay {based_on if based_on else n}."

    return {"tags": list(dict.fromkeys(tags)), "instruments": instruments, "description": desc}


# --- Reverb Logic ---
def get_reverb_data(name, based_on):
    n = name.lower()
    b = based_on.lower() if based_on else ""
    
    tags = []
    instruments = ["Universal"]
    desc = ""

    if "spring" in n or "tank" in n or "surf" in n:
        tags.append("Spring")
        desc = "Reverb de resortes física. Aporta un goteo percusivo ('drip') clásico del Surf y el Rockabilly."
    elif "plate" in n or "emt" in b:
        tags.append("Plate")
        desc = "Reverb de placa electromecánica. Muy difusa y brillante, espectacular para solos de guitarra."
    elif "hall" in n or "room" in n or "cave" in n or "chamber" in n or "tile" in n:
        tags.append("Ambient")
        desc = "Recrea acústicamente un espacio físico real, dándole tridimensionalidad natural al instrumento."
    elif "shimmer" in n or "octo" in n or "particle" in n or "glitz" in n or "searchlights" in n or "ganymede" in n or "synth" in n:
        tags.append("Synth")
        desc = "Reverb ambiental moderna que incluye síntesis u octavas en su cola (Shimmer). Ideal para paisajes sonoros."
    else:
        tags.append("Ambient")
        desc = f"Simulación de Reverb {based_on if based_on else n}."
        
    return {"tags": list(dict.fromkeys(tags)), "instruments": instruments, "description": desc}


updated_count = 0

# Process Delay
for m in catalog['catalog'].get('Delay', []):
    data = get_delay_data(m['name'], m.get('based_on', ''))
    m['tags'] = data['tags']
    m['instruments'] = data['instruments']
    m['description'] = data['description']
    updated_count += 1

# Process Reverb
for m in catalog['catalog'].get('Reverb', []):
    data = get_reverb_data(m['name'], m.get('based_on', ''))
    m['tags'] = data['tags']
    m['instruments'] = data['instruments']
    m['description'] = data['description']
    updated_count += 1


with open(filepath_catalog, 'w', encoding='utf-8') as f:
    json.dump(catalog, f, indent=2, ensure_ascii=False)

print(f"Group 3 (Delay, Reverb) successfully enriched! ({updated_count} models total)")
