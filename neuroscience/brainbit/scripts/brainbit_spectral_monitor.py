#!/usr/bin/env python3
"""
BrainBit Spectral Monitor with 1/f Analysis

A multi-page EEG monitor that shows:
1. Raw and filtered EEG signals (Page 1)
2. Power spectral density and 1/f analysis (Page 2)
"""

import time
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from scipy import signal
import threading
import tkinter as tk
from tkinter import ttk

# BrainFlow imports
import brainflow
from brainflow.board_shim import BoardShim, BrainFlowInputParams, BoardIds, LogLevels
from brainflow.data_filter import DataFilter, FilterTypes, DetrendOperations, WindowOperations

class SpectrumAnalyzer:
    """Helper class for spectrum analysis and 1/f power law fitting."""
    
    def __init__(self, data=None, sampling_rate=250):
        self.data = data
        self.sampling_rate = sampling_rate
        self.freqs = None
        self.psd = None
        self.power_law_params = None
    
    def compute_psd(self, data=None, nperseg=None, scaling='density'):
        """Compute power spectral density."""
        if data is not None:
            self.data = data
        
        if self.data is None:
            return None
        
        if nperseg is None:
            nperseg = min(256, len(self.data))
        
        self.freqs, self.psd = signal.welch(
            self.data, fs=self.sampling_rate, nperseg=nperseg, 
            scaling=scaling, detrend='constant'
        )
        
        return self.freqs, self.psd
    
    def fit_power_law(self, freq_range=None):
        """
        Fit a power law (1/f^α) to the PSD.
        Returns (offset, alpha) where PSD ≈ offset * f^(-alpha)
        """
        if self.freqs is None or self.psd is None:
            return None
        
        # Skip DC component (zero frequency)
        mask = self.freqs > 0
        
        # Apply frequency range filter if specified
        if freq_range is not None:
            low, high = freq_range
            mask = mask & (self.freqs >= low) & (self.freqs <= high)
        
        if not np.any(mask):
            return None
        
        # Get log-log values for linear fitting
        log_freqs = np.log10(self.freqs[mask])
        log_psd = np.log10(self.psd[mask])
        
        # Linear fit (y = mx + b) where m = -alpha and b = log10(offset)
        if len(log_freqs) > 1:  # Need at least 2 points for fitting
            coeffs = np.polyfit(log_freqs, log_psd, 1)
            slope, intercept = coeffs
            alpha = -slope  # Negative slope gives positive alpha
            offset = 10 ** intercept
            
            self.power_law_params = (offset, alpha)
            return offset, alpha
        
        return None
    
    def get_predicted_psd(self):
        """Get the predicted PSD values based on the power law fit."""
        if self.freqs is None or self.power_law_params is None:
            return None
        
        offset, alpha = self.power_law_params
        
        # Skip DC component
        mask = self.freqs > 0
        predicted = np.zeros_like(self.freqs)
        predicted[mask] = offset * self.freqs[mask] ** (-alpha)
        
        return predicted


class BrainBitSpectralMonitor:
    def __init__(self, window_size=5, update_interval=100):
        self.window_size = window_size  # in seconds
        self.update_interval = update_interval  # in milliseconds
        self.board = None
        self.board_id = None
        self.sampling_rate = None
        self.buffer_size = None
        self.eeg_channels = None
        self.ch_names = None
        
        # For active channel detection
        self.active_channels = []
        self.activity_threshold = 10  # μV standard deviation threshold
        
        # Data buffers
        self.buffers = {}
        self.filtered_buffers = {}
        
        # Frequency analysis
        self.analyzers = {}
        self.psd_freqs = {}
        self.psd_values = {}
        self.power_law_fits = {}
        
        # For plotting
        self.root = None
        self.notebook = None
        self.frames = {}
        self.figs = {}
        self.axes = {}
        self.lines = {}
        self.psd_lines = {}
        self.fit_lines = {}
        self.text_elements = {}
        self.animations = {}
        self.timestamp = None
        
        # Signal processing parameters
        self.notch_freq = 60  # Hz (for power line noise)
        self.bandpass_low = 1  # Hz (high-pass cutoff)
        self.bandpass_high = 30  # Hz (low-pass cutoff)
        
        # For thread safety
        self.lock = threading.Lock()
        
        # Colors for plots
        self.colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728']  # blue, orange, green, red
        
        # Frequency bands
        self.freq_bands = {
            'Delta': (0.5, 4),
            'Theta': (4, 8),
            'Alpha': (8, 13),
            'Beta': (13, 30),
            'Gamma': (30, 50)
        }
    
    def connect(self):
        """Connect to BrainBit device."""
        params = BrainFlowInputParams()
        
        # Set log level
        BoardShim.enable_dev_board_logger()
        BoardShim.set_log_level(LogLevels.LEVEL_INFO.value)
        
        # Try both board types
        board_ids = [BoardIds.BRAINBIT_BOARD, BoardIds.BRAINBIT_BLED_BOARD]
        
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
        for ch in self.eeg_channels:
            self.buffers[ch] = np.zeros(self.buffer_size)
            self.filtered_buffers[ch] = np.zeros(self.buffer_size)
            self.analyzers[ch] = SpectrumAnalyzer(sampling_rate=self.sampling_rate)
        
        # Start data stream
        self.board.start_stream()
        print("Data streaming started")
        
        # Wait a moment to collect some data
        time.sleep(1)
        
        # Detect which channels are active
        self.detect_active_channels()
        
        return True
    
    def detect_active_channels(self):
        """Detect which channels have significant activity."""
        # Get some initial data
        data = self.board.get_current_board_data(100)
        
        if data.size == 0 or data.shape[1] == 0:
            # If no data yet, consider all channels active
            self.active_channels = list(range(len(self.eeg_channels)))
            return
        
        # Check each channel for activity
        self.active_channels = []
        for i, ch in enumerate(self.eeg_channels):
            if ch < data.shape[0]:
                channel_data = data[ch]
                std_dev = np.std(channel_data)
                
                print(f"Channel {self.ch_names[i]} has std_dev: {std_dev:.2f} μV")
                
                if std_dev > self.activity_threshold:
                    self.active_channels.append(i)
        
        if not self.active_channels:
            # If no active channels detected, show all
            self.active_channels = list(range(len(self.eeg_channels)))
        
        print(f"Active channels: {[self.ch_names[i] for i in self.active_channels]}")
    
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
        # Create root window
        self.root = tk.Tk()
        self.root.title("BrainBit Spectral Monitor")
        self.root.geometry("1200x800")
        
        # Create notebook (tabbed interface)
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        
        # Create frames for each page
        self.frames['eeg'] = ttk.Frame(self.notebook)
        self.frames['spectral'] = ttk.Frame(self.notebook)
        
        self.notebook.add(self.frames['eeg'], text="EEG Signals")
        self.notebook.add(self.frames['spectral'], text="Spectral Analysis")
        
        # Setup EEG page
        self.setup_eeg_page()
        
        # Setup Spectral page
        self.setup_spectral_page()
        
        # Add key binding for quit
        self.root.bind('<q>', lambda event: self.root.quit())
        
        # Add text status at bottom
        status_frame = ttk.Frame(self.root)
        status_frame.pack(fill=tk.X, side=tk.BOTTOM)
        
        self.status_label = ttk.Label(
            status_frame, 
            text="BrainBit Spectral Monitor - Press 'Q' to quit",
            anchor=tk.CENTER
        )
        self.status_label.pack(fill=tk.X)
    
    def setup_eeg_page(self):
        """Set up the EEG signals page."""
        # Calculate how many EEG channels to display
        num_active = len(self.active_channels)
        
        # Create figure for EEG
        self.figs['eeg'] = plt.Figure(figsize=(10, 6), dpi=100)
        
        # Create canvas for the figure
        canvas = FigureCanvasTkAgg(self.figs['eeg'], master=self.frames['eeg'])
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        # Create axes for EEG plots
        self.axes['eeg'] = []
        for i in range(num_active):
            ax = self.figs['eeg'].add_subplot(num_active, 1, i+1)
            self.axes['eeg'].append(ax)
            
            # Set up EEG axis
            ch_idx = self.active_channels[i]
            ch_name = self.ch_names[ch_idx]
            ax.set_title(f'EEG Signal - {ch_name}')
            ax.set_ylabel('μV')
            ax.grid(True)
            
            # Set smaller initial y-limits
            ax.set_ylim(-100, 100)  # Smaller zoom as requested
            
            # Only add x-axis label to the bottom plot
            if i == num_active - 1:
                ax.set_xlabel('Time (s)')
        
        # Create x-axis values for time domain plots
        self.timestamp = np.linspace(-self.window_size, 0, self.buffer_size)
        
        # Initialize lines for EEG plots
        self.lines['eeg_raw'] = []
        self.lines['eeg_filtered'] = []
        
        for i in range(num_active):
            ch_idx = self.active_channels[i]
            
            # Raw EEG line (light color)
            raw_line, = self.axes['eeg'][i].plot(
                self.timestamp, np.zeros(self.buffer_size), 
                color=self.colors[i % len(self.colors)], alpha=0.3, linewidth=1
            )
            self.lines['eeg_raw'].append(raw_line)
            
            # Filtered EEG line (solid color)
            filtered_line, = self.axes['eeg'][i].plot(
                self.timestamp, np.zeros(self.buffer_size), 
                color=self.colors[i % len(self.colors)], linewidth=1.5
            )
            self.lines['eeg_filtered'].append(filtered_line)
        
        # Adjust layout
        self.figs['eeg'].tight_layout()
    
    def setup_spectral_page(self):
        """Set up the spectral analysis page."""
        # Calculate how many EEG channels to display
        num_active = len(self.active_channels)
        
        # Create figure for spectral analysis
        self.figs['spectral'] = plt.Figure(figsize=(10, 8), dpi=100)
        
        # Create canvas for the figure
        canvas = FigureCanvasTkAgg(self.figs['spectral'], master=self.frames['spectral'])
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        # Create grid for spectral plots (PSD and log-log)
        gs = self.figs['spectral'].add_gridspec(num_active, 2, hspace=0.3, wspace=0.3)
        
        # Initialize axes for spectral plots
        self.axes['psd'] = []
        self.axes['loglog'] = []
        
        for i in range(num_active):
            ch_idx = self.active_channels[i]
            ch_name = self.ch_names[ch_idx]
            
            # PSD plot
            ax_psd = self.figs['spectral'].add_subplot(gs[i, 0])
            ax_psd.set_title(f'Power Spectral Density - {ch_name}')
            ax_psd.set_ylabel('PSD (μV²/Hz)')
            ax_psd.grid(True)
            if i == num_active - 1:
                ax_psd.set_xlabel('Frequency (Hz)')
            self.axes['psd'].append(ax_psd)
            
            # Log-log plot for 1/f analysis
            ax_loglog = self.figs['spectral'].add_subplot(gs[i, 1])
            ax_loglog.set_title(f'1/f Analysis - {ch_name}')
            ax_loglog.set_ylabel('Log Power')
            ax_loglog.grid(True)
            if i == num_active - 1:
                ax_loglog.set_xlabel('Log Frequency (Hz)')
            ax_loglog.set_xscale('log')
            ax_loglog.set_yscale('log')
            ax_loglog.set_xlim(1, 100)
            self.axes['loglog'].append(ax_loglog)
            
            # Initialize PSD lines
            psd_line, = ax_psd.plot([], [], color=self.colors[i % len(self.colors)])
            self.psd_lines[ch_idx] = psd_line
            
            # Initialize 1/f fit line
            fit_line, = ax_loglog.plot([], [], 'r--', linewidth=1)
            data_line, = ax_loglog.plot([], [], 'o', color=self.colors[i % len(self.colors)], 
                                      markersize=2, alpha=0.7)
            self.fit_lines[ch_idx] = {'fit': fit_line, 'data': data_line}
            
            # Add text for power law parameters
            text = ax_loglog.text(0.02, 0.92, "", transform=ax_loglog.transAxes, 
                              fontsize=9, bbox=dict(facecolor='white', alpha=0.7))
            self.text_elements[ch_idx] = text
        
        # Adjust layout
        self.figs['spectral'].tight_layout()
    
    def update_eeg(self, frame):
        """Update function for EEG animation."""
        with self.lock:
            try:
                # Get latest data from board
                new_data = self.board.get_current_board_data(self.sampling_rate // 5)
                
                if new_data.size == 0 or new_data.shape[1] == 0:
                    return self.lines['eeg_filtered']
                
                # Process each active channel
                for i, ch_idx in enumerate(self.active_channels):
                    ch = self.eeg_channels[ch_idx]
                    
                    # Get channel data
                    if ch < new_data.shape[0]:
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
                            # Normalize each signal to its own max value
                            # This ensures all signals are visible even with poor electrode contact
                            normalized_raw = (self.buffers[ch] / raw_max) * 100  # Scale to ±100 for display
                            normalized_filtered = (self.filtered_buffers[ch] / filtered_max) * 100
                            
                            # Update raw EEG line with normalized data
                            self.lines['eeg_raw'][i].set_ydata(normalized_raw)
                            
                            # Update filtered EEG line with normalized data
                            self.lines['eeg_filtered'][i].set_ydata(normalized_filtered)
                            
                            # Set fixed y-axis limits for normalized signals
                            self.axes['eeg'][i].set_ylim(-120, 120)  # Slightly more than ±100 to avoid clipping
                        else:
                            # If signal is flat, just use original data
                            self.lines['eeg_raw'][i].set_ydata(self.buffers[ch])
                            self.lines['eeg_filtered'][i].set_ydata(self.filtered_buffers[ch])
                
                # Return all animated objects
                return self.lines['eeg_filtered']
            
            except Exception as e:
                print(f"Error updating EEG plots: {e}")
                import traceback
                traceback.print_exc()
                return self.lines['eeg_filtered']
    
    def update_spectral(self, frame):
        """Update function for spectral animation."""
        with self.lock:
            try:
                # Process each active channel for spectral analysis
                for ch_idx in self.active_channels:
                    ch = self.eeg_channels[ch_idx]
                    
                    # Skip if buffer is empty
                    if not hasattr(self, 'filtered_buffers') or ch not in self.filtered_buffers:
                        continue
                    
                    filtered_data = self.filtered_buffers[ch]
                    if np.all(filtered_data == 0):
                        continue
                    
                    # Compute PSD
                    analyzer = self.analyzers[ch]
                    freqs, psd = analyzer.compute_psd(filtered_data)
                    
                    # Store for band power calculations
                    self.psd_freqs[ch] = freqs
                    self.psd_values[ch] = psd
                    
                    # Update PSD line
                    i = self.active_channels.index(ch_idx)
                    self.psd_lines[ch_idx].set_data(freqs, psd)
                    self.axes['psd'][i].set_xlim(0, min(100, freqs[-1]))
                    self.axes['psd'][i].set_ylim(0, np.max(psd) * 1.1)
                    
                    # Fit power law (1/f^α)
                    # Skip very low frequencies for better fit
                    fit_result = analyzer.fit_power_law(freq_range=(2, 50))
                    
                    if fit_result is not None:
                        offset, alpha = fit_result
                        self.power_law_fits[ch] = (offset, alpha)
                        
                        # Update fit line in log-log plot
                        mask = freqs > 0  # Skip DC component for log scale
                        self.fit_lines[ch_idx]['data'].set_data(freqs[mask], psd[mask])
                        
                        # Generate predicted values from fit for visualization
                        pred_freqs = np.logspace(np.log10(1), np.log10(100), 100)
                        pred_psd = offset * pred_freqs ** (-alpha)
                        self.fit_lines[ch_idx]['fit'].set_data(pred_freqs, pred_psd)
                        
                        # Update power law text
                        self.text_elements[ch_idx].set_text(
                            f"1/f^α: α = {alpha:.2f}\n"
                            f"Offset = {offset:.1e}"
                        )
                        
                        # Calculate band powers
                        band_powers = self.calculate_band_powers(psd, freqs)
                        
                        # Find dominant band
                        if band_powers:
                            dominant_band = max(band_powers.items(), key=lambda x: x[1])[0]
                            
                            # Add band powers to text
                            band_text = f"Dominant: {dominant_band}\n"
                            for band, power in band_powers.items():
                                band_text += f"{band}: {power:.1f}\n"
                            
                            self.text_elements[ch_idx].set_text(
                                self.text_elements[ch_idx].get_text() + "\n" + band_text
                            )
                
                # List of all elements to update
                elements = []
                for ch_idx in self.active_channels:
                    if ch_idx in self.psd_lines:
                        elements.append(self.psd_lines[ch_idx])
                    if ch_idx in self.fit_lines:
                        elements.append(self.fit_lines[ch_idx]['fit'])
                        elements.append(self.fit_lines[ch_idx]['data'])
                    if ch_idx in self.text_elements:
                        elements.append(self.text_elements[ch_idx])
                
                return elements
            
            except Exception as e:
                print(f"Error updating spectral plots: {e}")
                import traceback
                traceback.print_exc()
                return []
    
    def run(self):
        """Run the monitor."""
        if self.board is None:
            self.connect()
        
        self.setup_display()
        
        # Set up the animations
        self.animations['eeg'] = FuncAnimation(
            self.figs['eeg'], self.update_eeg, interval=self.update_interval, 
            blit=True, cache_frame_data=False
        )
        
        self.animations['spectral'] = FuncAnimation(
            self.figs['spectral'], self.update_spectral, interval=500,  # Slower update for spectral
            blit=True, cache_frame_data=False
        )
        
        # Start Tkinter main loop
        self.root.mainloop()
    
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
    monitor = BrainBitSpectralMonitor(window_size=5, update_interval=100)
    
    try:
        monitor.run()
    except KeyboardInterrupt:
        print("Monitor interrupted by user")
    finally:
        monitor.stop()
        print("Monitor stopped")

if __name__ == "__main__":
    main()
