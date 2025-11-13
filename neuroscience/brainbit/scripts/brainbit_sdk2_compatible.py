#!/usr/bin/env python3
"""
BrainBit SDK2-Compatible Visualization using BrainFlow

This script provides an SDK2-inspired interface while using the reliable
BrainFlow library as the backend for device communication. It incorporates
advanced visualization features including real-time EEG, spectral analysis,
and 1/f spectral falloff.
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
eeg_data = {
    "T3": np.zeros(buffer_size),
    "T4": np.zeros(buffer_size),
    "O1": np.zeros(buffer_size),
    "O2": np.zeros(buffer_size)
}
eeg_data_filtered = {
    "T3": np.zeros(buffer_size),
    "T4": np.zeros(buffer_size),
    "O1": np.zeros(buffer_size),
    "O2": np.zeros(buffer_size)
}
data_lock = threading.Lock()
should_run = True

# Channel names for BrainBit Flex using BrainFlow numbering
channel_names = ["T3", "T4", "O1", "O2"]
eeg_channels = [1, 2, 3, 4]  # BrainFlow channel indices

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
        self.bandpass_high = 30.0
        
        # Initialize time vector for x-axis
        self.time_vector = np.linspace(-self.buffer_seconds, 0, self.buffer_size)
        
        # Initialize spectral analysis parameters
        self.psd_window_sec = 2.0
        self.psd_points = int(self.psd_window_sec * self.sample_rate)
        self.psd_freqs = np.linspace(0, self.sample_rate/2, self.psd_points//2 + 1)
        
    def detect_active_channels(self, data):
        """Determine which channels are active based on signal variance."""
        active_channels = []
        for i, channel in enumerate(eeg_channels):
            # Get the last 100 samples for the channel
            channel_data = data[channel][-100:]
            # Check if the channel has significant variance and is not just noise
            if np.var(channel_data) > 1.0:
                active_channels.append(i)
        return active_channels if active_channels else list(range(len(eeg_channels)))
    
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
    
    def apply_filters(self, data, sampling_rate):
        """Apply various filters to clean the EEG signal."""
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
    
    def compute_psd(self, data, fs):
        """Compute power spectral density using Welch's method."""
        # Use scipy's Welch method
        f, psd = signal.welch(data[-self.psd_points:], fs, nperseg=min(256, len(data)), 
                             scaling='density')
        return f, psd
    
    def fit_power_law(self, freqs, psd):
        """Fit a power law (1/f^α) to the PSD."""
        # Filter out low frequencies and zero/negative values
        mask = (freqs > 3) & (freqs < 40) & (psd > 0)
        if np.sum(mask) < 3:  # Need at least 3 points for a reasonable fit
            return None, None
        
        log_freqs = np.log10(freqs[mask])
        log_psd = np.log10(psd[mask])
        
        # Linear fit on log-log scale
        try:
            coeffs = np.polyfit(log_freqs, log_psd, 1)
            slope = coeffs[0]  # This is the exponent α in 1/f^α
            intercept = coeffs[1]
            
            # Generate the fitted line
            fit_psd = 10**(slope * log_freqs + intercept)
            
            return slope, (freqs[mask], fit_psd)
        except:
            return None, None
    
    def update_data(self):
        """Update EEG data in a continuous loop."""
        global eeg_data, eeg_data_filtered, should_run
        
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
                
                # Update active channels if needed
                if not self.active_channels:
                    self.active_channels = self.detect_active_channels(data)
                
                with data_lock:
                    # Update raw data
                    for idx, ch_idx in enumerate(eeg_channels):
                        ch_name = channel_names[idx]
                        eeg_data[ch_name] = data[ch_idx]
                        
                        # Apply filters to each channel
                        filtered = self.apply_filters(data[ch_idx].copy(), self.sample_rate)
                        eeg_data_filtered[ch_name] = filtered
                
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

def init_plot(fig, axes_eeg, axes_psd, lines_eeg, lines_eeg_filtered, lines_psd, lines_fit):
    """Initialize the plot."""
    x_data = np.linspace(-5, 0, buffer_size)
    
    # Initialize EEG time series plots
    for i, (ch_name, ch_data) in enumerate(eeg_data.items()):
        lines_eeg[i].set_data(x_data, ch_data)
        lines_eeg_filtered[i].set_data(x_data, eeg_data_filtered[ch_name])
        axes_eeg[i].set_xlim(-5, 0)
        axes_eeg[i].set_ylim(-100, 100)
    
    # Initialize PSD plots
    dummy_f = np.logspace(0, 2, 50)
    dummy_psd = np.ones_like(dummy_f)
    
    for i in range(len(axes_psd)):
        lines_psd[i].set_data(dummy_f, dummy_psd)
        if lines_fit[i]:
            lines_fit[i].set_data(dummy_f, dummy_psd)
        axes_psd[i].set_xlim(1, 50)
        axes_psd[i].set_ylim(0.01, 100)
    
    return lines_eeg + lines_eeg_filtered + lines_psd + [line for line in lines_fit if line]

def update_plot(frame, handler, fig, axes_eeg, axes_psd, lines_eeg, lines_eeg_filtered, 
               lines_psd, lines_fit, alpha_texts, status_text):
    """Update the plot with new data."""
    if handler is None:
        status_text.set_text("Device disconnected")
        return lines_eeg + lines_eeg_filtered + lines_psd + [line for line in lines_fit if line]
    
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
        
        for i, (ch_name, ch_data) in enumerate(eeg_data.items()):
            # Update raw signal
            lines_eeg[i].set_data(x_data, ch_data)
            
            # Update filtered signal
            filtered_data = eeg_data_filtered[ch_name]
            lines_eeg_filtered[i].set_data(x_data, filtered_data)
            
            # Adjust y-axis limits for EEG
            if np.any(ch_data != 0):
                data_max = max(np.max(np.abs(ch_data)), np.max(np.abs(filtered_data)))
                y_max = max(100, data_max * 1.2)
                axes_eeg[i].set_ylim(-y_max, y_max)
            
            # Compute and update PSD
            f, psd = handler.compute_psd(filtered_data, handler.sample_rate)
            if len(f) > 0 and len(psd) > 0:
                lines_psd[i].set_data(f, psd)
                
                # Fit 1/f power law
                alpha, fit_data = handler.fit_power_law(f, psd)
                if alpha is not None and fit_data is not None:
                    fit_f, fit_psd = fit_data
                    lines_fit[i].set_data(fit_f, fit_psd)
                    alpha_texts[i].set_text(f"1/f^α: α = {alpha:.2f}")
                    alpha_texts[i].set_color('green' if -2.5 < alpha < -0.5 else 'red')
                else:
                    alpha_texts[i].set_text("1/f^α: insufficient data")
                    alpha_texts[i].set_color('gray')
                
                # Adjust y-axis limits for PSD
                if np.any(psd > 0):
                    psd_min = np.min(psd[psd > 0]) * 0.5
                    psd_max = np.max(psd) * 2
                    axes_psd[i].set_ylim(psd_min, psd_max)
    
    return lines_eeg + lines_eeg_filtered + lines_psd + [line for line in lines_fit if line]

def create_spectral_visualization():
    """Create spectral visualization with PSD and 1/f analysis."""
    # Connect to BrainBit
    handler = find_and_connect_brainbit()
    if handler is None:
        logger.error("Failed to connect to BrainBit")
        return
    
    # Create figure with subplots for EEG and PSD
    fig = plt.figure(figsize=(15, 10))
    grid = plt.GridSpec(4, 2, hspace=0.4, wspace=0.3)
    
    # EEG time series plots on the left
    axes_eeg = []
    lines_eeg = []
    lines_eeg_filtered = []
    
    for i, ch_name in enumerate(channel_names):
        ax = fig.add_subplot(grid[i, 0])
        line_raw, = ax.plot([], [], lw=1.0, color='gray', alpha=0.7, label='Raw')
        line_filtered, = ax.plot([], [], lw=1.5, color='blue', label='Filtered')
        
        ax.set_title(f"Channel {ch_name}")
        ax.set_ylabel('µV')
        ax.set_xlabel('Time (s)' if i == len(channel_names) - 1 else '')
        ax.grid(True, alpha=0.3)
        ax.legend(loc='upper right', fontsize='small')
        
        axes_eeg.append(ax)
        lines_eeg.append(line_raw)
        lines_eeg_filtered.append(line_filtered)
    
    # PSD plots on the right
    axes_psd = []
    lines_psd = []
    lines_fit = []
    alpha_texts = []
    
    for i, ch_name in enumerate(channel_names):
        ax = fig.add_subplot(grid[i, 1])
        line_psd, = ax.plot([], [], lw=1.5, color='blue', label='PSD')
        line_fit, = ax.plot([], [], lw=1.5, color='red', linestyle='--', label='1/f fit')
        
        ax.set_title(f"Spectral Analysis - {ch_name}")
        ax.set_ylabel('Power (µV²/Hz)')
        ax.set_xlabel('Frequency (Hz)' if i == len(channel_names) - 1 else '')
        ax.grid(True, alpha=0.3)
        ax.set_xscale('log')
        ax.set_yscale('log')
        ax.legend(loc='upper right', fontsize='small')
        
        # Add text for alpha value
        alpha_text = ax.text(0.05, 0.95, "", transform=ax.transAxes, fontsize=9,
                           verticalalignment='top', bbox=dict(boxstyle='round', facecolor='white', alpha=0.7))
        
        axes_psd.append(ax)
        lines_psd.append(line_psd)
        lines_fit.append(line_fit)
        alpha_texts.append(alpha_text)
    
    # Add status text
    status_text = fig.text(0.5, 0.01, "Connecting...", ha='center', fontsize=12,
                         bbox=dict(boxstyle='round', facecolor='white', alpha=0.7))
    
    # Set figure title
    fig.suptitle('BrainBit Real-Time EEG Analysis', fontsize=16)
    
    # Create animation
    ani = FuncAnimation(
        fig, update_plot, 
        fargs=(handler, fig, axes_eeg, axes_psd, lines_eeg, lines_eeg_filtered, 
               lines_psd, lines_fit, alpha_texts, status_text),
        init_func=lambda: init_plot(fig, axes_eeg, axes_psd, lines_eeg, 
                                  lines_eeg_filtered, lines_psd, lines_fit),
        interval=100, blit=True
    )
    
    # Handle key events
    def on_key(event):
        if event.key == 'escape' or event.key == 'q':
            plt.close(fig)
    
    fig.canvas.mpl_connect('key_press_event', on_key)
    
    # Show the plot
    plt.tight_layout(rect=[0, 0.03, 1, 0.95])
    plt.show()
    
    # Clean up
    handler.disconnect()
    print("Disconnected from BrainBit")

def main():
    """Main function."""
    try:
        create_spectral_visualization()
    except KeyboardInterrupt:
        print("Interrupted by user")
    except Exception as e:
        logger.error(f"Error: {e}")
    finally:
        global should_run
        should_run = False

if __name__ == "__main__":
    main()
