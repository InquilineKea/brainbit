#!/usr/bin/env python3
"""
BrainBit Simple View

Basic EEG visualization showing all channels with minimal processing.
Features smaller fonts and focuses on showing raw signal clearly.
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
from brainflow.data_filter import DataFilter, DetrendOperations

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
                    # Update data for each channel (minimal processing)
                    for idx, ch_idx in enumerate(eeg_channels):
                        ch_name = channel_names[idx]
                        
                        # Apply simple detrending only
                        ch_data = data[ch_idx].copy()
                        DataFilter.detrend(ch_data, DetrendOperations.LINEAR.value)
                        
                        eeg_data[ch_name] = ch_data
                
                # Sleep to prevent CPU overuse
                time.sleep(0.05)
                
            except Exception as e:
                logger.error(f"Error updating data: {e}")
                time.sleep(0.1)

def init_plot():
    """Initialize the plot."""
    for i, line in enumerate(lines):
        line.set_data([], [])
    return lines

def update_plot(frame):
    """Update the plot with new data."""
    with data_lock:
        x_data = np.linspace(-5, 0, buffer_size)
        
        for i, ch_name in enumerate(channel_names):
            ch_data = eeg_data[ch_name]
            
            # Update the plot
            lines[i].set_data(x_data, ch_data)
            
            # Adjust y limits for better visualization
            if np.any(ch_data != 0):
                data_range = np.max(np.abs(ch_data))
                axes[i].set_ylim(-data_range * 1.2, data_range * 1.2)
    
    return lines

def main():
    """Main function."""
    try:
        # Connect to BrainBit
        logger.info("Connecting to BrainBit...")
        handler = BrainBitHandler()
        if not handler.connect():
            logger.error("Failed to connect to BrainBit")
            return
        
        # Setup global figure and animation
        global fig, axes, lines
        
        # Create figure
        fig, axes = plt.subplots(4, 1, figsize=(10, 8), sharex=True)
        plt.subplots_adjust(hspace=0.3)
        
        # Set smaller fonts for all text elements
        plt.rcParams.update({'font.size': 8})
        
        # Create lines for each channel
        lines = []
        for i, ch_name in enumerate(channel_names):
            line, = axes[i].plot([], [], lw=1.5)
            lines.append(line)
            
            # Set up axes
            axes[i].set_title(f"Channel {ch_name}", fontsize=9)
            axes[i].set_ylabel('μV', fontsize=8)
            axes[i].grid(True, alpha=0.3)
            
            # Make tick labels smaller
            axes[i].tick_params(labelsize=7)
        
        # Set x-axis label for bottom plot
        axes[-1].set_xlabel('Time (s)', fontsize=8)
        
        # Set figure title
        fig.suptitle('BrainBit EEG Signals', fontsize=10)
        
        # Create animation
        ani = FuncAnimation(
            fig, update_plot, init_func=init_plot,
            interval=100, blit=True, save_count=50
        )
        
        # Key event handler
        def on_key(event):
            if event.key == 'escape' or event.key == 'q':
                plt.close(fig)
        
        fig.canvas.mpl_connect('key_press_event', on_key)
        
        # Show the plot
        plt.tight_layout(rect=[0, 0, 1, 0.95])
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
