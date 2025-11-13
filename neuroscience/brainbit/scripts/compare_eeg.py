#!/usr/bin/env python3
"""
BrainBit EEG Comparison

This script connects to a BrainBit device, acquires new data,
and compares it with previously recorded data.
"""

import time
import numpy as np
import matplotlib.pyplot as plt
import os
import glob

# BrainFlow imports
import brainflow
from brainflow.board_shim import BoardShim, BrainFlowInputParams, BoardIds
from brainflow.data_filter import DataFilter, DetrendOperations

# MNE imports
import mne
from mne.channels import make_standard_montage
from mne.viz import plot_compare_evokeds

def get_latest_recording():
    """Find the most recent BrainBit recording file"""
    files = glob.glob('brainbit_recording_*.fif')
    if not files:
        return None
    return max(files, key=os.path.getctime)

def record_new_data(timeout=10):
    """Record new data from BrainBit"""
    # Initialize BrainFlow parameters
    params = BrainFlowInputParams()
    
    # Set log level to debug
    BoardShim.enable_dev_board_logger()
    
    # Initialize BrainBit board
    board_id = BoardIds.BRAINBIT_BOARD
    try:
        board = BoardShim(board_id, params)
        print("Connecting to BrainBit...")
        board.prepare_session()
    except brainflow.board_shim.BrainFlowError as e:
        print(f"Error connecting to BrainBit: {e}")
        print("Please ensure your BrainBit device is turned on and paired.")
        return None

    print(f"Connected to BrainBit. Starting {timeout}-second recording...")
    board.start_stream()
    time.sleep(timeout)
    data = board.get_board_data()
    board.stop_stream()
    board.release_session()
    print("Recording finished")

    # Process the data
    eeg_channels = BoardShim.get_eeg_channels(board_id)
    sampling_rate = BoardShim.get_sampling_rate(board_id)
    
    # Print board information
    print(f"\nBoard Information:")
    print(f"  Sampling Rate: {sampling_rate} Hz")
    print(f"  EEG Channels: {len(eeg_channels)}")
    
    # Apply minimal processing - just remove linear trend
    for channel in eeg_channels:
        DataFilter.detrend(data[channel], DetrendOperations.LINEAR.value)

    # Convert to MNE format
    eeg_data = data[eeg_channels, :]
    
    # Get BrainBit channel names
    ch_names = BoardShim.get_eeg_names(board_id)
    ch_types = ['eeg'] * len(eeg_channels)
    
    print(f"Channel names: {ch_names}")
    
    # Create MNE info object
    info = mne.create_info(ch_names=ch_names, sfreq=sampling_rate, ch_types=ch_types)
    
    # Create MNE Raw object
    raw = mne.io.RawArray(eeg_data, info)
    
    # Try to get standard EEG locations
    try:
        montage = make_standard_montage('standard_1020')
        raw.set_montage(montage, match_case=False, match_alias=True)
    except Exception as e:
        print(f"Could not set montage: {e}")
    
    # Save the raw data to a file
    timestamp = int(time.time())
    output_file = f"brainbit_recording_{timestamp}.fif"
    raw.save(output_file, overwrite=True)
    print(f"New data saved to {output_file}")
    
    return raw, output_file

def compare_recordings(previous_file, new_raw=None):
    """Compare a newly recorded EEG with a previously recorded one"""
    print(f"Loading previous recording: {previous_file}")
    previous_raw = mne.io.read_raw_fif(previous_file, preload=True)
    
    if new_raw is None:
        # Record new data
        new_raw, new_file = record_new_data()
    else:
        new_file = "Current recording (not saved)"
    
    if new_raw is None:
        print("Failed to record new data.")
        return
        
    # Create figure for comparison
    plt.figure(figsize=(15, 10))
    plt.suptitle("EEG Recording Comparison", fontsize=16)
    
    # Plot new and previous data on same axes (each channel)
    channels = previous_raw.ch_names
    for i, ch in enumerate(channels):
        plt.subplot(len(channels), 1, i+1)
        
        # Get data for the channel
        previous_data, _ = previous_raw[ch]
        new_data, _ = new_raw[ch]
        
        # Make sure they're the same length for plotting
        min_len = min(previous_data.shape[1], new_data.shape[1])
        previous_data = previous_data[:, :min_len]
        new_data = new_data[:, :min_len]
        
        # Create time axis (in seconds)
        time_axis = np.arange(min_len) / previous_raw.info['sfreq']
        
        # Plot both signals
        plt.plot(time_axis, previous_data.T, 'b-', alpha=0.7, label=f'Previous ({os.path.basename(previous_file)})')
        plt.plot(time_axis, new_data.T, 'r-', alpha=0.7, label=f'New ({os.path.basename(new_file)})')
        
        # Add labels
        plt.ylabel(f'{ch} (μV)')
        if i == 0:
            plt.legend()
        if i == len(channels) - 1:
            plt.xlabel('Time (s)')
    
    plt.tight_layout()
    
    # Compare power spectral densities
    fig, axes = plt.subplots(len(channels), 1, figsize=(12, 10))
    plt.suptitle("Power Spectral Density Comparison", fontsize=16)
    
    # Make axes iterable if there's only one channel
    if len(channels) == 1:
        axes = [axes]
    
    for i, ch in enumerate(channels):
        # Calculate PSD using MNE's current API
        previous_spectrum = previous_raw.compute_psd(picks=ch, fmax=50)
        new_spectrum = new_raw.compute_psd(picks=ch, fmax=50)
        
        # Get the data from the spectrum objects
        freqs_prev = previous_spectrum.freqs
        psd_prev = previous_spectrum.get_data(return_freqs=False)[0]
        
        freqs_new = new_spectrum.freqs
        psd_new = new_spectrum.get_data(return_freqs=False)[0]
        
        # Plot PSDs
        axes[i].plot(freqs_prev, 10 * np.log10(psd_prev), 'b-', label='Previous')
        axes[i].plot(freqs_new, 10 * np.log10(psd_new), 'r-', label='New')
        
        axes[i].set_title(f'Channel: {ch}')
        axes[i].set_xlabel('Frequency (Hz)')
        axes[i].set_ylabel('Power Spectral Density (dB)')
        
        # Add legend for first subplot
        if i == 0:
            axes[i].legend()
    
    plt.tight_layout()
    
    # Calculate and display correlation between recordings
    print("\nCorrelation between recordings:")
    for ch in channels:
        previous_data, _ = previous_raw[ch]
        new_data, _ = new_raw[ch]
        
        # Make sure they're the same length
        min_len = min(previous_data.shape[1], new_data.shape[1])
        previous_data = previous_data[0, :min_len]
        new_data = new_data[0, :min_len]
        
        # Calculate correlation
        correlation = np.corrcoef(previous_data, new_data)[0, 1]
        print(f"  {ch}: {correlation:.4f}")
    
    # Show all plots
    plt.show()

def main():
    previous_file = get_latest_recording()
    if previous_file:
        print(f"Found previous recording: {previous_file}")
        compare_recordings(previous_file)
    else:
        print("No previous recordings found. Please run brainbit_reader.py first.")

if __name__ == "__main__":
    main()
