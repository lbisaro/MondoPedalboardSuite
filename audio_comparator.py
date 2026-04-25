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
            # Correlación de fase simplificada: (L*R) / (norm(L)*norm(R))
            norm_l = np.linalg.norm(l)
            norm_r = np.linalg.norm(r)
            if norm_l > 0 and norm_r > 0:
                phase_corr = np.sum(l * r) / (norm_l * norm_r)

        return {
            "lufs": lufs,
            "max_peak_db": max_peak_db,
            "plr": plr,
            "avg_spectrum": avg_spectrum,
            "freqs": freqs,
            "phase_corr": phase_corr
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
                "phase_corr": metrics.get("phase_corr", 0)
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
