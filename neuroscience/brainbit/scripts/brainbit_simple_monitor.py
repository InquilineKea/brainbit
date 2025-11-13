#!/usr/bin/env python3
"""
BrainBit Simple Monitor

A simplified EEG monitor that focuses on active channels and displays battery level.
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

class BrainBitSimpleMonitor:
    def __init__(self, window_size=5, update_interval=100):
        self.window_size = window_size
        self.update_interval = update_interval
        self.board = None
        self.board_id = None
        self.sampling_rate = None
        self.buffer_size = None
        self.eeg_channels = None
        self.battery_channel = None
        self.ch_names = None
        
        # For active channel detection
        self.active_channels = []
        self.activity_threshold = 10  # μV standard deviation threshold
        
        # Data buffers
        self.buffers = {}
        self.filtered_buffers = {}
        self.battery_levels = []
        self.battery_times = []
        
        # For plotting
        self.fig = None
        self.axes = {}
        self.lines = {}
        self.battery_line = None
        self.battery_text = None
        self.status_text = None
        self.animation = None
        self.timestamp = None
        
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
        
        # Get battery channel
        self.battery_channel = BoardShim.get_battery_channel(self.board_id)
        
        print(f"EEG Channels: {self.ch_names}")
        print(f"Sampling Rate: {self.sampling_rate} Hz")
        print(f"Battery Channel: {self.battery_channel}")
        
        self.buffer_size = int(self.sampling_rate * self.window_size)
        
        # Initialize data buffers for all channels
        for ch in self.eeg_channels:
            self.buffers[ch] = np.zeros(self.buffer_size)
            self.filtered_buffers[ch] = np.zeros(self.buffer_size)
        
        # Initialize battery data
        self.battery_levels = []
        self.battery_times = []
        
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
    
    def read_battery_level(self, data):
        """Extract battery level from board data."""
        if self.battery_channel is None or self.battery_channel < 0:
            return None
        
        if data.size == 0 or data.shape[1] == 0 or data.shape[0] <= self.battery_channel:
            return None
        
        battery_data = data[self.battery_channel]
        if len(battery_data) == 0:
            return None
        
        # For some devices, battery is reported as a percentage (0-100)
        # For others, it might be a voltage that needs conversion
        battery_value = np.median(battery_data)  # Use median to filter outliers
        
        # Simple heuristic: if battery > 10, assume percentage, otherwise assume voltage
        if battery_value > 10:
            return battery_value  # Already percentage
        else:
            # Example conversion for voltage to percentage (adjust based on device)
            # Assuming 4.2V is 100% and 3.2V is 0%
            return max(0, min(100, (battery_value - 3.2) / (4.2 - 3.2) * 100))
    
    def setup_display(self):
        """Set up the visualization display."""
        # Create figure
        self.fig = plt.figure(figsize=(12, 8))
        self.fig.canvas.manager.set_window_title('BrainBit Simple Monitor')
        
        # Calculate how many EEG channels to display
        num_active = len(self.active_channels)
        
        # Create grid layout
        gs = gridspec.GridSpec(num_active + 1, 1, height_ratios=[3] * num_active + [1])
        
        # Create axes for EEG plots
        self.axes['eeg'] = []
        for i in range(num_active):
            ax = self.fig.add_subplot(gs[i])
            self.axes['eeg'].append(ax)
            
            # Set up EEG axis
            ch_idx = self.active_channels[i]
            ch_name = self.ch_names[ch_idx]
            ax.set_title(f'EEG Signal - {ch_name}')
            ax.set_ylabel('Amplitude (μV)')
            ax.grid(True)
            
            # Only add x-axis label to the bottom plot
            if i == num_active - 1:
                ax.set_xlabel('Time (s)')
        
        # Create axis for battery level
        self.axes['battery'] = self.fig.add_subplot(gs[-1])
        self.axes['battery'].set_title('Battery Level')
        self.axes['battery'].set_xlabel('Time (s)')
        self.axes['battery'].set_ylabel('Battery (%)')
        self.axes['battery'].set_ylim(0, 100)
        self.axes['battery'].grid(True)
        
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
        
        # Initialize battery level line
        self.battery_line, = self.axes['battery'].plot(
            [], [], 'g-', linewidth=2, marker='o', markersize=3
        )
        
        # Add text display for current battery level
        self.battery_text = self.axes['battery'].text(
            0.02, 0.85, "Battery: ---%", transform=self.axes['battery'].transAxes,
            fontsize=12, fontweight='bold',
            bbox=dict(facecolor='white', alpha=0.7, boxstyle='round')
        )
        
        # Global status indicator
        self.status_text = self.fig.text(
            0.5, 0.01, "BrainBit Simple Monitor - Press 'Q' to quit", 
            ha='center', fontsize=12,
            bbox=dict(facecolor='white', alpha=0.7, boxstyle='round')
        )
        
        # Add key binding for quit
        self.fig.canvas.mpl_connect('key_press_event', 
                                   lambda event: plt.close(self.fig) if event.key == 'q' else None)
        
        # Adjust layout
        plt.tight_layout()
        self.fig.subplots_adjust(hspace=0.3, bottom=0.1)
    
    def update(self, frame):
        """Update function for animation."""
        with self.lock:
            try:
                # Get latest data from board
                new_data = self.board.get_current_board_data(self.sampling_rate // 5)
                
                if new_data.size == 0 or new_data.shape[1] == 0:
                    return self.lines['eeg_filtered']
                
                # Read battery level
                battery = self.read_battery_level(new_data)
                if battery is not None:
                    current_time = time.time()
                    if not self.battery_times:
                        self.battery_times.append(0)
                    else:
                        self.battery_times.append(self.battery_times[-1] + self.update_interval / 1000.0)
                    
                    self.battery_levels.append(battery)
                    
                    # Keep history limited
                    if len(self.battery_times) > 100:
                        self.battery_times = self.battery_times[-100:]
                        self.battery_levels = self.battery_levels[-100:]
                    
                    # Update battery line
                    self.battery_line.set_data(self.battery_times, self.battery_levels)
                    
                    # Update battery text
                    color = 'green' if battery > 50 else 'orange' if battery > 20 else 'red'
                    self.battery_text.set_text(f"Battery: {battery:.1f}%")
                    self.battery_text.set_bbox(dict(
                        facecolor='white', alpha=0.7, boxstyle='round',
                        edgecolor=color, linewidth=2
                    ))
                    
                    # Set battery axis limits
                    if self.battery_times:
                        self.axes['battery'].set_xlim(0, max(10, self.battery_times[-1]))
                
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
                        
                        # Update raw EEG line
                        self.lines['eeg_raw'][i].set_ydata(self.buffers[ch])
                        
                        # Update filtered EEG line
                        self.lines['eeg_filtered'][i].set_ydata(self.filtered_buffers[ch])
                        
                        # Adjust y-axis limits for better visualization
                        data_range = self.filtered_buffers[ch]
                        std_dev = np.std(data_range)
                        if std_dev > 1:  # Only adjust if there's significant activity
                            amp = np.max(np.abs(data_range)) * 1.2  # Add 20% margin
                            self.axes['eeg'][i].set_ylim(-amp, amp)
                
                # Update status text
                if frame % 10 == 0:  # Update only occasionally
                    if battery is not None:
                        status = f"Battery: {battery:.1f}% | Sampling Rate: {self.sampling_rate} Hz"
                    else:
                        status = f"Sampling Rate: {self.sampling_rate} Hz"
                    self.status_text.set_text(status)
                
                # Return all animated objects
                return self.lines['eeg_filtered'] + [self.battery_line, self.battery_text, self.status_text]
            
            except Exception as e:
                print(f"Error updating plots: {e}")
                import traceback
                traceback.print_exc()
                return self.lines['eeg_filtered']
    
    def run(self):
        """Run the monitor."""
        if self.board is None:
            self.connect()
        
        self.setup_display()
        
        # Set up the animation
        self.animation = FuncAnimation(
            self.fig, self.update, interval=self.update_interval, 
            blit=False, cache_frame_data=False
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
    monitor = BrainBitSimpleMonitor(window_size=5, update_interval=100)
    
    try:
        monitor.run()
    except KeyboardInterrupt:
        print("Monitor interrupted by user")
    finally:
        monitor.stop()
        print("Monitor stopped")

if __name__ == "__main__":
    main()
