import json

filepath_tags = 'utils/tags.json'
with open(filepath_tags, 'r', encoding='utf-8') as f:
    tags_data = json.load(f)

# Add Cab tags
tags_data["Cab"] = {
    "1x8": {
        "type": "Configuración",
        "description": "Caja con un parlante de 8 pulgadas. Tono enfocado, menos graves, ideal para guitarras rítmicas cortantes o lo-fi."
    },
    "1x10": {
        "type": "Configuración",
        "description": "Caja con un parlante de 10 pulgadas. Respuesta rápida y percusiva con medios notorios."
    },
    "1x12": {
        "type": "Configuración",
        "description": "Caja con un parlante de 12 pulgadas. Estándar súper versátil de amplificadores combo."
    },
    "2x12": {
        "type": "Configuración",
        "description": "Caja con dos parlantes de 12 pulgadas. Gran dispersión sonora y graves amplios."
    },
    "4x10": {
        "type": "Configuración",
        "description": "Caja con cuatro parlantes de 10 pulgadas. Mucho punch y graves rápidos."
    },
    "4x12": {
        "type": "Configuración",
        "description": "Caja con cuatro parlantes de 12 pulgadas. Muralla de sonido direccional clásica del rock y metal."
    },
    "1x15": {
        "type": "Configuración",
        "description": "Caja con un parlante de 15 pulgadas. Gran respuesta en frecuencias muy graves."
    },
    "1x18": {
        "type": "Configuración",
        "description": "Caja con un parlante de 18 pulgadas. Frecuencias sub-graves masivas."
    },
    "8x10": {
        "type": "Configuración",
        "description": "Caja con ocho parlantes de 10 pulgadas. La mítica heladera para bajo, volumen y patada insuperables."
    },
    "Open Back": {
        "type": "Construcción",
        "description": "Parte trasera abierta. Sonido tridimensional y aireado, llena el cuarto y sus graves son más sueltos."
    },
    "Closed Back": {
        "type": "Construcción",
        "description": "Parte trasera cerrada. Sonido muy direccional, enfocado al frente con graves sumamente ajustados (tight)."
    },
    "American": {
        "type": "Origen del Parlante",
        "description": "Parlantes estilo Jensen, Eminence o EV. Limpios brillantes, graves profundos y agudos vidriosos."
    },
    "British": {
        "type": "Origen del Parlante",
        "description": "Parlantes estilo Celestion o Fane. Compresión natural, cálidos y fuerte realce en medios."
    }
}

with open(filepath_tags, 'w', encoding='utf-8') as f:
    json.dump(tags_data, f, indent=2, ensure_ascii=False)

print("tags.json updated with Cab categories.")

filepath_catalog = 'utils/helix_catalog.json'
with open(filepath_catalog, 'r', encoding='utf-8') as f:
    catalog = json.load(f)

def get_cab_data(name, based_on):
    n = name.lower()
    b = based_on.lower() if based_on else ""
    
    tags = []
    instruments = ["Guitar"]
    desc = ""

    # Size parsing
    sizes = ["1x8", "1x10", "1x12", "1x15", "1x18", "2x12", "4x10", "4x12", "6x10", "8x10", "2x15"]
    for s in sizes:
        if s in n or s in b:
            tags.append(s)
            break
            
    # Bass Amps
    if "bass" in n or "bass" in b or "ampeg" in b or "aguilar" in b or "acoustic 360" in b or "mesa/boogie 2x15" in b or "eden" in b or "hartke" in b or "gallien" in b or "1x15" in tags or "1x18" in tags or "8x10" in tags or ("4x10" in tags and "fender" not in b) or "sunn coliseum" in b:
        instruments = ["Bass"]
        
    if "fender bassman" in b and "4x10" in tags:
        instruments = ["Guitar", "Bass"]
        
    # Enclosure Type (Heuristics)
    if "fender" in b or "matchless" in b or "vox" in b or "roland" in b or "silvertone" in b or "supro" in b or "1x10" in tags or "1x8" in tags or "twin" in n or "deluxe" in n or "divided" in b or "open back" in b:
        if "bassman" not in b and "closed" not in b:
            if "Open Back" not in tags: tags.append("Open Back")
    
    if "marshall" in b or ("mesa" in b and "lone star" not in b) or "orange" in b or "bogner" in b or "engl" in b or "diezel" in b or "peavey" in b or "4x12" in tags or "closed" in b or "ampeg" in b or "8x10" in tags or "friedman" in b or "soldano" in b or "evh" in b or "revv" in b or "closed back" in b:
        if "Closed Back" not in tags: tags.append("Closed Back")
        
    # Speaker Voicing
    if "fender" in b or "mesa" in b and "lone star" in b or "jensen" in b or "eminence" in b or "electro-voice" in b or "american" in n or "us " in n or "supro" in b or "silvertone" in b:
        if "American" not in tags: tags.append("American")
    elif "marshall" in b or "vox" in b or "orange" in b or "matchless" in b or "celestion" in b or "greenback" in n or "creamback" in n or "v30" in n or "british" in n or "brit " in n or "hiwatt" in b or "fane" in b or "friedman" in b or "bogner" in b or "diezel" in b or "engl" in b or "revv" in b:
        if "British" not in tags: tags.append("British")
        
    # Desc
    desc = f"Simulación de la caja {based_on if based_on else n}."
    if "4x12" in tags and "Closed Back" in tags:
        desc += " Pared de sonido masiva y direccional, graves muy controlados."
    elif "Open Back" in tags:
        desc += " Sonido tridimensional y aireado, llena muy bien la habitación."
    elif "Bass" in instruments:
        desc += " Diseñada específicamente para reproducir bajas frecuencias con claridad."
        
    return {"tags": tags, "instruments": instruments, "description": desc}

updated_count = 0
for m in catalog['catalog'].get('Cab', []):
    data = get_cab_data(m['name'], m.get('based_on', ''))
    m['tags'] = data['tags']
    m['instruments'] = data['instruments']
    m['description'] = data['description']
    updated_count += 1

with open(filepath_catalog, 'w', encoding='utf-8') as f:
    json.dump(catalog, f, indent=2, ensure_ascii=False)

print(f"Cabs successfully enriched! ({updated_count} models)")
