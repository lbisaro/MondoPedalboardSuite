import urllib.request
import re
import json

req = urllib.request.Request('https://helixhelp.com/models?categoryId=1', headers={'User-Agent': 'Mozilla/5.0'})
try:
    html = urllib.request.urlopen(req).read().decode('utf-8')
    payload_id = re.search(r'href="/models/_payload\.json\?([^"]+)"', html)
    if payload_id:
        print('Payload ID:', payload_id.group(1))
        req2 = urllib.request.Request(f'https://helixhelp.com/models/_payload.json?{payload_id.group(1)}', headers={'User-Agent': 'Mozilla/5.0'})
        data = urllib.request.urlopen(req2).read().decode('utf-8')
        print(data[:500])
        # Save to file to inspect
        with open('scratch/helix_payload.json', 'w', encoding='utf-8') as f:
            f.write(data)
    else:
        print('No payload id found')
except Exception as e:
    print('Error:', e)
