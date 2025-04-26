#!/usr/bin/env python3
"""
Spectrum Analyzer

This script analyzes time series data to identify its frequency components using
Fourier analysis. It can detect periodic components and analyze aperiodic components
to determine if they follow a 1/f^n power law (pink noise, brown noise, etc.).

Features:
- Fast Fourier Transform (FFT) of time series data
- Power spectral density calculation
- Detection of dominant frequencies
- Power law fitting to identify 1/f^n relationships
- Visualization of both time and frequency domains
- Support for various windowing functions
"""

import numpy as np
import matplotlib.pyplot as plt
from scipy import signal
from scipy import optimize
import argparse
import os
import sys
from matplotlib.ticker import ScalarFormatter

class SpectrumAnalyzer:
    """
    A class for analyzing the frequency spectrum of time series data.
    """
    
    def __init__(self, time_series=None, sampling_rate=1.0, window='hann'):
        """
        Initialize the spectrum analyzer.
        
        Parameters:
        -----------
        time_series : array-like, optional
            The time series data to analyze
        sampling_rate : float, optional
            The sampling rate of the time series in Hz
        window : str, optional
            The windowing function to apply before FFT
        """
        self.time_series = time_series
        self.sampling_rate = sampling_rate
        self.window = window
        self.frequencies = None
        self.spectrum = None
        self.psd = None
        self.power_law_params = None
        
    def load_from_file(self, file_path, column=0, delimiter=',', skip_header=0):
        """
        Load time series data from a file.
        
        Parameters:
        -----------
        file_path : str
            Path to the file containing time series data
        column : int, optional
            Column index to use (0-based)
        delimiter : str, optional
            Delimiter used in the file
        skip_header : int, optional
            Number of header lines to skip
        """
        try:
            data = np.loadtxt(file_path, delimiter=delimiter, skiprows=skip_header)
            if data.ndim > 1:
                self.time_series = data[:, column]
            else:
                self.time_series = data
            print(f"Loaded {len(self.time_series)} data points from {file_path}")
            return True
        except Exception as e:
            print(f"Error loading file: {e}")
            return False
    
    def compute_fft(self):
        """
        Compute the Fast Fourier Transform of the time series.
        """
        if self.time_series is None:
            print("No time series data available")
            return False
        
        # Apply window function
        if self.window:
            window_function = signal.get_window(self.window, len(self.time_series))
            windowed_data = self.time_series * window_function
        else:
            windowed_data = self.time_series
        
        # Compute FFT
        self.spectrum = np.fft.rfft(windowed_data)
        
        # Compute frequency bins
        self.frequencies = np.fft.rfftfreq(len(self.time_series), d=1/self.sampling_rate)
        
        # Compute power spectral density
        self.psd = np.abs(self.spectrum)**2 / len(self.time_series)
        
        return True
    
    def fit_power_law(self, freq_range=None):
        """
        Fit a power law (1/f^n) to the power spectral density.
        
        Parameters:
        -----------
        freq_range : tuple, optional
            (min_freq, max_freq) range to use for fitting
        
        Returns:
        --------
        tuple
            (n, amplitude) where n is the power law exponent
        """
        if self.frequencies is None or self.psd is None:
            print("Compute FFT first")
            return None
        
        # Filter frequencies if range is specified
        if freq_range:
            min_freq, max_freq = freq_range
            mask = (self.frequencies >= min_freq) & (self.frequencies <= max_freq)
            freqs = self.frequencies[mask]
            psd_values = self.psd[mask]
        else:
            # Skip DC component (first value)
            freqs = self.frequencies[1:]
            psd_values = self.psd[1:]
        
        # Log transform for linear fitting
        log_freqs = np.log10(freqs)
        log_psd = np.log10(psd_values)
        
        # Define power law function for fitting
        def power_law(x, n, amplitude):
            return amplitude - n * x
        
        # Fit the power law
        try:
            params, _ = optimize.curve_fit(power_law, log_freqs, log_psd)
            n, amplitude = params
            self.power_law_params = (n, 10**amplitude)
            return self.power_law_params
        except Exception as e:
            print(f"Error fitting power law: {e}")
            return None
    
    def plot_time_series(self, ax=None):
        """
        Plot the time series data.
        
        Parameters:
        -----------
        ax : matplotlib.axes.Axes, optional
            Axes to plot on
        """
        if self.time_series is None:
            print("No time series data available")
            return
        
        if ax is None:
            fig, ax = plt.subplots(figsize=(10, 4))
        
        # Create time array
        time = np.arange(len(self.time_series)) / self.sampling_rate
        
        ax.plot(time, self.time_series)
        ax.set_xlabel('Time (s)')
        ax.set_ylabel('Amplitude')
        ax.set_title('Time Series')
        ax.grid(True)
        
        return ax
    
    def plot_spectrum(self, ax=None, log_scale=True, show_fit=True):
        """
        Plot the frequency spectrum.
        
        Parameters:
        -----------
        ax : matplotlib.axes.Axes, optional
            Axes to plot on
        log_scale : bool, optional
            Whether to use log scales for both axes
        show_fit : bool, optional
            Whether to show the power law fit
        """
        if self.frequencies is None or self.psd is None:
            print("Compute FFT first")
            return
        
        if ax is None:
            fig, ax = plt.subplots(figsize=(10, 6))
        
        # Plot the power spectral density
        ax.plot(self.frequencies, self.psd, label='Power Spectral Density')
        
        # Plot power law fit if available and requested
        if show_fit and self.power_law_params is not None:
            n, amplitude = self.power_law_params
            # Generate the fitted curve
            fit_freqs = self.frequencies[1:]  # Skip DC component
            fit_psd = amplitude * fit_freqs**(-n)
            ax.plot(fit_freqs, fit_psd, 'r--', 
                    label=f'1/f^{n:.2f} fit')
        
        # Set log scales if requested
        if log_scale:
            ax.set_xscale('log')
            ax.set_yscale('log')
            ax.xaxis.set_major_formatter(ScalarFormatter())
            ax.yaxis.set_major_formatter(ScalarFormatter())
        
        ax.set_xlabel('Frequency (Hz)')
        ax.set_ylabel('Power Spectral Density')
        ax.set_title('Frequency Spectrum')
        ax.grid(True, which='both', linestyle='--', alpha=0.7)
        ax.legend()
        
        return ax
    
    def plot_combined(self, log_scale=True, show_fit=True):
        """
        Create a combined plot with time series and spectrum.
        
        Parameters:
        -----------
        log_scale : bool, optional
            Whether to use log scales for frequency plot
        show_fit : bool, optional
            Whether to show the power law fit
        """
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10))
        
        self.plot_time_series(ax=ax1)
        self.plot_spectrum(ax=ax2, log_scale=log_scale, show_fit=show_fit)
        
        if self.power_law_params is not None:
            n, _ = self.power_law_params
            fig.suptitle(f'Spectrum Analysis (Power Law Exponent: {n:.2f})', fontsize=16)
        else:
            fig.suptitle('Spectrum Analysis', fontsize=16)
        
        plt.tight_layout()
        return fig
    
    def detect_dominant_frequencies(self, n_peaks=5, min_height=None):
        """
        Detect the dominant frequencies in the spectrum.
        
        Parameters:
        -----------
        n_peaks : int, optional
            Maximum number of peaks to detect
        min_height : float, optional
            Minimum height for a peak to be considered
        
        Returns:
        --------
        list of tuples
            (frequency, amplitude) for each detected peak
        """
        if self.frequencies is None or self.psd is None:
            print("Compute FFT first")
            return []
        
        # Find peaks in the PSD
        if min_height is None:
            min_height = np.max(self.psd) * 0.1  # 10% of max by default
        
        peaks, _ = signal.find_peaks(self.psd, height=min_height)
        
        # Sort peaks by amplitude
        peak_amplitudes = self.psd[peaks]
        sorted_indices = np.argsort(peak_amplitudes)[::-1]  # Descending order
        
        # Get top n_peaks
        top_peaks = []
        for i in sorted_indices[:n_peaks]:
            freq = self.frequencies[peaks[i]]
            amp = self.psd[peaks[i]]
            top_peaks.append((freq, amp))
        
        return top_peaks
    
    def analyze_and_report(self):
        """
        Perform a complete analysis and return a text report.
        """
        if self.time_series is None:
            return "No time series data available"
        
        # Compute FFT if not already done
        if self.frequencies is None:
            self.compute_fft()
        
        # Fit power law if not already done
        if self.power_law_params is None:
            self.fit_power_law()
        
        # Detect dominant frequencies
        dominant_freqs = self.detect_dominant_frequencies()
        
        # Generate report
        report = []
        report.append("Spectrum Analysis Report")
        report.append("======================\n")
        
        report.append(f"Time Series Length: {len(self.time_series)} samples")
        report.append(f"Sampling Rate: {self.sampling_rate} Hz")
        report.append(f"Duration: {len(self.time_series)/self.sampling_rate:.2f} seconds")
        report.append(f"Frequency Resolution: {self.sampling_rate/len(self.time_series):.4f} Hz")
        report.append(f"Nyquist Frequency: {self.sampling_rate/2} Hz\n")
        
        if self.power_law_params:
            n, amplitude = self.power_law_params
            report.append(f"Power Law Analysis:")
            report.append(f"  Exponent (n): {n:.4f}")
            report.append(f"  Amplitude: {amplitude:.4e}")
            
            # Categorize the noise type based on the exponent
            if 0.8 <= n <= 1.2:
                noise_type = "Pink noise (1/f)"
            elif 1.8 <= n <= 2.2:
                noise_type = "Brown noise (1/f²)"
            elif n < 0.3:
                noise_type = "White noise (flat spectrum)"
            elif n > 2.5:
                noise_type = "Black noise (steep falloff)"
            else:
                noise_type = f"1/f^{n:.2f} noise"
            
            report.append(f"  Noise Type: {noise_type}\n")
        
        if dominant_freqs:
            report.append("Dominant Frequencies:")
            for i, (freq, amp) in enumerate(dominant_freqs, 1):
                report.append(f"  {i}. {freq:.2f} Hz (amplitude: {amp:.4e})")
        else:
            report.append("No dominant frequencies detected")
        
        return "\n".join(report)

def generate_test_signal(signal_type, length=1000, sampling_rate=100, **kwargs):
    """
    Generate a test signal of the specified type.
    
    Parameters:
    -----------
    signal_type : str
        Type of signal to generate ('sine', 'square', 'noise', 'pink', 'brown')
    length : int, optional
        Length of the signal in samples
    sampling_rate : float, optional
        Sampling rate in Hz
    **kwargs : dict
        Additional parameters specific to the signal type
    
    Returns:
    --------
    tuple
        (time_array, signal_array)
    """
    time = np.arange(length) / sampling_rate
    
    if signal_type == 'sine':
        freq = kwargs.get('frequency', 5)
        amplitude = kwargs.get('amplitude', 1.0)
        phase = kwargs.get('phase', 0.0)
        signal = amplitude * np.sin(2 * np.pi * freq * time + phase)
        
    elif signal_type == 'square':
        freq = kwargs.get('frequency', 5)
        amplitude = kwargs.get('amplitude', 1.0)
        duty = kwargs.get('duty', 0.5)
        signal = amplitude * signal.square(2 * np.pi * freq * time, duty=duty)
        
    elif signal_type == 'noise':
        amplitude = kwargs.get('amplitude', 1.0)
        signal = amplitude * np.random.randn(length)
        
    elif signal_type == 'pink':
        # Generate pink noise using FFT method
        white_noise = np.random.randn(length)
        X = np.fft.rfft(white_noise)
        S = np.arange(len(X)) + 1  # +1 to avoid division by zero
        S = np.sqrt(1.0 / S)  # 1/f spectrum
        y = np.fft.irfft(X * S, n=length)
        signal = y * kwargs.get('amplitude', 1.0) / np.std(y)
        
    elif signal_type == 'brown':
        # Generate brown noise using cumulative sum of white noise
        white_noise = np.random.randn(length)
        brown = np.cumsum(white_noise)
        # Normalize
        signal = brown * kwargs.get('amplitude', 1.0) / np.std(brown)
        
    elif signal_type == 'composite':
        # Generate a composite signal with multiple components
        signal = np.zeros(length)
        
        # Add sine waves
        for freq, amp in kwargs.get('sine_components', [(5, 1.0), (10, 0.5), (20, 0.2)]):
            signal += amp * np.sin(2 * np.pi * freq * time)
        
        # Add noise if specified
        noise_type = kwargs.get('noise_type', None)
        noise_amp = kwargs.get('noise_amplitude', 0.1)
        
        if noise_type == 'white':
            signal += noise_amp * np.random.randn(length)
        elif noise_type == 'pink':
            white_noise = np.random.randn(length)
            X = np.fft.rfft(white_noise)
            S = np.arange(len(X)) + 1
            S = np.sqrt(1.0 / S)
            y = np.fft.irfft(X * S, n=length)
            signal += noise_amp * y / np.std(y)
        elif noise_type == 'brown':
            white_noise = np.random.randn(length)
            brown = np.cumsum(white_noise)
            signal += noise_amp * brown / np.std(brown)
    
    else:
        raise ValueError(f"Unknown signal type: {signal_type}")
    
    return time, signal

def parse_arguments():
    """
    Parse command-line arguments.
    """
    parser = argparse.ArgumentParser(description='Spectrum Analyzer for Time Series Data')
    
    # Input options
    input_group = parser.add_argument_group('Input Options')
    input_group.add_argument('--file', '-f', type=str, help='Input file with time series data')
    input_group.add_argument('--column', '-c', type=int, default=0, 
                            help='Column index to use from input file (0-based)')
    input_group.add_argument('--delimiter', '-d', type=str, default=',',
                            help='Delimiter used in input file')
    input_group.add_argument('--skip-header', type=int, default=0,
                            help='Number of header lines to skip')
    
    # Test signal options
    test_group = parser.add_argument_group('Test Signal Options')
    test_group.add_argument('--test', '-t', type=str, 
                           choices=['sine', 'square', 'noise', 'pink', 'brown', 'composite'],
                           help='Generate a test signal instead of reading from file')
    test_group.add_argument('--length', type=int, default=1000,
                           help='Length of test signal in samples')
    test_group.add_argument('--sampling-rate', type=float, default=100.0,
                           help='Sampling rate in Hz')
    test_group.add_argument('--frequency', type=float, default=5.0,
                           help='Frequency for sine or square test signals')
    
    # Analysis options
    analysis_group = parser.add_argument_group('Analysis Options')
    analysis_group.add_argument('--window', '-w', type=str, default='hann',
                              choices=['hann', 'hamming', 'blackman', 'boxcar', 'flattop', 'none'],
                              help='Window function to apply before FFT')
    analysis_group.add_argument('--min-freq', type=float, default=None,
                              help='Minimum frequency for power law fitting')
    analysis_group.add_argument('--max-freq', type=float, default=None,
                              help='Maximum frequency for power law fitting')
    
    # Output options
    output_group = parser.add_argument_group('Output Options')
    output_group.add_argument('--output', '-o', type=str, default=None,
                             help='Output file for the plot (png, pdf, svg, etc.)')
    output_group.add_argument('--report', '-r', type=str, default=None,
                             help='Output file for the analysis report')
    output_group.add_argument('--no-log', action='store_true',
                             help='Disable logarithmic scaling on plots')
    output_group.add_argument('--no-fit', action='store_true',
                             help='Disable power law fitting')
    
    return parser.parse_args()

def main():
    """
    Main function to run the spectrum analyzer.
    """
    args = parse_arguments()
    
    # Initialize the analyzer
    window = None if args.window == 'none' else args.window
    analyzer = SpectrumAnalyzer(sampling_rate=args.sampling_rate, window=window)
    
    # Load data or generate test signal
    if args.test:
        print(f"Generating {args.test} test signal...")
        _, signal = generate_test_signal(
            args.test, 
            length=args.length, 
            sampling_rate=args.sampling_rate,
            frequency=args.frequency
        )
        analyzer.time_series = signal
    elif args.file:
        if not analyzer.load_from_file(
            args.file, 
            column=args.column, 
            delimiter=args.delimiter, 
            skip_header=args.skip_header
        ):
            return
    else:
        print("No input specified. Use --file or --test")
        return
    
    # Compute FFT
    analyzer.compute_fft()
    
    # Fit power law if not disabled
    if not args.no_fit:
        freq_range = None
        if args.min_freq is not None and args.max_freq is not None:
            freq_range = (args.min_freq, args.max_freq)
        analyzer.fit_power_law(freq_range=freq_range)
    
    # Create plot
    fig = analyzer.plot_combined(log_scale=not args.no_log, show_fit=not args.no_fit)
    
    # Generate report
    report = analyzer.analyze_and_report()
    print("\n" + report)
    
    # Save report if requested
    if args.report:
        with open(args.report, 'w') as f:
            f.write(report)
        print(f"Report saved to {args.report}")
    
    # Save plot if requested
    if args.output:
        plt.savefig(args.output, dpi=300, bbox_inches='tight')
        print(f"Plot saved to {args.output}")
    else:
        plt.show()

if __name__ == "__main__":
    main()
