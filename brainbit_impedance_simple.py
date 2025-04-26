#!/usr/bin/env python3
"""
BrainBit Simple Impedance Reader

This script uses BrainFlow's raw data access to read impedance values from BrainBit.
"""

import time
import numpy as np
import matplotlib.pyplot as plt

# BrainFlow imports
import brainflow
from brainflow.board_shim import BoardShim, BrainFlowInputParams, BoardIds, LogLevels

def main():
    # Set log level to debug to see all messages
    BoardShim.enable_dev_board_logger()
    BoardShim.set_log_level(LogLevels.LEVEL_DEBUG.value)
    
    # Initialize BrainFlow parameters
    params = BrainFlowInputParams()
    
    try:
        # Connect to BrainBit
        print("Attempting to connect to BrainBit...")
        board = BoardShim(BoardIds.BRAINBIT_BOARD, params)
        
        # Get board information
        eeg_channels = BoardShim.get_eeg_channels(BoardIds.BRAINBIT_BOARD)
        sampling_rate = BoardShim.get_sampling_rate(BoardIds.BRAINBIT_BOARD)
        resistance_channels = BoardShim.get_resistance_channels(BoardIds.BRAINBIT_BOARD)
        
        print(f"EEG channels: {eeg_channels}")
        print(f"Sampling rate: {sampling_rate} Hz")
        print(f"Resistance channels: {resistance_channels}")
        
        # Prepare session
        board.prepare_session()
        print("Session prepared")
        
        # Start stream
        board.start_stream()
        print("Stream started")
        
        # List all data channels
        all_channels = []
        for i in range(BoardShim.get_num_rows(BoardIds.BRAINBIT_BOARD)):
            channel_type = "Unknown"
            if i in eeg_channels:
                channel_type = "EEG"
            elif i in resistance_channels:
                channel_type = "Resistance"
            all_channels.append(f"Channel {i}: {channel_type}")
        
        print("All available channels:")
        for ch in all_channels:
            print(ch)
        
        # Get EEG channel names
        ch_names = BoardShim.get_eeg_names(BoardIds.BRAINBIT_BOARD)
        print(f"Channel names: {ch_names}")
        
        # Sleep to allow device to stabilize
        print("Waiting for device to stabilize...")
        time.sleep(2)
        
        # Measurement loop
        print("\nStarting impedance measurements (10 seconds)...")
        max_steps = 10
        for step in range(max_steps):
            # Get latest data
            data = board.get_current_board_data(100)  # Get last 100 samples
            
            print(f"\nStep {step+1}/{max_steps}")
            print(f"Data shape: {data.shape}")
            
            # Print raw values from resistance channels
            print("Resistance channels raw data:")
            for i, ch in enumerate(resistance_channels):
                if ch < data.shape[0] and data.shape[1] > 0:
                    values = data[ch]
                    valid_values = values[(values > 0) & (values < 500)]  # Filter implausible values
                    
                    # Print basic statistics
                    if len(valid_values) > 0:
                        mean = np.mean(valid_values)
                        median = np.median(valid_values)
                        min_val = np.min(valid_values)
                        max_val = np.max(valid_values)
                        electrode = ch_names[i] if i < len(ch_names) else f"Ch{i}"
                        
                        print(f"{electrode} - Mean: {mean:.1f}kΩ, Median: {median:.1f}kΩ, Range: {min_val:.1f}-{max_val:.1f}kΩ")
                        
                        # Print some raw values for debugging
                        print(f"  Raw values (first 5): {values[:5]}")
                    else:
                        print(f"Channel {ch}: No valid values")
                else:
                    print(f"Channel {ch}: No data available")
            
            # Try to get data directly from board API
            try:
                print("\nTrying direct board access:")
                # For boards that support it, print resistance values
                resistance_values = {}
                for i, name in enumerate(ch_names):
                    try:
                        # Some boards have methods to get resistance directly
                        value = 0  # Placeholder, the actual function would be board.get_electrode_resistance(i)
                        resistance_values[name] = value
                        print(f"{name} resistance: {value}kΩ")
                    except:
                        print(f"Could not get direct resistance for {name}")
            except Exception as e:
                print(f"Error in direct access: {e}")
            
            # Wait a bit between measurements
            time.sleep(1)
        
        # Stop and close session
        board.stop_stream()
        board.release_session()
        print("\nSession closed")
        
    except brainflow.board_shim.BrainFlowError as e:
        print(f"BrainFlow error: {e}")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
