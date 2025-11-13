#!/usr/bin/env python3
"""
Spectrum Analyzer Examples

This script demonstrates how to use the spectrum_analyzer.py module with
different types of signals. It provides examples of analyzing:
- Sine waves (pure periodic signals)
- White noise (flat spectrum)
- Pink noise (1/f spectrum)
- Brown noise (1/f² spectrum)
- Composite signals (mixture of periodic and aperiodic components)

These examples serve as a tutorial for using the spectrum analyzer with
your own time series data.
"""

import numpy as np
import matplotlib.pyplot as plt
from spectrum_analyzer import SpectrumAnalyzer, generate_test_signal
import os

def example_sine_wave():
    """
    Example: Analyzing a sine wave (pure periodic signal)
    """
    print("\n=== Example 1: Sine Wave ===")
    
    # Generate a sine wave
    sampling_rate = 1000  # Hz
    duration = 1.0  # seconds
    frequency = 50  # Hz
    
    time, signal = generate_test_signal(
        'sine', 
        length=int(duration * sampling_rate),
        sampling_rate=sampling_rate,
        frequency=frequency,
        amplitude=1.0
    )
    
    # Create analyzer and analyze
    analyzer = SpectrumAnalyzer(signal, sampling_rate=sampling_rate)
    analyzer.compute_fft()
    
    # Detect dominant frequencies
    peaks = analyzer.detect_dominant_frequencies()
    print("Detected frequencies:")
    for i, (freq, amp) in enumerate(peaks, 1):
        print(f"  Peak {i}: {freq:.2f} Hz (amplitude: {amp:.4e})")
    
    # Plot results
    fig = analyzer.plot_combined(log_scale=True)
    plt.suptitle("Sine Wave Analysis", fontsize=16)
    
    return fig

def example_white_noise():
    """
    Example: Analyzing white noise (flat spectrum)
    """
    print("\n=== Example 2: White Noise ===")
    
    # Generate white noise
    sampling_rate = 1000  # Hz
    duration = 5.0  # seconds
    
    time, signal = generate_test_signal(
        'noise', 
        length=int(duration * sampling_rate),
        sampling_rate=sampling_rate,
        amplitude=1.0
    )
    
    # Create analyzer and analyze
    analyzer = SpectrumAnalyzer(signal, sampling_rate=sampling_rate)
    analyzer.compute_fft()
    analyzer.fit_power_law()
    
    # Print report
    report = analyzer.analyze_and_report()
    print(report)
    
    # Plot results
    fig = analyzer.plot_combined(log_scale=True)
    plt.suptitle("White Noise Analysis", fontsize=16)
    
    return fig

def example_pink_noise():
    """
    Example: Analyzing pink noise (1/f spectrum)
    """
    print("\n=== Example 3: Pink Noise ===")
    
    # Generate pink noise
    sampling_rate = 1000  # Hz
    duration = 10.0  # seconds
    
    time, signal = generate_test_signal(
        'pink', 
        length=int(duration * sampling_rate),
        sampling_rate=sampling_rate,
        amplitude=1.0
    )
    
    # Create analyzer and analyze
    analyzer = SpectrumAnalyzer(signal, sampling_rate=sampling_rate)
    analyzer.compute_fft()
    analyzer.fit_power_law()
    
    # Print report
    report = analyzer.analyze_and_report()
    print(report)
    
    # Plot results
    fig = analyzer.plot_combined(log_scale=True)
    plt.suptitle("Pink Noise Analysis", fontsize=16)
    
    return fig

def example_brown_noise():
    """
    Example: Analyzing brown noise (1/f² spectrum)
    """
    print("\n=== Example 4: Brown Noise ===")
    
    # Generate brown noise
    sampling_rate = 1000  # Hz
    duration = 10.0  # seconds
    
    time, signal = generate_test_signal(
        'brown', 
        length=int(duration * sampling_rate),
        sampling_rate=sampling_rate,
        amplitude=1.0
    )
    
    # Create analyzer and analyze
    analyzer = SpectrumAnalyzer(signal, sampling_rate=sampling_rate)
    analyzer.compute_fft()
    analyzer.fit_power_law()
    
    # Print report
    report = analyzer.analyze_and_report()
    print(report)
    
    # Plot results
    fig = analyzer.plot_combined(log_scale=True)
    plt.suptitle("Brown Noise Analysis", fontsize=16)
    
    return fig

def example_composite_signal():
    """
    Example: Analyzing a composite signal (periodic + noise)
    """
    print("\n=== Example 5: Composite Signal ===")
    
    # Generate a composite signal with sine waves and pink noise
    sampling_rate = 1000  # Hz
    duration = 5.0  # seconds
    
    time, signal = generate_test_signal(
        'composite', 
        length=int(duration * sampling_rate),
        sampling_rate=sampling_rate,
        sine_components=[(10, 1.0), (25, 0.5), (50, 0.25)],
        noise_type='pink',
        noise_amplitude=0.5
    )
    
    # Create analyzer and analyze
    analyzer = SpectrumAnalyzer(signal, sampling_rate=sampling_rate)
    analyzer.compute_fft()
    
    # Detect dominant frequencies
    peaks = analyzer.detect_dominant_frequencies()
    print("Detected frequencies:")
    for i, (freq, amp) in enumerate(peaks, 1):
        print(f"  Peak {i}: {freq:.2f} Hz (amplitude: {amp:.4e})")
    
    # Fit power law to the noise floor (excluding the peaks)
    # We'll use a frequency range that avoids the main peaks
    analyzer.fit_power_law(freq_range=(100, 500))
    
    # Print report
    report = analyzer.analyze_and_report()
    print(report)
    
    # Plot results
    fig = analyzer.plot_combined(log_scale=True)
    plt.suptitle("Composite Signal Analysis", fontsize=16)
    
    return fig

def main():
    """
    Run all examples and save the plots.
    """
    print("Running Spectrum Analyzer Examples")
    
    # Create output directory for plots
    output_dir = "spectrum_examples"
    os.makedirs(output_dir, exist_ok=True)
    
    # Run examples
    examples = [
        (example_sine_wave, "sine_wave"),
        (example_white_noise, "white_noise"),
        (example_pink_noise, "pink_noise"),
        (example_brown_noise, "brown_noise"),
        (example_composite_signal, "composite_signal")
    ]
    
    for example_func, name in examples:
        fig = example_func()
        output_file = os.path.join(output_dir, f"{name}.png")
        fig.savefig(output_file, dpi=300, bbox_inches='tight')
        print(f"Saved plot to {output_file}")
        plt.close(fig)
    
    print("\nAll examples completed. Plots saved to the 'spectrum_examples' directory.")

if __name__ == "__main__":
    main()
