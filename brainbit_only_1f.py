#!/usr/bin/env python3
"""
BrainBit 1/f Analysis Only

A simple, focused script that only shows 1/f spectral analysis.
"""

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from scipy import signal
from scipy import stats
from brainflow.board_shim import BoardShim, BrainFlowInputParams, LogLevels, BoardIds
from brainflow.data_filter import DataFilter, DetrendOperations, FilterTypes

# Global variables
board = None
fig = None
axes = None
psd_lines = None
fit_lines = None
slope_texts = None

def apply_filters(data, sample_rate):
    """Apply only detrending to the data."""
    if len(data) == 0:
        return data
    
    filtered_data = data.copy()
    
    try:
        # Just detrend (remove DC offset)
        DataFilter.detrend(filtered_data, DetrendOperations.CONSTANT.value)
    except Exception as e:
        print(f"Filter error: {e}")
    
    return filtered_data

def compute_psd(data, fs):
    """Compute power spectral density using Welch's method."""
    # Use a simple window size
    nperseg = min(4 * fs, len(data))
    if nperseg < 32:  # Minimum size for meaningful PSD
        return np.array([]), np.array([])
    
    f, psd = signal.welch(data, fs, nperseg=nperseg)
    return f, psd

def fit_1f_spectrum(f, psd, f_range=(1, 30)):
    """Very simple 1/f spectral slope calculation."""
    # Basic filtering to avoid log of zero or negative
    mask = (f > 0) & (psd > 0)
    
    # Skip if not enough data points
    if np.sum(mask) < 5:
        return 0, np.array([]), np.array([])
    
    # Find frequency range indices
    idx = np.logical_and(f >= f_range[0], f <= f_range[1]) & mask
    
    # Skip if not enough data points in range
    if np.sum(idx) < 5:
        return 0, np.array([]), np.array([])
    
    # Linear fit in log-log space
    log_f = np.log10(f[idx])
    log_psd = np.log10(psd[idx])
    slope, intercept, _, _, _ = stats.linregress(log_f, log_psd)
    
    # Generate the fit line for plotting
    f_fit = f[idx]
    fit_log_psd = intercept + slope * np.log10(f_fit)
    fit_psd = 10 ** fit_log_psd
    
    return slope, f_fit, fit_psd

def main():
    """Main function to connect to BrainBit and display 1/f analysis."""
    global board, fig, axes, psd_lines, fit_lines, slope_texts
    
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
    
    # Window size for analysis (4 seconds)
    window_size = int(4 * sample_rate)
    
    # Channel names and indices for BrainBit
    channel_names = ["T3", "T4", "O1", "O2"]
    eeg_channels = [1, 2, 3, 4]  # BrainFlow channel indices
    
    # Create figure with 4 subplots (one per channel)
    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    axes = axes.flatten()
    plt.subplots_adjust(hspace=0.4, wspace=0.3)
    
    # Initialize lines and text for each channel
    psd_lines = []
    fit_lines = []
    slope_texts = []
    
    for i, ax in enumerate(axes):
        # Create PSD line and fit line
        psd_line, = ax.plot([], [], lw=1.5, color='blue', label='PSD')
        fit_line, = ax.plot([], [], lw=1.5, color='red', linestyle='--', label='1/f Fit')
        psd_lines.append(psd_line)
        fit_lines.append(fit_line)
        
        # Set up axes
        ax.set_title(f"Channel {channel_names[i]} - 1/f Analysis", fontsize=12)
        ax.set_xlabel('Frequency (Hz)', fontsize=10)
        ax.set_ylabel('PSD (µV²/Hz)', fontsize=10)
        ax.set_xscale('log')
        ax.set_yscale('log')
        ax.set_xlim(1, 50)
        ax.set_ylim(0.1, 1e4)
        ax.grid(True, which='both', linestyle='--', alpha=0.7)
        ax.legend(loc='upper right')
        
        # Add text for slope info
        text = ax.text(
            0.05, 0.95, "", 
            transform=ax.transAxes,
            fontsize=10,
            bbox=dict(facecolor='white', alpha=0.7),
            verticalalignment='top'
        )
        slope_texts.append(text)
    
    # Set figure title
    fig.suptitle('BrainBit 1/f Spectral Analysis', fontsize=14)
    
    # Add status text
    status_text = fig.text(
        0.5, 0.01, "Connected", 
        ha='center', fontsize=10
    )
    
    # Animation update function - no blitting for stability
    def update(frame):
        # Get the latest data
        data = board.get_current_board_data(window_size)
        
        if data.size == 0 or data.shape[1] < window_size:
            return
        
        # Process each channel
        for i, ch_idx in enumerate(eeg_channels):
            if ch_idx < data.shape[0]:
                # Get channel data
                ch_data = data[ch_idx]
                
                # Basic detrending
                filtered_data = apply_filters(ch_data, sample_rate)
                
                # Compute PSD
                f, psd = compute_psd(filtered_data, sample_rate)
                
                if len(f) > 0 and len(psd) > 0:
                    # Update PSD line
                    psd_lines[i].set_data(f, psd)
                    
                    # Compute and update 1/f fit
                    slope, f_fit, psd_fit = fit_1f_spectrum(f, psd)
                    
                    # Only update fit line if we got valid data
                    if len(f_fit) > 0 and len(psd_fit) > 0:
                        fit_lines[i].set_data(f_fit, psd_fit)
                        
                        # Update slope text
                        slope_texts[i].set_text(f"1/f Exponent: {slope:.2f}")
                        
                        # Update title
                        axes[i].set_title(
                            f"{channel_names[i]}: 1/f Exponent = {slope:.2f}", 
                            fontsize=11
                        )
        
        # Update status text
        status_text.set_text(f"Window size: {window_size} samples | Time: {window_size/sample_rate:.1f}s")
    
    # Create animation (no blitting for stability)
    ani = FuncAnimation(
        fig, update,
        interval=500, blit=False, cache_frame_data=False
    )
    
    # Show the plot
    plt.tight_layout(rect=[0, 0.03, 1, 0.95])
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
