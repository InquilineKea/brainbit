#!/usr/bin/env python3
"""
BrainBit Band Power Analyzer (Fixed Version)

Displays the relative power of alpha, beta, delta, and theta bands
across all 4 channels (T3, T4, O1, O2) in real-time.
"""

import time
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import threading
import logging
from datetime import datetime

# BrainFlow imports
import brainflow
from brainflow.board_shim import BoardShim, BrainFlowInputParams, LogLevels, BoardIds
from brainflow.data_filter import DataFilter, FilterTypes, DetrendOperations

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global variables
buffer_size = 1250  # 5 seconds at 250 Hz
window_size = 500   # 2 seconds for FFT analysis

# Initialize band powers dictionary
band_powers = {
    "T3": {"delta": 0.2, "theta": 0.2, "alpha": 0.2, "beta": 0.2, "gamma": 0.2},
    "T4": {"delta": 0.2, "theta": 0.2, "alpha": 0.2, "beta": 0.2, "gamma": 0.2},
    "O1": {"delta": 0.2, "theta": 0.2, "alpha": 0.2, "beta": 0.2, "gamma": 0.2},
    "O2": {"delta": 0.2, "theta": 0.2, "alpha": 0.2, "beta": 0.2, "gamma": 0.2}
}

data_lock = threading.Lock()
should_run = True

# Channel names and indices
channel_names = ["T3", "T4", "O1", "O2"]
eeg_channels = [1, 2, 3, 4]  # BrainFlow channel indices

# Frequency bands
bands = {
    "delta": (1, 4),
    "theta": (4, 8),
    "alpha": (8, 13),
    "beta": (13, 30),
    "gamma": (30, 45)
}

# Colors for bands
band_colors = {
    "delta": "royalblue",
    "theta": "forestgreen",
    "alpha": "crimson",
    "beta": "darkorange",
    "gamma": "darkviolet"
}

class BrainBitHandler:
    """Handler for BrainBit device band power analysis."""
    
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
    
    def compute_band_powers(self, data, sample_rate):
        """Compute relative power for each frequency band."""
        try:
            # Apply preprocessing
            processed_data = data.copy()
            
            # Detrend
            DataFilter.detrend(processed_data, DetrendOperations.LINEAR.value)
            
            # Remove environmental noise (60Hz)
            DataFilter.remove_environmental_noise(processed_data, sample_rate, FilterTypes.BUTTERWORTH.value)
            
            # Calculate band powers
            powers = {}
            for band_name, (low_freq, high_freq) in bands.items():
                band_power = DataFilter.get_band_power(processed_data, sample_rate, low_freq, high_freq)
                powers[band_name] = max(band_power, 0)  # Ensure non-negative
            
            # Calculate total power for normalization
            total_power = sum(powers.values())
            
            # Normalize to get relative powers
            if total_power > 0:
                for band in powers:
                    powers[band] = powers[band] / total_power
                return powers
            else:
                # Return default distribution if total power is zero
                return {"delta": 0.2, "theta": 0.2, "alpha": 0.2, "beta": 0.2, "gamma": 0.2}
        
        except Exception as e:
            logger.error(f"Error in band power computation: {e}")
            return {"delta": 0.2, "theta": 0.2, "alpha": 0.2, "beta": 0.2, "gamma": 0.2}
    
    def update_data(self):
        """Update band powers continuously."""
        global band_powers, should_run
        
        while should_run:
            try:
                # Check if board is connected
                if not self.board:
                    time.sleep(0.1)
                    continue
                
                # Get data from the board
                data = self.board.get_current_board_data(self.buffer_size)
                
                if data.size == 0 or data.shape[1] < window_size:
                    time.sleep(0.05)
                    continue
                
                # Update band powers for each channel
                for idx, ch_idx in enumerate(eeg_channels):
                    ch_name = channel_names[idx]
                    
                    # Get most recent window of data for analysis
                    recent_data = data[ch_idx, -window_size:]
                    
                    # Skip channels with no signal (flat lines)
                    if np.std(recent_data) < 1e-6:
                        continue
                    
                    # Compute band powers
                    channel_powers = self.compute_band_powers(recent_data, self.sample_rate)
                    
                    # Update global dictionary with data lock
                    with data_lock:
                        band_powers[ch_name] = channel_powers
                
                # Sleep to prevent CPU overuse (shorter to be more responsive)
                time.sleep(0.1)
                
            except Exception as e:
                logger.error(f"Error updating data: {e}")
                time.sleep(0.1)

def create_band_power_visualization():
    """Create visualization for relative band powers."""
    # Connect to BrainBit
    logger.info("Connecting to BrainBit...")
    handler = BrainBitHandler()
    if not handler.connect():
        logger.error("Failed to connect to BrainBit")
        return
    
    # Create figure and axes
    fig, axes = plt.subplots(2, 2, figsize=(10, 8))
    ax_bars = axes.flatten()
    plt.subplots_adjust(hspace=0.4, wspace=0.3)
    
    # Set smaller fonts
    plt.rcParams.update({'font.size': 8})
    
    # Prepare band names and positions
    band_names = ["delta", "theta", "alpha", "beta", "gamma"]
    x = np.arange(len(band_names))
    width = 0.7
    
    # Create bars and text for each channel
    bar_containers = []
    texts = []
    
    for i, ch_name in enumerate(channel_names):
        # Create bars with initial values
        bars = ax_bars[i].bar(
            x, 
            [0.2, 0.2, 0.2, 0.2, 0.2],  # Initial equal distribution
            width,
            color=[band_colors[name] for name in band_names]
        )
        
        bar_containers.append(bars)
        
        # Set up axis
        ax_bars[i].set_title(f"Channel {ch_name}", fontsize=9)
        ax_bars[i].set_ylim(0, 1)
        ax_bars[i].set_ylabel("Relative Power", fontsize=8)
        ax_bars[i].set_xticks(x)
        ax_bars[i].set_xticklabels(["Delta", "Theta", "Alpha", "Beta", "Gamma"], fontsize=7)
        ax_bars[i].tick_params(axis='both', which='major', labelsize=7)
        
        # Add text for values
        text = ax_bars[i].text(
            0.5, 0.92, f"{ch_name}: initializing...",
            horizontalalignment='center',
            transform=ax_bars[i].transAxes,
            fontsize=7,
            bbox=dict(facecolor='white', alpha=0.7)
        )
        
        texts.append(text)
    
    # Add status text
    status_text = fig.text(
        0.5, 0.01, "Connected",
        ha="center", fontsize=8,
        bbox=dict(facecolor='white', alpha=0.7)
    )
    
    # Set figure title
    fig.suptitle('BrainBit EEG Band Power Analysis', fontsize=10)
    
    # Add info text
    info_text = fig.text(
        0.5, 0.05,
        "Band ranges: Delta (1-4 Hz), Theta (4-8 Hz), Alpha (8-13 Hz), Beta (13-30 Hz), Gamma (30-45 Hz)\n"
        "Close your eyes to see increased alpha power, especially in O1/O2 channels",
        ha='center', fontsize=7
    )
    
    # Update function for animation
    def update(frame):
        with data_lock:
            # Update each channel's bars and text
            for i, ch_name in enumerate(channel_names):
                powers = band_powers[ch_name]
                
                # Update bar heights
                for j, band in enumerate(band_names):
                    bar_containers[i][j].set_height(powers[band])
                
                # Update text with values
                texts[i].set_text(
                    f"{ch_name}: δ={powers['delta']:.2f}, θ={powers['theta']:.2f}, "
                    f"α={powers['alpha']:.2f}, β={powers['beta']:.2f}"
                )
        
        # Update status with time
        status_text.set_text(f"Connected | {datetime.now().strftime('%H:%M:%S')}")
        
        # Return all artists that need to be redrawn
        return sum([list(bars) for bars in bar_containers], []) + texts + [status_text]
    
    # Create animation
    ani = FuncAnimation(
        fig, update,
        interval=200, blit=True
    )
    
    # Key event handler for exit
    def on_key(event):
        if event.key == 'escape' or event.key == 'q':
            plt.close(fig)
    
    fig.canvas.mpl_connect('key_press_event', on_key)
    
    # Show the plot
    plt.tight_layout(rect=[0, 0.08, 1, 0.95])
    plt.show()
    
    # Clean up
    handler.disconnect()

def main():
    """Main function."""
    try:
        create_band_power_visualization()
    except KeyboardInterrupt:
        print("Interrupted by user")
    except Exception as e:
        logger.error(f"Error: {e}")
    finally:
        global should_run
        should_run = False

if __name__ == "__main__":
    main()
