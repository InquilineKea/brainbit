#!/usr/bin/env python3
"""
Direct EEG Display

Creates a matplotlib window directly displaying EEG data without browser interface.
"""

import time
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import threading

# BrainFlow imports
import brainflow
from brainflow.board_shim import BoardShim, BrainFlowInputParams, BoardIds, LogLevels
from brainflow.data_filter import DataFilter, FilterTypes, DetrendOperations

# Global variables
board = None
eeg_channels = None
ch_names = None
sampling_rate = None
buffer_size = 1250  # 5 seconds at 250 Hz

# Buffers for EEG data
eeg_data = {}

# Lock for thread safety
data_lock = threading.Lock()

def connect_to_brainbit():
    """Connect to BrainBit device."""
    global board, eeg_channels, ch_names, sampling_rate
    
    params = BrainFlowInputParams()
    
    # Set log level
    BoardShim.enable_dev_board_logger()
    BoardShim.set_log_level(LogLevels.LEVEL_INFO.value)
    
    try:
        print("Attempting to connect to BrainBit...")
        board = BoardShim(BoardIds.BRAINBIT_BOARD, params)
        board.prepare_session()
        print("Successfully connected to BrainBit!")
    except brainflow.board_shim.BrainFlowError as e:
        print(f"Failed to connect to BrainBit: {e}")
        try:
            print("Attempting to connect to BrainBit BLED...")
            board = BoardShim(BoardIds.BRAINBIT_BLED_BOARD, params)
            board.prepare_session()
            print("Successfully connected to BrainBit BLED!")
        except brainflow.board_shim.BrainFlowError as e2:
            print(f"Failed to connect to BrainBit BLED: {e2}")
            return False
    
    # Get device info
    eeg_channels = BoardShim.get_eeg_channels(board.get_board_id())
    ch_names = BoardShim.get_eeg_names(board.get_board_id())
    sampling_rate = BoardShim.get_sampling_rate(board.get_board_id())
    
    print(f"EEG Channels: {ch_names}")
    print(f"Sampling Rate: {sampling_rate} Hz")
    
    # Initialize data buffers
    for ch in eeg_channels:
        eeg_data[ch] = np.zeros(buffer_size)
    
    # Start data stream
    board.start_stream()
    print("Data streaming started")
    return True

def update_eeg_data():
    """Update EEG data from the board."""
    while True:
        try:
            if board is None:
                time.sleep(0.1)
                continue
            
            # Get latest data
            new_data = board.get_current_board_data(sampling_rate // 10)
            
            if new_data.size == 0 or new_data.shape[1] == 0:
                time.sleep(0.1)
                continue
            
            with data_lock:
                for i, ch in enumerate(eeg_channels):
                    # Get channel data
                    if ch < new_data.shape[0]:
                        channel_data = new_data[ch]
                        if len(channel_data) == 0:
                            continue
                        
                        # Update buffer with new data
                        if len(channel_data) < buffer_size:
                            eeg_data[ch] = np.roll(eeg_data[ch], -len(channel_data))
                            eeg_data[ch][-len(channel_data):] = channel_data
                        else:
                            eeg_data[ch] = channel_data[-buffer_size:]
            
            time.sleep(0.05)
        
        except Exception as e:
            print(f"Error updating EEG data: {e}")
            time.sleep(1)

def update_plot(frame, lines, axes):
    """Update function for matplotlib animation."""
    with data_lock:
        for i, ch in enumerate(eeg_channels):
            if i < len(lines):
                # Get the data
                data = eeg_data[ch]
                
                # Normalize to make the signal clearly visible
                if np.max(np.abs(data)) > 0:
                    normalized_data = data / np.max(np.abs(data)) * 100
                    lines[i].set_ydata(normalized_data)
                    axes[i].set_title(f"{ch_names[i]} (Max: {np.max(np.abs(data)):.2f} μV)")
    
    return lines

def main():
    """Main function."""
    # Connect to BrainBit
    if not connect_to_brainbit():
        print("Failed to connect to BrainBit. Exiting.")
        return
    
    try:
        # Start data acquisition thread
        data_thread = threading.Thread(target=update_eeg_data)
        data_thread.daemon = True
        data_thread.start()
        
        # Create plot
        fig, axes = plt.subplots(len(eeg_channels), 1, figsize=(12, 8), sharex=True)
        if len(eeg_channels) == 1:
            axes = [axes]  # Convert to list for consistent indexing
        
        # Configure each subplot
        lines = []
        time_axis = np.linspace(-buffer_size/sampling_rate, 0, buffer_size)
        
        for i, ch in enumerate(eeg_channels):
            line, = axes[i].plot(time_axis, np.zeros(buffer_size))
            lines.append(line)
            
            axes[i].set_ylim(-120, 120)
            axes[i].set_ylabel('μV')
            axes[i].grid(True)
            
            if i == len(eeg_channels) - 1:
                axes[i].set_xlabel('Time (s)')
        
        # Set up the animation
        ani = FuncAnimation(
            fig, update_plot, fargs=(lines, axes),
            interval=100, blit=False
        )
        
        plt.tight_layout()
        plt.suptitle('BrainBit Direct EEG Display', fontsize=16)
        plt.show()
        
    except KeyboardInterrupt:
        print("Interrupted by user")
    finally:
        if board:
            board.stop_stream()
            board.release_session()
            print("BrainBit disconnected")

if __name__ == "__main__":
    main()
