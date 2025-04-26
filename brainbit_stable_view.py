#!/usr/bin/env python3
"""
BrainBit Stable Multi-View

Shows raw EEG signals, band power, and 1/f spectral analysis in a single window with tabbed interface.
Features:
- Fixed y-axes to prevent constant rescaling
- Raw EEG visualization
- Absolute band power display
- 1/f spectral analysis with slope estimation (Voytek method)
- No blitting for maximum stability
"""

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from scipy import signal
from scipy import stats
from brainflow.board_shim import BoardShim, BrainFlowInputParams, LogLevels, BoardIds
import matplotlib.gridspec as gridspec
from matplotlib.widgets import Button

# Global variables
board = None
fig = None
gs = None
current_tab = "raw"  # 'raw', 'power', or 'spectral'

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
eeg_y_limit = 150      # ±150 μV for raw EEG
power_y_limit = 50      # 0-50 μV²/Hz for band power
spectral_y_limit = 1e4   # 0-10,000 for PSD

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
    Fit the 1/f spectral slope (Voytek method).
    Returns the slope (exponent) and estimated brain age.
    
    A steeper slope (more negative exponent) is associated with older brain age.
    Young adults typically have slopes around -1 to -2.
    Older adults typically have slopes around -2 to -3.
    """
    # Log-transform the data
    log_f = np.log10(f)
    log_psd = np.log10(psd)
    
    # Find frequency range indices
    idx = np.logical_and(f >= f_range[0], f <= f_range[1])
    
    # Skip if not enough data points
    if np.sum(idx) < 5:
        return 0, 0, f[idx], np.zeros_like(f[idx])
    
    # Linear fit in log-log space
    slope, intercept, r_value, p_value, std_err = stats.linregress(log_f[idx], log_psd[idx])
    
    # Very rough estimation of "brain age" (for demonstration)
    # This is oversimplified - real brain age estimation is much more complex
    if slope > -1:
        brain_age = "< 20 yrs"
    elif slope > -2:
        brain_age = "20-40 yrs"
    elif slope > -3:
        brain_age = "40-60 yrs"
    else:
        brain_age = "> 60 yrs"
    
    # Generate the fit line
    fit_log_psd = intercept + slope * log_f[idx]
    fit_psd = 10 ** fit_log_psd
    
    return slope, brain_age, f[idx], fit_psd

def switch_tab(target_tab):
    """Switch to specified tab."""
    global current_tab
    current_tab = target_tab
    show_current_tab()

def switch_to_raw(event):
    """Switch to raw EEG tab."""
    switch_tab("raw")

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
    ax_raw_button = plt.axes([0.25, 0.95, 0.15, 0.04])
    ax_power_button = plt.axes([0.42, 0.95, 0.15, 0.04])
    ax_spectral_button = plt.axes([0.59, 0.95, 0.15, 0.04])
    
    btn_raw = Button(ax_raw_button, 'Raw EEG')
    btn_power = Button(ax_power_button, 'Band Power')
    btn_spectral = Button(ax_spectral_button, '1/f Analysis')
    
    btn_raw.on_clicked(switch_to_raw)
    btn_power.on_clicked(switch_to_power)
    btn_spectral.on_clicked(switch_to_spectral)
    
    # Create main grid for content
    gs = gridspec.GridSpec(4, 1, figure=fig, hspace=0.4, top=0.9)
    
    # Create EEG axes
    eeg_axes = []
    eeg_lines = []
    for i in range(4):
        ax = fig.add_subplot(gs[i, 0])
        ax.tab_type = "raw"  # Add attribute to identify tab
        eeg_axes.append(ax)
        
        line, = ax.plot([], [], lw=1.5, color='blue')
        eeg_lines.append(line)
        
        ax.set_title(f"Channel {channel_names[i]}", fontsize=12)
        ax.set_ylabel('μV', fontsize=10)
        ax.grid(True)
        
        # Fixed y-axis limits
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
        ax.set_title(f"Channel {channel_names[i]} - Raw Power", fontsize=12)
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
        ax.set_title(f"Channel {channel_names[i]} - Spectral Analysis", fontsize=12)
        ax.set_xlabel('Frequency (Hz)', fontsize=10)
        ax.set_ylabel('PSD (µV²/Hz)', fontsize=10)
        ax.set_xscale('log')
        ax.set_yscale('log')
        ax.set_xlim(1, 50)
        ax.set_ylim(0.1, spectral_y_limit)
        ax.grid(True, which='both', linestyle='--', alpha=0.7)
        ax.legend(loc='upper right')
        
        # Add text for slope and brain age estimate
        text = ax.text(
            0.05, 0.95, "", 
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
        tab_names = {"raw": "Raw EEG", "power": "Band Power", "spectral": "1/f Analysis"}
        status_text.set_text(f"Connected | Tab: {tab_names[current_tab]}")
        
        # Get the latest data
        data = board.get_current_board_data(max(buffer_size, window_size))
        
        if data.size == 0 or data.shape[1] == 0:
            return
        
        # Update Raw EEG tab
        if current_tab == "raw":
            x_data = np.linspace(-buffer_seconds, 0, min(buffer_size, data.shape[1]))
            
            for i, ch_idx in enumerate(eeg_channels):
                if ch_idx < data.shape[0]:
                    # Get last buffer_size samples or available samples
                    samples = min(buffer_size, data.shape[1])
                    y_data = data[ch_idx, -samples:]
                    
                    # Update line data
                    eeg_lines[i].set_data(x_data[-len(y_data):], y_data)
        
        # Update Band Power tab  
        elif current_tab == "power":
            if data.shape[1] >= window_size:
                for i, ch_idx in enumerate(eeg_channels):
                    if ch_idx < data.shape[0]:
                        # Get channel data (last window_size samples)
                        ch_data = data[ch_idx, -window_size:]
                        
                        # Calculate power for each band
                        powers = []
                        for band_name, band_range in bands.items():
                            power = compute_band_power(ch_data, sample_rate, band_range)
                            powers.append(power)
                        
                        # Update bar heights
                        for j, bar in enumerate(power_bars[i]):
                            bar.set_height(min(powers[j], power_y_limit * 0.95))
                        
                        # Update title with values
                        power_axes[i].set_title(
                            f"{channel_names[i]}: δ:{powers[0]:.1f}, θ:{powers[1]:.1f}, α:{powers[2]:.1f}, β:{powers[3]:.1f}", 
                            fontsize=10
                        )
        
        # Update Spectral Analysis tab
        elif current_tab == "spectral":
            if data.shape[1] >= window_size:
                for i, ch_idx in enumerate(eeg_channels):
                    if ch_idx < data.shape[0]:
                        # Get channel data (last window_size samples)
                        ch_data = data[ch_idx, -window_size:]
                        
                        # Compute PSD
                        f, psd = compute_psd(ch_data, sample_rate)
                        
                        if len(f) > 0 and len(psd) > 0:
                            # Update PSD line
                            psd_lines[i].set_data(f, psd)
                            
                            # Compute and update 1/f fit
                            slope, brain_age, f_fit, psd_fit = fit_1f_spectrum(f, psd)
                            fit_lines[i].set_data(f_fit, psd_fit)
                            
                            # Update slope text
                            slope_texts[i].set_text(
                                f"1/f Slope: {slope:.2f}\nEst. Brain Age: {brain_age}"
                            )
                            
                            # Update title
                            spectral_axes[i].set_title(
                                f"Channel {channel_names[i]} - 1/f Analysis", 
                                fontsize=12
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
