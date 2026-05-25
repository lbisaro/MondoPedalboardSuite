import numpy as np
import pyloudnorm as pyln
import scipy.signal as signal

class AudioComparator:
    def __init__(self, sample_rate=48000):
        self.sample_rate = sample_rate
        self.meter = pyln.Meter(sample_rate)

    def set_sample_rate(self, sr):
        if self.sample_rate != sr:
            self.sample_rate = sr
            self.meter = pyln.Meter(sr)

    def calculate_metrics(self, audio):
        """
        Calcula métricas para un array de audio (NumPy).
        Se asume audio en formato float32, rango [-1, 1].
        Si es estéreo, debe ser (N, 2).
        """
        if audio.ndim == 1:
            # Convertir a estéreo (mono duplicado) para consistencia si es necesario, 
            # pero pyloudnorm maneja mono.
            audio_stereo = np.column_stack((audio, audio))
        else:
            audio_stereo = audio

        # 1. Sonoridad Percibida (LUFS)
        try:
            lufs = self.meter.integrated_loudness(audio_stereo)
            # Evitar -infinito para compatibilidad con JSON
            if np.isinf(lufs):
                lufs = -99.0
        except Exception:
            lufs = -99.0

        # 2. Max Peak
        max_peak = np.max(np.abs(audio))
        max_peak_db = 20 * np.log10(max_peak + 1e-12)

        # 3. Factor de Cresta y PLR
        # PLR = Peak to Loudness Ratio
        # Si es silencio (lufs muy bajo), el PLR no tiene sentido
        plr = max_peak_db - lufs if lufs > -90.0 else 0.0

        # 4. Análisis Espectral Promediado (Long-term Average Spectrum)
        # Dividimos el audio en bloques, calculamos FFT y promediamos magnitudes.
        n_fft = 4096
        hop = n_fft // 2
        # Ventana de Hann para reducir leakage
        window = np.hanning(n_fft)
        
        # Preparar frames
        n_frames = (len(audio) - n_fft) // hop + 1
        if n_frames > 0:
            mags = []
            for i in range(n_frames):
                start = i * hop
                frame = audio[start : start + n_fft]
                if frame.ndim > 1:
                    frame = np.mean(frame, axis=1) # Mono para el espectro
                
                # FFT y magnitud
                spec = np.abs(np.fft.rfft(frame * window))
                mags.append(spec)
            
            avg_spectrum = np.mean(mags, axis=0)
            freqs = np.fft.rfftfreq(n_fft, 1 / self.sample_rate)
        else:
            avg_spectrum = np.zeros(n_fft // 2 + 1)
            freqs = np.fft.rfftfreq(n_fft, 1 / self.sample_rate)

        # 5. Correlación de Fase (Stereo Width)
        phase_corr = 0
        if audio.ndim > 1 and audio.shape[1] >= 2:
            l = audio[:, 0]
            r = audio[:, 1]
            norm_l = np.linalg.norm(l)
            norm_r = np.linalg.norm(r)
            if norm_l > 0 and norm_r > 0:
                phase_corr = np.sum(l * r) / (norm_l * norm_r)
        
        # 6. Nuevas métricas para detectar Crunch/Distorsión
        # Brillo (Spectral Centroid)
        if np.sum(avg_spectrum) > 0:
            centroid = np.sum(freqs * avg_spectrum) / np.sum(avg_spectrum)
        else:
            centroid = 0.0

        # Saturation Index (basado en la densidad armónica y PLR)
        # Una señal distorsionada tiene un PLR menor (más comprimida)
        # y más energía en frecuencias altas (armónicos).
        # Este es un valor heurístico (0-100)
        # Referencia: Limpio usualmente PLR > 14, Crunch 8-12, Lead < 8
        sat_val = max(0, min(100, (16 - plr) * 6.25)) if lufs > -70 else 0.0

        # Energy Bands (Low: <250Hz, Mid: 250-4kHz, High: >4kHz)
        low_mask = freqs < 250
        mid_mask = (freqs >= 250) & (freqs < 4000)
        high_mask = freqs >= 4000
        
        def get_band_energy(mask):
            if np.any(mask):
                return 20 * np.log10(np.mean(avg_spectrum[mask]) + 1e-12)
            return -99.0

        energy_bands = {
            "low": get_band_energy(low_mask),
            "mid": get_band_energy(mid_mask),
            "high": get_band_energy(high_mask)
        }

        # 7. Sustain (Relación entre energía total y picos)
        # Calculamos el ratio de energía mantenida.
        # Un valor más alto significa que la nota 'dura' más tiempo a un volumen alto.
        # Usamos una ventana de RMS para ver la consistencia.
        window_size = int(0.05 * self.sample_rate) # 50ms
        if len(audio) > window_size:
            # Dividir en bloques y calcular RMS
            n_blocks = len(audio) // window_size
            rms_blocks = []
            for i in range(n_blocks):
                block = audio[i*window_size : (i+1)*window_size]
                rms_blocks.append(np.sqrt(np.mean(block**2)))
            
            rms_blocks = np.array(rms_blocks)
            max_rms = np.max(rms_blocks) + 1e-12
            # Sustain es el porcentaje de bloques que mantienen al menos el 30% del RMS máximo
            sustain_val = (np.sum(rms_blocks > (max_rms * 0.3)) / n_blocks) * 100
        else:
            sustain_val = 0.0

        return {
            "lufs": lufs,
            "max_peak_db": max_peak_db,
            "plr": plr,
            "avg_spectrum": avg_spectrum,
            "freqs": freqs,
            "phase_corr": phase_corr,
            "centroid": centroid,
            "saturation": sat_val,
            "energy_bands": energy_bands,
            "sustain": sustain_val
        }

    def normalize_to_target(self, audio, target_lufs):
        """
        Normaliza el audio para que coincida con el target_lufs.
        """
        if audio.ndim == 1:
            audio_stereo = np.column_stack((audio, audio))
        else:
            audio_stereo = audio
            
        current_lufs = self.meter.integrated_loudness(audio_stereo)
        if current_lufs == -np.inf:
            return audio
            
        gain_db = target_lufs - current_lufs
        gain_linear = 10 ** (gain_db / 20.0)
        return audio * gain_linear

    def save_guitar_di(self, path, audio, sample_rate, metrics):
        """
        Guarda el audio y sus métricas en un único archivo binario (.mondodi).
        """
        import pickle
        data = {
            "version": "1.0",
            "audio": audio,
            "sample_rate": sample_rate,
            "metrics": {
                "lufs": metrics["lufs"],
                "max_peak_db": metrics["max_peak_db"],
                "plr": metrics["plr"],
                "avg_spectrum": metrics["avg_spectrum"],
                "freqs": metrics["freqs"],
                "phase_corr": metrics.get("phase_corr", 0),
                "centroid": metrics.get("centroid", 0),
                "saturation": metrics.get("saturation", 0),
                "energy_bands": metrics.get("energy_bands", {}),
                "sustain": metrics.get("sustain", 0)
            }
        }
        with open(path, 'wb') as f:
            pickle.dump(data, f)

    def load_guitar_di(self, path):
        """
        Carga un archivo .mondodi y devuelve el audio y las métricas.
        """
        import pickle
        with open(path, 'rb') as f:
            data = pickle.load(f)
        return data["audio"], data["sample_rate"], data["metrics"]

    def save_eq_reference(self, path, freqs, values):
        """
        Guarda una referencia de EQ en un archivo binario (.mndEqRef).
        """
        import pickle
        data = {
            "version": "1.0",
            "freqs": freqs,
            "values": values
        }
        with open(path, 'wb') as f:
            pickle.dump(data, f)

    def load_eq_reference(self, path):
        """
        Carga una referencia de EQ desde un archivo .mndEqRef.
        """
        import pickle
        with open(path, 'rb') as f:
            data = pickle.load(f)
        return data["freqs"], data["values"]

    def save_preset_reference(self, path, metrics):
        """
        Guarda las métricas de un preset como referencia (.mndPrstRef).
        """
        import pickle
        data = {
            "version": "1.1",
            "metrics": metrics
        }
        with open(path, 'wb') as f:
            pickle.dump(data, f)

    def load_preset_reference(self, path):
        """
        Carga una referencia de preset (.mndPrstRef).
        """
        import pickle
        with open(path, 'rb') as f:
            data = pickle.load(f)
        return data["metrics"]
