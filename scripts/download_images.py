import json
import urllib.request
import os
from concurrent.futures import ThreadPoolExecutor

def download_image(url, filepath):
    try:
        if not os.path.exists(filepath):
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req) as response, open(filepath, 'wb') as out_file:
                out_file.write(response.read())
            return f"Success: {url}"
    except Exception as e:
        return f"Error downloading {url}: {e}"

def run():
    os.makedirs('assets/icons_models', exist_ok=True)
    with open('utils/helix_catalog.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    tasks = []
    # Collect all unique images
    images = set()
    for cat, models in data.get('catalog', {}).items():
        for m in models:
            img = m.get('image')
            if img:
                # the catalog has it as 'assets/icons_models/filename.png'
                filename = os.path.basename(img)
                # For some models, the url is /images/icons_models/...
                # In helixhelp, the base path is https://helixhelp.com/images/icons_models/
                url = f"https://helixhelp.com/images/icons_models/{filename}"
                images.add((url, img))
                
    print(f"Starting download of {len(images)} unique images...")
    
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(download_image, url, path) for url, path in images]
        for f in futures:
            res = f.result()
            if res:
                print(res)
                
    print("All downloads finished!")

if __name__ == '__main__':
    run()
