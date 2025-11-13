# Spectrum Analyzer

A Python tool for analyzing time series data in the frequency domain. This tool performs Fast Fourier Transform (FFT) analysis to identify periodic components and detect power-law relationships (1/f^n noise patterns) in the frequency spectrum.

## Features

- Fast Fourier Transform (FFT) of time series data
- Power spectral density calculation
- Detection of dominant frequencies
- Power law fitting to identify 1/f^n relationships
- Visualization of both time and frequency domains
- Support for various windowing functions
- Comprehensive analysis reports
- Command-line interface for easy use

## Requirements

- Python 3.6 or higher
- NumPy
- SciPy
- Matplotlib

## Installation

1. Clone or download this repository
2. Install the required dependencies:

```bash
pip install numpy scipy matplotlib
```

No additional installation is needed - the scripts can be run directly.

## Usage

### Basic Usage

```bash
python spectrum_analyzer.py --file your_data.csv
```

This will analyze the time series data in the first column of `your_data.csv` and display the results.

### Command-line Options

#### Input Options:
- `--file`, `-f`: Input file with time series data
- `--column`, `-c`: Column index to use from input file (0-based, default: 0)
- `--delimiter`, `-d`: Delimiter used in input file (default: ',')
- `--skip-header`: Number of header lines to skip (default: 0)

#### Test Signal Options:
- `--test`, `-t`: Generate a test signal instead of reading from file
  - Options: 'sine', 'square', 'noise', 'pink', 'brown', 'composite'
- `--length`: Length of test signal in samples (default: 1000)
- `--sampling-rate`: Sampling rate in Hz (default: 100.0)
- `--frequency`: Frequency for sine or square test signals (default: 5.0)

#### Analysis Options:
- `--window`, `-w`: Window function to apply before FFT
  - Options: 'hann', 'hamming', 'blackman', 'boxcar', 'flattop', 'none'
- `--min-freq`: Minimum frequency for power law fitting
- `--max-freq`: Maximum frequency for power law fitting

#### Output Options:
- `--output`, `-o`: Output file for the plot (png, pdf, svg, etc.)
- `--report`, `-r`: Output file for the analysis report
- `--no-log`: Disable logarithmic scaling on plots
- `--no-fit`: Disable power law fitting

### Examples

#### Analyze a CSV file:
```bash
python spectrum_analyzer.py --file data.csv --column 1 --delimiter "," --skip-header 1
```

#### Generate and analyze a sine wave:
```bash
python spectrum_analyzer.py --test sine --frequency 10 --sampling-rate 1000 --length 10000
```

#### Generate and analyze pink noise:
```bash
python spectrum_analyzer.py --test pink --sampling-rate 1000 --length 10000
```

#### Save results to files:
```bash
python spectrum_analyzer.py --file data.csv --output spectrum.png --report analysis.txt
```

## Understanding 1/f^n Noise

Many natural and man-made systems exhibit power-law behavior in their frequency spectra, often described as 1/f^n noise. The exponent n characterizes the type of noise:

- **n ≈ 0**: White noise - flat spectrum, equal power at all frequencies
- **n ≈ 1**: Pink noise (1/f) - power decreases proportionally to frequency
- **n ≈ 2**: Brown noise (1/f²) - power decreases with the square of frequency
- **n > 2**: Black noise - steep falloff at higher frequencies

### Significance of 1/f^n Noise

1/f^n noise patterns appear in many natural phenomena and complex systems:

- **Pink noise (n ≈ 1)** is found in:
  - Heart rate variability
  - Neural activity
  - Music and speech
  - Financial market fluctuations
  - Natural images

- **Brown noise (n ≈ 2)** is found in:
  - Brownian motion
  - Weather patterns
  - Some geological processes

The presence and specific exponent of 1/f^n noise can provide insights into the underlying dynamics of a system, including:
- Self-organized criticality
- Long-range correlations
- Fractal properties
- Complex system behavior

## Interpreting the Results

### Time Series Plot
The top plot shows your original time series data. Look for:
- Obvious periodic patterns
- Trends
- Discontinuities or anomalies

### Frequency Spectrum Plot
The bottom plot shows the power spectral density. Look for:

1. **Peaks**: Sharp peaks indicate periodic components (sine waves) at specific frequencies.
   - The height of the peak indicates the amplitude of the component
   - The width of the peak relates to the stability of the frequency

2. **Noise Floor**: The background spectrum between peaks.
   - A flat noise floor suggests white noise
   - A sloping noise floor suggests colored noise (pink, brown, etc.)

3. **Power Law Fit**: The dashed line shows the fitted 1/f^n relationship.
   - The exponent n is shown in the title
   - How well the line fits the data indicates how well the signal follows a power law

### Analysis Report
The text report provides:
- Basic signal properties (length, sampling rate, etc.)
- Power law exponent and noise type classification
- List of dominant frequencies detected

## Examples

The `spectrum_analyzer_examples.py` script demonstrates how to use the analyzer with different types of signals:

1. **Sine Wave**: A pure periodic signal with a single frequency component
2. **White Noise**: Random signal with equal power across all frequencies
3. **Pink Noise**: 1/f noise with power decreasing proportionally to frequency
4. **Brown Noise**: 1/f² noise with power decreasing with the square of frequency
5. **Composite Signal**: A mixture of periodic components and noise

Run the examples script to see these analyses in action:

```bash
python spectrum_analyzer_examples.py
```

This will generate example plots in the `spectrum_examples` directory.

### Example: Pink Noise Analysis

Pink noise (1/f noise) has equal energy per octave and appears as a straight line with slope -1 on a log-log plot:

```
Spectrum Analysis Report
======================

Time Series Length: 10000 samples
Sampling Rate: 1000 Hz
Duration: 10.00 seconds
Frequency Resolution: 0.1000 Hz
Nyquist Frequency: 500.0 Hz

Power Law Analysis:
  Exponent (n): 0.9872
  Amplitude: 1.0234e-02
  Noise Type: Pink noise (1/f)

Dominant Frequencies:
  1. 0.10 Hz (amplitude: 1.0234e-02)
  2. 0.20 Hz (amplitude: 5.1172e-03)
  3. 0.30 Hz (amplitude: 3.4115e-03)
  4. 0.40 Hz (amplitude: 2.5586e-03)
  5. 0.50 Hz (amplitude: 2.0469e-03)
```

The exponent n ≈ 1 confirms this is pink noise, and the straight-line fit on the log-log plot shows the 1/f relationship.

## Programmatic Usage

You can also use the `SpectrumAnalyzer` class in your own Python scripts:

```python
from spectrum_analyzer import SpectrumAnalyzer
import numpy as np

# Create or load your time series data
sampling_rate = 1000  # Hz
time = np.arange(0, 10, 1/sampling_rate)  # 10 seconds of data
signal = np.sin(2 * np.pi * 5 * time) + 0.5 * np.random.randn(len(time))

# Create analyzer and analyze
analyzer = SpectrumAnalyzer(signal, sampling_rate=sampling_rate)
analyzer.compute_fft()
analyzer.fit_power_law()

# Get results
dominant_freqs = analyzer.detect_dominant_frequencies()
power_law_exponent = analyzer.power_law_params[0] if analyzer.power_law_params else None

# Generate report
report = analyzer.analyze_and_report()
print(report)

# Create visualization
fig = analyzer.plot_combined()
fig.savefig('my_analysis.png')
```

## References and Further Reading

### Signal Processing and Fourier Analysis
- Smith, S. W. (1997). The Scientist and Engineer's Guide to Digital Signal Processing. [Link](http://www.dspguide.com/)
- Oppenheim, A. V., & Schafer, R. W. (2009). Discrete-Time Signal Processing. Prentice Hall.

### 1/f Noise and Power Laws
- Bak, P., Tang, C., & Wiesenfeld, K. (1987). Self-organized criticality: An explanation of the 1/f noise. Physical Review Letters, 59(4), 381.
- Mandelbrot, B. B., & Van Ness, J. W. (1968). Fractional Brownian motions, fractional noises and applications. SIAM Review, 10(4), 422-437.
- Voss, R. F., & Clarke, J. (1975). '1/f noise' in music and speech. Nature, 258(5533), 317-318.

### Python Libraries for Signal Processing
- SciPy: [scipy.signal](https://docs.scipy.org/doc/scipy/reference/signal.html)
- NumPy: [numpy.fft](https://numpy.org/doc/stable/reference/routines.fft.html)

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- NumPy, SciPy, and Matplotlib developers for their excellent scientific computing libraries
- The signal processing community for developing and documenting FFT algorithms and applications
