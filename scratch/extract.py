import json
import re
with open('scratch/helix_payload.json', encoding='utf-8') as f:
    data = f.read()

# Just print all strings longer than 4 chars
strings = re.findall(r'"([^"\\]+)"', data)
params = [s for s in strings if 'Bass' in s or 'Treble' in s or 'Drive' in s or 'Time' in s or 'Feedback' in s]
print("Found some parameter-like strings:", params[:20])

models = [s for s in strings if 'Placater' in s or 'Scream' in s]
print("Found some model-like strings:", models[:20])
