import json

filepath_tags = 'utils/tags.json'
with open(filepath_tags, 'r', encoding='utf-8') as f:
    tags_data = json.load(f)

def sanitize_tag(tag):
    if tag == "Synth / Ladder": return "Synth"
    if tag == "Tremolo / Vibrato": return "Tremolo"
    if tag == "Analog / BBD": return "Analog"
    
    words = tag.replace("-", " ").split(" ")
    res = []
    for w in words:
        if not w: continue
        res.append(w[0].upper() + w[1:])
    return "".join(res)

# 1. Update tags.json
new_tags_data = {}
for category, tag_dict in tags_data.items():
    new_tags_data[category] = {}
    for tag, info in tag_dict.items():
        if category == "Instrument" and tag == "Acoustic":
            continue # Remove Acoustic
        
        new_tag = sanitize_tag(tag)
        new_tags_data[category][new_tag] = info

with open(filepath_tags, 'w', encoding='utf-8') as f:
    json.dump(new_tags_data, f, indent=2, ensure_ascii=False)

# 2. Update helix_catalog.json
filepath_catalog = 'utils/helix_catalog.json'
with open(filepath_catalog, 'r', encoding='utf-8') as f:
    catalog = json.load(f)

for cat, items in catalog['catalog'].items():
    for m in items:
        # Update instruments
        if "instruments" in m:
            new_insts = []
            for i in m["instruments"]:
                if i == "Acoustic": continue
                new_insts.append(sanitize_tag(i))
            m["instruments"] = list(dict.fromkeys(new_insts))
        
        # Update tags
        if "tags" in m:
            new_tags = []
            for t in m["tags"]:
                new_tags.append(sanitize_tag(t))
            m["tags"] = list(dict.fromkeys(new_tags))

with open(filepath_catalog, 'w', encoding='utf-8') as f:
    json.dump(catalog, f, indent=2, ensure_ascii=False)

print("Tags have been successfully cleaned and sanitized!")
