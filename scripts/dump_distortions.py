import json

with open('utils/helix_catalog.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

distortions = data['catalog'].get('Distortion', [])
with open('distortions_list.txt', 'w', encoding='utf-8') as f:
    for m in distortions:
        f.write(f"{m['name']} | {m.get('based_on', '')}\n")
