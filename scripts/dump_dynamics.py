import json
with open('utils/helix_catalog.json', 'r', encoding='utf-8') as f:
    catalog = json.load(f)

dynamics = catalog['catalog'].get('Dynamics', [])
with open('dynamics_list.txt', 'w', encoding='utf-8') as f:
    for m in dynamics:
        f.write(f"{m['name']} | {m.get('based_on', '')}\n")
