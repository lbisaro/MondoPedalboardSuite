import json

filepath = 'utils/tags.json'
with open(filepath, 'r', encoding='utf-8') as f:
    tags_data = json.load(f)

# Add Universal / Instrument tags to the root or a new section
tags_data["Instrument"] = {
    "Guitar": {
        "type": "Instrumento Recomendado",
        "description": "Optimizado o diseñado clásicamente para Guitarra Eléctrica."
    },
    "Bass": {
        "type": "Instrumento Recomendado",
        "description": "Optimizado o diseñado clásicamente para Bajo Eléctrico, preservando frecuencias graves."
    },
    "Acoustic": {
        "type": "Instrumento Recomendado",
        "description": "Diseñado para Guitarra Acústica u otros instrumentos acústicos."
    },
    "Universal": {
        "type": "Instrumento Recomendado",
        "description": "Efecto de rango completo, funciona excelente con cualquier instrumento, voces o sintes."
    }
}

# Remove "Bass" from Distortion tags as it's now an Instrument tag
if "Bass" in tags_data["Distortion"]:
    del tags_data["Distortion"]["Bass"]

tags_data["Amp"] = {
    "Clean": {
        "type": "Nivel de Ganancia",
        "description": "Diseñados para mantenerse limpios a altos volúmenes, con mucho techo limpio (headroom)."
    },
    "Crunch": {
        "type": "Nivel de Ganancia",
        "description": "Rompen fácilmente o están en el famoso 'edge of breakup'. Ideales para blues y rock clásico."
    },
    "High-Gain": {
        "type": "Nivel de Ganancia",
        "description": "Múltiples etapas de ganancia, diseñados para metal, hard rock moderno o tonos solistas."
    },
    "American": {
        "type": "Origen / Carácter Tonal",
        "description": "Sonido clásico de EE.UU. Agudos cristalinos, graves profundos y medios ligeramente recortados."
    },
    "British": {
        "type": "Origen / Carácter Tonal",
        "description": "Sonido clásico del Reino Unido. Fuerte presencia en medios, sonido más ronco o con 'chime'."
    },
    "Boutique": {
        "type": "Origen / Carácter Tonal",
        "description": "Diseño artesanal o de altísima gama, gran respuesta táctil y armónicos complejos."
    },
    "6L6": {
        "type": "Etapa de Potencia",
        "description": "Válvulas clásicas americanas. Mucho volumen, graves grandes y agudos redondos."
    },
    "EL34": {
        "type": "Etapa de Potencia",
        "description": "Válvulas clásicas británicas. Gran compresión al saturar y medios agresivos."
    },
    "EL84": {
        "type": "Etapa de Potencia",
        "description": "Menor potencia, saturan rápido y tienen el famoso brillo/chime en agudos."
    },
    "6V6": {
        "type": "Etapa de Potencia",
        "description": "Válvulas americanas de menor potencia. Graves más sueltos y agudos dulces."
    },
    "Solid State": {
        "type": "Etapa de Potencia",
        "description": "Amplificadores a transistores, sin válvulas. Extremadamente limpios o muy particulares."
    }
}

with open(filepath, 'w', encoding='utf-8') as f:
    json.dump(tags_data, f, indent=2, ensure_ascii=False)

print("tags.json updated with Amp and Instrument categories.")

# Now update Distortions in helix_catalog.json
catalog_path = 'utils/helix_catalog.json'
with open(catalog_path, 'r', encoding='utf-8') as f:
    catalog = json.load(f)

for m in catalog['catalog'].get('Distortion', []):
    tags = m.get('tags', [])
    
    # Si tenia Bass como tag viejo, lo convertimos a Instrumento
    if "Bass" in tags:
        tags.remove("Bass")
        instruments = ["Bass"]
    else:
        # Algunos son de guitarra y bajo, pero por defecto pongamos Guitar
        # Vamos a hacer algunos universales como el Bitcrusher, Megaphone, Studio EQ
        if m['name'] in ["Bitcrusher", "Megaphone"]:
            instruments = ["Universal"]
        elif m['name'] in ["Dark Dove Fuzz", "Ampeg Scrambler"]:
            # Estos son fuzzes muy usados en bajo
            instruments = ["Guitar", "Bass"]
        else:
            instruments = ["Guitar"]
            
    m['instruments'] = instruments
    m['tags'] = tags

with open(catalog_path, 'w', encoding='utf-8') as f:
    json.dump(catalog, f, indent=2, ensure_ascii=False)

print("Distortions updated with instruments.")

# Also list Amps to a file so we can categorize them
amps = catalog['catalog'].get('Amp', [])
with open('amps_list.txt', 'w', encoding='utf-8') as f:
    for a in amps:
        f.write(f"{a['name']} | {a.get('based_on', '')}\n")
print(f"Dumped {len(amps)} Amps to amps_list.txt")

