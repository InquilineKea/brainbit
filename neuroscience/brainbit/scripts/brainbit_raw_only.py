#!/usr/bin/env python3
"""
BrainBit Raw Waveform Display

Displays raw EEG waveforms with minimal processing and fixed scales
to ensure signals are always visible.
"""

import time
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import threading
import logging

# BrainFlow imports
import brainflow
from brainflow.board_shim import BoardShim, BrainFlowInputParams, LogLevels, BoardIds

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global variables
buffer_size = 1250  # 5 seconds at 250 Hz
eeg_data = {
    "T3": np.zeros(buffer_size),
    "T4": np.zeros(buffer_size),
    "O1": np.zeros(buffer_size),
    "O2": np.zeros(buffer_size)
}
data_lock = threading.Lock()
should_run = True

# Channel names for BrainBit
channel_names = ["T3", "T4", "O1", "O2"]
eeg_channels = [1, 2, 3, 4]  # BrainFlow channel indices

class BrainBitHandler:
    """Simple handler for BrainBit device."""
    
    def __init__(self):
        """Initialize the BrainBit handler."""
        self.board = None
        self.board_id = BoardIds.BRAINBIT_BOARD
        self.sample_rate = BoardShim.get_sampling_rate(self.board_id)
        self.buffer_size = buffer_size
        self.data_thread = None
        
    def connect(self):
        """Connect to the BrainBit device."""
        try:
            # Set log level
            BoardShim.enable_dev_board_logger()
            BoardShim.set_log_level(LogLevels.LEVEL_INFO)
            
            # Initialize parameters
            params = BrainFlowInputParams()
            
            # Create board shim instance
            self.board = BoardShim(self.board_id, params)
            
            # Connect to the board
            self.board.prepare_session()
            self.board.start_stream(45000)
            
            logger.info("Connected to BrainBit device")
            
            # Start data acquisition thread
            global should_run
            should_run = True
            self.data_thread = threading.Thread(target=self.update_data)
            self.data_thread.daemon = True
            self.data_thread.start()
            
            return True
            
        except Exception as e:
            logger.error(f"Error connecting to BrainBit: {e}")
            if self.board:
                try:
                    self.board.release_session()
                except:
                    pass
            return False
    
    def disconnect(self):
        """Disconnect from the BrainBit device."""
        try:
            global should_run
            should_run = False
            
            if self.data_thread:
                self.data_thread.join(timeout=1.0)
            
            if self.board:
                self.board.stop_stream()
                self.board.release_session()
                logger.info("Disconnected from BrainBit")
        except Exception as e:
            logger.error(f"Error disconnecting from BrainBit: {e}")
    
    def update_data(self):
        """Update EEG data continuously."""
        global eeg_data, should_run
        
        while should_run:
            try:
                # Check if board is connected
                if not self.board:
                    time.sleep(0.1)
                    continue
                
                # Get data from the board
                data = self.board.get_current_board_data(self.buffer_size)
                
                if data.size == 0 or data.shape[1] < self.buffer_size:
                    time.sleep(0.05)
                    continue
                
                with data_lock:
                    # Update data for each channel (completely raw - no processing)
                    for idx, ch_idx in enumerate(eeg_channels):
                        ch_name = channel_names[idx]
                        eeg_data[ch_name] = data[ch_idx]
                
                # Print raw values to confirm data is coming in
                if np.random.rand() < 0.05:  # Print occasionally (5% chance)
                    print(f"Raw values: T3: {data[1, -1]:.1f}, T4: {data[2, -1]:.1f}, "
                          f"O1: {data[3, -1]:.1f}, O2: {data[4, -1]:.1f}")
                
                # Sleep to prevent CPU overuse
                time.sleep(0.05)
                
            except Exception as e:
                logger.error(f"Error updating data: {e}")
                time.sleep(0.1)

def main():
    """Main function."""
    try:
        # Connect to BrainBit
        logger.info("Connecting to BrainBit...")
        handler = BrainBitHandler()
        if not handler.connect():
            logger.error("Failed to connect to BrainBit")
            return
        
        # Create figure
        fig, axes = plt.subplots(4, 1, figsize=(12, 8), sharex=True)
        plt.subplots_adjust(hspace=0.5)
        
        # Set figure title
        fig.suptitle('BrainBit RAW EEG', fontsize=16, fontweight='bold')
        
        # Create lines for each channel
        lines = []
        for i, ch_name in enumerate(channel_names):
            line, = axes[i].plot([], [], lw=1.5, color='blue')
            lines.append(line)
            
            # Set up axes
            axes[i].set_title(f"Channel {ch_name}", fontsize=14)
            axes[i].set_ylabel('μV', fontsize=12)
            axes[i].grid(True)
            
            # Use FIXED y-limits to ensure signals are always visible
            # BrainBit signals typically range from -50000 to 50000 μV when unfiltered
            axes[i].set_ylim(-10000, 10000)
        
        # Set x-axis label for bottom plot
        axes[-1].set_xlabel('Time (s)', fontsize=12)
        
        # Add status text
        status_text = fig.text(0.5, 0.02, "Collecting data...", 
                             ha='center', fontsize=12,
                             bbox=dict(facecolor='white', alpha=0.8))
        
        # Initialize the plot
        def init():
            for line in lines:
                line.set_data([], [])
            return lines
        
        # Update function for animation
        def update(frame):
            x_data = np.linspace(-5, 0, buffer_size)
            
            with data_lock:
                for i, ch_name in enumerate(channel_names):
                    # Update line data
                    lines[i].set_data(x_data, eeg_data[ch_name])
                    
                    # Show current value on plot
                    if len(eeg_data[ch_name]) > 0:
                        current_val = eeg_data[ch_name][-1]
                        axes[i].set_title(f"Channel {ch_name}: {current_val:.1f} μV", fontsize=12)
                
                # Update status text
                status_text.set_text(f"BrainBit RAW EEG - Fixed Scale ±10,000 μV")
            
            return lines
        
        # Create animation
        ani = FuncAnimation(
            fig, update, init_func=init,
            interval=100, blit=True
        )
        
        # Show the plot
        plt.show()
        
        # Clean up
        handler.disconnect()
        
    except KeyboardInterrupt:
        print("Interrupted by user")
    except Exception as e:
        logger.error(f"Error: {e}")
    finally:
        global should_run
        should_run = False

if __name__ == "__main__":
    main()
