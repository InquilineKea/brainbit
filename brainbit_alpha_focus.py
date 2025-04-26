#!/usr/bin/env python3
"""
BrainBit Alpha Rhythm Visualization

This script specifically focuses on detecting and visualizing alpha rhythm (8-13 Hz)
with enhanced filtering and specialized normalization to better observe alpha waves,
especially during eyes-closed periods.
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
eeg_data_filtered = {
    "T3": np.zeros(buffer_size),
    "T4": np.zeros(buffer_size),
    "O1": np.zeros(buffer_size),
    "O2": np.zeros(buffer_size)
}
eeg_alpha_power = {
    "T3": np.zeros(buffer_size),
    "T4": np.zeros(buffer_size),
    "O1": np.zeros(buffer_size),
    "O2": np.zeros(buffer_size)
}
alpha_ratio = {
    "T3": 0,
    "T4": 0,
    "O1": 0,
    "O2": 0
}
data_lock = threading.Lock()
should_run = True

# Channel names for BrainBit Flex using BrainFlow numbering
channel_names = ["T3", "T4", "O1", "O2"]
eeg_channels = [1, 2, 3, 4]  # BrainFlow channel indices

# Frequency bands for power ratio calculation
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
        self.active_channels = []
        self.data_thread = None
        self.last_update = time.time()
        
        # Filtering parameters
        self.notch_freq = 60.0
        self.bandpass_low = 1.0
        self.bandpass_high = 45.0  # Wider range to capture more frequencies for comparison
        
        # Alpha-specific filter
        self.alpha_low = 8.0
        self.alpha_high = 13.0
        
        # Initialize time vector for x-axis
        self.time_vector = np.linspace(-self.buffer_seconds, 0, self.buffer_size)
        
        # Initialize spectral analysis parameters
        self.psd_window_sec = 2.0
        self.psd_points = int(self.psd_window_sec * self.sample_rate)
        self.psd_freqs = np.linspace(0, self.sample_rate/2, self.psd_points//2 + 1)
        
        # Alpha detection parameters
        self.alpha_window = 2.0  # 2-second window for alpha detection
        self.alpha_points = int(self.alpha_window * self.sample_rate)
        self.envelope_smooth = 50  # Smoothing for alpha envelope
        
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
    
    def get_battery_level(self):
        """Get the battery level of the device."""
        try:
            if self.board:
                # BrainFlow doesn't directly expose battery level for BrainBit
                # Returning a placeholder value
                return 100
            return 0
        except Exception as e:
            logger.error(f"Error getting battery level: {e}")
            return 0
    
    def apply_general_filters(self, data, sampling_rate):
        """Apply general filters to clean the EEG signal."""
        # Make a copy to avoid modifying the original data
        filtered_data = data.copy()
        
        # 1. Detrend the signal
        DataFilter.detrend(filtered_data, DetrendOperations.LINEAR.value)
        
        # 2. Apply notch filter to remove power line noise
        DataFilter.remove_environmental_noise(filtered_data, sampling_rate, FilterTypes.BUTTERWORTH.value)
        
        # 3. Apply bandpass filter for EEG frequencies of interest
        DataFilter.perform_bandpass(filtered_data, sampling_rate, 
                                    self.bandpass_low, self.bandpass_high, 
                                    4, FilterTypes.BUTTERWORTH.value, 0)
        
        return filtered_data
    
    def extract_alpha_component(self, data, sampling_rate):
        """Extract the alpha rhythm component (8-13 Hz) from the signal."""
        # Make a copy to avoid modifying the original data
        alpha_data = data.copy()
        
        # Apply a narrow bandpass filter specifically for alpha (8-13 Hz)
        DataFilter.perform_bandpass(alpha_data, sampling_rate, 
                                  self.alpha_low, self.alpha_high, 
                                  4, FilterTypes.BUTTERWORTH.value, 0)
        
        return alpha_data
    
    def compute_band_power(self, data, sampling_rate, freq_range):
        """Compute power in a specific frequency band."""
        # Compute PSD
        f, psd = signal.welch(data, sampling_rate, nperseg=min(256, len(data)))
        
        # Find indices corresponding to the frequency range
        idx_band = np.logical_and(f >= freq_range[0], f <= freq_range[1])
        
        # Compute band power (mean of PSD in the frequency range)
        if np.any(idx_band):
            band_power = np.mean(psd[idx_band])
        else:
            band_power = 0
            
        return band_power
    
    def compute_alpha_envelope(self, alpha_filtered, sampling_rate):
        """Compute the envelope of alpha oscillations using Hilbert transform."""
        # Get the analytic signal (envelope)
        analytic_signal = signal.hilbert(alpha_filtered)
        
        # Compute the amplitude envelope
        amplitude_envelope = np.abs(analytic_signal)
        
        # Smooth the envelope
        if len(amplitude_envelope) > self.envelope_smooth:
            kernel = np.ones(self.envelope_smooth) / self.envelope_smooth
            amplitude_envelope = np.convolve(amplitude_envelope, kernel, mode='same')
        
        return amplitude_envelope
    
    def compute_alpha_ratio(self, data, sampling_rate):
        """Compute the ratio of alpha power to total power."""
        # Compute power in each frequency band
        band_powers = {}
        for band_name, freq_range in bands.items():
            band_powers[band_name] = self.compute_band_power(data, sampling_rate, freq_range)
        
        # Compute total power
        total_power = sum(band_powers.values())
        
        # Compute alpha ratio
        if total_power > 0:
            alpha_ratio = band_powers["alpha"] / total_power
        else:
            alpha_ratio = 0
            
        # Create a score that emphasizes strong alpha
        # Higher when alpha dominates, especially compared to neighboring bands
        alpha_score = 0
        if band_powers["theta"] > 0 and band_powers["beta"] > 0:
            alpha_theta_ratio = band_powers["alpha"] / band_powers["theta"]
            alpha_beta_ratio = band_powers["alpha"] / band_powers["beta"]
            alpha_score = alpha_ratio * (alpha_theta_ratio + alpha_beta_ratio) / 2
        
        return alpha_ratio, alpha_score, band_powers
    
    def update_data(self):
        """Update EEG data in a continuous loop."""
        global eeg_data_filtered, eeg_alpha_power, alpha_ratio, should_run
        
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
                        
                        # Apply general filters
                        filtered = self.apply_general_filters(data[ch_idx].copy(), self.sample_rate)
                        
                        # Extract alpha component
                        alpha_component = self.extract_alpha_component(filtered.copy(), self.sample_rate)
                        
                        # Compute alpha envelope (for visualization)
                        alpha_env = self.compute_alpha_envelope(alpha_component, self.sample_rate)
                        
                        # Compute alpha ratio
                        alpha_rat, alpha_score, powers = self.compute_alpha_ratio(
                            filtered[-self.alpha_points:], self.sample_rate)
                        
                        # Update data structures
                        eeg_data_filtered[ch_name] = filtered
                        eeg_alpha_power[ch_name] = alpha_env
                        alpha_ratio[ch_name] = alpha_score
                
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

def init_plot(fig, axes_eeg, axes_alpha, lines_eeg, lines_alpha, power_bars):
    """Initialize the plot."""
    x_data = np.linspace(-5, 0, buffer_size)
    
    # Initialize EEG time series plots
    for i, (ch_name, ch_data) in enumerate(eeg_data_filtered.items()):
        lines_eeg[i].set_data(x_data, ch_data)
        lines_alpha[i].set_data(x_data, np.zeros_like(x_data))
        axes_eeg[i].set_xlim(-5, 0)
        axes_eeg[i].set_ylim(-100, 100)  # Start with a reasonable range
        
        # Initialize alpha power bars
        power_bars[i].set_width(0)
        power_bars[i].set_facecolor('blue')
    
    return lines_eeg + lines_alpha + power_bars

def update_plot(frame, handler, fig, axes_eeg, axes_alpha, lines_eeg, lines_alpha, 
               power_bars, alpha_texts, status_text):
    """Update the plot with new data."""
    if handler is None:
        status_text.set_text("Device disconnected")
        return lines_eeg + lines_alpha + power_bars
    
    # Get battery level
    try:
        battery = handler.get_battery_level()
        status = f"Connected | Battery: {battery}% | "
        timestamp = datetime.now().strftime("%H:%M:%S")
        status_text.set_text(f"{status} {timestamp}")
    except Exception as e:
        status_text.set_text(f"Error: {e}")
    
    # Update the plot data
    with data_lock:
        x_data = np.linspace(-5, 0, buffer_size)
        
        for i, ch_name in enumerate(channel_names):
            # Get filtered data and alpha power
            filtered_data = eeg_data_filtered[ch_name]
            alpha_data = eeg_alpha_power[ch_name]
            alpha_score = alpha_ratio[ch_name]
            
            # Scale data for better visualization
            if np.any(filtered_data != 0):
                # Find a reasonable scale for the data
                data_scale = np.max(np.abs(filtered_data)) * 1.2
                y_scale = max(50, data_scale)
                
                # Scale alpha envelope to match main signal
                alpha_scale = alpha_data * (y_scale / max(np.max(alpha_data), 1e-6))
                
                # Update plots
                lines_eeg[i].set_data(x_data, filtered_data)
                lines_alpha[i].set_data(x_data, alpha_scale)
                axes_eeg[i].set_ylim(-y_scale, y_scale)
                
                # Update alpha power bar
                power_bars[i].set_width(alpha_score * 0.9)  # Scale to fit in subplot
                
                # Set color based on alpha strength
                if alpha_score > 0.4:  # Strong alpha
                    power_bars[i].set_facecolor('green')
                    alpha_texts[i].set_text(f"Alpha: Strong ({alpha_score:.2f})")
                    alpha_texts[i].set_color('green')
                elif alpha_score > 0.2:  # Moderate alpha
                    power_bars[i].set_facecolor('blue')
                    alpha_texts[i].set_text(f"Alpha: Moderate ({alpha_score:.2f})")
                    alpha_texts[i].set_color('blue')
                else:  # Weak alpha
                    power_bars[i].set_facecolor('gray')
                    alpha_texts[i].set_text(f"Alpha: Weak ({alpha_score:.2f})")
                    alpha_texts[i].set_color('gray')
    
    return lines_eeg + lines_alpha + power_bars

def create_alpha_visualization():
    """Create specialized visualization for alpha rhythm detection."""
    # Connect to BrainBit
    handler = find_and_connect_brainbit()
    if handler is None:
        logger.error("Failed to connect to BrainBit")
        return
    
    # Create figure
    fig = plt.figure(figsize=(14, 10))
    plt.subplots_adjust(hspace=0.4, wspace=0.3)
    
    # Create grid for layout
    grid = plt.GridSpec(4, 2, height_ratios=[3, 3, 3, 3], width_ratios=[5, 1])
    
    # EEG plots
    axes_eeg = []
    axes_alpha = []
    lines_eeg = []
    lines_alpha = []
    power_bars = []
    alpha_texts = []
    
    for i, ch_name in enumerate(channel_names):
        # Main EEG plot
        ax = fig.add_subplot(grid[i, 0])
        line_eeg, = ax.plot([], [], lw=1.5, color='blue', label='Filtered EEG')
        line_alpha, = ax.plot([], [], lw=1.5, color='red', alpha=0.7, label='Alpha Band')
        
        ax.set_title(f"Channel {ch_name}")
        ax.set_ylabel('μV')
        ax.set_xlabel('Time (s)' if i == len(channel_names) - 1 else '')
        ax.grid(True, alpha=0.3)
        ax.legend(loc='upper right', fontsize='small')
        
        # Alpha power bar plot
        ax_alpha = fig.add_subplot(grid[i, 1])
        power_bar = ax_alpha.barh(0, 0, height=0.5, color='blue')
        ax_alpha.set_xlim(0, 1)
        ax_alpha.set_yticks([])
        ax_alpha.set_title("α Power")
        
        # Add text for alpha strength
        alpha_text = ax_alpha.text(0.5, -0.2, "Alpha: --", 
                                 ha='center', fontsize=9,
                                 transform=ax_alpha.transAxes)
        
        # Store references
        axes_eeg.append(ax)
        axes_alpha.append(ax_alpha)
        lines_eeg.append(line_eeg)
        lines_alpha.append(line_alpha)
        power_bars.append(power_bar)
        alpha_texts.append(alpha_text)
    
    # Add status text
    status_text = fig.text(0.5, 0.01, "Connecting...", ha='center', fontsize=12,
                         bbox=dict(boxstyle='round', facecolor='white', alpha=0.7))
    
    # Set figure title
    fig.suptitle('BrainBit Alpha Rhythm Detection', fontsize=16)
    
    # Add instructions
    instructions = fig.text(0.5, 0.05, 
                          "Close your eyes for 5-10 seconds to see alpha rhythm\n"
                          "Press 'q' or 'Escape' to quit",
                          ha='center', fontsize=10)
    
    # Create animation
    ani = FuncAnimation(
        fig, update_plot, 
        fargs=(handler, fig, axes_eeg, axes_alpha, lines_eeg, lines_alpha, 
               power_bars, alpha_texts, status_text),
        init_func=lambda: init_plot(fig, axes_eeg, axes_alpha, lines_eeg, 
                                  lines_alpha, power_bars),
        interval=100, blit=True, save_count=100
    )
    
    # Handle key events
    def on_key(event):
        if event.key == 'escape' or event.key == 'q':
            plt.close(fig)
    
    fig.canvas.mpl_connect('key_press_event', on_key)
    
    # Show the plot
    plt.tight_layout(rect=[0, 0.07, 1, 0.95])
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
