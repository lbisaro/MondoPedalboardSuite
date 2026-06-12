import json

distortions_data = {
    "Kinky Boost": {"tags": ["Boost", "Preamp", "Low-Gain"], "description": "Emula el preamplificador del legendario Echoplex EP-3. Excelente para engordar el tono y dar un brillo dulce a la señal."},
    "Deranged Master": {"tags": ["Boost", "Vintage", "Mid-hump"], "description": "Basado en el Dallas Rangemaster. Clásico treble booster usado por Brian May y Tony Iommi para empujar amplificadores oscuros al límite."},
    "Minotaur": {"tags": ["Overdrive", "Transparent", "Low-Gain"], "description": "Basado en el mítico Klon Centaur. Ideal como clean boost o para un overdrive cremoso con un ligero realce de medios-agudos."},
    "Teemah!": {"tags": ["Overdrive", "Transparent", "Low-Gain"], "description": "Basado en el Paul Cochrane Timmy. Overdrive sumamente transparente con potentes controles de EQ de recorte (cut) de graves y agudos."},
    "Heir Apparent": {"tags": ["Overdrive", "Transparent", "Mid-hump"], "description": "Basado en el Analogman Prince of Tone. Overdrive clásico estilo Bluesbreaker pero con más opciones de clipeo y ganancia."},
    "Tone Sovereign": {"tags": ["Overdrive", "Transparent", "Mid-hump"], "description": "Basado en el Analogman King of Tone. Dos pedales Bluesbreaker modificados en serie, famoso por su claridad y respuesta dinámica."},
    "Alpaca Rogue": {"tags": ["Overdrive", "Fuzz", "Vintage"], "description": "Basado en el Way Huge Red Llama. Un circuito basado en lógica CMOS que va desde un boost transparente hasta un fuzz tipo Tweed rompiendo."},
    "Compulsive Drive": {"tags": ["Overdrive", "Distortion", "Modern"], "description": "Basado en el Fulltone OCD. Un drive muy dinámico con gran cantidad de volumen disponible y un rango amplio de ganancia, desde sutil hasta casi distorsión."},
    "Dhyana Drive": {"tags": ["Overdrive", "Mid-hump", "Low-Gain"], "description": "Basado en el Hermida Zendrive. Famoso por emular el sonido fluido y cremoso de los amplificadores Dumble Overdrive Special."},
    "Horizon Drive": {"tags": ["Overdrive", "Modern", "Mid-hump"], "description": "Basado en el Horizon Precision Drive. Diseñado específicamente para empujar amplificadores de high-gain modernos y apretar los graves (djent/metal)."},
    "Valve Driver": {"tags": ["Overdrive", "Preamp", "Vintage"], "description": "Basado en el Chandler Tube Driver. Famoso por ser usado por David Gilmour y Eric Johnson. Utiliza una válvula real en su circuito original."},
    "Top Secret OD": {"tags": ["Overdrive", "Vintage", "Transparent"], "description": "Basado en el DOD OD-250. Uno de los primeros overdrives, bastante transparente y dinámico, precursor del Distortion+."},
    "Prize Drive": {"tags": ["Overdrive", "Transparent", "Bass"], "description": "Basado en el Nobels ODR-1. Overdrive muy popular en la escena de Nashville. Mantiene muy bien las frecuencias graves a diferencia del Tube Screamer."},
    "Scream 808": {"tags": ["Overdrive", "Mid-hump", "Vintage"], "description": "Basado en el Ibanez TS808. El estándar de oro de los overdrives con realce de medios. Perfecto para empujar válvulas al límite o limpiar graves en high-gain."},
    "Pillars": {"tags": ["Overdrive", "Mid-hump", "Modern"], "description": "Basado en el Earthquaker Devices Plumes. Una reinterpretación moderna del Tube Screamer con más volumen, claridad y tres opciones de clipeo."},
    "Hedgehog D9": {"tags": ["Distortion", "Scooped", "Vintage"], "description": "Basado en el MAXON SD9. Distorsión clásica con un notable recorte de medios, favorita de guitarristas como Scott Henderson."},
    "Stupor OD": {"tags": ["Overdrive", "Mid-hump", "Vintage"], "description": "Basado en el BOSS SD-1. Similar al Tube Screamer pero con clipeo asimétrico, dando un tono más rasposo y rico en armónicos pares."},
    "Deez One Vintage": {"tags": ["Distortion", "Vintage"], "description": "Basado en el BOSS DS-1 (Japón). Distorsión brillante y agresiva. Funciona mejor sobre amplificadores que ya están al borde de saturar."},
    "Deez One Mod": {"tags": ["Distortion", "Modern"], "description": "Basado en el BOSS DS-1 modificado por Keeley. Mejora la respuesta de graves, añade opciones de clipeo con LEDs y reduce el ruido del circuito original."},
    "Ratatoullie Dist": {"tags": ["Distortion", "Fuzz", "Vintage"], "description": "Basado en el Pro Co RAT clásico con el chip LM308. Distorsión muy versátil que a alta ganancia entra en territorio de Fuzz."},
    "Vermin Dist": {"tags": ["Distortion", "Fuzz", "Modern"], "description": "Basado en un Pro Co RAT más moderno. Tono agresivo y cortante que funciona excelente en mezclas densas de rock y punk."},
    "Vital Dist": {"tags": ["Distortion", "Octave", "Fuzz", "Modern"], "description": "Basado en la sección de distorsión del EQD Life Pedal (Sunn O))). Diseñado para doom metal, produce paredes de sonido masivas."},
    "Vital Boost": {"tags": ["Boost", "Modern"], "description": "Basado en la sección de boost del EQD Life Pedal. Un boost limpio y opresivo diseñado para saturar al extremo la etapa de entrada del ampli."},
    "KWB": {"tags": ["Distortion", "Modern"], "description": "Basado en el Benadrian Kowloon Walled Bunny. Distorsión estilo RAT muy modificada, ofreciendo varios modos de clipeo y texturas únicas."},
    "Legendary Drive": {"tags": ["Preamp", "High-Gain"], "description": "Emula el canal sucio del Carvin VLD1 Legacy Drive de Steve Vai. Tono líquido, súper suave y lleno de sustain."},
    "Swedish Chainsaw": {"tags": ["Distortion", "Scooped", "High-Gain"], "description": "Basado en el BOSS HM-2 (Japón). Responsable del sonido death metal sueco (Entombed, At The Gates) al poner todas las perillas al máximo."},
    "Arbitrator Fuzz": {"tags": ["Fuzz", "Vintage", "Germanium"], "description": "Basado en el Arbiter Fuzz Face original. Fuzz muy reactivo al potenciómetro de volumen de la guitarra. Tono clásico de Jimi Hendrix."},
    "Pocket Fuzz": {"tags": ["Fuzz", "Vintage"], "description": "Basado en el Jordan Boss Tone. Fuzz que originalmente se enchufaba directo a la guitarra. Sonido muy áspero y distintivo de fines de los 60s."},
    "Bighorn Fuzz": {"tags": ["Fuzz", "Scooped", "Vintage"], "description": "Basado en el Ram's Head Big Muff del '73. Menos ganancia que otras versiones, pero con una claridad excelente, usado célebremente por David Gilmour."},
    "Triangle Fuzz": {"tags": ["Fuzz", "Scooped", "Vintage"], "description": "Basado en el primer Big Muff de EHX (Triangle). Tono muy denso, con gran sustain y mucha compresión."},
    "Dark Dove Fuzz": {"tags": ["Fuzz", "Scooped", "Bass"], "description": "Basado en el Russian Big Muff de los 90s. Tono más oscuro y con unos graves inmensos, muy popular también entre bajistas."},
    "Ballistic Fuzz": {"tags": ["Fuzz", "Scooped", "Vintage"], "description": "Basado en el Euthymia ICBM. Una réplica del IC Big Muff de los años 70 (como el de Smashing Pumpkins)."},
    "Industrial Fuzz": {"tags": ["Fuzz", "Germanium", "Modern"], "description": "Basado en el Z.Vex Fuzz Factory. Fuzz híper versátil, caótico y oscilante, popularizado por Muse."},
    "Tycoctavia Fuzz": {"tags": ["Fuzz", "Octave", "Vintage"], "description": "Basado en el Tycobrahe Octavia. Combina un fuzz agresivo con una clara octava alta, especialmente notable al tocar en el mástil."},
    "Wringer Fuzz": {"tags": ["Fuzz", "Scooped", "Modern"], "description": "Basado en el BOSS FZ-2 Hyper Fuzz modificado de Garbage. Genera texturas masivas, ideal para riffs de stoner rock y doom metal."},
    "Thrifter Fuzz": {"tags": ["Fuzz", "Modern"], "description": "Diseño original de Line 6. Un fuzz adaptable e intuitivo para diferentes aplicaciones modernas."},
    "Xenomorph Fuzz": {"tags": ["Fuzz", "Octave", "Modern"], "description": "Basado en el Subdecay Harmonic Antagonizer. Fuzz extremo y sintetizado que puede lograr sonidos rotos, glitchy y de 8 bits."},
    "Megaphone": {"tags": ["Distortion", "Preamp", "Modern"], "description": "Efecto especial tipo megáfono. Recorta agresivamente las frecuencias graves y agudas simulando un dispositivo de baja fidelidad."},
    "Bitcrusher": {"tags": ["Distortion", "Modern"], "description": "Diseño de Line 6. Destruye digitalmente la señal reduciendo la tasa de muestreo y la profundidad de bits para tonos lo-fi e industriales."},
    "Ampeg Scrambler": {"tags": ["Fuzz", "Octave", "Bass"], "description": "Basado en el Ampeg Scrambler. Fuzz muy áspero con una sutil octava aguda, diseñado originalmente para bajo pero usado por muchos guitarristas."},
    "ZeroAmp": {"tags": ["Preamp", "Distortion", "Bass"], "description": "Basado en el Tech 21 SansAmp Bass Driver DI. Estándar de la industria para conseguir un buen tono de bajo por línea con saturación valvular emulada."},
    "Regal": {"tags": ["Preamp", "Bass", "Transparent"], "description": "Basado en el Noble Preamp Bass DI. Preamplificador de válvulas de altísima calidad para bajo, ofreciendo calidez, punch y enorme claridad."},
    "Obsidian 7000": {"tags": ["Distortion", "Preamp", "Bass", "Modern"], "description": "Basado en el Darkglass B7K Ultra. Preamplificador y distorsión para bajo agresivo y moderno, el estándar del metal contemporáneo."},
    "Clawthorn Drive": {"tags": ["Overdrive", "Fuzz", "Bass"], "description": "Basado en el Wounded Paw Battering Ram. Pedal de distorsión para bajo con canales paralelos de overdrive y fuzz para conservar la fundamental."},
    "Tube Drive": {"tags": ["Overdrive", "Preamp", "Vintage"], "description": "Versión legacy del Chandler Tube Driver. Overdrive clásico potenciado por válvula."},
    "Screamer": {"tags": ["Overdrive", "Mid-hump", "Vintage"], "description": "Versión legacy del Ibanez Tube Screamer. Clásico empuje de medios."},
    "Overdrive": {"tags": ["Overdrive", "Transparent", "Vintage"], "description": "Versión legacy del DOD OD-250. Drive dinámico y crudo."},
    "Classic Dist": {"tags": ["Distortion", "Vintage"], "description": "Versión legacy del Pro Co RAT original. Distorsión versátil clásica."},
    "Heavy Dist": {"tags": ["Distortion", "High-Gain", "Scooped"], "description": "Versión legacy del BOSS Metal Zone. Distorsión potente con ecualizador paramétrico profundo."},
    "Colordrive": {"tags": ["Overdrive", "Vintage"], "description": "Versión legacy del Colorsound Overdriver. Overdrive orgánico y poderoso de los 70s."},
    "Buzz Saw": {"tags": ["Fuzz", "Vintage"], "description": "Versión legacy del Maestro Fuzz Tone. Uno de los primeros pedales de fuzz, famoso por Satisfaction de The Rolling Stones."},
    "Facial Fuzz": {"tags": ["Fuzz", "Vintage"], "description": "Versión legacy del Arbiter Fuzz Face."},
    "Jumbo Fuzz": {"tags": ["Fuzz", "Vintage"], "description": "Versión legacy del Vox Tone Bender. Fuzz rasposo y rico de la invasión británica."},
    "Fuzz Pi": {"tags": ["Fuzz", "Scooped", "Vintage"], "description": "Versión legacy del EHX Big Muff Pi."},
    "Jet Fuzz": {"tags": ["Fuzz", "Vintage"], "description": "Versión legacy del Roland Jet Phaser. Combina fuzz denso con phaser, sonido icónico funk/rock de los 70s."},
    "L6 Drive": {"tags": ["Overdrive", "Modern"], "description": "Versión legacy de un Colorsound Overdriver modificado por Line 6."},
    "L6 Distortion": {"tags": ["Distortion", "Modern"], "description": "Distorsión original legacy de Line 6."},
    "Sub Oct Fuzz": {"tags": ["Fuzz", "Octave", "Vintage"], "description": "Versión legacy del PAiA Roctave Divider. Fuzz brutal combinado con sub-octavas."},
    "Octave Fuzz": {"tags": ["Fuzz", "Octave", "Vintage"], "description": "Versión legacy del Tycobrahe Octavia."},
    "Bronze Master": {"tags": ["Fuzz", "Octave", "Bass"], "description": "Versión legacy del Maestro Bass Brassmaster. Fuzz de bajo clásico, muy agresivo y con fuerte carácter de octava."},
    "Killer Z": {"tags": ["Distortion", "High-Gain", "Scooped"], "description": "Otra variante legacy del BOSS Metal Zone MT-2."}
}

import os
filepath = 'utils/helix_catalog.json'

with open(filepath, 'r', encoding='utf-8') as f:
    catalog_json = json.load(f)

# Update models
updated_count = 0
for model in catalog_json['catalog'].get('Distortion', []):
    name = model['name']
    if name in distortions_data:
        model['tags'] = distortions_data[name]['tags']
        model['description'] = distortions_data[name]['description']
        updated_count += 1

with open(filepath, 'w', encoding='utf-8') as f:
    json.dump(catalog_json, f, indent=2, ensure_ascii=False)

print(f"Successfully updated {updated_count} Distortion models with tags and descriptions.")
