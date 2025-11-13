#!/usr/bin/env python3
"""
BrainBit Advanced Monitor

Features:
- Real-time display of all 4 channels (T3, T4, O1, O2)
- 1/f spectral falloff analysis
- Electrode impedance monitoring
- Spectral band power analysis
"""

import time
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from matplotlib.gridspec import GridSpec
import scipy.signal
from datetime import datetime
import threading
import os
from scipy import stats

# BrainFlow imports
import brainflow
from brainflow.board_shim import BoardShim, BrainFlowInputParams, BoardIds, LogLevels
from brainflow.data_filter import DataFilter, DetrendOperations, FilterTypes

class BrainBitAdvancedMonitor:
    def __init__(self, window_size=10, update_interval=100, save_data=True):
        """
        Initialize the advanced monitor with all features.
        
        Parameters:
        -----------
        window_size : int
            Size of the display window in seconds
        update_interval : int
            Update interval in milliseconds
        save_data : bool
            Whether to save recorded data to files
        """
        self.window_size = window_size
        self.update_interval = update_interval
        self.save_data = save_data
        self.board = None
        self.board_id = None
        self.sampling_rate = None
        self.buffer_size = None
        self.eeg_channels = None
        self.impedance_channels = None
        self.ch_names = None
        
        # Data storage
        self.data_buffers = None 
        self.impedance_values = None
        self.impedance_history = [] 
        
        # For plotting
        self.fig = None
        self.axes = None
        self.lines = None
        self.impedance_text = None
        self.impedance_ax = None
        self.timestamp = None
        self.animation = None
        
        # For 1/f analysis
        self.last_slope_update = 0
        self.slope_update_interval = 1.0  # seconds
        self.slopes = {}
        self.slope_history = {ch: [] for ch in range(4)}
        self.slope_time = []
        
        # For band power calculation
        self.bands = {
            'Delta': (0.5, 4),
            'Theta': (4, 8),
            'Alpha': (8, 13),
            'Beta': (13, 30),
            'Gamma': (30, 50)
        }
        
        # Colors
        self.channel_colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728']  # blue, orange, green, red
        self.band_colors = ['#e41a1c', '#377eb8', '#4daf4a', '#984ea3', '#ff7f00']  # red, blue, green, purple, orange
        
        # For thread safety
        self.lock = threading.Lock()
        
        # For data recording
        self.recording = False
        self.record_data = []
        self.record_timestamps = []
        self.record_start_time = None
        
        # Create data directory if it doesn't exist
        self.data_dir = os.path.join(os.getcwd(), 'brainbit_data')
        if save_data and not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)
    
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
        self.impedance_channels = BoardShim.get_resistance_channels(self.board_id)
        self.ch_names = BoardShim.get_eeg_names(self.board_id)
        
        print(f"EEG Channels: {self.ch_names}")
        print(f"Impedance Channels: {self.impedance_channels}")
        
        self.buffer_size = self.sampling_rate * self.window_size
        
        # Initialize data buffers for all channels
        self.data_buffers = {ch: np.zeros(self.buffer_size) for ch in self.eeg_channels}
        
        # Initialize impedance values
        self.impedance_values = {ch: 0 for ch in range(len(self.ch_names))}
        
        # Start data stream
        self.board.start_stream()
        print("Data streaming started")
        
        return True
    
    def setup_display(self):
        """Set up the visualization display."""
        # Create a larger figure
        self.fig = plt.figure(figsize=(16, 12))
        self.fig.canvas.manager.set_window_title('BrainBit Advanced Monitor - All Channels')
        
        # Create a complex layout with GridSpec
        gs = GridSpec(6, 4, figure=self.fig)
        
        # Create axes for different visualizations
        self.axes = {
            'eeg': [
                self.fig.add_subplot(gs[0, 0:2]),  # T3
                self.fig.add_subplot(gs[0, 2:4]),  # T4
                self.fig.add_subplot(gs[1, 0:2]),  # O1
                self.fig.add_subplot(gs[1, 2:4]),  # O2
            ],
            'spectrum': [
                self.fig.add_subplot(gs[2, 0:2]),  # Spectrum for all channels
                self.fig.add_subplot(gs[2, 2:4]),  # 1/f slope analysis
            ],
            'band_power': self.fig.add_subplot(gs[3, :]),  # Band powers for all channels
            'impedance': self.fig.add_subplot(gs[4, :]),  # Impedance values
            'slope_history': self.fig.add_subplot(gs[5, :]),  # 1/f slope history
        }
        
        # EEG signals (one per channel)
        for i, ch_name in enumerate(self.ch_names):
            self.axes['eeg'][i].set_title(f'EEG Signal - {ch_name}')
            self.axes['eeg'][i].set_xlabel('Time (s)')
            self.axes['eeg'][i].set_ylabel('Amplitude (μV)')
            self.axes['eeg'][i].grid(True)
        
        # Frequency spectrum & 1/f analysis
        self.axes['spectrum'][0].set_title('Frequency Spectrum (All Channels)')
        self.axes['spectrum'][0].set_xlabel('Frequency (Hz)')
        self.axes['spectrum'][0].set_ylabel('Power (dB)')
        self.axes['spectrum'][0].grid(True)
        
        self.axes['spectrum'][1].set_title('1/f Spectral Falloff')
        self.axes['spectrum'][1].set_xlabel('log(Frequency)')
        self.axes['spectrum'][1].set_ylabel('log(Power)')
        self.axes['spectrum'][1].grid(True)
        
        # Band Powers
        self.axes['band_power'].set_title('Brain Wave Band Powers')
        self.axes['band_power'].set_xlabel('Frequency Band')
        self.axes['band_power'].set_ylabel('Relative Power')
        self.axes['band_power'].grid(True)
        
        # Impedance display
        self.axes['impedance'].set_title('Electrode Impedance')
        self.axes['impedance'].set_xlabel('Time')
        self.axes['impedance'].set_ylabel('Impedance (kΩ)')
        self.axes['impedance'].grid(True)
        
        # 1/f Slope history
        self.axes['slope_history'].set_title('1/f Slope History')
        self.axes['slope_history'].set_xlabel('Time (s)')
        self.axes['slope_history'].set_ylabel('Slope')
        self.axes['slope_history'].grid(True)
        
        # Create x-axis for time domain plots
        self.timestamp = np.linspace(-self.window_size, 0, self.buffer_size)
        
        # Initialize lines for all plots
        self.lines = {}
        
        # EEG signals
        self.lines['eeg'] = []
        for i, ch in enumerate(self.eeg_channels):
            line, = self.axes['eeg'][i].plot(
                self.timestamp, np.zeros(self.buffer_size), 
                color=self.channel_colors[i], linewidth=1
            )
            self.lines['eeg'].append(line)
        
        # Frequencies for spectrum
        self.freqs = np.fft.rfftfreq(self.buffer_size, 1.0/self.sampling_rate)
        self.freqs = self.freqs[self.freqs <= 50]  # Limit to 50 Hz
        
        # Spectrum for all channels
        self.lines['spectrum'] = []
        for i, ch in enumerate(self.eeg_channels):
            line, = self.axes['spectrum'][0].plot(
                self.freqs, np.zeros_like(self.freqs), 
                color=self.channel_colors[i], linewidth=1,
                label=self.ch_names[i]
            )
            self.lines['spectrum'].append(line)
        
        # Add legend to spectrum plot
        self.axes['spectrum'][0].legend(loc='upper right')
        
        # 1/f analysis lines
        self.lines['1f'] = []
        for i, ch in enumerate(self.eeg_channels):
            # Scatter plot of log-log data
            scatter = self.axes['spectrum'][1].scatter(
                [], [], 
                color=self.channel_colors[i], s=3, alpha=0.5,
                label=f"{self.ch_names[i]} data"
            )
            # Regression line
            line, = self.axes['spectrum'][1].plot(
                [], [], 
                color=self.channel_colors[i], linewidth=2, linestyle='--',
                label=f"{self.ch_names[i]} fit"
            )
            self.lines['1f'].append((scatter, line))
        
        # Add legend to 1/f plot
        self.axes['spectrum'][1].legend(loc='lower left')
        
        # Add colored regions for frequency bands on spectrum plot
        for (band_name, (fmin, fmax)), color in zip(self.bands.items(), self.band_colors):
            idx = np.logical_and(self.freqs >= fmin, self.freqs <= fmax)
            x_band = self.freqs[idx]
            if len(x_band) > 0:
                self.axes['spectrum'][0].axvspan(fmin, fmax, color=color, alpha=0.2)
                self.axes['spectrum'][0].text((fmin + fmax)/2, -5, band_name, 
                                            color=color, ha='center', fontweight='bold')
        
        # Initialize bar chart for band powers - grouped by channels
        x = np.arange(len(self.bands))
        width = 0.2  # Width of the bars
        
        self.lines['band_power'] = []
        for i, ch in enumerate(self.eeg_channels):
            bars = self.axes['band_power'].bar(
                x + i*width - 0.3, np.zeros(len(self.bands)), 
                width, color=self.channel_colors[i], alpha=0.7,
                label=self.ch_names[i]
            )
            self.lines['band_power'].append(bars)
        
        # Add legend and labels for band power plot
        self.axes['band_power'].set_xticks(x)
        self.axes['band_power'].set_xticklabels(self.bands.keys())
        self.axes['band_power'].legend(loc='upper right')
        
        # Impedance history
        self.lines['impedance'] = []
        for i, ch_name in enumerate(self.ch_names):
            line, = self.axes['impedance'].plot(
                [], [], color=self.channel_colors[i], 
                marker='o', linestyle='-', markersize=4,
                label=ch_name
            )
            self.lines['impedance'].append(line)
        
        # Add legend for impedance plot
        self.axes['impedance'].legend(loc='upper right')
        
        # Text display for current impedance values
        self.impedance_text = self.fig.text(
            0.02, 0.01, "Initializing impedance values...", 
            fontsize=12, bbox=dict(facecolor='white', alpha=0.7)
        )
        
        # 1/f slope history
        self.lines['slope_history'] = []
        for i, ch in enumerate(self.eeg_channels):
            line, = self.axes['slope_history'].plot(
                [], [], color=self.channel_colors[i], 
                marker='.', linestyle='-', markersize=4,
                label=self.ch_names[i]
            )
            self.lines['slope_history'].append(line)
        
        # Add legend for slope history plot
        self.axes['slope_history'].legend(loc='upper right')
        
        # Recording status indicator
        self.recording_text = self.fig.text(
            0.5, 0.01, "Press 'R' to start recording, 'S' to stop", 
            fontsize=12, ha='center', bbox=dict(facecolor='white', alpha=0.7)
        )
        
        # Add key bindings
        self.fig.canvas.mpl_connect('key_press_event', self._on_key_press)
        
        # Adjust layout
        plt.tight_layout()
        self.fig.subplots_adjust(hspace=0.4, bottom=0.06)
    
    def _on_key_press(self, event):
        """Handle keyboard commands."""
        if event.key == 'r' and not self.recording:
            self._start_recording()
        elif event.key == 's' and self.recording:
            self._stop_recording()
        elif event.key == 'q':
            plt.close(self.fig)
    
    def _start_recording(self):
        """Start recording data."""
        self.recording = True
        self.record_data = []
        self.record_timestamps = []
        self.record_start_time = time.time()
        self.recording_text.set_text("RECORDING - Press 'S' to stop")
        self.recording_text.set_color('red')
        print("Recording started.")
    
    def _stop_recording(self):
        """Stop recording and save data."""
        if not self.recording:
            return
            
        self.recording = False
        self.recording_text.set_text("Recording stopped - Press 'R' to start new recording")
        self.recording_text.set_color('black')
        
        if self.save_data and self.record_data:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = os.path.join(self.data_dir, f"brainbit_recording_{timestamp}.npz")
            
            np.savez(
                filename, 
                eeg_data=np.array(self.record_data),
                timestamps=np.array(self.record_timestamps),
                channel_names=self.ch_names,
                sampling_rate=self.sampling_rate
            )
            
            print(f"Recording saved to {filename}")
    
    def calculate_1f_slope(self, freqs, power_spectrum, ch_idx):
        """Calculate the 1/f spectral slope."""
        # Use frequencies between 1 and 40 Hz to calculate the slope
        mask = np.logical_and(freqs >= 1, freqs <= 40)
        
        if not np.any(mask):
            return None, None
            
        log_freqs = np.log10(freqs[mask])
        log_power = np.log10(power_spectrum[mask])
        
        # Linear regression to find the slope
        slope, intercept, r_value, p_value, std_err = stats.linregress(log_freqs, log_power)
        
        # Generate points for the regression line
        x_range = np.linspace(min(log_freqs), max(log_freqs), 100)
        y_fit = slope * x_range + intercept
        
        # Store the slope
        self.slopes[ch_idx] = slope
        
        return (log_freqs, log_power), (x_range, y_fit)
    
    def measure_impedance(self):
        """Get the latest impedance values from the device."""
        try:
            # Get impedance data from a different method
            data = self.board.get_current_board_data(256)
            
            if data.size == 0 or data.shape[1] == 0:
                return
                
            # For BrainBit, we need to access resistance channels with correct indexes
            for i, imp_ch in enumerate(self.impedance_channels):
                # Access the resistance channel if available
                if imp_ch < data.shape[0] and i < len(self.ch_names):
                    values = data[imp_ch]
                    # Filter out implausible values
                    valid_values = values[(values > 0) & (values < 500)]
                    if len(valid_values) > 0:
                        # Use median as it's more robust to outliers
                        self.impedance_values[i] = np.median(valid_values)
                    
            # Print current impedance values for debugging
            print(f"Current impedance values: {self.impedance_values}")
                        
            # Record for history
            timestamp = datetime.now().strftime('%H:%M:%S')
            self.impedance_history.append((timestamp, self.impedance_values.copy()))
            
            # Keep only last 100 measurements
            if len(self.impedance_history) > 100:
                self.impedance_history = self.impedance_history[-100:]
                
        except Exception as e:
            print(f"Error measuring impedance: {e}")
    
    def update(self, frame):
        """Update function for animation."""
        with self.lock:
            try:
                # Get latest data from board
                new_data = self.board.get_current_board_data(self.sampling_rate // 10)
                
                if new_data.size == 0 or new_data.shape[1] == 0:
                    return self.lines['eeg']  # Return just the EEG lines as a fallback
                
                current_time = time.time()
                
                # Measure impedance more often - every frame
                self.measure_impedance()
                
                # Update EEG buffers for each channel
                for i, ch in enumerate(self.eeg_channels):
                    channel_data = new_data[ch]
                    if len(channel_data) == 0:
                        continue
                        
                    # Update buffer with new data (sliding window)
                    if len(channel_data) < len(self.data_buffers[ch]):
                        self.data_buffers[ch] = np.roll(self.data_buffers[ch], -len(channel_data))
                        self.data_buffers[ch][-len(channel_data):] = channel_data
                    else:
                        # If we got more data than buffer size, just take the latest window_size worth
                        self.data_buffers[ch] = channel_data[-self.buffer_size:]
                    
                    # Apply detrending to each channel
                    DataFilter.detrend(self.data_buffers[ch], DetrendOperations.LINEAR.value)
                
                # Record data if recording is active
                if self.recording:
                    self.record_data.append([self.data_buffers[ch][-len(channel_data):] for ch in self.eeg_channels])
                    self.record_timestamps.append(current_time - self.record_start_time)
                
                # Update EEG signal plots
                for i, ch in enumerate(self.eeg_channels):
                    self.lines['eeg'][i].set_ydata(self.data_buffers[ch])
                    # Adjust y-axis limits for better visualization
                    data_range = self.data_buffers[ch]
                    amp = np.max(np.abs(data_range)) * 1.2  # Add 20% margin
                    self.axes['eeg'][i].set_ylim(-amp, amp)
                
                # Calculate and update spectra for all channels
                band_powers = {ch: {band: 0 for band in self.bands} for ch in self.eeg_channels}
                
                for i, ch in enumerate(self.eeg_channels):
                    # Calculate FFT
                    fft_data = np.fft.rfft(self.data_buffers[ch] * np.hamming(len(self.data_buffers[ch])))
                    fft_data = np.abs(fft_data[:len(self.freqs)]) ** 2  # Power spectrum
                    
                    # Convert to dB, avoiding log(0)
                    fft_data_db = 10 * np.log10(fft_data + 1e-10)
                    
                    # Update spectrum plot
                    self.lines['spectrum'][i].set_ydata(fft_data_db)
                    
                    # Calculate band powers
                    for band_name, (fmin, fmax) in self.bands.items():
                        idx = np.logical_and(self.freqs >= fmin, self.freqs <= fmax)
                        if np.any(idx):
                            band_power = np.mean(fft_data[idx])
                            band_powers[ch][band_name] = band_power
                    
                    # Update 1/f analysis plots
                    data_points, fit_line = self.calculate_1f_slope(self.freqs, fft_data, i)
                    
                    if data_points and fit_line:
                        # Update scatter plot
                        self.lines['1f'][i][0].set_offsets(np.column_stack(data_points))
                        
                        # Update regression line
                        self.lines['1f'][i][1].set_data(fit_line)
                    
                    # Store slope history (every 1 second)
                    if current_time - self.last_slope_update > self.slope_update_interval:
                        if i == 0:  # Only do this once per update cycle
                            self.last_slope_update = current_time
                            self.slope_time.append(current_time)
                            if len(self.slope_time) > 100:
                                self.slope_time = self.slope_time[-100:]
                        
                        if i in self.slopes:
                            self.slope_history[i].append(self.slopes[i])
                            if len(self.slope_history[i]) > 100:
                                self.slope_history[i] = self.slope_history[i][-100:]
                
                # Set reasonable limits for spectrum plot
                self.axes['spectrum'][0].set_ylim(-80, 0)
                
                # Set reasonable limits for 1/f plot
                self.axes['spectrum'][1].set_xlim(-0.1, 1.8)  # log10 of 1-40 Hz
                self.axes['spectrum'][1].set_ylim(-4, 4)      # Typical log power range
                
                # Update band power bar chart
                for i, ch in enumerate(self.eeg_channels):
                    # Get heights for bars
                    band_values = [10 * np.log10(band_powers[ch][band] + 1e-10) + 80 for band in self.bands]
                    
                    # Update heights
                    for j, bar in enumerate(self.lines['band_power'][i]):
                        bar.set_height(band_values[j])
                
                # Set reasonable limits for band power plot
                self.axes['band_power'].set_ylim(0, 60)
                
                # Update impedance plot if we have history
                if self.impedance_history:
                    times, values = zip(*self.impedance_history)
                    
                    for i, line in enumerate(self.lines['impedance']):
                        channel_values = [val[i] for val in values]
                        line.set_data(range(len(times)), channel_values)
                    
                    # Set reasonable axis limits
                    self.axes['impedance'].set_xlim(0, len(times))
                    max_imp = max([max([val[i] for val in values] or [0]) for i in range(len(self.ch_names))])
                    self.axes['impedance'].set_ylim(0, max_imp * 1.1 or 100)
                    
                    # Update x-axis labels periodically
                    if len(times) > 0 and frame % 30 == 0:
                        self.axes['impedance'].set_xticks(range(0, len(times), max(1, len(times)//5)))
                        self.axes['impedance'].set_xticklabels([times[i] for i in range(0, len(times), max(1, len(times)//5))])
                    
                    # Update text display with current values
                    imp_text = "Current Impedance (kΩ):\n"
                    for i, ch_name in enumerate(self.ch_names):
                        current_imp = self.impedance_values.get(i, 0)
                        quality = "Good" if current_imp < 100 else "Poor"
                        imp_text += f"{ch_name}: {current_imp:.1f} kΩ ({quality})\n"
                    self.impedance_text.set_text(imp_text)
                
                # Update 1/f slope history plot
                if self.slope_time:
                    x = range(len(self.slope_time))
                    
                    for i, line in enumerate(self.lines['slope_history']):
                        if self.slope_history[i]:
                            line.set_data(x[-len(self.slope_history[i]):], self.slope_history[i])
                    
                    # Set reasonable axis limits
                    self.axes['slope_history'].set_xlim(0, max(10, len(self.slope_time)))
                    min_slope = min([min(slopes or [0]) for slopes in self.slope_history.values()])
                    max_slope = max([max(slopes or [0]) for slopes in self.slope_history.values()])
                    margin = max(0.5, (max_slope - min_slope) * 0.1)
                    self.axes['slope_history'].set_ylim(min_slope - margin, max_slope + margin)
                
                # Add dominant band info
                if frame % 10 == 0:
                    # Find dominant band for each channel
                    dominant_bands = {}
                    for i, ch in enumerate(self.eeg_channels):
                        ch_name = self.ch_names[i]
                        max_band = max(band_powers[ch].items(), key=lambda x: x[1])[0]
                        dominant_bands[ch_name] = max_band
                    
                    # Update title with dominant bands
                    info_text = "  ".join([f"{ch}: {band}" for ch, band in dominant_bands.items()])
                    self.fig.suptitle(f"BrainBit Advanced Monitor - {datetime.now().strftime('%H:%M:%S')}\nDominant Bands: {info_text}", 
                                     fontsize=14)
                
                # Return just the EEG lines for safe animation update
                return self.lines['eeg']
            
            except Exception as e:
                print(f"Error updating plots: {e}")
                import traceback
                traceback.print_exc()
                return self.lines['eeg'] if 'eeg' in self.lines else []
    
    def run(self):
        """Run the advanced monitor."""
        if self.board is None:
            self.connect()
        
        self.setup_display()
        
        # Set up the animation with more robust settings
        self.animation = FuncAnimation(
            self.fig, self.update, interval=self.update_interval, 
            blit=False, cache_frame_data=False  # Disable blitting for more stability
        )
        
        # Show the plot
        plt.show()
    
    def stop(self):
        """Stop data acquisition and release resources."""
        if self.recording:
            self._stop_recording()
            
        if self.board:
            try:
                self.board.stop_stream()
                self.board.release_session()
                print("BrainBit disconnected")
            except Exception as e:
                print(f"Error disconnecting: {e}")

def main():
    monitor = BrainBitAdvancedMonitor(window_size=10, update_interval=100)
    
    try:
        monitor.run()
    except KeyboardInterrupt:
        print("Monitor interrupted by user")
    finally:
        monitor.stop()
        print("Monitor stopped")

if __name__ == "__main__":
    main()
