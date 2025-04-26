#!/usr/bin/env python3
"""
BrainBit Alpha Rhythm Detector

Specialized script for detecting and visualizing alpha rhythm (8-13 Hz),
with specific focus on occipital channels (O1, O2) where alpha is most prominent.
Uses advanced signal processing techniques to enhance alpha wave detection.
"""

import time
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from scipy import signal
import threading
import logging
from datetime import datetime

# BrainFlow imports
import brainflow
from brainflow.board_shim import BoardShim, BrainFlowInputParams, LogLevels, BoardIds
from brainflow.data_filter import DataFilter, FilterTypes, AggOperations, DetrendOperations

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global variables for data visualization
buffer_size = 1250  # 5 seconds at 250 Hz
sampling_rate = 250  # Hz for BrainBit
window_size = int(2 * sampling_rate)  # 2-second window for alpha analysis

# Data buffers
eeg_filtered = {
    "T3": np.zeros(buffer_size),
    "T4": np.zeros(buffer_size),
    "O1": np.zeros(buffer_size),
    "O2": np.zeros(buffer_size)
}
alpha_filtered = {
    "T3": np.zeros(buffer_size),
    "T4": np.zeros(buffer_size),
    "O1": np.zeros(buffer_size),
    "O2": np.zeros(buffer_size)
}
band_powers = {
    "T3": {"delta": 0, "theta": 0, "alpha": 0, "beta": 0, "gamma": 0},
    "T4": {"delta": 0, "theta": 0, "alpha": 0, "beta": 0, "gamma": 0},
    "O1": {"delta": 0, "theta": 0, "alpha": 0, "beta": 0, "gamma": 0},
    "O2": {"delta": 0, "theta": 0, "alpha": 0, "beta": 0, "gamma": 0}
}
alpha_scores = {
    "T3": 0.0,
    "T4": 0.0,
    "O1": 0.0,
    "O2": 0.0
}
data_lock = threading.Lock()
should_run = True

# Channel names for BrainBit Flex using BrainFlow numbering
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

class BrainBitHandler:
    """Handles communication with BrainBit device using BrainFlow."""
    
    def __init__(self):
        """Initialize the BrainBit handler."""
        self.board = None
        self.board_id = BoardIds.BRAINBIT_BOARD
        self.sample_rate = BoardShim.get_sampling_rate(self.board_id)
        self.buffer_seconds = 5
        self.buffer_size = int(self.sample_rate * self.buffer_seconds)
        self.data_thread = None
        
        # Filter parameters
        self.notch_freq = 60.0
        
        # Time window for spectral analysis
        self.analysis_window = int(2 * self.sample_rate)  # 2 seconds
        
    def connect(self):
        """Connect to the BrainBit device."""
        try:
            # Set log level to INFO
            BoardShim.enable_dev_board_logger()
            BoardShim.set_log_level(LogLevels.LEVEL_INFO)
            
            # Initialize board parameters
            params = BrainFlowInputParams()
            
            # Create board shim instance
            self.board = BoardShim(self.board_id, params)
            
            # Connect to the board
            self.board.prepare_session()
            self.board.start_stream(45000)  # Use a large buffer
            
            logger.info("Connected to BrainBit device")
            logger.info(f"Sampling rate: {self.sample_rate} Hz")
            
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
    
    def apply_filters(self, data, lowcut=1.0, highcut=45.0):
        """Apply various filters to clean the EEG signal."""
        # Make a copy to avoid modifying the original data
        filtered_data = data.copy()
        
        # Detrend
        DataFilter.detrend(filtered_data, DetrendOperations.LINEAR.value)
        
        # Remove environmental noise (60Hz)
        DataFilter.remove_environmental_noise(filtered_data, self.sample_rate, FilterTypes.BUTTERWORTH.value)
        
        # Apply bandpass filter
        DataFilter.perform_bandpass(filtered_data, self.sample_rate, 
                                   lowcut, highcut, 
                                   4, FilterTypes.BUTTERWORTH.value, 0)
        
        return filtered_data
    
    def extract_band_component(self, data, low_freq, high_freq):
        """Extract specific frequency band component."""
        band_data = data.copy()
        
        # Apply narrow bandpass for the specific band
        DataFilter.perform_bandpass(band_data, self.sample_rate, 
                                   low_freq, high_freq, 
                                   4, FilterTypes.BUTTERWORTH.value, 0)
        
        return band_data
    
    def compute_band_powers(self, data):
        """Compute power in different frequency bands."""
        # Get the most recent window of data
        window = data[-self.analysis_window:]
        
        # Compute powers for each band
        powers = {}
        for band_name, (low_freq, high_freq) in bands.items():
            # Use DataFilter's built-in band power calculation
            band_power = DataFilter.get_band_power(window, self.sample_rate, low_freq, high_freq)
            powers[band_name] = band_power
        
        return powers
    
    def calculate_alpha_score(self, powers):
        """Calculate a normalized alpha score based on band powers."""
        total_power = sum(powers.values())
        
        if total_power <= 0:
            return 0.0
        
        # Basic alpha ratio
        alpha_ratio = powers["alpha"] / total_power
        
        # Enhanced alpha score that emphasizes alpha prominence
        # Higher when alpha is strong compared to neighboring bands
        alpha_score = 0.0
        if powers["theta"] > 0 and powers["beta"] > 0:
            # Compare alpha to neighboring bands (theta and beta)
            alpha_theta_ratio = powers["alpha"] / powers["theta"]
            alpha_beta_ratio = powers["alpha"] / powers["beta"]
            
            # Geometric mean of ratios gives higher score when alpha dominates both neighbors
            neighbor_ratio = np.sqrt(alpha_theta_ratio * alpha_beta_ratio)
            
            # Combine absolute and relative measures
            alpha_score = alpha_ratio * neighbor_ratio
            
            # Normalize to a 0-1 scale (clip at 1.0)
            alpha_score = min(alpha_score / 2.0, 1.0)
        
        return alpha_score
    
    def update_data(self):
        """Update EEG data in a continuous loop."""
        global eeg_filtered, alpha_filtered, band_powers, alpha_scores, should_run
        
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
                    # Process each channel
                    for idx, ch_idx in enumerate(eeg_channels):
                        ch_name = channel_names[idx]
                        
                        # General filtering (1-45 Hz)
                        filtered = self.apply_filters(data[ch_idx].copy(), 1.0, 45.0)
                        eeg_filtered[ch_name] = filtered
                        
                        # Extract alpha component (8-13 Hz)
                        alpha_band = self.extract_band_component(filtered.copy(), 8.0, 13.0)
                        alpha_filtered[ch_name] = alpha_band
                        
                        # Compute band powers
                        ch_powers = self.compute_band_powers(filtered)
                        band_powers[ch_name] = ch_powers
                        
                        # Calculate alpha score
                        alpha_scores[ch_name] = self.calculate_alpha_score(ch_powers)
                
                # Sleep a bit to prevent CPU overuse
                time.sleep(0.05)
                
            except Exception as e:
                logger.error(f"Error updating data: {e}")
                time.sleep(0.1)

def find_and_connect_brainbit():
    """Find and connect to a BrainBit device."""
    logger.info("Connecting to BrainBit...")
    handler = BrainBitHandler()
    if handler.connect():
        logger.info("Connected successfully")
        return handler
    else:
        logger.error("Failed to connect")
        return None

def init_plot(fig, ax_eeg, ax_alpha, lines_eeg, lines_alpha, ax_powers, bar_containers, alpha_indicators):
    """Initialize the plot."""
    x_data = np.linspace(-5, 0, buffer_size)
    
    # Initialize EEG plots
    for i, ch_name in enumerate(channel_names):
        lines_eeg[i].set_data(x_data, np.zeros(buffer_size))
        lines_alpha[i].set_data(x_data, np.zeros(buffer_size))
        
        # Set initial y limits
        ax_eeg[i].set_ylim(-100, 100)
        
        # Initialize bar heights for power spectrum
        for bar in bar_containers[i].patches:
            bar.set_height(0)
        
        # Initialize alpha indicator
        alpha_indicators[i].set_height(0)
    
    return lines_eeg + lines_alpha

def update_plot(frame, handler, fig, ax_eeg, ax_alpha, lines_eeg, lines_alpha,
               ax_powers, bar_containers, alpha_indicators, alpha_texts, status_text):
    """Update the plot with new data."""
    if handler is None:
        status_text.set_text("Device disconnected")
        return lines_eeg + lines_alpha
    
    timestamp = datetime.now().strftime("%H:%M:%S")
    status_text.set_text(f"Connected | {timestamp}")
    
    with data_lock:
        x_data = np.linspace(-5, 0, buffer_size)
        
        for i, ch_name in enumerate(channel_names):
            # Get the filtered signals
            eeg_signal = eeg_filtered[ch_name]
            alpha_signal = alpha_filtered[ch_name]
            
            # Update EEG plot
            if np.any(eeg_signal != 0):
                # Normalize for display
                max_val = max(np.max(np.abs(eeg_signal)), 1e-6)
                
                # Scale alpha to match EEG for better visualization
                scaled_alpha = alpha_signal * (max_val / max(np.max(np.abs(alpha_signal)), 1e-6))
                
                # Set data
                lines_eeg[i].set_data(x_data, eeg_signal)
                lines_alpha[i].set_data(x_data, scaled_alpha)
                
                # Adjust y-axis limits based on data
                y_max = np.max(np.abs(eeg_signal)) * 1.2
                ax_eeg[i].set_ylim(-y_max, y_max)
            
            # Update power spectrum bars
            powers = band_powers[ch_name]
            bar_values = [powers[band] for band in ["delta", "theta", "alpha", "beta", "gamma"]]
            
            # Normalize power values for better visualization
            if sum(bar_values) > 0:
                norm_values = [p / max(bar_values) for p in bar_values]
                
                # Update bar heights
                for j, bar in enumerate(bar_containers[i].patches):
                    bar.set_height(norm_values[j])
                
                # Highlight alpha bar
                bar_containers[i].patches[2].set_color('red')  # Alpha is the 3rd bar (index 2)
            
            # Update alpha score indicator
            alpha_score = alpha_scores[ch_name]
            alpha_indicators[i].set_height(alpha_score)
            
            # Set color based on alpha strength
            if alpha_score > 0.6:  # Strong alpha
                alpha_indicators[i].set_color('green')
                alpha_texts[i].set_text(f"Strong α: {alpha_score:.2f}")
                alpha_texts[i].set_color('green')
            elif alpha_score > 0.3:  # Moderate alpha
                alpha_indicators[i].set_color('blue')
                alpha_texts[i].set_text(f"Moderate α: {alpha_score:.2f}")
                alpha_texts[i].set_color('blue')
            else:  # Weak alpha
                alpha_indicators[i].set_color('gray')
                alpha_texts[i].set_text(f"Weak α: {alpha_score:.2f}")
                alpha_texts[i].set_color('gray')
    
    return lines_eeg + lines_alpha

def create_alpha_visualization():
    """Create specialized visualization for alpha rhythm detection."""
    # Connect to BrainBit
    handler = find_and_connect_brainbit()
    if handler is None:
        logger.error("Failed to connect to BrainBit")
        return
    
    # Create figure
    fig = plt.figure(figsize=(14, 10), constrained_layout=True)
    gs = fig.add_gridspec(4, 3, height_ratios=[1, 1, 1, 1])
    
    # Initialize plots
    ax_eeg = []
    ax_alpha = []
    ax_powers = []
    lines_eeg = []
    lines_alpha = []
    bar_containers = []
    alpha_indicators = []
    alpha_texts = []
    
    band_labels = ['δ', 'θ', 'α', 'β', 'γ']
    
    for i, ch_name in enumerate(channel_names):
        # Main EEG plot
        ax = fig.add_subplot(gs[i, 0:2])
        line_eeg, = ax.plot([], [], lw=1.5, color='blue', label='EEG')
        line_alpha, = ax.plot([], [], lw=1.5, color='red', alpha=0.7, label='Alpha Band')
        
        ax.set_title(f"Channel {ch_name}")
        ax.set_ylabel('μV')
        ax.set_xlabel('Time (s)' if i == len(channel_names) - 1 else '')
        ax.grid(True, alpha=0.3)
        ax.legend(loc='upper right', fontsize='small')
        
        # Power spectrum plot
        ax_power = fig.add_subplot(gs[i, 2])
        x = np.arange(5)
        bars = ax_power.bar(x, np.zeros(5), width=0.7)
        
        # Add alpha score indicator
        alpha_ind = ax_power.bar([5.5], [0], width=0.7, color='blue')
        
        # Configure power spectrum plot
        ax_power.set_xticks(np.append(x, 5.5))
        ax_power.set_xticklabels(band_labels + ['score'])
        ax_power.set_ylim(0, 1.1)
        ax_power.set_title(f"Band Powers - {ch_name}")
        
        # Add text for alpha strength
        alpha_text = ax_power.text(5.5, 0.05, "α: --", ha='center', fontsize=8)
        
        # Store references
        ax_eeg.append(ax)
        ax_alpha.append(ax)
        ax_powers.append(ax_power)
        lines_eeg.append(line_eeg)
        lines_alpha.append(line_alpha)
        bar_containers.append(bars)
        alpha_indicators.append(alpha_ind[0])
        alpha_texts.append(alpha_text)
    
    # Add status text
    status_text = fig.text(0.5, 0.01, "Connecting...", ha='center', fontsize=12,
                         bbox=dict(boxstyle='round', facecolor='white', alpha=0.7))
    
    # Add instructions
    instructions = fig.text(0.5, 0.05, 
                          "Close your eyes for 5-10 seconds to see alpha rhythm\n"
                          "Press 'q' or 'Escape' to quit",
                          ha='center', fontsize=10)
    
    # Set figure title
    fig.suptitle('BrainBit Alpha Rhythm Detector', fontsize=16)
    
    # Create animation
    ani = FuncAnimation(
        fig, update_plot, 
        fargs=(handler, fig, ax_eeg, ax_alpha, lines_eeg, lines_alpha,
              ax_powers, bar_containers, alpha_indicators, alpha_texts, status_text),
        init_func=lambda: init_plot(fig, ax_eeg, ax_alpha, lines_eeg, lines_alpha,
                                  ax_powers, bar_containers, alpha_indicators),
        interval=100, blit=True, save_count=100
    )
    
    # Handle key events
    def on_key(event):
        if event.key == 'escape' or event.key == 'q':
            plt.close(fig)
    
    fig.canvas.mpl_connect('key_press_event', on_key)
    
    # Show the plot
    plt.show()
    
    # Clean up
    handler.disconnect()
    print("Disconnected from BrainBit")

def main():
    """Main function."""
    try:
        create_alpha_visualization()
    except KeyboardInterrupt:
        print("Interrupted by user")
    except Exception as e:
        logger.error(f"Error: {e}")
    finally:
        global should_run
        should_run = False

if __name__ == "__main__":
    main()
