#!/usr/bin/env python3
"""
BrainBit Flex Real-Time EEG Monitor

This script provides a real-time visualization of BrainBit EEG data
with a 10-second rolling window display and frequency analysis.
"""

import time
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from datetime import datetime
import threading

# BrainFlow imports
import brainflow
from brainflow.board_shim import BoardShim, BrainFlowInputParams, BoardIds, LogLevels
from brainflow.data_filter import DataFilter, DetrendOperations

class BrainBitRealTimeMonitor:
    def __init__(self, window_size=10, update_interval=100):
        """
        Initialize the real-time monitor.
        
        Parameters:
        -----------
        window_size : int
            Size of the display window in seconds
        update_interval : int
            Update interval in milliseconds
        """
        self.window_size = window_size
        self.update_interval = update_interval
        self.board = None
        self.board_id = None
        self.sampling_rate = None
        self.buffer_size = None
        self.eeg_channels = None
        self.active_channel = None
        self.active_channel_idx = None
        self.active_channel_name = None
        
        # For plotting
        self.fig = None
        self.axes = None
        self.lines = None
        self.timestamp = None
        self.data_buffer = None
        self.animation = None
        
        # For band power calculation
        self.bands = {
            'Delta': (0.5, 4),
            'Theta': (4, 8),
            'Alpha': (8, 13),
            'Beta': (13, 30),
            'Gamma': (30, 50)
        }
        self.band_powers = {band: [] for band in self.bands}
        self.times = []  # For tracking band power over time
        
        # For thread safety
        self.lock = threading.Lock()
    
    def connect(self):
        """Connect to BrainBit device."""
        params = BrainFlowInputParams()
        
        # Set log level
        BoardShim.enable_dev_board_logger()
        BoardShim.set_log_level(LogLevels.LEVEL_INFO.value)
        
        # Try both board types
        board_ids = [BoardIds.BRAINBIT_BLED_BOARD, BoardIds.BRAINBIT_BOARD]
        
        for board_id in board_ids:
            try:
                print(f"Attempting to connect with board ID: {board_id}...")
                board = BoardShim(board_id, params)
                board.prepare_session()
                self.board = board
                self.board_id = board_id
                print(f"Successfully connected using board ID: {board_id}")
                break
            except brainflow.board_shim.BrainFlowError as e:
                print(f"Failed to connect with board ID {board_id}: {e}")
        
        if self.board is None:
            raise ConnectionError("Could not connect to BrainBit device")
        
        # Get device info
        self.sampling_rate = BoardShim.get_sampling_rate(self.board_id)
        self.eeg_channels = BoardShim.get_eeg_channels(self.board_id)
        self.buffer_size = self.sampling_rate * self.window_size
        
        # Start data stream
        self.board.start_stream()
        print("Data streaming started")
        
        # Wait a moment to collect some initial data
        time.sleep(1)
        
        # Find the active channel
        self._detect_active_channel()
        
        return True
    
    def _detect_active_channel(self):
        """Detect which channel has the most activity."""
        # Get some initial data
        data = self.board.get_current_board_data(256)
        
        # Find channel with highest variance
        variances = [np.var(data[ch]) for ch in self.eeg_channels]
        self.active_channel_idx = np.argmax(variances)
        self.active_channel = self.eeg_channels[self.active_channel_idx]
        
        # Get channel name
        ch_names = BoardShim.get_eeg_names(self.board_id)
        self.active_channel_name = ch_names[self.active_channel_idx]
        
        print(f"Detected active channel: {self.active_channel_name}")
        
        # Initialize data buffer for the active channel
        self.data_buffer = np.zeros(self.buffer_size)
    
    def setup_display(self):
        """Set up the visualization display."""
        # Create figure and subplots
        self.fig = plt.figure(figsize=(12, 9))
        self.fig.canvas.manager.set_window_title(f'BrainBit Real-Time Monitor - {self.active_channel_name}')
        
        # Create 3 subplots: EEG signal, spectrum, and band powers over time
        gs = self.fig.add_gridspec(3, 1, height_ratios=[2, 1, 1])
        self.axes = [
            self.fig.add_subplot(gs[0]),  # EEG signal
            self.fig.add_subplot(gs[1]),  # Frequency spectrum
            self.fig.add_subplot(gs[2])   # Band powers over time
        ]
        
        # EEG Signal
        self.axes[0].set_title(f'Real-Time EEG - {self.active_channel_name} Channel')
        self.axes[0].set_xlabel('Time (s)')
        self.axes[0].set_ylabel('Amplitude (μV)')
        self.axes[0].grid(True)
        
        # Create x-axis for time domain plot
        self.timestamp = np.linspace(-self.window_size, 0, self.buffer_size)
        
        # Initialize line for EEG signal
        self.lines = [self.axes[0].plot(self.timestamp, np.zeros(self.buffer_size), 'b-', linewidth=1)[0]]
        
        # Frequency Spectrum
        self.axes[1].set_title('Frequency Spectrum')
        self.axes[1].set_xlabel('Frequency (Hz)')
        self.axes[1].set_ylabel('Power (dB)')
        self.axes[1].grid(True)
        
        # Frequencies for spectrum
        self.freqs = np.fft.rfftfreq(self.buffer_size, 1.0/self.sampling_rate)
        self.freqs = self.freqs[self.freqs <= 50]  # Limit to 50 Hz
        
        # Initialize line for spectrum
        self.lines.append(self.axes[1].plot(self.freqs, np.zeros_like(self.freqs), 'g-')[0])
        
        # Colors for the bands
        self.band_colors = ['r', 'g', 'b', 'orange', 'c']
        
        # Add colored regions for each frequency band
        for (band_name, (fmin, fmax)), color in zip(self.bands.items(), self.band_colors):
            idx = np.logical_and(self.freqs >= fmin, self.freqs <= fmax)
            x_band = self.freqs[idx]
            if len(x_band) > 0:
                self.axes[1].axvspan(fmin, fmax, color=color, alpha=0.3)
                self.axes[1].text((fmin + fmax)/2, 0, band_name, color=color, 
                                 ha='center', fontweight='bold')
        
        # Band Powers Over Time
        self.axes[2].set_title('Band Powers Over Time')
        self.axes[2].set_xlabel('Time (s)')
        self.axes[2].set_ylabel('Relative Power')
        self.axes[2].grid(True)
        
        # Initialize lines for band powers
        for i, band in enumerate(self.bands):
            self.lines.append(self.axes[2].plot([], [], color=self.band_colors[i], linestyle='-', label=band)[0])
        
        self.axes[2].legend(loc='upper left')
        
        # Adjust layout
        plt.tight_layout()
    
    def update(self, frame):
        """Update function for animation."""
        with self.lock:
            try:
                # Get latest data from board
                new_data = self.board.get_current_board_data(self.sampling_rate)
                
                if new_data.size == 0 or new_data.shape[1] == 0:
                    return self.lines
                
                # Get active channel data
                active_data = new_data[self.active_channel]
                
                # Update buffer with new data (sliding window)
                if len(active_data) < len(self.data_buffer):
                    self.data_buffer = np.roll(self.data_buffer, -len(active_data))
                    self.data_buffer[-len(active_data):] = active_data
                else:
                    # If we got more data than buffer size, just take the latest window_size worth
                    self.data_buffer = active_data[-self.buffer_size:]
                
                # Apply detrending
                DataFilter.detrend(self.data_buffer, DetrendOperations.LINEAR.value)
                
                # Update EEG signal plot
                self.lines[0].set_ydata(self.data_buffer)
                
                # Calculate and update spectrum
                fft_data = np.fft.rfft(self.data_buffer * np.hamming(len(self.data_buffer)))
                fft_data = np.abs(fft_data[:len(self.freqs)]) ** 2
                # Convert to dB scale with normalization, avoiding log(0)
                fft_data = 10 * np.log10(fft_data + 1e-10)
                self.lines[1].set_ydata(fft_data)
                
                # Calculate band powers
                current_time = time.time()
                for i, (band_name, (fmin, fmax)) in enumerate(self.bands.items()):
                    band_idx = np.logical_and(self.freqs >= fmin, self.freqs <= fmax)
                    if np.any(band_idx):
                        band_power = np.mean(fft_data[band_idx])
                        self.band_powers[band_name].append(band_power)
                        # Keep only the last 50 points for display
                        if len(self.band_powers[band_name]) > 50:
                            self.band_powers[band_name] = self.band_powers[band_name][-50:]
                
                # Update times list for x-axis of band power plot
                if len(self.times) == 0:
                    self.times.append(0)
                else:
                    self.times.append(self.times[-1] + self.update_interval/1000.0)
                    if len(self.times) > 50:
                        self.times = self.times[-50:]
                
                # Update band power lines
                for i, band in enumerate(self.bands):
                    self.lines[i+2].set_data(self.times, self.band_powers[band])
                
                # Adjust y axis limits for each plot
                self.axes[0].set_ylim(np.min(self.data_buffer) * 1.1, np.max(self.data_buffer) * 1.1)
                self.axes[1].set_ylim(min(fft_data) - 5, max(fft_data) + 5)
                
                # For band powers plot, use fixed scale or auto-adjust
                min_power = min([min(powers) if powers else 0 for powers in self.band_powers.values()])
                max_power = max([max(powers) if powers else 0 for powers in self.band_powers.values()])
                self.axes[2].set_xlim(self.times[0], self.times[-1])
                self.axes[2].set_ylim(min_power - 5, max_power + 5)
                
                # Add status text with dominant band
                if frame % 5 == 0:  # Update every 5 frames to reduce computation
                    current_powers = {band: self.band_powers[band][-1] if self.band_powers[band] else float('-inf') 
                                     for band in self.bands}
                    dominant_band = max(current_powers.items(), key=lambda x: x[1])[0]
                    status_text = f"Dominant: {dominant_band} | Time: {datetime.now().strftime('%H:%M:%S')}"
                    plt.figtext(0.5, 0.01, status_text, ha="center", fontsize=10, 
                                bbox={"facecolor":"white", "alpha":0.5, "pad":5})
            
            except Exception as e:
                print(f"Error updating plots: {e}")
            
            return self.lines
    
    def run(self):
        """Run the real-time monitor."""
        if self.board is None:
            self.connect()
        
        self.setup_display()
        
        # Set up the animation
        self.animation = FuncAnimation(
            self.fig, self.update, interval=self.update_interval, 
            blit=True, cache_frame_data=False
        )
        
        # Show the plot
        plt.show()
    
    def stop(self):
        """Stop data acquisition and release resources."""
        if self.board:
            try:
                self.board.stop_stream()
                self.board.release_session()
                print("BrainBit disconnected")
            except Exception as e:
                print(f"Error disconnecting: {e}")

def main():
    monitor = BrainBitRealTimeMonitor(window_size=10, update_interval=100)
    
    try:
        monitor.run()
    except KeyboardInterrupt:
        print("Monitor interrupted by user")
    finally:
        monitor.stop()
        print("Monitor stopped")

if __name__ == "__main__":
    main()
