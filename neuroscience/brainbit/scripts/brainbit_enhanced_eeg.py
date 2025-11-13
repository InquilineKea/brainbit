#!/usr/bin/env python3
"""
BrainBit Enhanced EEG Monitor

Features:
- Advanced filtering for cleaner EEG signals
- Artifact detection and rejection
- SNR optimization
- Enhanced spectral visualization
"""

import time
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from scipy import signal
from datetime import datetime
import threading

# BrainFlow imports
import brainflow
from brainflow.board_shim import BoardShim, BrainFlowInputParams, BoardIds, LogLevels
from brainflow.data_filter import DataFilter, FilterTypes, DetrendOperations, NoiseTypes

class BrainBitEnhancedEEG:
    def __init__(self, window_size=10, update_interval=100):
        self.window_size = window_size
        self.update_interval = update_interval
        self.board = None
        self.board_id = None
        self.sampling_rate = None
        self.buffer_size = None
        self.eeg_channels = None
        self.ch_names = None
        
        # Signal processing parameters
        self.notch_freq = 60  # Hz (for power line noise)
        self.bandpass_low = 1  # Hz (high-pass cutoff)
        self.bandpass_high = 40  # Hz (low-pass cutoff)
        self.filter_order = 4
        
        # Data buffers
        self.raw_buffers = None
        self.filtered_buffers = None
        self.artifact_mask = None
        self.signal_quality = None
        
        # For plotting
        self.fig = None
        self.axes = None
        self.lines = {}
        self.timestamp = None
        self.animation = None
        
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
        
        # For recording
        self.recording = False
        self.record_data = []
        self.record_timestamps = []
        self.record_start_time = None
    
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
        self.ch_names = BoardShim.get_eeg_names(self.board_id)
        
        print(f"EEG Channels: {self.ch_names}")
        print(f"Sampling Rate: {self.sampling_rate} Hz")
        
        self.buffer_size = int(self.sampling_rate * self.window_size)
        
        # Initialize data buffers for all channels
        self.raw_buffers = {ch: np.zeros(self.buffer_size) for ch in self.eeg_channels}
        self.filtered_buffers = {ch: np.zeros(self.buffer_size) for ch in self.eeg_channels}
        self.artifact_mask = np.zeros(self.buffer_size, dtype=bool)
        self.signal_quality = {ch: 0 for ch in self.eeg_channels}
        
        # Start data stream
        self.board.start_stream()
        print("Data streaming started")
        
        return True
    
    def apply_filters(self, data):
        """Apply advanced filtering to EEG data."""
        # Make a copy to avoid modifying original data
        filtered = np.copy(data)
        
        try:
            # Remove DC offset
            DataFilter.detrend(filtered, DetrendOperations.CONSTANT.value)
            
            # Apply a notch filter at 50/60 Hz to remove power line noise
            DataFilter.perform_bandstop(filtered, self.sampling_rate,
                                      self.notch_freq, 4.0, 
                                      self.filter_order,
                                      FilterTypes.BUTTERWORTH.value, 0)
            
            # Apply bandpass filter to keep only relevant brain frequencies
            DataFilter.perform_bandpass(filtered, self.sampling_rate,
                                      self.bandpass_low, self.bandpass_high,
                                      self.filter_order,
                                      FilterTypes.BUTTERWORTH.value, 0)
            
            # Apply additional smoothing if needed
            DataFilter.perform_rolling_filter(filtered, 3, FilterTypes.ROLLING_MEAN.value)
        
        except Exception as e:
            print(f"Error in filtering: {e}")
        
        return filtered
    
    def detect_artifacts(self, data, threshold_std=2.5):
        """
        Detect artifacts in EEG data.
        Returns a boolean mask where True indicates an artifact.
        """
        # Basic amplitude thresholding
        std = np.std(data)
        mean = np.mean(data)
        threshold = threshold_std * std
        
        # Mark samples that exceed threshold as artifacts
        artifacts = np.abs(data - mean) > threshold
        
        # Use morphological operations to fill small gaps and remove isolated points
        if np.any(artifacts):
            # Fill small gaps (less than 100ms)
            gap_fill_samples = int(0.1 * self.sampling_rate)
            for i in range(len(artifacts) - gap_fill_samples):
                if artifacts[i] and artifacts[i + gap_fill_samples]:
                    artifacts[i:i + gap_fill_samples] = True
        
        return artifacts
    
    def calculate_signal_quality(self, data, artifacts):
        """
        Calculate signal quality metrics (0-100%).
        100% means perfect signal, 0% means unusable.
        """
        if len(data) == 0:
            return 0
        
        # Percentage of non-artifact data
        artifact_percent = np.mean(artifacts) * 100
        
        # Signal-to-noise ratio estimation
        # Use frequency domain analysis to estimate SNR
        # Assuming brain signals are mainly 1-30 Hz, and noise is outside this range
        try:
            fft_data = np.fft.rfft(data)
            freqs = np.fft.rfftfreq(len(data), 1.0/self.sampling_rate)
            
            # Identify signal and noise bands
            signal_mask = (freqs >= 1) & (freqs <= 30)
            noise_mask = ~signal_mask & (freqs > 0)  # Exclude DC
            
            # Calculate power in signal and noise bands
            signal_power = np.sum(np.abs(fft_data[signal_mask]) ** 2)
            noise_power = np.sum(np.abs(fft_data[noise_mask]) ** 2) if np.any(noise_mask) else 1e-10
            
            # Calculate SNR in dB
            snr_db = 10 * np.log10(signal_power / noise_power) if noise_power > 0 else 30
            
            # Convert to percentage (assuming 20dB is excellent, 0dB is poor)
            snr_percent = min(100, max(0, (snr_db / 20) * 100))
            
            # Combine artifact and SNR metrics
            quality = (100 - artifact_percent) * 0.7 + snr_percent * 0.3
            
            return min(100, max(0, quality))
        
        except Exception as e:
            print(f"Error calculating signal quality: {e}")
            return 50  # Default to medium quality on error
    
    def setup_display(self):
        """Set up the visualization display."""
        # Create figure and subplots
        self.fig = plt.figure(figsize=(14, 10))
        self.fig.canvas.manager.set_window_title('BrainBit Enhanced EEG Monitor')
        
        # Create 3 rows of plots: 
        # 1. EEG signals (4 channels)
        # 2. Spectrogram (4 channels)
        # 3. Band power/SNR (1 panel)
        
        # Create grid for plots
        gs = plt.GridSpec(6, 4, figure=self.fig)
        
        # EEG signal plots (raw and filtered overlaid)
        self.axes = {}
        self.axes['eeg'] = []
        
        for i, ch_idx in enumerate(self.eeg_channels):
            # Create axis for this channel
            ax = self.fig.add_subplot(gs[i // 2, (i % 2) * 2:((i % 2) + 1) * 2])
            self.axes['eeg'].append(ax)
            
            # Set up axis
            ch_name = self.ch_names[i]
            ax.set_title(f'EEG Signal - {ch_name}')
            ax.set_xlabel('Time (s)')
            ax.set_ylabel('Amplitude (μV)')
            ax.grid(True)
        
        # Spectrograms
        self.axes['spectrograms'] = []
        for i, ch_idx in enumerate(self.eeg_channels):
            # Create axis for this channel's spectrogram
            ax = self.fig.add_subplot(gs[2 + i // 2, (i % 2) * 2:((i % 2) + 1) * 2])
            self.axes['spectrograms'].append(ax)
            
            # Set up axis
            ch_name = self.ch_names[i]
            ax.set_title(f'Spectrogram - {ch_name}')
            ax.set_xlabel('Time (s)')
            ax.set_ylabel('Frequency (Hz)')
        
        # Band power
        self.axes['band_power'] = self.fig.add_subplot(gs[4:6, :])
        self.axes['band_power'].set_title('EEG Band Power')
        self.axes['band_power'].set_xlabel('Frequency Band')
        self.axes['band_power'].set_ylabel('Relative Power')
        self.axes['band_power'].grid(True)
        
        # Create x-axis for time domain plots
        self.timestamp = np.linspace(-self.window_size, 0, self.buffer_size)
        
        # Initialize lines for EEG plots
        self.lines['eeg_raw'] = []
        self.lines['eeg_filtered'] = []
        self.lines['eeg_artifacts'] = []
        self.lines['quality_indicators'] = []
        
        for i, ax in enumerate(self.axes['eeg']):
            # Raw EEG line (light color)
            raw_line, = ax.plot(self.timestamp, np.zeros(self.buffer_size), 
                               color=self.channel_colors[i], alpha=0.3, linewidth=1)
            self.lines['eeg_raw'].append(raw_line)
            
            # Filtered EEG line (solid color)
            filtered_line, = ax.plot(self.timestamp, np.zeros(self.buffer_size), 
                                   color=self.channel_colors[i], linewidth=1.5)
            self.lines['eeg_filtered'].append(filtered_line)
            
            # Artifact highlighting
            artifact_line, = ax.plot([], [], 'r.', markersize=4, alpha=0.5)
            self.lines['eeg_artifacts'].append(artifact_line)
            
            # Signal quality indicator
            quality_text = ax.text(0.05, 0.95, "Quality: ---%", 
                                 transform=ax.transAxes, fontsize=10,
                                 verticalalignment='top',
                                 bbox=dict(boxstyle='round', facecolor='white', alpha=0.5))
            self.lines['quality_indicators'].append(quality_text)
        
        # Initialize spectrograms
        self.spectrograms = []
        for i, ax in enumerate(self.axes['spectrograms']):
            spec = ax.imshow(np.zeros((50, self.buffer_size // 10)), 
                           aspect='auto', cmap='viridis', origin='lower')
            self.spectrograms.append(spec)
            
            # Add colorbar
            cbar = plt.colorbar(spec, ax=ax)
            cbar.set_label('Power (dB)')
        
        # Initialize bar chart for band powers
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
        
        # Global status indicator
        self.status_text = self.fig.text(0.5, 0.01, "BrainBit EEG Signal Enhancement Active", 
                                       ha='center', fontsize=12,
                                       bbox=dict(boxstyle='round', facecolor='white', alpha=0.7))
        
        # Add key bindings
        self.fig.canvas.mpl_connect('key_press_event', self._on_key_press)
        
        # Adjust layout
        plt.tight_layout()
        self.fig.subplots_adjust(hspace=0.3, wspace=0.3, bottom=0.05)
    
    def _on_key_press(self, event):
        """Handle keyboard commands."""
        if event.key == 'r' and not self.recording:
            self._start_recording()
        elif event.key == 's' and self.recording:
            self._stop_recording()
        elif event.key == 'q':
            plt.close(self.fig)
        elif event.key == 'f':
            # Toggle between filter settings
            if self.bandpass_high == 40:
                self.bandpass_high = 30
                self.filter_order = 2
                print("Filter settings changed to gentle (1-30 Hz, order 2)")
            else:
                self.bandpass_high = 40
                self.filter_order = 4
                print("Filter settings changed to standard (1-40 Hz, order 4)")
    
    def _start_recording(self):
        """Start recording data."""
        self.recording = True
        self.record_data = []
        self.record_timestamps = []
        self.record_start_time = time.time()
        self.status_text.set_text("RECORDING - Press 'S' to stop")
        self.status_text.set_color('red')
        print("Recording started.")
    
    def _stop_recording(self):
        """Stop recording and save data."""
        if not self.recording:
            return
            
        self.recording = False
        self.status_text.set_text("BrainBit EEG Signal Enhancement Active (Press 'R' to record)")
        self.status_text.set_color('black')
        
        if self.record_data:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"brainbit_enhanced_{timestamp}.npz"
            
            np.savez(
                filename, 
                eeg_data=np.array(self.record_data),
                timestamps=np.array(self.record_timestamps),
                channel_names=self.ch_names,
                sampling_rate=self.sampling_rate
            )
            
            print(f"Recording saved to {filename}")
    
    def update_spectrogram(self, data, ch_idx):
        """Update spectrogram for a given channel."""
        # Calculate spectrogram
        # Use short windows with overlap for better time resolution
        window_size = min(256, len(data) // 5)  # Use smaller window for better time resolution
        overlap = window_size // 2
        
        # Calculate spectrogram
        f, t, Sxx = signal.spectrogram(data, fs=self.sampling_rate, 
                                     window='hanning', 
                                     nperseg=window_size, 
                                     noverlap=overlap,
                                     scaling='density')
        
        # Convert to dB scale (log10)
        Sxx_db = 10 * np.log10(Sxx + 1e-10)
        
        # Limit frequency range to 0-50 Hz
        mask = f <= 50
        f = f[mask]
        Sxx_db = Sxx_db[mask, :]
        
        # Update spectrogram
        self.spectrograms[ch_idx].set_data(Sxx_db)
        self.spectrograms[ch_idx].set_extent([self.timestamp[0], self.timestamp[-1], f[0], f[-1]])
        
        # Adjust colormap scale for better visualization
        vmin = np.percentile(Sxx_db, 5)
        vmax = np.percentile(Sxx_db, 95)
        self.spectrograms[ch_idx].set_clim(vmin, vmax)
        
        return Sxx_db, f, t
    
    def update(self, frame):
        """Update function for animation."""
        with self.lock:
            try:
                # Get latest data from board
                new_data = self.board.get_current_board_data(self.sampling_rate // 10)
                
                if new_data.size == 0 or new_data.shape[1] == 0:
                    return self.lines['eeg_filtered']
                
                current_time = time.time()
                
                # Process each channel
                band_powers = {ch: {band: 0 for band in self.bands} for ch in self.eeg_channels}
                
                for i, ch in enumerate(self.eeg_channels):
                    # Get channel data
                    channel_data = new_data[ch]
                    if len(channel_data) == 0:
                        continue
                    
                    # Update raw buffer with new data (sliding window)
                    if len(channel_data) < len(self.raw_buffers[ch]):
                        self.raw_buffers[ch] = np.roll(self.raw_buffers[ch], -len(channel_data))
                        self.raw_buffers[ch][-len(channel_data):] = channel_data
                    else:
                        # If we got more data than buffer size, just take the latest window_size worth
                        self.raw_buffers[ch] = channel_data[-self.buffer_size:]
                    
                    # Apply filtering
                    self.filtered_buffers[ch] = self.apply_filters(self.raw_buffers[ch])
                    
                    # Detect artifacts
                    artifacts = self.detect_artifacts(self.filtered_buffers[ch])
                    artifact_indices = np.where(artifacts)[0]
                    
                    # Calculate signal quality
                    quality = self.calculate_signal_quality(self.filtered_buffers[ch], artifacts)
                    self.signal_quality[ch] = quality
                    
                    # Record data if recording is active
                    if self.recording:
                        self.record_data.append(self.filtered_buffers[ch][-len(channel_data):])
                        if i == 0:  # Only add timestamp once per channel group
                            self.record_timestamps.append(current_time - self.record_start_time)
                    
                    # Update raw EEG line
                    self.lines['eeg_raw'][i].set_ydata(self.raw_buffers[ch])
                    
                    # Update filtered EEG line
                    self.lines['eeg_filtered'][i].set_ydata(self.filtered_buffers[ch])
                    
                    # Update artifact markers
                    if len(artifact_indices) > 0:
                        self.lines['eeg_artifacts'][i].set_data(
                            self.timestamp[artifact_indices],
                            self.filtered_buffers[ch][artifact_indices]
                        )
                    else:
                        self.lines['eeg_artifacts'][i].set_data([], [])
                    
                    # Update quality indicator
                    color = 'green' if quality > 80 else 'orange' if quality > 50 else 'red'
                    self.lines['quality_indicators'][i].set_text(f"Quality: {quality:.1f}%")
                    self.lines['quality_indicators'][i].set_bbox(dict(
                        boxstyle='round', facecolor='white', 
                        alpha=0.5, edgecolor=color, linewidth=2
                    ))
                    
                    # Update spectrogram
                    self.update_spectrogram(self.filtered_buffers[ch], i)
                    
                    # Adjust y-axis limits for better visualization
                    data_range = self.filtered_buffers[ch]
                    amp = np.max(np.abs(data_range)) * 1.2  # Add 20% margin
                    self.axes['eeg'][i].set_ylim(-amp, amp)
                    
                    # Calculate band powers for bar chart
                    try:
                        # Calculate FFT
                        fft_data = np.fft.rfft(self.filtered_buffers[ch] * np.hamming(len(self.filtered_buffers[ch])))
                        freqs = np.fft.rfftfreq(len(self.filtered_buffers[ch]), 1.0/self.sampling_rate)
                        fft_data = np.abs(fft_data) ** 2  # Power spectrum
                        
                        # Calculate band powers
                        for band_name, (fmin, fmax) in self.bands.items():
                            idx = np.logical_and(freqs >= fmin, freqs <= fmax)
                            if np.any(idx):
                                band_power = np.mean(fft_data[idx])
                                band_powers[ch][band_name] = band_power
                    except Exception as e:
                        print(f"Error calculating band powers: {e}")
                
                # Update band power bar chart
                for i, ch in enumerate(self.eeg_channels):
                    # Get heights for bars
                    band_values = [10 * np.log10(band_powers[ch][band] + 1e-10) + 80 for band in self.bands]
                    
                    # Update heights
                    for j, bar in enumerate(self.lines['band_power'][i]):
                        bar.set_height(band_values[j])
                
                # Set reasonable limits for band power plot
                self.axes['band_power'].set_ylim(0, 60)
                
                # Update status text with quality overview
                if frame % 10 == 0:  # Update only occasionally for better performance
                    avg_quality = np.mean([self.signal_quality[ch] for ch in self.eeg_channels])
                    quality_status = "Excellent" if avg_quality > 80 else "Good" if avg_quality > 65 else "Fair" if avg_quality > 50 else "Poor"
                    self.status_text.set_text(f"Signal Quality: {quality_status} ({avg_quality:.1f}%) | Press 'F' to change filters, 'R' to record")
                
                # Return just the filtered EEG lines for animation update
                return self.lines['eeg_filtered']
            
            except Exception as e:
                print(f"Error updating plots: {e}")
                import traceback
                traceback.print_exc()
                return self.lines['eeg_filtered'] if 'eeg_filtered' in self.lines else []
    
    def run(self):
        """Run the enhanced EEG monitor."""
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
    monitor = BrainBitEnhancedEEG(window_size=10, update_interval=100)
    
    try:
        monitor.run()
    except KeyboardInterrupt:
        print("Monitor interrupted by user")
    finally:
        monitor.stop()
        print("Monitor stopped")

if __name__ == "__main__":
    main()
