import json

filepath = 'utils/helix_catalog.json'

with open(filepath, 'r', encoding='utf-8') as f:
    catalog = json.load(f)

def get_amp_data(name, based_on):
    n = name.lower()
    b = based_on.lower() if based_on else ""
    
    tags = []
    instruments = ["Guitar"]
    desc = ""

    # Bass Amps
    if "ampeg" in b or "ampeg" in n or "b-15" in n or "svt" in n:
        tags = ["Clean", "American"]
        instruments = ["Bass"]
        desc = "Clásico amplificador de bajo Ampeg, el estándar absoluto de la industria."
    elif "acoustic 360" in b or "woody blue" in n:
        tags = ["Clean", "Solid State"]
        instruments = ["Bass"]
        desc = "Basado en el Acoustic 360, famoso preamplificador de bajo a transistores de los 70s."
    elif "aguilar" in b or "agua" in n:
        tags = ["Clean", "Modern"]
        instruments = ["Bass"]
        desc = "Basado en Aguilar, sonido de bajo moderno, articulado y con mucho cuerpo."
    elif "orange ad200" in b or "mandarin | 200 bass" in n or "mandarin" in n and "bass" in n:
        tags = ["Crunch", "British"]
        instruments = ["Bass"]
        desc = "Basado en el Orange AD200. Tono británico muy cálido, con un saturado redondo y denso para el bajo."
    elif "carbine" in b or "bass 400" in b or "cali 400" in n or "cali | bass" in n or "cali" in n and "bass" in n:
        tags = ["Clean", "American", "6L6"]
        instruments = ["Bass"]
        desc = "Basado en los legendarios equipos de bajo de Mesa/Boogie. Enorme techo limpio y respuesta percusiva."
    elif "gallien-krueger" in b or "cougar 800" in n:
        tags = ["Clean", "Solid State"]
        instruments = ["Bass"]
        desc = "Basado en el GK 800RB. Amplificador a transistores icónico del rock y punk de los 80/90s (ej. Flea)."
    elif "sunn coliseum" in b or "del sol 300" in n:
        tags = ["Clean", "Solid State"]
        instruments = ["Bass"]
        desc = "Basado en el Sunn Coliseum 300. Puro volumen de estado sólido, con frecuencias graves sísmicas."
    elif "pearce" in b or "busy one" in n:
        tags = ["Crunch", "Solid State"]
        instruments = ["Bass", "Guitar"]
        desc = "Basado en el Pearce BC-1. Preamplificador a transistores, famoso por ser el tono dual de Billy Sheehan."
    elif "dripman" in n or ("bassman" in b and "silverface" in b):
        tags = ["Clean", "American", "6L6"]
        instruments = ["Bass", "Guitar"]
        desc = "Basado en el Fender Bassman Silverface. Sirve tanto para bajo clásico como plataforma cristalina para guitarra."
        
    # Guitar Clean / American
    elif "fender" in b or "tweed" in n or "fullerton" in n or "us princess" in n or "us super" in n or "us deluxe" in n or "us double" in n:
        if "tweed" in n or "tweed" in b or "bassman" in b:
            tags = ["Crunch", "American", "6L6"]
            desc = "Clásico circuito Fender Tweed de los años 50s. Excelente ruptura orgánica y medios pronunciados."
        elif "deluxe" in b or "deluxe" in n:
            tags = ["Clean", "American", "6V6"]
            desc = "Sonido clásico de combo mediano Fender. Satura de forma increíblemente cremosa a niveles lógicos."
        elif "twin" in b or "double" in n:
            tags = ["Clean", "American", "6L6"]
            desc = "El rey del 'headroom'. Volúmenes brutales sin saturar. La plataforma perfecta para pedales."
        else:
            tags = ["Clean", "American", "6L6"]
            desc = "Clásico tono limpio americano estilo Fender: bajos gigantes y agudos cristalinos."
            
    elif "roland" in b or "jazz rivet" in n:
        tags = ["Clean", "Solid State"]
        desc = "Basado en el Roland JC-120. Tono limpio estéril, puro y con un brillo icónico de los 80s."
    elif "silvertone" in b or "mail order" in n:
        tags = ["Crunch", "American"]
        desc = "Basado en el Silvertone 1484. Un diseño más primitivo con un sonido rasposo y garagero."
        
    # British / Crunch
    elif "vox" in b or "essex" in n or "a30" in n:
        tags = ["Crunch", "British", "EL84"]
        desc = "Tono clásico Vox. Caracterizado por sus medios-agudos chispeantes (el famoso 'chime') y respuesta rápida."
    elif "orange" in b or "mandarin" in n:
        tags = ["Crunch", "British", "EL34"]
        desc = "Basado en Orange. Tonos densos, fuzz-like en saturación alta y muchos medios graves (stoner/doom)."
    elif "marshall" in b or "brit" in n or "park 75" in b:
        tags = ["Crunch", "British", "EL34"]
        if "jcm" in b or "2203" in n or "2204" in n or "plexi" in n:
            tags = ["High-Gain", "British", "EL34"]
            desc = "Ataque frontal Marshall estilo Plexi o JCM800. Cortante, con agudos agresivos y rugido en medios."
        else:
            desc = "Tono Marshall vintage temprano estilo JTM-45. Graves sueltos y distorsión tipo blues clásico."
    elif "hiwatt" in b or "whowatt" in n:
        tags = ["Clean", "British", "EL34"]
        desc = "Basado en Hiwatt DR-103. Tono inmenso de amplio espectro, favorito de David Gilmour. Excelente con pedales Fuzz."

    # Boutique
    elif "matchless" in b or "matchstick" in n:
        tags = ["Crunch", "Boutique", "EL84"]
        desc = "Basado en Matchless. Una evolución moderna del diseño Vox con dinámicas increíbles y riqueza tridimensional."
    elif "trainwreck" in b or "derailed" in n:
        tags = ["Crunch", "Boutique"]
        desc = "Basado en Trainwreck Express. Exageradamente sensible a la púa: limpio al acariciar, rabioso al golpear."
    elif "divided" in b or "jrt" in b:
        tags = ["Crunch", "Boutique", "6V6"]
        desc = "Basado en ÷13 JRT 9/15. Mezcla características americanas y británicas tempranas."
    elif "grammatico" in n:
        tags = ["Crunch", "Boutique"]
        desc = "Basado en los refinados diseños Grammatico. Clones super pulidos de circuitos Tweed clásicos y Dumble."
        
    # High Gain
    elif "mesa" in b and "rectifier" in b or "cali rectifire" in n:
        tags = ["High-Gain", "American", "6L6"]
        desc = "Pared de sonido metalera de fines de los 90s/00s. Graves abrumadores y medios hundidos (scoop)."
    elif "mesa" in b and ("mark" in b or "iv" in b) or "cali iv" in n:
        tags = ["High-Gain", "American", "6L6"]
        desc = "Basado en el Mesa Mark IV. Tono líquido super enfocado en medios, el clásico sonido solista de John Petrucci."
    elif "lone star" in b or "cali texas" in n:
        tags = ["Clean", "Boutique", "6L6"]
        desc = "Limpios inmensos estilo Texas blues y canales de saturación sumamente melosos y llenos."
    elif "peavey 5150" in b or "evh 5150" in b or "panama" in n:
        tags = ["High-Gain", "American", "6L6"]
        desc = "Basado en el linaje 5150. El estándar absoluto del metal contemporáneo y metalcore. Definición increíble."
    elif "peavey invective" in b or "vitriol" in n:
        tags = ["High-Gain", "American", "6L6"]
        desc = "Basado en el Peavey Invective, optimizado por Misha Mansoor (Periphery) para guitarras de rango extendido y djent."
    elif "soldano" in b or "solo lead" in n:
        tags = ["High-Gain", "American", "6L6"]
        desc = "Basado en el Soldano SLO-100. El antecesor del Rectifier y 5150; compresión de válvulas masiva y sustain infinito."
    elif "bogner" in b or "german" in n:
        tags = ["High-Gain", "Boutique", "EL34"]
        desc = "Basado en el intrincado diseño Bogner (Ecstasy/Shiva/Uberschall). Tono muy oscuro, denso y sofisticado."
    elif "engl" in b or "angl meteor" in n:
        tags = ["High-Gain", "Modern"]
        desc = "Basado en ENGL Fireball. Ataque rapidísimo y rigidez de graves tremenda, ideal para thrash y death metal veloz."
    elif "diezel" in b or "benzin" in n:
        tags = ["High-Gain", "Modern"]
        desc = "Basado en Diezel VH4. Alta ganancia estéril y ultra comprimida. El tono percusivo y apretado de Adam Jones de Tool."
    elif "revv" in b or "revv" in n:
        tags = ["High-Gain", "Modern"]
        desc = "Basado en los potentes Revv Generator canadienses. Distorsión moderna hiper clara con un corte fenomenal en mezclas."
    elif "archon" in b or "archetype" in n:
        tags = ["High-Gain", "American", "6L6"]
        desc = "Basado en PRS Archon. Canal limpio impecable emparejado con un canal de saturación obscuro y pesado."
    
    # Line 6 Originals
    elif "line 6" in b or "line 6" in n:
        if "badonk" in n or "fatality" in n or "doom" in n or "epic" in n or "oblivion" in n or "elektrik" in n:
            tags = ["High-Gain", "Modern"]
            desc = "Diseño original de Line 6 para músicos modernos que tocan metal y djent en afinaciones graves."
        elif "litigator" in n or "aristocrat" in n or "carillon" in n or "ventoux" in n:
            tags = ["Crunch", "Boutique"]
            desc = "Amplificador de media ganancia hiper reactivo, original de Line 6. Responde al volumen de la guitarra como un valvular real."
        elif "clarity" in n:
            tags = ["Clean", "Solid State"]
            desc = "Diseño original. Amplificador Full Range Flat Response, no colorea y pasa el sonido puro de la guitarra."
        else:
            tags = ["Crunch", "Modern"]
            desc = "Diseño original de Line 6 enfocado en rellenar vacíos tonales en el mercado."
            
    # Others
    elif "mic" in b or "studio tube pre" in n:
        tags = ["Clean"]
        instruments = ["Universal"]
        desc = "Preamplificador de micrófono valvular clásico. Aporta calidez y excitación armónica general a la señal."
    elif "sunn model t" in b or "moo)))n" in n:
        tags = ["Clean", "American"]
        desc = "Basado en el Sunn Model T de los 70s. Tremenda potencia, plataforma clásica adorada por el Doom/Stoner."
    elif "supro" in b or "soup pro" in n:
        tags = ["Crunch", "American"]
        desc = "Basado en el pequeño Supro de Jimmy Page. Tono rústico con graves inflados y saturación arenosa."
    elif "gibson eh-185" in b or "stone age" in n:
        tags = ["Crunch", "Vintage"]
        desc = "Basado en un amplificador Gibson muy primitivo. Al saturar suena a 'consola rota' que fascina en el blues/indie."
    elif "victoria" in b or "voltage queen" in n:
        tags = ["Clean", "Boutique"]
        desc = "Clon boutique superior de clásicos vintage americanos. Extraodinario detalle al toque de la púa."
    
    # Fallback default
    if not desc:
        desc = f"Emulación basada en el {based_on if based_on else n}."
        if not tags: tags = ["Crunch"]
        
    return {"tags": tags, "instruments": instruments, "description": desc}


for m in catalog['catalog'].get('Amp', []):
    data = get_amp_data(m['name'], m.get('based_on', ''))
    m['tags'] = data['tags']
    m['instruments'] = data['instruments']
    m['description'] = data['description']

with open(filepath, 'w', encoding='utf-8') as f:
    json.dump(catalog, f, indent=2, ensure_ascii=False)

print("Amps successfully enriched!")
