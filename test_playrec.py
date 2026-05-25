import os
import sys
# Habilitar soporte ASIO antes de importar sounddevice
os.environ['SD_ENABLE_ASIO'] = '1'

import time
import numpy as np
import soundfile as sf
import sounddevice as sd
import mido

def test_matching():
    print("=== TEST TONE MATCHER (ASIO & MIDI DIAGNOSTIC) ===")
    
    # 1. List audio devices
    print("\n--- Audio Devices ---")
    devices = sd.query_devices()
    helix_in_idx = None
    helix_out_idx = None
    for idx, dev in enumerate(devices):
        if "helix" in dev["name"].lower() or "asio" in dev["name"].lower():
            print(f"[{idx}] {dev['name']} (In: {dev['max_input_channels']}, Out: {dev['max_output_channels']}, Default SR: {dev['default_samplerate']})")
            if "asio" in dev["name"].lower() and "helix" in dev["name"].lower():
                helix_in_idx = idx
                helix_out_idx = idx
    
    if helix_in_idx is None:
        # Fallback to look for any ASIO device
        for idx, dev in enumerate(devices):
            if "asio" in dev["name"].lower():
                helix_in_idx = idx
                helix_out_idx = idx
                print(f"Using ASIO fallback: [{idx}] {dev['name']}")
                break
                
    if helix_in_idx is None:
        print("No ASIO Helix device found. Please enter device IDs manually from the list above.")
        try:
            helix_in_idx = int(input("Enter Input Device ID: "))
            helix_out_idx = int(input("Enter Output Device ID: "))
        except:
            print("Invalid input.")
            return

    # 2. Get hardware info
    in_info = sd.query_devices(helix_in_idx)
    out_info = sd.query_devices(helix_out_idx)
    device_sr = int(in_info['default_samplerate'])
    print(f"\nDevice Native Sample Rate: {device_sr} Hz")

    # 3. Load DI audio
    di_path = "archivos_wav/di.wav"
    if not os.path.exists(di_path):
        print(f"Error: {di_path} not found.")
        return
        
    print(f"Loading {di_path}...")
    di_audio, sr = sf.read(di_path)
    if di_audio.ndim > 1:
        di_audio = np.mean(di_audio, axis=1)
    
    print(f"Loaded DI. Length: {len(di_audio)} samples, SR: {sr} Hz, Duration: {len(di_audio)/sr:.2f} seconds")

    # Resample if sample rate doesn't match native device sample rate
    if sr != device_sr:
        print(f"Warning: File SR ({sr} Hz) does not match Device SR ({device_sr} Hz). Resampling...")
        from scipy.signal import resample
        num_samples = int(len(di_audio) * device_sr / sr)
        di_audio = resample(di_audio, num_samples).astype(np.float32)
        sr = device_sr
        print(f"Resampled to {len(di_audio)} samples at {sr} Hz")

    # 4. MIDI setup
    print("\n--- MIDI Output Ports ---")
    ports = mido.get_output_names()
    helix_midi = None
    for p in ports:
        print(f"- {p}")
        if "helix" in p.lower():
            helix_midi = p
            
    if not helix_midi and ports:
        helix_midi = ports[0]
        print(f"No Helix MIDI port found. Using first available: {helix_midi}")
    elif not ports:
        print("No MIDI output ports found.")
        
    cc_num = 17
    cc_val = 64
    
    if helix_midi:
        print(f"Testing MIDI: Sending CC {cc_num} = {cc_val} to port '{helix_midi}'...")
        try:
            with mido.open_output(helix_midi) as port:
                msg = mido.Message('control_change', control=cc_num, value=cc_val)
                port.send(msg)
            print("MIDI sent successfully.")
        except Exception as e:
            print(f"MIDI Error: {e}")

    # 5. Playrec test
    print("\nStarting Playrec Test (3 seconds)...")
    # Tuncate DI to 3 seconds for quick test
    test_len = min(len(di_audio), int(3 * sr))
    di_test = di_audio[:test_len]
    
    # We will use ASIO channels 1 (In) and 1 (Out) (indexes 0)
    # The default channel is usually fine, let's prompt or use channel 1
    send_ch = 0
    recv_ch = 0
    
    num_out = send_ch + 1
    num_in = recv_ch + 1
    
    out_array = np.zeros((len(di_test), num_out), dtype=np.float32)
    out_array[:, send_ch] = di_test
    
    try:
        print(f"Opening playrec stream on Device {helix_in_idx}...")
        recorded = sd.playrec(
            out_array,
            samplerate=sr,
            device=(helix_in_idx, helix_out_idx),
            channels=num_in,
            blocking=True
        )
        print("Playrec completed successfully!")
        print(f"Recorded array shape: {recorded.shape}")
        max_val = np.max(np.abs(recorded))
        print(f"Recorded Max Peak: {max_val:.4f} ({20*np.log10(max_val+1e-12):.2f} dBFS)")
    except Exception as e:
        print(f"\nPlayrec failed with error: {e}")
        
if __name__ == "__main__":
    test_matching()
