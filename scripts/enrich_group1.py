import json

filepath_tags = 'utils/tags.json'
with open(filepath_tags, 'r', encoding='utf-8') as f:
    tags_data = json.load(f)

# Add EQ tags
tags_data["EQ"] = {
    "Graphic EQ": {"type": "Tipo de Ecualizador", "description": "Frecuencias fijas controladas por deslizadores. Fáciles de visualizar y rápidos de ajustar."},
    "Parametric EQ": {"type": "Tipo de Ecualizador", "description": "Permite elegir la frecuencia exacta, el ancho de banda (Q) y la ganancia. Súper quirúrgicos."},
    "Studio EQ": {"type": "Tipo de Ecualizador", "description": "Emulaciones de hardware de estudio de alta gama. Aportan color y carácter analógico ('magia')."}
}

# Add Wah tags
tags_data["Wah"] = {
    "Inductor": {"type": "Circuito de Wah", "description": "El circuito clásico tipo Fasel. Tono muy vocal, rasposo y expresivo. El sonido del rock clásico."},
    "Optical": {"type": "Circuito de Wah", "description": "Diseño óptico moderno sin potenciómetro. Barrido más amplio, limpios claros, muy usado en Metal."},
    "Custom": {"type": "Circuito de Wah", "description": "Diseños originales altamente modificables donde puedes alterar las frecuencias base y resonancias."}
}

# Add Filter tags
tags_data["Filter"] = {
    "Envelope": {"type": "Tipo de Filtro", "description": "Filtros de envolvente (Auto-wahs). El filtro reacciona a la fuerza con la que golpees las cuerdas."},
    "LFO Filter": {"type": "Tipo de Filtro", "description": "Barrido automatizado por un oscilador (LFO), generando movimiento constante independiente de tu técnica."},
    "Synth / Ladder": {"type": "Tipo de Filtro", "description": "Filtros basados en sintetizadores. Altamente resonantes y gruesos, logran tonos láser y sintetizados."}
}

with open(filepath_tags, 'w', encoding='utf-8') as f:
    json.dump(tags_data, f, indent=2, ensure_ascii=False)


filepath_catalog = 'utils/helix_catalog.json'
with open(filepath_catalog, 'r', encoding='utf-8') as f:
    catalog = json.load(f)

# --- EQ Logic ---
def get_eq_data(name, based_on):
    n = name.lower()
    b = based_on.lower() if based_on else ""
    
    tags = []
    instruments = ["Universal"]
    desc = ""

    if "graphic" in n or "graphic" in b or "10 band" in n or "ge-7" in b:
        tags.extend(["Graphic EQ", "Stompbox"])
        desc = "Ecualizador gráfico clásico. Ideal para ajustes rápidos o para moldear drásticamente una distorsión."
    elif "parametric" in n or "para" in n:
        tags.extend(["Parametric EQ", "Studio"])
        desc = "Ecualizador paramétrico. Excelente para buscar y destruir frecuencias problemáticas de forma quirúrgica."
    elif "pultec" in b or "studio" in n or "api" in b or "shelf" in n or "console" in b:
        tags.extend(["Studio EQ", "Studio"])
        desc = "Emulación de EQ de consola/estudio analógico. Aporta calidez y sedosidad en agudos y graves."
    elif "cali q" in n or "mesa" in b:
        tags.extend(["Graphic EQ", "Stompbox"])
        instruments = ["Guitar", "Bass"]
        desc = "Basado en el EQ gráfico de 5 bandas del Mesa Boogie Mark IV. El famoso sonido 'Scoop' en V."
    elif "acoustic" in n:
        tags.extend(["Parametric EQ", "Stompbox"])
        instruments = ["Universal"]
        desc = "Ecualizador optimizado para domar los acoples y resonancias de instrumentos acústicos."
    else:
        tags.extend(["Studio EQ"])
        desc = f"Simulación de ecualización {based_on if based_on else n}."
        
    return {"tags": tags, "instruments": instruments, "description": desc}


# --- Wah Logic ---
def get_wah_data(name, based_on):
    n = name.lower()
    b = based_on.lower() if based_on else ""
    
    tags = ["Wah"]
    instruments = ["Guitar"]
    desc = ""

    if "cry" in b or "baby" in b or "vox" in b or "v847" in b or "clyde" in b or "mccoy" in b or "fassel" in n:
        tags.extend(["Inductor", "Vintage"])
        desc = "Clásico circuito inductor tipo Fasel. Tono vocal legendario, indispensable para blues y rock."
    elif "morley" in b or "optical" in b or "bad horsie" in b:
        tags.extend(["Optical", "Modern"])
        desc = "Wah de barrido óptico. Rango frecuencial más extenso y sin partes mecánicas que se desgasten."
    elif "bass" in n or "bass" in b:
        instruments = ["Bass"]
        tags.extend(["Inductor", "Modern"])
        desc = "Wah calibrado específicamente para no perder las frecuencias graves del bajo."
    elif "custom" in n or "line 6" in b or "original" in b or "v-etta" in n:
        tags.extend(["Custom", "Modern"])
        desc = "Diseño original de Line 6 con parámetros extra para personalizar el Q y el barrido a tu gusto."
    else:
        tags.extend(["Inductor"])
        desc = f"Simulación de Wah {based_on if based_on else n}."

    return {"tags": list(dict.fromkeys(tags)), "instruments": instruments, "description": desc}


# --- Filter Logic ---
def get_filter_data(name, based_on):
    n = name.lower()
    b = based_on.lower() if based_on else ""
    
    tags = ["Filter"]
    instruments = ["Guitar", "Bass"]
    desc = ""

    if "mutron" in b or "mu-tron" in b or "q-tron" in b or "seamoon" in b or "envelope" in b or "auto" in n or "touch" in b:
        tags.extend(["Envelope", "Vintage"])
        desc = "Filtro de envolvente clásico (Auto-wah). Responde a las dinámicas de tu mano derecha. Ícono del Funk."
        if "seamoon" in b:
            desc = "Basado en el Seamoon Funk Machine. Filtro grumoso y vocal muy popular entre bajistas."
    elif "seek" in b or "obi" in n or "lfo" in b or "step" in n or "rhythm" in b:
        tags.extend(["LFO Filter", "Modern"])
        desc = "Filtro rítmico o automatizado. Crea secuencias de movimiento pulsante sin importar la dinámica al tocar."
    elif "moog" in b or "synth" in n or "ladder" in b or "synth" in b:
        tags.extend(["Synth / Ladder", "Studio"])
        desc = "Filtro resonante de escalera (Ladder) estilo sintetizador. Tono extremadamente gordo y profundo."
    else:
        tags.extend(["Custom", "Modern"])
        desc = f"Filtro especial {based_on if based_on else n}. Modela frecuencias de manera exótica."
        
    return {"tags": list(dict.fromkeys(tags)), "instruments": instruments, "description": desc}


updated_count = 0

# Process EQ
for m in catalog['catalog'].get('EQ', []):
    data = get_eq_data(m['name'], m.get('based_on', ''))
    m['tags'] = data['tags']
    m['instruments'] = data['instruments']
    m['description'] = data['description']
    updated_count += 1

# Process Wah
for m in catalog['catalog'].get('Wah', []):
    data = get_wah_data(m['name'], m.get('based_on', ''))
    m['tags'] = data['tags']
    m['instruments'] = data['instruments']
    m['description'] = data['description']
    updated_count += 1

# Process Filter
for m in catalog['catalog'].get('Filter', []):
    data = get_filter_data(m['name'], m.get('based_on', ''))
    m['tags'] = data['tags']
    m['instruments'] = data['instruments']
    m['description'] = data['description']
    updated_count += 1


with open(filepath_catalog, 'w', encoding='utf-8') as f:
    json.dump(catalog, f, indent=2, ensure_ascii=False)

print(f"Group 1 (EQ, Wah, Filter) successfully enriched! ({updated_count} models total)")
