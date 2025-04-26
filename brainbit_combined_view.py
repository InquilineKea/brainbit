#!/usr/bin/env python3
"""
BrainBit Combined View

Shows raw EEG signals and band power in a single window with tabbed interface.
"""

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from scipy import signal
from brainflow.board_shim import BoardShim, BrainFlowInputParams, LogLevels, BoardIds
import matplotlib.gridspec as gridspec
from matplotlib.widgets import Button

# Global variables
board = None
data_buffer = None
fig = None
gs = None
eeg_axes = None
power_axes = None
eeg_lines = None
power_bars = None
current_tab = "raw"  # 'raw' or 'power'

# Frequency bands
bands = {
    "delta": (1, 4),
    "theta": (4, 8),
    "alpha": (8, 13),
    "beta": (13, 30)
}

# Colors for the bands
band_colors = {
    "delta": "royalblue",
    "theta": "forestgreen", 
    "alpha": "crimson",
    "beta": "darkorange"
}

def compute_band_power(data, fs, band):
    """Compute absolute power in a frequency band using Welch's method."""
    low, high = band
    
    # Use Welch's method to estimate PSD
    f, psd = signal.welch(data, fs, nperseg=min(256, len(data)))
    
    # Find indices corresponding to the frequency band
    idx = np.logical_and(f >= low, f <= high)
    
    # Calculate absolute power (mean of PSD in the band)
    if np.any(idx):
        band_power = np.mean(psd[idx])
    else:
        band_power = 0
        
    return band_power

def switch_to_raw(event):
    """Switch to raw EEG tab."""
    global current_tab
    current_tab = "raw"
    show_current_tab()

def switch_to_power(event):
    """Switch to band power tab."""
    global current_tab
    current_tab = "power"
    show_current_tab()

def show_current_tab():
    """Show only the currently selected tab."""
    if current_tab == "raw":
        # Show EEG axes, hide power axes
        for ax in eeg_axes:
            ax.set_visible(True)
        for ax in power_axes:
            ax.set_visible(False)
    else:
        # Show power axes, hide EEG axes
        for ax in eeg_axes:
            ax.set_visible(False)
        for ax in power_axes:
            ax.set_visible(True)
    
    fig.canvas.draw_idle()

def main():
    """Main function to connect to BrainBit and display data."""
    global board, data_buffer, fig, gs, eeg_axes, power_axes, eeg_lines, power_bars
    
    # Connect to BrainBit
    print("Connecting to BrainBit...")
    
    # Set log level
    BoardShim.enable_dev_board_logger()
    BoardShim.set_log_level(LogLevels.LEVEL_INFO)
    
    # Initialize parameters
    params = BrainFlowInputParams()
    board_id = BoardIds.BRAINBIT_BOARD
    
    # Create board shim instance
    board = BoardShim(board_id, params)
    
    # Connect to the board
    board.prepare_session()
    board.start_stream()
    
    print("Connected to BrainBit")
    
    # Get sampling rate
    sample_rate = BoardShim.get_sampling_rate(board_id)
    print(f"Sampling rate: {sample_rate} Hz")
    
    # Buffer and window sizes
    buffer_seconds = 5
    buffer_size = int(buffer_seconds * sample_rate)
    window_size = int(2 * sample_rate)  # 2 seconds for power calculation
    
    # Channel names and indices for BrainBit
    channel_names = ["T3", "T4", "O1", "O2"]
    eeg_channels = [1, 2, 3, 4]  # BrainFlow channel indices
    
    # Create figure
    fig = plt.figure(figsize=(12, 8))
    
    # Create tab buttons
    ax_raw_button = plt.axes([0.3, 0.95, 0.15, 0.04])
    ax_power_button = plt.axes([0.55, 0.95, 0.15, 0.04])
    
    btn_raw = Button(ax_raw_button, 'Raw EEG')
    btn_power = Button(ax_power_button, 'Band Power')
    
    btn_raw.on_clicked(switch_to_raw)
    btn_power.on_clicked(switch_to_power)
    
    # Create main grid for content
    gs = gridspec.GridSpec(4, 1, figure=fig, hspace=0.4, top=0.9)
    
    # Create EEG axes
    eeg_axes = []
    eeg_lines = []
    for i, ch_name in enumerate(channel_names):
        ax = fig.add_subplot(gs[i, 0])
        eeg_axes.append(ax)
        
        line, = ax.plot([], [], lw=1.5, color='blue')
        eeg_lines.append(line)
        
        ax.set_title(f"Channel {ch_name}", fontsize=12)
        ax.set_ylabel('μV', fontsize=10)
        ax.grid(True)
        ax.set_ylim(-50000, 50000)
        
    # Set x-axis label for bottom EEG plot
    eeg_axes[-1].set_xlabel('Time (s)', fontsize=10)
    
    # Create Power axes (initially hidden)
    power_axes = []
    power_bars = []
    band_names = list(bands.keys())
    x = np.arange(len(band_names))
    
    for i, ch_name in enumerate(channel_names):
        # Create power axis in same position as EEG axis
        ax = fig.add_subplot(gs[i, 0])
        power_axes.append(ax)
        
        # Create initial bars with zeros
        bars = ax.bar(
            x, 
            np.zeros(len(band_names)),
            color=[band_colors[name] for name in band_names]
        )
        power_bars.append(bars)
        
        # Set up axes
        ax.set_title(f"Channel {ch_name} - Raw Power", fontsize=12)
        ax.set_xticks(x)
        ax.set_xticklabels(["Delta", "Theta", "Alpha", "Beta"])
        ax.set_ylabel("Power (µV²/Hz)")
        ax.set_ylim(0, 100)  # Initial scale, will auto-adjust
        ax.set_visible(False)  # Initially hidden
    
    # Set figure title
    fig.suptitle('BrainBit Real-Time Visualization', fontsize=14)
    
    # Add status text
    status_text = fig.text(
        0.5, 0.01, "Connected", 
        ha='center', fontsize=10
    )
    
    # Initialize the x-time data for EEG
    x_time = np.linspace(-buffer_seconds, 0, buffer_size)
    
    # Animation update function
    def update(frame):
        # Update status
        status_text.set_text(f"Connected | Tab: {'Raw EEG' if current_tab == 'raw' else 'Band Power'}")
        
        # Get the latest data
        data = board.get_current_board_data(buffer_size)
        
        if data.size > 0 and data.shape[1] > 0:
            # Update Raw EEG tab
            if current_tab == "raw":
                x_data = np.linspace(-buffer_seconds, 0, data.shape[1])
                
                for i, ch_idx in enumerate(eeg_channels):
                    if ch_idx < data.shape[0]:
                        # Update line data
                        eeg_lines[i].set_data(x_data, data[ch_idx])
                        
                        # Auto-adjust y-limits if data exists and has variation
                        if data[ch_idx].size > 0 and np.max(data[ch_idx]) != np.min(data[ch_idx]):
                            max_val = np.max(np.abs(data[ch_idx]))
                            eeg_axes[i].set_ylim(-max_val*1.2, max_val*1.2)
            
            # Update Band Power tab
            else:
                # Use a smaller window for power calculation
                if data.shape[1] >= window_size:
                    for i, ch_idx in enumerate(eeg_channels):
                        if ch_idx < data.shape[0]:
                            # Get channel data
                            ch_data = data[ch_idx, -window_size:]
                            
                            # Calculate power for each band
                            powers = []
                            for band_name, band_range in bands.items():
                                power = compute_band_power(ch_data, sample_rate, band_range)
                                powers.append(power)
                            
                            # Update bar heights
                            for j, bar in enumerate(power_bars[i]):
                                bar.set_height(powers[j])
                            
                            # Update title with values
                            power_axes[i].set_title(
                                f"{ch_name}: δ:{powers[0]:.1f}, θ:{powers[1]:.1f}, α:{powers[2]:.1f}, β:{powers[3]:.1f}", 
                                fontsize=10
                            )
                            
                            # Adjust y-axis scale if needed
                            max_power = max(powers) if powers else 0
                            if max_power > 0:
                                power_axes[i].set_ylim(0, max_power * 1.2)
    
    # Create animation
    ani = FuncAnimation(
        fig, update,
        interval=100, cache_frame_data=False
    )
    
    # Show initial tab
    show_current_tab()
    
    # Key event handler for clean exit
    def on_key(event):
        if event.key == 'escape' or event.key == 'q':
            plt.close(fig)
    
    fig.canvas.mpl_connect('key_press_event', on_key)
    
    # Show the plot
    plt.tight_layout(rect=[0, 0.05, 1, 0.9])
    plt.show()
    
    # Clean up when the plot is closed
    board.stop_stream()
    board.release_session()
    print("Disconnected from BrainBit")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Interrupted by user")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        # Make sure to disconnect
        if 'board' in globals() and board is not None:
            try:
                board.stop_stream()
                board.release_session()
                print("Disconnected from BrainBit")
            except:
                pass
