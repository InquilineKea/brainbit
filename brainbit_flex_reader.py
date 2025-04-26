#!/usr/bin/env python3
"""
BrainBit Flex EEG Reader

This script is specifically customized for the BrainBit Flex device.
It connects to the device using BrainFlow, acquires data, and
visualizes it using MNE-Python.
"""

import time
import numpy as np
import argparse
import matplotlib.pyplot as plt
from datetime import datetime

# BrainFlow imports
import brainflow
from brainflow.board_shim import BoardShim, BrainFlowInputParams, BoardIds, LogLevels
from brainflow.data_filter import DataFilter, DetrendOperations

# MNE imports
import mne
from mne.channels import make_standard_montage

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser()
    parser.add_argument('--timeout', type=int, default=10,
                        help='recording time in seconds')
    parser.add_argument('--mac', type=str, help='MAC address of the device',
                        default='')
    args = parser.parse_args()

    # Initialize BrainFlow parameters
    params = BrainFlowInputParams()
    params.mac_address = args.mac
    
    # Set log level to debug
    BoardShim.enable_dev_board_logger()
    BoardShim.set_log_level(LogLevels.LEVEL_DEBUG.value)
    
    # Try to connect with BRAINBIT_BLED_BOARD first (Bluetooth LE version),
    # if that fails, try the standard BRAINBIT_BOARD
    board_ids = [BoardIds.BRAINBIT_BLED_BOARD, BoardIds.BRAINBIT_BOARD]
    board = None
    connected_board_id = None
    
    for board_id in board_ids:
        try:
            print(f"Attempting to connect with board ID: {board_id}...")
            board = BoardShim(board_id, params)
            board.prepare_session()
            connected_board_id = board_id
            print(f"Successfully connected using board ID: {board_id}")
            break
        except brainflow.board_shim.BrainFlowError as e:
            print(f"Failed to connect with board ID {board_id}: {e}")
            if board is not None:
                try:
                    board.release_session()
                except:
                    pass
    
    if board is None:
        print("Could not connect to BrainBit Flex. Please ensure the device is turned on and paired.")
        return

    print(f"Connected to BrainBit Flex. Starting {args.timeout}-second recording...")
    board.start_stream()
    
    start_time = time.time()
    try:
        # Show real-time status during recording
        while time.time() - start_time < args.timeout:
            time_left = args.timeout - (time.time() - start_time)
            print(f"\rRecording in progress... {time_left:.1f} seconds left", end="")
            time.sleep(0.5)
        print("\nFinishing recording...")
    except KeyboardInterrupt:
        print("\nRecording interrupted by user")
    
    # Get all the data collected so far
    data = board.get_board_data()
    board.stop_stream()
    board.release_session()
    print("Recording finished")

    # Process and analyze the data
    analyze_data(data, connected_board_id)

def analyze_data(data, board_id):
    # Get device information
    try:
        device_name = BoardShim.get_device_name(board_id)
    except:
        device_name = "BrainBit Flex"
    
    # Get channel info
    eeg_channels = BoardShim.get_eeg_channels(board_id)
    sampling_rate = BoardShim.get_sampling_rate(board_id)
    
    # Print board information
    print(f"\nDevice Information:")
    print(f"  Device: {device_name}")
    print(f"  Board ID: {board_id}")
    print(f"  Sampling Rate: {sampling_rate} Hz")
    print(f"  EEG Channels: {len(eeg_channels)}")
    
    # Get BrainBit channel names
    ch_names = BoardShim.get_eeg_names(board_id)
    
    # Find the active channel by looking for the one with the most variance
    channel_variances = [np.var(data[ch]) for ch in eeg_channels]
    active_channel_idx = np.argmax(channel_variances)
    active_channel = eeg_channels[active_channel_idx]
    active_channel_name = ch_names[active_channel_idx]
    
    print(f"\nDetected active channel: {active_channel_name} (index: {active_channel_idx})")
    print(f"Channel variance: {channel_variances[active_channel_idx]:.2f}")
    
    # Apply minimal processing - just remove linear trend
    DataFilter.detrend(data[active_channel], DetrendOperations.LINEAR.value)

    # Calculate basic statistics for the active channel
    mean = np.mean(data[active_channel])
    std = np.std(data[active_channel])
    min_val = np.min(data[active_channel])
    max_val = np.max(data[active_channel])
    
    print(f"\nActive Channel ({active_channel_name}) statistics:")
    print(f"  Mean: {mean:.6f}µV")
    print(f"  Std Dev: {std:.6f}µV")
    print(f"  Min: {min_val:.6f}µV")
    print(f"  Max: {max_val:.6f}µV")
    
    # Convert to MNE format - use only the active channel
    eeg_data = np.array([data[active_channel]])
    
    # Create MNE info object for just the active channel
    info = mne.create_info(ch_names=[active_channel_name], sfreq=sampling_rate, ch_types=['eeg'])
    
    # Create MNE Raw object
    raw = mne.io.RawArray(eeg_data, info)
    
    # Plot the Raw EEG data
    print("\nPlotting raw EEG data...")
    raw.plot(scalings='auto', title=f'BrainBit Flex - {active_channel_name} Channel', show=False, block=True)
    
    # Calculate and plot power spectral density for frequency analysis
    plt.figure(figsize=(12, 8))
    plt.suptitle(f"BrainBit Flex - {active_channel_name} Channel Frequency Analysis", fontsize=16)
    
    # Define brain wave bands for analysis
    bands = {
        'Delta': (0.5, 4),
        'Theta': (4, 8),
        'Alpha': (8, 13),
        'Beta': (13, 30),
        'Gamma': (30, 50)
    }
    
    # Compute power spectral density
    spectrum = raw.compute_psd(fmax=50)
    freqs = spectrum.freqs
    psds = spectrum.get_data(return_freqs=False)[0]
    
    # Plot the spectrum
    plt.plot(freqs, 10 * np.log10(psds), 'b-', linewidth=2)
    plt.xlabel('Frequency (Hz)', fontsize=12)
    plt.ylabel('Power Spectral Density (dB)', fontsize=12)
    plt.grid(True, alpha=0.3)
    
    # Calculate and mark band powers
    band_powers = {}
    colors = ['r', 'g', 'purple', 'orange', 'c']
    
    plt.figure(figsize=(14, 10))
    plt.subplot(211)
    plt.title(f"BrainBit Flex - {active_channel_name} Frequency Spectrum", fontsize=14)
    plt.plot(freqs, 10 * np.log10(psds), 'b-', linewidth=2)
    
    # Add band annotations
    for (band_name, (fmin, fmax)), color in zip(bands.items(), colors):
        # Find frequencies in the band
        idx_band = np.logical_and(freqs >= fmin, freqs <= fmax)
        # Calculate average power in band
        band_power = np.mean(psds[idx_band]) if np.any(idx_band) else 0
        # Store for later use
        band_powers[band_name] = band_power
        
        # Highlight the band on the plot
        band_freqs = freqs[idx_band]
        band_psds = psds[idx_band]
        if len(band_freqs) > 0:  # Only if we have data points in this range
            plt.fill_between(band_freqs, 0, 10 * np.log10(band_psds), 
                           color=color, alpha=0.3)
        
            # Add label for the band
            y_pos = 10 * np.log10(np.max(band_psds)) + 1
            plt.text((fmin + fmax)/2, y_pos, band_name, ha='center', 
                   color=color, fontsize=12, fontweight='bold')
    
    plt.grid(True, alpha=0.3)
    plt.xlabel('Frequency (Hz)', fontsize=12)
    plt.ylabel('Power Spectral Density (dB)', fontsize=12)
    
    # Add a bar chart of the band powers
    plt.subplot(212)
    plt.title(f"BrainBit Flex - {active_channel_name} Band Powers", fontsize=14)
    
    # Prepare data for the bar chart
    band_names = list(bands.keys())
    powers_db = [10 * np.log10(band_powers[band]) for band in band_names]
    
    # Plot bar chart
    bars = plt.bar(band_names, powers_db, color=colors, alpha=0.7)
    
    # Add value labels on top of each bar
    for bar, power in zip(bars, powers_db):
        plt.text(bar.get_x() + bar.get_width()/2., power + 0.5,
               f'{power:.1f} dB', ha='center', fontsize=11)
    
    plt.grid(axis='y', linestyle='--', alpha=0.7)
    plt.ylabel('Band Power (dB)', fontsize=12)
    
    # Adjust layout
    plt.tight_layout()
    plt.subplots_adjust(top=0.9)
    
    # Save the raw data to a file with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"brainbit_flex_{active_channel_name}_{timestamp}_raw.fif"
    raw.save(output_file, overwrite=True)
    print(f"Raw data saved to {output_file}")
    
    # Save a summary of the analysis
    summary_file = f"brainbit_flex_{active_channel_name}_{timestamp}_summary.txt"
    with open(summary_file, 'w') as f:
        f.write(f"BrainBit Flex EEG Analysis Summary - {active_channel_name} Channel\n")
        f.write(f"Recorded on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Device: {device_name}\n")
        f.write(f"Board ID: {board_id}\n")
        f.write(f"Sampling Rate: {sampling_rate} Hz\n")
        f.write(f"Active Channel: {active_channel_name}\n\n")
        
        f.write("Brain Wave Band Powers:\n")
        for band, power in band_powers.items():
            f.write(f"  {band}: {power:.6f} uV² ({10 * np.log10(power):.2f} dB)\n")
        
        # Add interpretation
        f.write("\nInterpretation:\n")
        dominant_band = max(band_powers.items(), key=lambda x: x[1])[0]
        f.write(f"  Dominant frequency band: {dominant_band}\n")
        
        # Add some interpretation based on dominant band
        interpretations = {
            'Delta': "Delta waves (0.5-4 Hz) are most prominent during deep sleep. High delta while awake may indicate deep relaxation or possible attention issues.",
            'Theta': "Theta waves (4-8 Hz) are associated with drowsiness, meditation, creativity, and REM sleep. They can indicate relaxation and daydreaming.",
            'Alpha': "Alpha waves (8-13 Hz) appear during relaxed wakefulness, especially with eyes closed. They indicate a calm, relaxed, but alert state of mind.",
            'Beta': "Beta waves (13-30 Hz) are associated with normal waking consciousness and active thinking. They indicate active concentration and mental activity.",
            'Gamma': "Gamma waves (30+ Hz) are associated with higher cognitive functions, peak concentration, and possibly heightened awareness."
        }
        f.write(f"  {interpretations.get(dominant_band, 'No interpretation available.')}\n")
    
    print(f"Analysis summary saved to {summary_file}")
    
    # Show all plots
    plt.show()

if __name__ == "__main__":
    main()
