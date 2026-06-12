import json

filepath_catalog = 'utils/helix_catalog.json'
with open(filepath_catalog, 'r', encoding='utf-8') as f:
    catalog = json.load(f)

# The Amps are already enriched. 
# Preamps have the exact same names, just under the 'Preamp' category.
# Sometimes the name might have ' Pre' at the end, but usually it's identical or substring.

amps_data = {}
for m in catalog['catalog'].get('Amp', []):
    amps_data[m['name']] = m

updated_count = 0
for m in catalog['catalog'].get('Preamp', []):
    name = m['name']
    
    # Intenta hacer match exacto o parcial
    match = amps_data.get(name)
    if not match:
        # Preamps are usually named exactly like Amps. If not, fallback to based_on
        for a_name, a_data in amps_data.items():
            if m.get('based_on') and a_data.get('based_on') == m.get('based_on'):
                match = a_data
                break
                
    if match:
        m['tags'] = match.get('tags', [])
        m['instruments'] = match.get('instruments', [])
        
        # Modify description slightly
        orig_desc = match.get('description', '')
        desc = "Versión Preamplificador. " + orig_desc
        m['description'] = desc
    else:
        # Fallback
        m['tags'] = ["Crunch"]
        m['instruments'] = ["Guitar"]
        m['description'] = f"Versión Preamplificador de {m.get('based_on') if m.get('based_on') else name}."
        
    updated_count += 1

with open(filepath_catalog, 'w', encoding='utf-8') as f:
    json.dump(catalog, f, indent=2, ensure_ascii=False)

print(f"Group 4 (Preamp) successfully enriched! ({updated_count} models total)")
