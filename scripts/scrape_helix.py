from playwright.sync_api import sync_playwright
import time
import json
import os
import urllib.request

def get_standard_params(category):
    cat = category.lower()
    if 'amp' in cat or 'preamp' in cat:
        return [
            {"name": "Drive", "type": "knob", "default": 5.0},
            {"name": "Bass", "type": "knob", "default": 5.0},
            {"name": "Mid", "type": "knob", "default": 5.0},
            {"name": "Treble", "type": "knob", "default": 5.0},
            {"name": "Presence", "type": "knob", "default": 5.0},
            {"name": "Ch Vol", "type": "knob", "default": 8.0},
            {"name": "Master", "type": "knob", "default": 10.0}
        ]
    elif 'distortion' in cat or 'dynamics' in cat or 'eq' in cat:
        return [
            {"name": "Drive", "type": "knob", "default": 5.0},
            {"name": "Tone", "type": "knob", "default": 5.0},
            {"name": "Level", "type": "knob", "default": 8.0}
        ]
    elif 'delay' in cat:
        return [
            {"name": "Time", "type": "knob", "default": 500},
            {"name": "Feedback", "type": "knob", "default": 30},
            {"name": "Mix", "type": "knob", "default": 40}
        ]
    elif 'reverb' in cat:
        return [
            {"name": "Decay", "type": "knob", "default": 4.0},
            {"name": "Pre Delay", "type": "knob", "default": 10},
            {"name": "Mix", "type": "knob", "default": 35}
        ]
    elif 'modulation' in cat or 'filter' in cat or 'pitch' in cat or 'wah' in cat:
        return [
            {"name": "Speed", "type": "knob", "default": 3.0},
            {"name": "Depth", "type": "knob", "default": 5.0},
            {"name": "Mix", "type": "knob", "default": 50}
        ]
    else:
        return [
            {"name": "Param 1", "type": "knob", "default": 5.0},
            {"name": "Param 2", "type": "knob", "default": 5.0}
        ]

def scrape():
    os.makedirs('assets/icons_helix', exist_ok=True)
    catalog = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # Fix the viewport to avoid mobile layout issues
        page = browser.new_page(viewport={'width': 1920, 'height': 1080})
        page.goto('https://helixhelp.com/models')
        time.sleep(3)
        
        # Click each category in the sidebar
        categories = page.locator('aside button').evaluate_all('nodes => nodes.map(n => n.innerText).filter(t => t && t !== "None")')
        
        # The first few might be "Filter models" etc. Let's just use known ones
        known_cats = ['Distortion', 'Dynamics', 'EQ', 'Modulation', 'Delay', 'Reverb', 'Pitch/Synth', 'Filter', 'Wah', 'Amp', 'Preamp', 'Cab']
        
        for cat in known_cats:
            print(f"Scraping category: {cat}")
            try:
                # Select category from the first dropdown
                page.locator('select').first.select_option(label=cat)
                time.sleep(2) # wait for models to render
                
                # Get all models rendered
                models = page.evaluate('''() => {
                    let results = [];
                    document.querySelectorAll('h3.text-xl').forEach(h3 => {
                        let name = h3.innerText.trim();
                        let based_on = "";
                        let next = h3.nextElementSibling;
                        if (next && next.innerText.includes('Based on:')) {
                            based_on = next.innerText.replace('Based on:', '').trim();
                        }
                        
                        // find previous sibling image
                        let img = null;
                        let prev = h3.previousElementSibling;
                        while(prev) {
                            if(prev.tagName === 'IMG') { img = prev.src; break; }
                            if(prev.querySelector('img')) { img = prev.querySelector('img').src; break; }
                            prev = prev.previousElementSibling;
                        }
                        if(!img) {
                            let parent = h3.parentElement;
                            if(parent && parent.querySelector('img')) img = parent.querySelector('img').src;
                        }
                        results.push({name, based_on, image: img});
                    });
                    return results;
                }''')
                
                print(f"  Found {len(models)} models")
                
                catalog_cat = []
                for m in models:
                    img_filename = None
                    if m.get('image') and 'data:image' not in m['image']:
                        img_url = m['image']
                        if img_url.startswith('/'):
                            img_url = 'https://helixhelp.com' + img_url
                        filename = m['name'].replace('/', '_').replace(' ', '').replace(':', '') + ".png"
                        filepath = os.path.join('assets/icons_helix', filename)
                        try:
                            # only download if not exists
                            if not os.path.exists(filepath):
                                urllib.request.urlretrieve(img_url, filepath)
                            img_filename = 'assets/icons_helix/' + filename
                        except Exception as e:
                            print(f"  Failed to DL image {img_url}: {e}")
                    
                    catalog_cat.append({
                        "name": m['name'],
                        "based_on": m['based_on'],
                        "image": img_filename,
                        "parameters": get_standard_params(cat)
                    })
                    
                catalog[cat] = catalog_cat
                
            except Exception as e:
                print(f"Error scraping {cat}: {e}")
                
        browser.close()
        
    with open('utils/helix_catalog.json', 'w', encoding='utf-8') as f:
        json.dump({"metadata": {"version": "2.0.0", "source": "Scraped helixhelp.com with defaults"}, "catalog": catalog}, f, indent=2)

    print("Done generating catalog!")

if __name__ == '__main__':
    scrape()
