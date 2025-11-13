#!/usr/bin/env python3
"""
BrainBit Smooth View

A high-resolution EEG visualizer with proper filtering and normalization.
"""

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import time
from scipy import signal
from brainflow.board_shim import BoardShim, BrainFlowInputParams, BoardIds
from brainflow.data_filter import DataFilter, FilterTypes, DetrendOperations, WindowOperations

# Create figure and subplots
plt.ion()  # Turn on interactive mode
fig, axes = plt.subplots(4, 1, figsize=(12, 10))
fig.suptitle('BrainBit EEG - Filtered & Normalized', fontsize=16)
plt.tight_layout(rect=[0, 0, 1, 0.96])  # Make room for suptitle

# Channel names and lines
ch_names = ['T3', 'T4', 'O1', 'O2']
colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728']  # nice colors for each channel

# Set up display parameters
DISPLAY_TIME = 3  # seconds of data to display
MAX_BUFFER_TIME = 10  # seconds of data to keep in buffer

# Empty lists for raw and filtered data
raw_lines = []
filtered_lines = []

# Create line objects and labels for each channel
for i, ax in enumerate(axes):
    # Raw data (light)
    raw_line, = ax.plot([], [], lw=1, alpha=0.3, color=colors[i])
    raw_lines.append(raw_line)
    
    # Filtered data (bold)
    filtered_line, = ax.plot([], [], lw=2, color=colors[i])
    filtered_lines.append(filtered_line)
    
    # Set up axes
    ax.set_title(f"Channel {ch_names[i]}")
    ax.set_ylabel('Normalized')
    ax.set_ylim(-1.2, 1.2)  # Normalized signals will be in range [-1, 1]
    ax.grid(True)
    
    # Add display legend
    ax.legend([filtered_line, raw_line], ['Filtered', 'Raw'], 
             loc='upper right', framealpha=0.3)

axes[-1].set_xlabel('Time (s)')

# Text for filter info and stats
filter_text = fig.text(0.01, 0.01, "", ha='left', fontsize=9,
                      bbox=dict(facecolor='white', alpha=0.8))

class BrainBitMonitor:
    def __init__(self):
        self.board = None
        self.eeg_channels = None
        self.sampling_rate = None
        
        # Buffer parameters
        self.display_samples = None  # Will be set based on sampling rate
        self.max_buffer_samples = None
        
        # Data buffers for each channel
        self.raw_buffers = []
        self.filtered_buffers = []
        self.time_values = []
        
        # Filter settings
        self.filter_bp_low = 1.0  # Hz - high-pass cutoff
        self.filter_bp_high = 30.0  # Hz - low-pass cutoff
        self.filter_notch_freq = 60.0  # Hz - power line frequency
        
        # Statistics for signal quality
        self.signal_stats = {}
        
    def connect(self):
        """Connect to BrainBit device."""
        print("Connecting to BrainBit...")
        params = BrainFlowInputParams()
        
        # Try connecting to BrainBit
        try:
            board = BoardShim(BoardIds.BRAINBIT_BOARD, params)
            board.prepare_session()
            
            self.board = board
            self.eeg_channels = BoardShim.get_eeg_channels(BoardIds.BRAINBIT_BOARD)
            self.sampling_rate = BoardShim.get_sampling_rate(BoardIds.BRAINBIT_BOARD)
            
            # Calculate buffer sizes
            self.display_samples = int(DISPLAY_TIME * self.sampling_rate)
            self.max_buffer_samples = int(MAX_BUFFER_TIME * self.sampling_rate)
            
            # Initialize time values
            self.time_values = np.linspace(-DISPLAY_TIME, 0, self.display_samples)
            
            # Initialize empty buffers for each channel
            for _ in range(len(self.eeg_channels)):
                self.raw_buffers.append(np.zeros(self.max_buffer_samples))
                self.filtered_buffers.append(np.zeros(self.max_buffer_samples))
                self.signal_stats[ch_names[_]] = {'mean': 0, 'std': 0, 'min': 0, 'max': 0}
            
            # Start streaming
            self.board.start_stream()
            print(f"Connected to BrainBit! Sampling at {self.sampling_rate} Hz")
            
            return True
        
        except Exception as e:
            print(f"Failed to connect: {e}")
            return False
    
    def apply_filters(self, data):
        """Apply multiple filters to improve signal quality."""
        filtered = np.copy(data)
        
        try:
            # Step 1: Remove DC offset/detrend
            DataFilter.detrend(filtered, DetrendOperations.CONSTANT.value)
            
            # Step 2: Apply a notch filter at power line frequency (50/60 Hz)
            DataFilter.perform_bandstop(filtered, self.sampling_rate,
                                      self.filter_notch_freq - 2, self.filter_notch_freq + 2,
                                      2, FilterTypes.BUTTERWORTH.value, 0)
            
            # Step 3: Apply bandpass filter to keep only brain frequencies
            DataFilter.perform_bandpass(filtered, self.sampling_rate,
                                      self.filter_bp_low, self.filter_bp_high,
                                      2, FilterTypes.BUTTERWORTH.value, 0)
            
            # Step 4: Apply additional smoothing if needed
            # (disabled by default to preserve signal detail)
            # DataFilter.perform_rolling_filter(filtered, 3, AggOperations.MEAN.value)
            
        except Exception as e:
            print(f"Error in filtering: {e}")
        
        return filtered
    
    def normalize_signal(self, data):
        """Normalize signal to range [-1, 1] based on its own amplitude."""
        if np.max(np.abs(data)) > 0:
            return data / np.max(np.abs(data))
        return data
    
    def update(self):
        """Get new data and update buffers."""
        if self.board is None:
            return False
        
        try:
            # Get latest data (1/10 second of data)
            data = self.board.get_current_board_data(int(self.sampling_rate / 10))
            
            if data.size == 0 or data.shape[1] == 0:
                return False
            
            # Process each channel
            for i, ch in enumerate(self.eeg_channels):
                if ch < data.shape[0]:
                    # Get channel data
                    channel_data = data[ch]
                    
                    if len(channel_data) == 0:
                        continue
                    
                    # Update raw buffer
                    if len(channel_data) < len(self.raw_buffers[i]):
                        self.raw_buffers[i] = np.roll(self.raw_buffers[i], -len(channel_data))
                        self.raw_buffers[i][-len(channel_data):] = channel_data
                    else:
                        # If we got more data than buffer size, just take the latest
                        self.raw_buffers[i] = channel_data[-self.max_buffer_samples:]
                    
                    # Apply filters to the entire buffer
                    self.filtered_buffers[i] = self.apply_filters(self.raw_buffers[i].copy())
                    
                    # Update signal statistics
                    self.signal_stats[ch_names[i]] = {
                        'mean': np.mean(self.filtered_buffers[i][-self.display_samples:]),
                        'std': np.std(self.filtered_buffers[i][-self.display_samples:]),
                        'min': np.min(self.filtered_buffers[i][-self.display_samples:]),
                        'max': np.max(self.filtered_buffers[i][-self.display_samples:])
                    }
            
            return True
        
        except Exception as e:
            print(f"Error updating data: {e}")
            return False
    
    def update_plot(self):
        """Update the plot with current data."""
        for i in range(len(self.eeg_channels)):
            if i >= len(raw_lines) or i >= len(filtered_lines):
                continue
            
            # Get the data for display (last X seconds)
            raw_display = self.raw_buffers[i][-self.display_samples:]
            filtered_display = self.filtered_buffers[i][-self.display_samples:]
            
            # Normalize the signals
            normalized_raw = self.normalize_signal(raw_display)
            normalized_filtered = self.normalize_signal(filtered_display)
            
            # Update the plots
            raw_lines[i].set_data(self.time_values[:len(raw_display)], normalized_raw)
            filtered_lines[i].set_data(self.time_values[:len(filtered_display)], normalized_filtered)
            
            # Set x-axis limits to show only the specified time window
            axes[i].set_xlim(-DISPLAY_TIME, 0)
        
        # Update filter info text
        stats_text = f"Bandpass: {self.filter_bp_low}-{self.filter_bp_high} Hz | Notch: {self.filter_notch_freq} Hz\n"
        
        for ch in ch_names:
            if ch in self.signal_stats:
                stats = self.signal_stats[ch]
                stats_text += f"{ch}: μ={stats['mean']:.1f} σ={stats['std']:.1f} | "
        
        filter_text.set_text(stats_text)
    
    def disconnect(self):
        """Disconnect from BrainBit."""
        if self.board:
            self.board.stop_stream()
            self.board.release_session()
            print("Disconnected from BrainBit.")

def main():
    """Main function."""
    monitor = BrainBitMonitor()
    
    try:
        if not monitor.connect():
            print("Failed to connect to BrainBit. Exiting.")
            return
        
        print("Displaying EEG data with higher temporal resolution.")
        print("Signals are filtered and normalized to range [-1, 1].")
        print("Press Ctrl+C to exit.")
        
        # Tight subplot layout
        plt.tight_layout()
        plt.subplots_adjust(top=0.9, bottom=0.1)
        
        # Main loop
        while True:
            # Update data
            monitor.update()
            
            # Update the plot
            monitor.update_plot()
            
            # Refresh the display
            plt.pause(0.05)  # 50ms refresh rate for smooth animation
    
    except KeyboardInterrupt:
        print("\nExiting...")
    finally:
        monitor.disconnect()
        plt.close()

if __name__ == "__main__":
    main()
