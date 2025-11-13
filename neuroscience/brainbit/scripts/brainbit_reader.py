#!/usr/bin/env python3
"""
BrainBit EEG Reader

This script connects to a BrainBit device using BrainFlow, acquires data,
and visualizes it using MNE-Python.
"""

import time
import numpy as np
import argparse
import matplotlib.pyplot as plt

# BrainFlow imports
import brainflow
from brainflow.board_shim import BoardShim, BrainFlowInputParams, BoardIds
from brainflow.data_filter import DataFilter, DetrendOperations

# MNE imports
import mne
from mne.channels import make_standard_montage

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser()
    parser.add_argument('--timeout', type=int, default=10,
                        help='recording time in seconds')
    parser.add_argument('--serial-port', type=str, help='serial port',
                        default='')
    args = parser.parse_args()

    # Initialize BrainFlow parameters
    params = BrainFlowInputParams()
    params.serial_port = args.serial_port
    
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
        return

    print(f"Connected to BrainBit. Starting {args.timeout}-second recording...")
    board.start_stream()
    time.sleep(args.timeout)
    data = board.get_board_data()
    board.stop_stream()
    board.release_session()
    print("Recording finished")

    # Process the data
    analyze_data(data, board_id, args.timeout)

def analyze_data(data, board_id, timeout):
    # Get channel info
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
    
    # Plot the Raw EEG data
    print("\nPlotting raw EEG data...")
    raw.plot(scalings='auto', title='BrainBit EEG Data', show=False, block=True)
    
    # Plot power spectral density
    print("Plotting power spectral density...")
    raw.plot_psd(fmax=50, average=True)
    
    # Show all plots
    plt.show()
    
    # Save the raw data to a file
    output_file = f"brainbit_recording_{int(time.time())}.fif"
    raw.save(output_file, overwrite=True)
    print(f"Data saved to {output_file}")

if __name__ == "__main__":
    main()
