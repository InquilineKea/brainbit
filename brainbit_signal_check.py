#!/usr/bin/env python3
"""
BrainBit Signal Check

Simple terminal-based monitor to verify if BrainBit is sending any data.
"""

import time
import numpy as np
from brainflow.board_shim import BoardShim, BrainFlowInputParams, BoardIds

def check_brainbit_signal():
    """Connect to BrainBit and check for signal in each channel."""
    params = BrainFlowInputParams()
    
    try:
        # Connect to BrainBit
        print("Connecting to BrainBit...")
        board = BoardShim(BoardIds.BRAINBIT_BOARD, params)
        board.prepare_session()
        
        # Get device info
        board_id = board.get_board_id()
        eeg_channels = BoardShim.get_eeg_channels(board_id)
        ch_names = BoardShim.get_eeg_names(board_id)
        
        print(f"Connected to BrainBit! (ID: {board_id})")
        print(f"EEG Channels: {ch_names}")
        
        # Start streaming
        board.start_stream()
        print("Streaming started. Collecting data for 20 seconds...")
        print("\nRAW SIGNAL VALUES (Press Ctrl+C to stop):")
        print("-" * 80)
        print(f"{'Time':8} | {'T3':>15} | {'T4':>15} | {'O1':>15} | {'O2':>15} |")
        print("-" * 80)
        
        # Monitor for 20 seconds
        start_time = time.time()
        while time.time() - start_time < 20:
            # Get latest data (250 samples = 1 second)
            data = board.get_current_board_data(250)
            
            if data.size > 0 and data.shape[1] > 0:
                # Calculate statistics for each channel
                stats = {}
                for i, ch in enumerate(eeg_channels):
                    if ch < data.shape[0]:
                        ch_data = data[ch]
                        if len(ch_data) > 0:
                            stats[ch_names[i]] = {
                                'mean': np.mean(ch_data),
                                'std': np.std(ch_data),
                                'min': np.min(ch_data),
                                'max': np.max(ch_data),
                                'last': ch_data[-1] if len(ch_data) > 0 else 0
                            }
                
                # Print current values
                if len(stats) == 4:  # Make sure we have all channels
                    elapsed = time.time() - start_time
                    print(f"{elapsed:8.2f} | {stats['T3']['last']:15.2f} | {stats['T4']['last']:15.2f} | {stats['O1']['last']:15.2f} | {stats['O2']['last']:15.2f} |")
            
            # Short delay
            time.sleep(1)
        
        # Print final statistics
        print("\nFINAL CHANNEL STATISTICS:")
        print("-" * 80)
        print(f"{'Channel':8} | {'Mean':>12} | {'StdDev':>12} | {'Min':>12} | {'Max':>12} |")
        print("-" * 80)
        
        data = board.get_current_board_data(5 * 250)  # Get last 5 seconds
        
        for i, ch in enumerate(eeg_channels):
            if ch < data.shape[0]:
                ch_data = data[ch]
                ch_name = ch_names[i]
                
                if len(ch_data) > 0:
                    mean = np.mean(ch_data)
                    std = np.std(ch_data)
                    min_val = np.min(ch_data)
                    max_val = np.max(ch_data)
                    
                    print(f"{ch_name:8} | {mean:12.2f} | {std:12.2f} | {min_val:12.2f} | {max_val:12.2f} |")
        
        # Check if signal is present
        signal_present = False
        electrode_status = {}
        
        for i, ch in enumerate(eeg_channels):
            if ch < data.shape[0]:
                ch_data = data[ch]
                ch_name = ch_names[i]
                
                if len(ch_data) > 0:
                    std = np.std(ch_data)
                    if std > 5:  # Arbitrary threshold for "active" signal
                        signal_present = True
                        electrode_status[ch_name] = "OK"
                    else:
                        electrode_status[ch_name] = "Weak/No Signal"
        
        print("\nELECTRODE STATUS:")
        print("-" * 50)
        for ch_name, status in electrode_status.items():
            print(f"{ch_name:8}: {status}")
        
        if signal_present:
            print("\n✅ BrainBit is sending data! At least one channel has signal.")
        else:
            print("\n❌ No clear EEG signal detected. Please check electrode contacts.")
            print("Tips:")
            print("1. Make sure device is charged")
            print("2. Clean electrode contacts")
            print("3. Ensure proper placement on head")
            print("4. Wet electrodes with saline solution if available")
        
        # Stop streaming
        board.stop_stream()
        board.release_session()
        
    except KeyboardInterrupt:
        print("\nMonitoring stopped by user.")
        if 'board' in locals():
            board.stop_stream()
            board.release_session()
    except Exception as e:
        print(f"\nError: {e}")

if __name__ == "__main__":
    check_brainbit_signal()
