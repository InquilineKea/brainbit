#!/usr/bin/env python3
"""
BrainBit Very Basic Display

Absolutely minimal processing - just shows the raw signals as they come from the device.
"""

import time
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from brainflow.board_shim import BoardShim, BrainFlowInputParams, LogLevels, BoardIds

# Global variables
buffer_seconds = 5
board = None
fig = None
axes = None
lines = None

def main():
    """Main function to connect to BrainBit and display data."""
    global board, fig, axes, lines
    
    # Connect to BrainBit
    print("Connecting to BrainBit...")
    
    # Set log level
    BoardShim.enable_dev_board_logger()
    BoardShim.set_log_level(LogLevels.LEVEL_INFO)
    
    # Initialize parameters
    params = BrainFlowInputParams()
    board_id = BoardIds.BRAINBIT_BOARD
    
    # Create board shim instance
    board = BoardShim(board_id, params)
    
    # Connect to the board
    board.prepare_session()
    board.start_stream()
    
    print("Connected to BrainBit")
    
    # Get sampling rate and calculate buffer size
    sample_rate = BoardShim.get_sampling_rate(board_id)
    buffer_size = int(buffer_seconds * sample_rate)
    print(f"Sampling rate: {sample_rate} Hz")
    print(f"Buffer size: {buffer_size} samples")
    
    # Create figure
    fig, axes = plt.subplots(4, 1, figsize=(12, 8), sharex=True)
    plt.subplots_adjust(hspace=0.4)
    
    # Channel names and indices for BrainBit
    channel_names = ["T3", "T4", "O1", "O2"]
    eeg_channels = [1, 2, 3, 4]  # BrainFlow channel indices
    
    # Create lines for each channel
    lines = []
    for i, ch_name in enumerate(channel_names):
        line, = axes[i].plot([], [], lw=1.5, color='blue')
        lines.append(line)
        
        # Set up axes
        axes[i].set_title(f"Channel {ch_name}", fontsize=12)
        axes[i].set_ylabel('μV', fontsize=10)
        axes[i].grid(True)
        
        # Medium fixed scale at first - will be auto-adjusted
        axes[i].set_ylim(-50000, 50000)
    
    # Set x-axis label for bottom plot
    axes[-1].set_xlabel('Time (s)', fontsize=10)
    
    # Set figure title
    fig.suptitle('BrainBit Raw Signals', fontsize=14)
    
    # Initialize the plot
    def init():
        for line in lines:
            line.set_data([], [])
        return lines
    
    # Update function for animation
    def update(frame):
        # Get the latest data
        data = board.get_current_board_data(buffer_size)
        
        if data.size > 0 and data.shape[1] > 0:
            x_data = np.linspace(-buffer_seconds, 0, data.shape[1])
            
            for i, ch_idx in enumerate(eeg_channels):
                if ch_idx < data.shape[0]:
                    # Update line data
                    lines[i].set_data(x_data, data[ch_idx])
                    
                    # Auto-adjust y-limits if data exists and has variation
                    if data[ch_idx].size > 0 and np.max(data[ch_idx]) != np.min(data[ch_idx]):
                        max_val = np.max(np.abs(data[ch_idx]))
                        axes[i].set_ylim(-max_val*1.2, max_val*1.2)
        
        return lines
    
    # Create animation
    ani = FuncAnimation(
        fig, update, init_func=init,
        interval=100, blit=True, cache_frame_data=False
    )
    
    # Show the plot
    plt.show()
    
    # Clean up when the plot is closed
    board.stop_stream()
    board.release_session()
    print("Disconnected from BrainBit")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Interrupted by user")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        # Make sure to disconnect
        if 'board' in globals() and board is not None:
            try:
                board.stop_stream()
                board.release_session()
                print("Disconnected from BrainBit")
            except:
                pass
