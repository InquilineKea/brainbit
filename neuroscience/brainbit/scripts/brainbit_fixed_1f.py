#!/usr/bin/env python3
"""
BrainBit Multi-View with Fixed 1/f Analysis

Shows filtered and normalized EEG signals, band power, and 1/f spectral analysis.
- Filtered signals with each channel independently normalized
- Band power analysis for each frequency range
- 1/f spectral analysis using the original pre-normalization approach
"""

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from scipy import signal
from scipy import stats
from brainflow.board_shim import BoardShim, BrainFlowInputParams, LogLevels, BoardIds
from brainflow.data_filter import DataFilter, DetrendOperations, FilterTypes
import matplotlib.gridspec as gridspec
from matplotlib.widgets import Button

# Global variables
board = None
fig = None
gs = None
current_tab = "filtered"  # 'filtered', 'power', or 'spectral'

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

# Fixed y-axis limits
eeg_y_limit = 1.0       # ±1.0 (normalized) for EEG
power_y_limit = 50      # 0-50 μV²/Hz for band power
spectral_y_limit = 1e4  # 0-10,000 for PSD

def apply_filters(data, sample_rate):
    """Apply the full filter pipeline to EEG data."""
    if len(data) == 0:
        return data
    
    filtered_data = data.copy()
    
    try:
        # 1. Detrend (remove DC offset and linear trends)
        DataFilter.detrend(filtered_data, DetrendOperations.LINEAR.value)
        
        # 2. Bandpass filter (1-30 Hz) - Butterworth order 4
        DataFilter.perform_bandpass(filtered_data, sample_rate, 1.0, 30.0, 4, 
                                    FilterTypes.BUTTERWORTH.value, 0)
    except Exception as e:
        print(f"Filter error: {e}")
    
    return filtered_data

def normalize_signal(signal_data):
    """Normalize signal to range [-1, 1] for better visualization."""
    if len(signal_data) == 0 or np.max(signal_data) == np.min(signal_data):
        return np.zeros_like(signal_data)
    
    # Get absolute max value
    abs_max = np.max(np.abs(signal_data))
    if abs_max > 0:
        return signal_data / abs_max
    else:
        return signal_data

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

def compute_psd(data, fs):
    """Compute power spectral density using Welch's method."""
    # Use a suitable window size (e.g., 4 seconds of data or maximum available)
    nperseg = min(4 * fs, len(data))
    if nperseg < 32:  # Minimum size for meaningful PSD
        return np.array([]), np.array([])
    
    f, psd = signal.welch(data, fs, nperseg=nperseg)
    return f, psd

def fit_1f_spectrum(f, psd, f_range=(1, 30)):
    """
    Simple 1/f spectral slope calculation (pre-normalization approach).
    Returns the slope (exponent).
    """
    # Filter out zeros and negatives for log transform
    mask = (f > 0) & (psd > 0)
    if np.sum(mask) < 5:
        return 0, f, np.zeros_like(f)
    
    # Log-transform the data
    log_f = np.log10(f[mask])
    log_psd = np.log10(psd[mask])
    
    # Find frequency range indices
    idx = np.logical_and(f >= f_range[0], f <= f_range[1])
    idx = idx & mask  # Combine with valid mask
    
    # Skip if not enough data points
    if np.sum(idx) < 5:
        return 0, f[idx], np.zeros_like(f[idx])
    
    # Linear fit in log-log space
    slope, intercept, r_value, p_value, std_err = stats.linregress(log_f[idx], log_psd[idx])
    
    # Generate the fit line for plotting
    fit_log_psd = intercept + slope * np.log10(f[idx])
    fit_psd = 10 ** fit_log_psd
    
    return slope, f[idx], fit_psd

def switch_tab(target_tab):
    """Switch to specified tab."""
    global current_tab
    current_tab = target_tab
    show_current_tab()

def switch_to_filtered(event):
    """Switch to filtered EEG tab."""
    switch_tab("filtered")

def switch_to_power(event):
    """Switch to band power tab."""
    switch_tab("power")

def switch_to_spectral(event):
    """Switch to spectral analysis tab."""
    switch_tab("spectral")

def show_current_tab():
    """Show only the currently selected tab."""
    # Update visibility of plot containers
    plt.figure(fig.number)
    
    # Hide all axes first
    for ax in plt.gcf().get_axes():
        if hasattr(ax, 'tab_type'):
            ax.set_visible(ax.tab_type == current_tab)
    
    # Redraw the canvas
    fig.canvas.draw_idle()

def main():
    """Main function to connect to BrainBit and display data."""
    global board, fig, gs, current_tab
    
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
    window_size = int(4 * sample_rate)  # 4 seconds for spectral analysis
    
    # Channel names and indices for BrainBit
    channel_names = ["T3", "T4", "O1", "O2"]
    eeg_channels = [1, 2, 3, 4]  # BrainFlow channel indices
    
    # Create figure
    fig = plt.figure(figsize=(12, 8))
    
    # Create tab buttons
    ax_filtered_button = plt.axes([0.25, 0.95, 0.15, 0.04])
    ax_power_button = plt.axes([0.42, 0.95, 0.15, 0.04])
    ax_spectral_button = plt.axes([0.59, 0.95, 0.15, 0.04])
    
    btn_filtered = Button(ax_filtered_button, 'Filtered EEG')
    btn_power = Button(ax_power_button, 'Band Power')
    btn_spectral = Button(ax_spectral_button, '1/f Analysis')
    
    btn_filtered.on_clicked(switch_to_filtered)
    btn_power.on_clicked(switch_to_power)
    btn_spectral.on_clicked(switch_to_spectral)
    
    # Create main grid for content
    gs = gridspec.GridSpec(4, 1, figure=fig, hspace=0.4, top=0.9)
    
    # Create Filtered EEG axes
    eeg_axes = []
    eeg_lines = []
    for i in range(4):
        ax = fig.add_subplot(gs[i, 0])
        ax.tab_type = "filtered"  # Add attribute to identify tab
        eeg_axes.append(ax)
        
        line, = ax.plot([], [], lw=1.5, color='blue')
        eeg_lines.append(line)
        
        ax.set_title(f"Channel {channel_names[i]} (Filtered, Normalized)", fontsize=12)
        ax.set_ylabel('Amplitude', fontsize=10)
        ax.grid(True)
        
        # Fixed y-axis limits for normalized signal
        ax.set_ylim(-eeg_y_limit, eeg_y_limit)
        
    # Set x-axis label for bottom EEG plot
    eeg_axes[-1].set_xlabel('Time (s)', fontsize=10)
    
    # Create Power axes (initially hidden)
    power_axes = []
    power_bars = []
    band_names = list(bands.keys())
    x = np.arange(len(band_names))
    
    for i in range(4):
        # Create power axis in same position as EEG axis
        ax = fig.add_subplot(gs[i, 0])
        ax.tab_type = "power"  # Add attribute to identify tab
        power_axes.append(ax)
        
        # Create initial bars with zeros
        bars = ax.bar(
            x, 
            np.zeros(len(band_names)),
            color=[band_colors[name] for name in band_names]
        )
        power_bars.append(bars)
        
        # Set up axes
        ax.set_title(f"Channel {channel_names[i]} - Band Power", fontsize=12)
        ax.set_xticks(x)
        ax.set_xticklabels(["Delta", "Theta", "Alpha", "Beta"])
        ax.set_ylabel("Power (µV²/Hz)")
        
        # Fixed y-axis limits
        ax.set_ylim(0, power_y_limit)
        
        # Initially hidden
        ax.set_visible(False)
    
    # Create Spectral axes (initially hidden)
    spectral_axes = []
    psd_lines = []
    fit_lines = []
    slope_texts = []
    
    for i in range(4):
        # Create spectral axis in same position
        ax = fig.add_subplot(gs[i, 0])
        ax.tab_type = "spectral"  # Add attribute to identify tab
        spectral_axes.append(ax)
        
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
        ax.set_ylim(0.1, spectral_y_limit)
        ax.grid(True, which='both', linestyle='--', alpha=0.7)
        ax.legend(loc='upper right')
        
        # Add text for slope and alpha details
        text = ax.text(
            0.02, 0.95, "", 
            transform=ax.transAxes,
            fontsize=10,
            bbox=dict(facecolor='white', alpha=0.7),
            verticalalignment='top'
        )
        slope_texts.append(text)
        
        # Initially hidden
        ax.set_visible(False)
    
    # Set figure title
    fig.suptitle('BrainBit Multi-View Analysis', fontsize=14)
    
    # Add status text
    status_text = fig.text(
        0.5, 0.01, "Connected", 
        ha='center', fontsize=10
    )
    
    # Initialize the x-time data for EEG
    x_time = np.linspace(-buffer_seconds, 0, buffer_size)
    
    # Animation update function - no blitting for stability
    def update(frame):
        # Update status text
        tab_names = {
            "filtered": "Filtered EEG", 
            "power": "Band Power", 
            "spectral": "1/f Analysis"
        }
        status_text.set_text(f"Connected | Tab: {tab_names[current_tab]}")
        
        # Get the latest data
        data = board.get_current_board_data(max(buffer_size, window_size))
        
        if data.size == 0 or data.shape[1] == 0:
            return
        
        # Update Filtered EEG tab
        if current_tab == "filtered":
            x_data = np.linspace(-buffer_seconds, 0, min(buffer_size, data.shape[1]))
            
            for i, ch_idx in enumerate(eeg_channels):
                if ch_idx < data.shape[0]:
                    # Get last buffer_size samples or available samples
                    samples = min(buffer_size, data.shape[1])
                    y_data = data[ch_idx, -samples:]
                    
                    if len(y_data) > 0:
                        # Apply filters
                        filtered_data = apply_filters(y_data, sample_rate)
                        
                        # Normalize signal to range [-1, 1]
                        normalized_data = normalize_signal(filtered_data)
                        
                        # Update line data
                        eeg_lines[i].set_data(x_data[-len(normalized_data):], normalized_data)
                        
                        # Update title with stats
                        rms = np.sqrt(np.mean(np.square(filtered_data)))
                        eeg_axes[i].set_title(
                            f"{channel_names[i]}: Filtered, Normalized (RMS: {rms:.1f}µV)", 
                            fontsize=10
                        )
        
        # Update Band Power tab  
        elif current_tab == "power":
            if data.shape[1] >= window_size:
                for i, ch_idx in enumerate(eeg_channels):
                    if ch_idx < data.shape[0]:
                        # Get channel data (last window_size samples)
                        ch_data = data[ch_idx, -window_size:]
                        
                        # Apply filters 
                        filtered_data = apply_filters(ch_data, sample_rate)
                        
                        # Calculate power for each band
                        powers = []
                        for band_name, band_range in bands.items():
                            power = compute_band_power(filtered_data, sample_rate, band_range)
                            powers.append(power)
                        
                        # Update bar heights (cap at y-limit * 0.95 to avoid overflow)
                        for j, bar in enumerate(power_bars[i]):
                            bar.set_height(min(powers[j], power_y_limit * 0.95))
                        
                        # Calculate alpha ratio (alpha/theta)
                        alpha_theta_ratio = powers[2] / powers[1] if powers[1] > 0 else 0
                        
                        # Update title with values
                        power_axes[i].set_title(
                            f"{channel_names[i]}: δ:{powers[0]:.1f}, θ:{powers[1]:.1f}, α:{powers[2]:.1f}, β:{powers[3]:.1f} (α/θ: {alpha_theta_ratio:.2f})", 
                            fontsize=9
                        )
        
        # Update Spectral Analysis tab
        elif current_tab == "spectral":
            if data.shape[1] >= window_size:
                for i, ch_idx in enumerate(eeg_channels):
                    if ch_idx < data.shape[0]:
                        # Get channel data (last window_size samples)
                        ch_data = data[ch_idx, -window_size:]
                        
                        # Apply filters (but don't normalize for spectral analysis)
                        filtered_data = apply_filters(ch_data, sample_rate)
                        
                        # Compute PSD on the non-normalized filtered data
                        f, psd = compute_psd(filtered_data, sample_rate)
                        
                        if len(f) > 0 and len(psd) > 0:
                            # Update PSD line
                            psd_lines[i].set_data(f, psd)
                            
                            # Compute and update 1/f fit using simpler method
                            slope, f_fit, psd_fit = fit_1f_spectrum(f, psd)
                            fit_lines[i].set_data(f_fit, psd_fit)
                            
                            # Update slope text with basic information
                            slope_texts[i].set_text(f"1/f Exponent: {slope:.2f}")
                            
                            # Update title with the slope value
                            spectral_axes[i].set_title(
                                f"{channel_names[i]}: 1/f Exponent = {slope:.2f}", 
                                fontsize=10
                            )
    
    # Create animation (no blitting for maximum stability)
    ani = FuncAnimation(
        fig, update,
        interval=200, blit=False
    )
    
    # Show initial tab
    show_current_tab()
    
    # Key event handler for clean exit
    def on_key(event):
        if event.key == 'escape' or event.key == 'q':
            plt.close(fig)
    
    fig.canvas.mpl_connect('key_press_event', on_key)
    
    # Show the plot with specific padding for buttons
    plt.subplots_adjust(top=0.9, bottom=0.05)
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
