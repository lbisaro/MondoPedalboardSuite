import os
import urllib.request

base_url = 'https://hxview.netlify.app/'
dirs = {
    'icons_category': [
        'Amp.svg', 'Cab.svg', 'Delay.svg', 'Distortion.svg', 'Dynamics.svg', 
        'EQ.svg', 'Filter.svg', 'IR.svg', 'Looper.svg', 'Modulation.svg', 
        'PitchSynth.svg', 'Preamp.svg', 'Return.svg', 'Reverb.svg', 'Send.svg', 
        'SendReturn.svg', 'VolumePan.svg', 'Wah.svg'
    ],
    'icons_controllers': ['exppedal.svg'],
    'icons_io': ['multi.svg', 'none.svg', 'output_multi.svg', 'output_path.svg']
}

for d, files in dirs.items():
    os.makedirs(f'assets/{d}', exist_ok=True)
    for f in files:
        url = f'{base_url}{d}/{f}'
        path = f'assets/{d}/{f}'
        try:
            urllib.request.urlretrieve(url, path)
            print(f'Downloaded {path}')
        except Exception as e:
            print(f'Failed {url}: {e}')
