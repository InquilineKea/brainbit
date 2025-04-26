#!/usr/bin/env python3
"""
BrainBit Impedance Monitor

This script focuses exclusively on measuring and displaying electrode impedance 
values for all channels of the BrainBit device.
"""

import time
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import threading

# BrainFlow imports
import brainflow
from brainflow.board_shim import BoardShim, BrainFlowInputParams, BoardIds, LogLevels

class BrainBitImpedanceMonitor:
    def __init__(self, update_interval=100):
        self.update_interval = update_interval
        self.board = None
        self.board_id = None
        self.eeg_channels = None
        self.resistance_channels = None
        self.ch_names = None
        
        # Data storage for impedance values
        self.impedance_values = {}
        self.impedance_history = {0: [], 1: [], 2: [], 3: []}
        self.timestamps = []
        
        # For plotting
        self.fig = None
        self.ax = None
        self.lines = []
        self.bar_container = None
        self.impedance_text = None
        self.animation = None
        
        # For thread safety
        self.lock = threading.Lock()
        
        # Colors for channels
        self.colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728']  # blue, orange, green, red
    
    def connect(self):
        """Connect to BrainBit device."""
        params = BrainFlowInputParams()
        
        # Set log level to debug to see more output
        BoardShim.enable_dev_board_logger()
        BoardShim.set_log_level(LogLevels.LEVEL_DEBUG.value)
        
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
        self.eeg_channels = BoardShim.get_eeg_channels(self.board_id)
        self.resistance_channels = BoardShim.get_resistance_channels(self.board_id)
        self.ch_names = BoardShim.get_eeg_names(self.board_id)
        
        print(f"EEG Channels: {self.ch_names}")
        print(f"Resistance Channels: {self.resistance_channels}")
        
        # Initialize impedance values
        for i in range(len(self.ch_names)):
            self.impedance_values[i] = 0
        
        # Start data stream
        self.board.start_stream()
        print("Data streaming started")
        
        # Wait a bit to stabilize the connection
        time.sleep(1)
        
        return True
    
    def setup_display(self):
        """Set up the visualization display for impedance values."""
        self.fig, (self.ax_time, self.ax_bars) = plt.subplots(2, 1, figsize=(10, 8))
        self.fig.canvas.manager.set_window_title('BrainBit Impedance Monitor')
        
        # Time plot for impedance history
        self.ax_time.set_title('Electrode Impedance History')
        self.ax_time.set_xlabel('Time (s)')
        self.ax_time.set_ylabel('Impedance (kΩ)')
        self.ax_time.set_ylim(0, 200)  # Set initial range
        self.ax_time.grid(True)
        
        # Initialize lines for impedance history
        self.lines = []
        for i, ch_name in enumerate(self.ch_names):
            line, = self.ax_time.plot([], [], 
                                     color=self.colors[i], 
                                     marker='o', linestyle='-', markersize=4,
                                     label=ch_name)
            self.lines.append(line)
        
        self.ax_time.legend(loc='upper right')
        
        # Bar chart for current impedance values
        self.ax_bars.set_title('Current Electrode Impedance')
        x = np.arange(len(self.ch_names))
        self.bar_container = self.ax_bars.bar(x, [0] * len(self.ch_names), 
                                             color=self.colors, alpha=0.7)
        self.ax_bars.set_xticks(x)
        self.ax_bars.set_xticklabels(self.ch_names)
        self.ax_bars.set_ylabel('Impedance (kΩ)')
        self.ax_bars.set_ylim(0, 200)
        
        # Add text for impedance values on bars
        self.bar_texts = []
        for bar in self.bar_container:
            text = self.ax_bars.text(bar.get_x() + bar.get_width() / 2, 5, '0',
                                   ha='center', va='bottom', fontsize=12, fontweight='bold')
            self.bar_texts.append(text)
        
        # Text display for contact quality
        self.quality_texts = []
        for i, ch_name in enumerate(self.ch_names):
            text = self.ax_bars.text(i, -30, 'Unknown',
                                   ha='center', va='center', fontsize=10, 
                                   bbox=dict(facecolor='white', alpha=0.5, boxstyle='round'))
            self.quality_texts.append(text)
        
        # Information text
        self.info_text = self.fig.text(0.5, 0.01, 
                                     "Impedance values for good contact: <100 kΩ", 
                                     ha='center', fontsize=12, 
                                     bbox=dict(facecolor='white', alpha=0.7))
        
        plt.tight_layout()
        self.fig.subplots_adjust(bottom=0.1)
    
    def measure_impedance(self):
        """Get the latest impedance values from the device."""
        try:
            # Get board data including resistance channels
            data = self.board.get_current_board_data(256)  # Get a good amount of samples
            
            if data.size == 0 or data.shape[1] == 0:
                return
            
            # Debugging the data shape and resistance channels
            print(f"Data shape: {data.shape}, Resistance channels: {self.resistance_channels}")
            
            # Check if we have enough channels in the data
            if data.shape[0] <= max(self.resistance_channels, default=0):
                print(f"Not enough channels in data: {data.shape[0]} vs {self.resistance_channels}")
                
                # Try a different approach - direct resistance reading
                resistance_data = {}
                try:
                    for i, electrode in enumerate(self.ch_names):
                        # Try to get resistance directly from board
                        try:
                            res = self.board.get_resistance_channel(i)
                            resistance_data[i] = res
                            print(f"Direct resistance for {electrode}: {res}")
                        except Exception as e:
                            print(f"Could not get direct resistance for {electrode}: {e}")
                except Exception as e:
                    print(f"Error in direct resistance reading: {e}")
                
                # If we have any values from direct reading, use them
                if resistance_data:
                    for i, res in resistance_data.items():
                        if res > 0 and res < 500:  # Sanity check
                            self.impedance_values[i] = res
                
                return
                
            # Try to get impedance values from the resistance channels
            for i, ch_idx in enumerate(self.resistance_channels):
                if i >= len(self.ch_names):
                    continue
                    
                # Get the resistance channel data
                if ch_idx < data.shape[0]:
                    values = data[ch_idx]
                    
                    # Filter out implausible values
                    valid_values = values[(values > 0) & (values < 500)]
                    
                    if len(valid_values) > 0:
                        # Use median as it's more robust to outliers
                        median_value = np.median(valid_values)
                        self.impedance_values[i] = median_value
                        print(f"Channel {self.ch_names[i]} impedance: {median_value:.1f} kΩ")
            
            # Record history
            current_time = time.time()
            if not self.timestamps:
                self.timestamps.append(0)
            else:
                self.timestamps.append(self.timestamps[-1] + self.update_interval / 1000.0)
            
            # Keep history limited to 100 points
            if len(self.timestamps) > 100:
                self.timestamps = self.timestamps[-100:]
            
            # Add current values to history
            for i in range(len(self.ch_names)):
                self.impedance_history[i].append(self.impedance_values.get(i, 0))
                if len(self.impedance_history[i]) > 100:
                    self.impedance_history[i] = self.impedance_history[i][-100:]
            
        except Exception as e:
            print(f"Error measuring impedance: {e}")
            import traceback
            traceback.print_exc()
    
    def update(self, frame):
        """Update function for animation."""
        with self.lock:
            try:
                # Measure impedance
                self.measure_impedance()
                
                # Update time series plot
                x = self.timestamps
                for i, line in enumerate(self.lines):
                    y = self.impedance_history[i]
                    if len(y) > 0:
                        line.set_data(x[-len(y):], y)
                
                # Adjust x-axis limits
                if self.timestamps:
                    self.ax_time.set_xlim(0, max(10, self.timestamps[-1]))
                
                # Adjust y-axis limits if needed
                max_imp = 0
                for hist in self.impedance_history.values():
                    if hist:
                        max_imp = max(max_imp, max(hist))
                
                if max_imp > 0:
                    self.ax_time.set_ylim(0, max(200, max_imp * 1.2))
                
                # Update bar heights
                for i, bar in enumerate(self.bar_container):
                    value = self.impedance_values.get(i, 0)
                    bar.set_height(value)
                    
                    # Update text on bars
                    self.bar_texts[i].set_text(f"{value:.1f}")
                    self.bar_texts[i].set_position((bar.get_x() + bar.get_width() / 2, value + 5))
                    
                    # Update quality indicator
                    if value < 25:
                        quality = "Excellent"
                        color = 'green'
                    elif value < 100:
                        quality = "Good"
                        color = 'blue'
                    elif value < 200:
                        quality = "Fair"
                        color = 'orange'
                    else:
                        quality = "Poor"
                        color = 'red'
                    
                    self.quality_texts[i].set_text(quality)
                    self.quality_texts[i].set_color(color)
                
                # Adjust bar chart y-axis limit if needed
                self.ax_bars.set_ylim(0, max(200, max_imp * 1.2))
                
                # Update info text with timestamp
                self.info_text.set_text(f"Electrode Impedance Monitor - {time.strftime('%H:%M:%S')}")
                
                # Return the updated artists
                return self.lines + [self.bar_container] + self.bar_texts + self.quality_texts + [self.info_text]
            
            except Exception as e:
                print(f"Error updating display: {e}")
                import traceback
                traceback.print_exc()
                return self.lines
    
    def run(self):
        """Run the impedance monitor."""
        if self.board is None:
            self.connect()
        
        self.setup_display()
        
        # Set up the animation
        self.animation = FuncAnimation(
            self.fig, self.update, interval=self.update_interval, 
            blit=False, cache_frame_data=False  # Disable blitting for stability
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
    monitor = BrainBitImpedanceMonitor(update_interval=500)  # Update every 500ms
    
    try:
        monitor.run()
    except KeyboardInterrupt:
        print("Monitor interrupted by user")
    finally:
        monitor.stop()
        print("Monitor stopped")

if __name__ == "__main__":
    main()
