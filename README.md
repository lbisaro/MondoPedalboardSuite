# Mondo Pedalboard Suite 🎸🎛️

**Mondo Pedalboard Suite** is a professional-grade audio analysis desktop application designed specifically for guitarists and sound engineers using high-end modelers (like Line 6 Helix, Fractal Audio, Quad Cortex, etc.). It provides real-time frequency analysis and a specialized tool for comparing and matching presets using Direct Injection (DI) recordings.

![Main Interface Mockup](https://github.com/lbisaro/MondoPedalboardSuite/blob/master/docs/screenshot.png) 

## 🚀 Key Features

### 1. EQ Analyzer (Real-Time Frequency Response)
Analyze the frequency response of your hardware in real-time with surgical precision.
- **Perfect Periodic Noise**: Uses custom-generated noise that avoids FFT leakage, providing a crystal-clear frequency curve without jitter.
- **Advanced Smoothing**: Choose between raw data or fractional octave smoothing (1/3, 1/6, 1/12 Octave) for a professional visualization.
- **Persistence References**: Save your favorite curves as `.mndEqRef` binary files and overlay them to match EQs across different devices or presets.
- **Interactive Plot**: High-performance `pyqtgraph` implementation with crosshair tracking and delta measurement tools.

### 2. Preset Comparator (Matching & Dynamics)
The ultimate tool for making two different presets sound and feel the same.
- **DI Recording**: Record your guitar's dry signal directly into the app using a dedicated DI channel.
- **A/B Comparison**: Play your DI back through two different presets (Preset A and Preset B) and capture their responses.
- **Loudness Analysis**: Professional metering including **LUFS** (Integrated Loudness), **Max Peak**, and **PLR** (Peak-to-Loudness Ratio/Dynamics).
- **Visual Diff**: Automatically highlights the frequency differences between Preset A and B, showing exactly where you need to add or cut EQ.
- **Custom Binary Format**: Stores audio and analysis data in highly optimized `.mndDI` files.

### 3. Professional Hardware Integration
- **ASIO Support**: Low-latency performance for accurate measurements.
- **Flexible Routing**: Configure input, output, and DI record channels independently.
- **Auto Sample-Rate**: Dynamically adapts to your hardware's current sample rate (44.1k, 48k, 96k, etc.).

## 🛠️ Technology Stack
- **Python 3.13+**
- **PySide6** (Qt for Python) for a modern, responsive UI.
- **Numpy & SciPy** for high-performance DSP.
- **Pyqtgraph** for real-time data visualization.
- **Sounddevice** for robust audio I/O.
- **Pyloudnorm** for ITU-R BS.1770-4 loudness compliance.

## 📦 Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/lbisaro/MondoPedalboardSuite.git
   cd MondoPedalboardSuite
   ```

2. Create a virtual environment and install dependencies:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. Run the application:
   ```bash
   python MondoPBSuite.py
   ```

## 📂 File Formats
The app uses custom binary formats to keep data organized and portable:
- **`.mndDI`**: Bundles raw DI audio with pre-calculated metrics (LUFS, Peak, Spectrum).
- **`.mndEqRef`**: Stores averaged frequency response curves for the EQ Analyzer.

## 🎨 Design Aesthetics
Built with a "Premium Dark" aesthetic, featuring:
- Vibrant teal and orange highlights.
- Modern typography.
- Glassmorphism-inspired cards and interactive elements.
- Smooth transitions and real-time visual feedback.

---
Developed with ❤️ by **Antigravity** & **lbisaro**.
