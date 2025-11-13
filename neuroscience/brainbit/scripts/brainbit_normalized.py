#!/usr/bin/env python3
"""
BrainBit Normalized Monitor

Shows real-time EEG signals with each channel normalized to its own maximum amplitude,
plus power spectral density and 1/f analysis.
"""

import time
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import matplotlib.gridspec as gridspec
from scipy import signal
import threading

# BrainFlow imports
import brainflow
from brainflow.board_shim import BoardShim, BrainFlowInputParams, BoardIds, LogLevels
from brainflow.data_filter import DataFilter, FilterTypes, DetrendOperations

class BrainBitNormalizedMonitor:
    def __init__(self, window_size=5, update_interval=100):
        self.window_size = window_size
        self.update_interval = update_interval
        self.board = None
        self.board_id = None
        self.sampling_rate = None
        self.buffer_size = None
        self.eeg_channels = None
        self.ch_names = None
        
        # Data buffers
        self.buffers = {}
        self.filtered_buffers = {}
        
        # For plotting
        self.fig = None
        self.gs = None
        self.axes = {}
        self.lines = {}
        self.psd_lines = {}
        self.loglog_lines = {}
        self.text_elements = {}
        self.animation = None
        self.timestamp = None
        
        # Spectral analysis
        self.freq_bands = {
            'Delta': (0.5, 4),
            'Theta': (4, 8),
            'Alpha': (8, 13),
            'Beta': (13, 30),
            'Gamma': (30, 50)
        }
        
        # Signal processing parameters
        self.notch_freq = 60  # Hz (for power line noise)
        self.bandpass_low = 1  # Hz (high-pass cutoff)
        self.bandpass_high = 30  # Hz (low-pass cutoff)
        
        # For thread safety
        self.lock = threading.Lock()
        
        # Colors for plots
        self.colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728']  # blue, orange, green, red
    
    def connect(self):
        """Connect to BrainBit device."""
        params = BrainFlowInputParams()
        
        # Set log level
        BoardShim.enable_dev_board_logger()
        BoardShim.set_log_level(LogLevels.LEVEL_INFO.value)
        
        try:
            print("Attempting to connect to BrainBit...")
            board = BoardShim(BoardIds.BRAINBIT_BOARD, params)
            board.prepare_session()
            self.board = board
            self.board_id = BoardIds.BRAINBIT_BOARD
            print("Successfully connected to BrainBit!")
        except brainflow.board_shim.BrainFlowError as e:
            print(f"Failed to connect to BrainBit: {e}")
            try:
                print("Attempting to connect to BrainBit BLED...")
                board = BoardShim(BoardIds.BRAINBIT_BLED_BOARD, params)
                board.prepare_session()
                self.board = board
                self.board_id = BoardIds.BRAINBIT_BLED_BOARD
                print("Successfully connected to BrainBit BLED!")
            except brainflow.board_shim.BrainFlowError as e2:
                print(f"Failed to connect to BrainBit BLED: {e2}")
                raise ConnectionError("Could not connect to any BrainBit device")
        
        # Get device info
        self.sampling_rate = BoardShim.get_sampling_rate(self.board_id)
        self.eeg_channels = BoardShim.get_eeg_channels(self.board_id)
        self.ch_names = BoardShim.get_eeg_names(self.board_id)
        
        print(f"EEG Channels: {self.ch_names}")
        print(f"Sampling Rate: {self.sampling_rate} Hz")
        
        self.buffer_size = int(self.sampling_rate * self.window_size)
        
        # Initialize data buffers for all channels
        for ch in self.eeg_channels:
            self.buffers[ch] = np.zeros(self.buffer_size)
            self.filtered_buffers[ch] = np.zeros(self.buffer_size)
        
        # Start data stream
        self.board.start_stream()
        print("Data streaming started")
        
        # Wait to collect some initial data
        time.sleep(1)
        
        return True
    
    def apply_filters(self, data):
        """Apply filters to EEG data."""
        filtered = np.copy(data)
        
        try:
            # Remove DC offset
            DataFilter.detrend(filtered, DetrendOperations.CONSTANT.value)
            
            # Apply a notch filter at 50/60 Hz to remove power line noise
            DataFilter.perform_bandstop(filtered, self.sampling_rate,
                                      self.notch_freq - 2, self.notch_freq + 2, 
                                      2, FilterTypes.BUTTERWORTH.value, 0)
            
            # Apply bandpass filter to keep only relevant brain frequencies
            DataFilter.perform_bandpass(filtered, self.sampling_rate,
                                      self.bandpass_low, self.bandpass_high,
                                      2, FilterTypes.BUTTERWORTH.value, 0)
        except Exception as e:
            print(f"Error in filtering: {e}")
        
        return filtered
    
    def compute_psd(self, data):
        """Compute power spectral density for given data."""
        if np.all(data == 0):
            return None, None
        
        # Use scipy's welch method
        freqs, psd = signal.welch(
            data, fs=self.sampling_rate, nperseg=min(256, len(data)),
            scaling='density', detrend='constant'
        )
        
        return freqs, psd
    
    def fit_power_law(self, freqs, psd, freq_range=(2, 50)):
        """
        Fit a power law (1/f^α) to the PSD.
        Returns (offset, alpha) where PSD ≈ offset * f^(-alpha)
        """
        if freqs is None or psd is None:
            return None
        
        # Skip DC component (zero frequency)
        mask = freqs > 0
        
        # Apply frequency range filter if specified
        if freq_range is not None:
            low, high = freq_range
            mask = mask & (freqs >= low) & (freqs <= high)
        
        if not np.any(mask):
            return None
        
        # Get log-log values for linear fitting
        log_freqs = np.log10(freqs[mask])
        log_psd = np.log10(psd[mask])
        
        # Linear fit (y = mx + b) where m = -alpha and b = log10(offset)
        if len(log_freqs) > 1:  # Need at least 2 points for fitting
            coeffs = np.polyfit(log_freqs, log_psd, 1)
            slope, intercept = coeffs
            alpha = -slope  # Negative slope gives positive alpha
            offset = 10 ** intercept
            
            return offset, alpha
        
        return None
    
    def calculate_band_powers(self, psd, freqs):
        """Calculate power in each frequency band."""
        band_powers = {}
        
        for band_name, (low_freq, high_freq) in self.freq_bands.items():
            # Find indices corresponding to this band
            band_mask = (freqs >= low_freq) & (freqs <= high_freq)
            
            if np.any(band_mask):
                # Calculate average power in this band
                band_powers[band_name] = np.mean(psd[band_mask])
            else:
                band_powers[band_name] = 0
        
        return band_powers
    
    def setup_display(self):
        """Set up the visualization display."""
        # Create figure
        self.fig = plt.figure(figsize=(16, 10))
        self.fig.canvas.manager.set_window_title('BrainBit Normalized Monitor')
        
        # Number of channels
        n_channels = len(self.eeg_channels)
        
        # Create grid layout for the figure
        self.gs = gridspec.GridSpec(n_channels, 3, width_ratios=[3, 1, 1], height_ratios=[1] * n_channels)
        
        # Initialize axes for EEG and spectral analysis
        self.axes['eeg'] = []
        self.axes['psd'] = []
        self.axes['loglog'] = []
        
        # Create timestamp for time domain plots
        self.timestamp = np.linspace(-self.window_size, 0, self.buffer_size)
        
        # Initialize line collections for all plots
        self.lines['eeg_raw'] = []
        self.lines['eeg_filtered'] = []
        self.psd_lines = []
        self.loglog_lines = {'data': [], 'fit': []}
        self.text_elements = []
        
        # Setup plots for each channel
        for i, ch in enumerate(self.eeg_channels):
            ch_name = self.ch_names[i]
            
            # EEG time domain plot
            ax_eeg = self.fig.add_subplot(self.gs[i, 0])
            self.axes['eeg'].append(ax_eeg)
            ax_eeg.set_title(f'EEG Signal - {ch_name} (Normalized)')
            ax_eeg.set_ylabel('Amplitude')
            ax_eeg.grid(True)
            
            if i == n_channels - 1:  # Only add x-label to bottom plot
                ax_eeg.set_xlabel('Time (s)')
            
            # Set y-limits for normalized signals
            ax_eeg.set_ylim(-120, 120)
            
            # Create lines for raw and filtered EEG
            raw_line, = ax_eeg.plot(
                self.timestamp, np.zeros(self.buffer_size),
                color=self.colors[i % len(self.colors)], alpha=0.3, linewidth=1
            )
            filtered_line, = ax_eeg.plot(
                self.timestamp, np.zeros(self.buffer_size),
                color=self.colors[i % len(self.colors)], linewidth=1.5
            )
            
            self.lines['eeg_raw'].append(raw_line)
            self.lines['eeg_filtered'].append(filtered_line)
            
            # PSD plot
            ax_psd = self.fig.add_subplot(self.gs[i, 1])
            self.axes['psd'].append(ax_psd)
            ax_psd.set_title(f'PSD - {ch_name}')
            if i == n_channels - 1:
                ax_psd.set_xlabel('Frequency (Hz)')
            ax_psd.set_ylabel('Power')
            ax_psd.grid(True)
            
            # Create PSD line
            psd_line, = ax_psd.plot(
                [], [], color=self.colors[i % len(self.colors)], linewidth=1.5
            )
            self.psd_lines.append(psd_line)
            
            # Log-log plot for 1/f analysis
            ax_loglog = self.fig.add_subplot(self.gs[i, 2])
            self.axes['loglog'].append(ax_loglog)
            ax_loglog.set_title(f'1/f Analysis - {ch_name}')
            if i == n_channels - 1:
                ax_loglog.set_xlabel('Log Frequency (Hz)')
            ax_loglog.set_ylabel('Log Power')
            ax_loglog.set_xscale('log')
            ax_loglog.set_yscale('log')
            ax_loglog.set_xlim(1, 100)
            ax_loglog.grid(True)
            
            # Create log-log lines for data and fit
            loglog_data, = ax_loglog.plot(
                [], [], 'o', color=self.colors[i % len(self.colors)],
                markersize=2, alpha=0.7
            )
            loglog_fit, = ax_loglog.plot(
                [], [], 'r--', linewidth=1.5
            )
            
            self.loglog_lines['data'].append(loglog_data)
            self.loglog_lines['fit'].append(loglog_fit)
            
            # Add text for power law parameters
            text = ax_loglog.text(
                0.05, 0.95, "", transform=ax_loglog.transAxes,
                fontsize=9, verticalalignment='top',
                bbox=dict(facecolor='white', alpha=0.7, boxstyle='round')
            )
            self.text_elements.append(text)
        
        # Add key binding for quit
        self.fig.canvas.mpl_connect('key_press_event', self.on_key_press)
        
        # Status text
        self.status_text = self.fig.suptitle(
            "BrainBit Normalized Monitor - Press 'Q' to quit",
            fontsize=12
        )
        
        # Adjust layout
        self.fig.tight_layout()
        self.fig.subplots_adjust(top=0.95)
    
    def update(self, frame):
        """Update function for animation."""
        with self.lock:
            try:
                # Get latest data from board
                new_data = self.board.get_current_board_data(self.sampling_rate // 5)
                
                if new_data.size == 0 or new_data.shape[1] == 0:
                    return []
                
                # Elements to update in animation
                elements_to_update = []
                
                # Process each channel
                for i, ch in enumerate(self.eeg_channels):
                    if ch >= new_data.shape[0]:
                        continue
                    
                    # Get channel data
                    channel_data = new_data[ch]
                    if len(channel_data) == 0:
                        continue
                    
                    # Update buffer with new data (sliding window)
                    if len(channel_data) < len(self.buffers[ch]):
                        self.buffers[ch] = np.roll(self.buffers[ch], -len(channel_data))
                        self.buffers[ch][-len(channel_data):] = channel_data
                    else:
                        # If we got more data than buffer size, just take the latest window_size worth
                        self.buffers[ch] = channel_data[-self.buffer_size:]
                    
                    # Apply filtering
                    self.filtered_buffers[ch] = self.apply_filters(self.buffers[ch])
                    
                    # Normalize signals for display
                    raw_max = np.max(np.abs(self.buffers[ch]))
                    filtered_max = np.max(np.abs(self.filtered_buffers[ch]))
                    
                    # Avoid division by zero
                    if raw_max > 0 and filtered_max > 0:
                        # Normalize each signal to its own maximum
                        normalized_raw = (self.buffers[ch] / raw_max) * 100
                        normalized_filtered = (self.filtered_buffers[ch] / filtered_max) * 100
                        
                        # Update EEG plots
                        self.lines['eeg_raw'][i].set_ydata(normalized_raw)
                        self.lines['eeg_filtered'][i].set_ydata(normalized_filtered)
                        
                        elements_to_update.extend([self.lines['eeg_raw'][i], self.lines['eeg_filtered'][i]])
                    
                    # Update spectral plots (no conditional - update every frame for smoother appearance)
                    # Power Spectral Density
                    freqs, psd = self.compute_psd(self.filtered_buffers[ch])
                    
                    if freqs is not None and psd is not None:
                        # Update PSD plot
                        self.psd_lines[i].set_data(freqs, psd)
                        
                        # Only update axis limits on first few frames or occasionally
                        if frame < 10 or frame % 30 == 0:
                            self.axes['psd'][i].set_xlim(0, min(100, freqs[-1]))
                            if np.max(psd) > 0:
                                psd_max = np.max(psd) * 1.1
                                # Smooth the max limit change
                                current_ylim = self.axes['psd'][i].get_ylim()[1]
                                if current_ylim == 1:  # Initial setting
                                    self.axes['psd'][i].set_ylim(0, psd_max)
                                else:
                                    # Smooth transition of y-limit
                                    new_max = 0.9 * current_ylim + 0.1 * psd_max
                                    self.axes['psd'][i].set_ylim(0, new_max)
                        
                        elements_to_update.append(self.psd_lines[i])
                        
                        # Update log-log plot
                        mask = freqs > 0  # Skip DC component for log scale
                        self.loglog_lines['data'][i].set_data(freqs[mask], psd[mask])
                        elements_to_update.append(self.loglog_lines['data'][i])
                        
                        # Fit power law
                        fit_result = self.fit_power_law(freqs, psd)
                        
                        if fit_result is not None:
                            offset, alpha = fit_result
                            
                            # Generate predicted values for visualization
                            pred_freqs = np.logspace(np.log10(1), np.log10(100), 100)
                            pred_psd = offset * pred_freqs ** (-alpha)
                            
                            # Update fit line
                            self.loglog_lines['fit'][i].set_data(pred_freqs, pred_psd)
                            elements_to_update.append(self.loglog_lines['fit'][i])
                            
                            # Calculate band powers
                            band_powers = self.calculate_band_powers(psd, freqs)
                            
                            # Find dominant band
                            if band_powers:
                                dominant_band = max(band_powers.items(), key=lambda x: x[1])[0]
                                
                                # Update text with power law and band powers
                                info_text = f"1/f^α: α = {alpha:.2f}\n"
                                info_text += f"Dominant: {dominant_band}\n"
                                
                                # Format band powers
                                for band, power in band_powers.items():
                                    if band == dominant_band:
                                        info_text += f"{band}: {power:.1f} ←\n"
                                    else:
                                        info_text += f"{band}: {power:.1f}\n"
                                
                                self.text_elements[i].set_text(info_text)
                                elements_to_update.append(self.text_elements[i])
                
                # Return everything even though we're not using blitting
                return elements_to_update
            
            except Exception as e:
                print(f"Error in update: {e}")
                import traceback
                traceback.print_exc()
                return []
    
    def on_key_press(self, event):
        """Handle key press events."""
        if event.key == 'q':
            plt.close(self.fig)
    
    def run(self):
        """Run the monitor."""
        if self.board is None:
            self.connect()
        
        self.setup_display()
        
        # Set up the animation
        self.animation = FuncAnimation(
            self.fig, self.update, interval=self.update_interval, 
            blit=False, cache_frame_data=False  # Disable blitting to fix blinking
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
    monitor = BrainBitNormalizedMonitor(window_size=5, update_interval=100)
    
    try:
        monitor.run()
    except KeyboardInterrupt:
        print("Monitor interrupted by user")
    finally:
        monitor.stop()
        print("Monitor stopped")

if __name__ == "__main__":
    main()
