#!/usr/bin/env python3
"""
BrainBit Simple Power Display

Shows the raw power of Delta, Theta, Alpha, and Beta bands for all channels
using a simple, non-blitting animation approach.
"""

import time
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from scipy import signal
from brainflow.board_shim import BoardShim, BrainFlowInputParams, LogLevels, BoardIds

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

def main():
    """Main function to connect to BrainBit and display band powers."""
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
    
    # Analysis window (2 seconds)
    window_size = int(2 * sample_rate)
    
    # Channel names and indices for BrainBit
    channel_names = ["T3", "T4", "O1", "O2"]
    eeg_channels = [1, 2, 3, 4]  # BrainFlow channel indices
    
    # Create figure
    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    axes = axes.flatten()
    plt.subplots_adjust(hspace=0.4, wspace=0.3)
    
    # Create initial bars
    band_names = list(bands.keys())
    x = np.arange(len(band_names))
    bar_containers = []
    
    for i, ch_name in enumerate(channel_names):
        # Create initial bars with zeros
        bars = axes[i].bar(
            x, 
            np.zeros(len(band_names)),
            color=[band_colors[name] for name in band_names]
        )
        bar_containers.append(bars)
        
        # Set up axes
        axes[i].set_title(f"Channel {ch_name} - Raw Power", fontsize=12)
        axes[i].set_xticks(x)
        axes[i].set_xticklabels(["Delta", "Theta", "Alpha", "Beta"])
        axes[i].set_ylabel("Absolute Power (µV²/Hz)")
        axes[i].set_ylim(0, 100)  # Initial scale, will auto-adjust
    
    # Set figure title
    fig.suptitle('BrainBit Raw Band Power (Absolute)', fontsize=14)
    
    # Add explanation
    fig.text(
        0.5, 0.02,
        "Showing absolute power (µV²/Hz) in each frequency band\n"
        "Delta (1-4 Hz), Theta (4-8 Hz), Alpha (8-13 Hz), Beta (13-30 Hz)",
        ha='center', fontsize=9
    )
    
    # Simple update function without blitting
    def update(frame):
        # Get the latest data
        data = board.get_current_board_data(window_size)
        
        if data.size > 0 and data.shape[1] >= window_size:
            # Compute band powers for each channel
            for i, ch_idx in enumerate(eeg_channels):
                if ch_idx < data.shape[0]:
                    # Get channel data
                    ch_data = data[ch_idx]
                    
                    # Calculate power for each band
                    powers = []
                    for band_name, band_range in bands.items():
                        power = compute_band_power(ch_data, sample_rate, band_range)
                        powers.append(power)
                    
                    # Update bar heights
                    for j, bar in enumerate(bar_containers[i]):
                        bar.set_height(powers[j])
                    
                    # Update title with values
                    axes[i].set_title(
                        f"{ch_name}: δ:{powers[0]:.1f}, θ:{powers[1]:.1f}, α:{powers[2]:.1f}, β:{powers[3]:.1f}", 
                        fontsize=10
                    )
                    
                    # Adjust y-axis scale if needed
                    max_power = max(powers) if powers else 0
                    if max_power > 0:
                        axes[i].set_ylim(0, max_power * 1.2)
    
    # Create animation (no blitting for stability)
    ani = FuncAnimation(
        fig, update,
        interval=200, blit=False
    )
    
    # Key event handler for clean exit
    def on_key(event):
        if event.key == 'escape' or event.key == 'q':
            plt.close(fig)
    
    fig.canvas.mpl_connect('key_press_event', on_key)
    
    # Show the plot
    plt.tight_layout(rect=[0, 0.05, 1, 0.95])
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
        if 'board' in globals() and 'board' in locals() and board is not None:
            try:
                board.stop_stream()
                board.release_session()
                print("Disconnected from BrainBit")
            except:
                pass
