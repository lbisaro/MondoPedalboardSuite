import json
import re

def update_catalog():
    # 1. Extract params from JS file
    try:
        with open('scrap/IR_files/BpccKnah.js.descarga', 'r', encoding='utf-8') as f:
            js = f.read()
    except FileNotFoundError:
        print("Could not find JS file.")
        return

    # Extract first set of objects:
    params_by_name = {}
    matches1 = re.findall(r'(\{\"id\":\"([^\"]+)\",\"name\":\"([^\"]+)\".*?\"params\":(\[[^\]]+\])\})', js)
    for block_str, block_id, name, params_str in matches1:
        try:
            params_json = json.loads(params_str)
            param_names = []
            for p in params_json:
                if isinstance(p, dict):
                    param_names.extend(p.keys())
                    
            m_img = re.search(r'\"image\":\"([^\"]+)\"', block_str)
            img = m_img.group(1) if m_img else None
            params_by_name[name] = {"params": param_names, "image": img}
        except Exception as e:
            pass
            
    print(f"Extracted {len(params_by_name)} unique models with parameters from JS.")
    
    # 2. Update catalog
    with open('utils/helix_catalog.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    catalog = data.get('catalog', {})
    
    updated_count = 0
    not_found = []
    
    for cat, models in catalog.items():
        cleaned_models = []
        for m in models:
            # Skip invalid models scraped from UI text like 'Filter models', 'Select category', etc.
            if m['name'] in ['Filter models', 'Select category', 'None', 'Guitar', 'Bass'] or m['name'].startswith('Found '):
                continue
                
            # If name matches JS exactly, or starts with it
            matched_params = None
            if m['name'] in params_by_name:
                matched_params = params_by_name[m['name']]
            else:
                # Try partial match (e.g., 'WhoWatt 100' vs 'WhoWatt')
                for js_name in params_by_name:
                    if js_name in m['name'] or m['name'] in js_name:
                        matched_params = params_by_name[js_name]
                        break
                        
            if matched_params:
                m['parameters'] = [{"name": p, "type": "knob", "default": 5.0} for p in matched_params["params"]]
                if matched_params["image"]:
                    m['image'] = f"assets/icons_models/{matched_params['image']}"
                updated_count += 1
            else:
                not_found.append(m['name'])
                
            cleaned_models.append(m)
            
        catalog[cat] = cleaned_models
        
    # Write back
    with open('utils/helix_catalog.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
        
    print(f"Successfully updated {updated_count} models with REAL parameters!")
    if not_found:
        print(f"Could not find parameters for {len(not_found)} models.")
        
if __name__ == '__main__':
    update_catalog()
