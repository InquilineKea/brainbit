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
import time
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
QUALITY_TAB_NAME = "quality"
raw_normalized = True  # True: z-score, False: microvolts
raw_filter_on = False  # Band-pass filtering for Raw tab
raw_notch_on = False   # 60 Hz notch filter for Raw tab
log_file = None
last_log_ts = 0.0
last_snapshot_ts = 0.0
alpha_baseline = {}     # per-channel EMA baseline for alpha power
last_alpha_flag_ts = 0.0

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

def apply_raw_axis_mode(eeg_axes, buffer_seconds):
    """Apply axis labels and limits for the Raw tab based on raw_normalized."""
    for ax in eeg_axes:
        if raw_normalized:
            ax.set_ylabel('Normalized (z)', fontsize=10)
            ax.set_ylim(-3, 3)
        else:
            ax.set_ylabel('μV', fontsize=10)
            ax.set_ylim(-eeg_y_limit, eeg_y_limit)
        ax.set_xlim(-buffer_seconds, 0)

def main():
    """Main function to connect to BrainBit and display data."""
    global board, fig, gs, current_tab, log_file, last_log_ts, last_snapshot_ts, raw_filter_on, raw_notch_on, alpha_baseline, last_alpha_flag_ts
    
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
    # Initialize logging
    try:
        log_file = open("eeg_log.txt", "a", buffering=1)
        log_file.write(f"\n=== EEG session start {time.strftime('%Y-%m-%d %H:%M:%S')} ===\n")
        log_file.flush()
    except Exception as e:
        print(f"Could not open eeg_log.txt for logging: {e}")
    
    # Buffer and window sizes
    buffer_seconds = 5
    buffer_size = int(buffer_seconds * sample_rate)
    window_size = int(4 * sample_rate)  # 4 seconds for spectral analysis
    
    # Channel indices via BrainFlow descriptor
    eeg_channels = BoardShim.get_eeg_channels(board_id)
    print(f"EEG channel indices: {eeg_channels}")
    # Channel names for BrainBit (fallback generic if unexpected count)
    if len(eeg_channels) == 4:
        channel_names = ["T3", "T4", "O1", "O2"]
    else:
        channel_names = [f"Ch {i+1}" for i in range(len(eeg_channels))]
    
    # Create figure
    fig = plt.figure(figsize=(12, 8))
    
    # Create tab buttons
    ax_raw_button = plt.axes([0.25, 0.95, 0.15, 0.04])
    ax_power_button = plt.axes([0.42, 0.95, 0.15, 0.04])
    ax_spectral_button = plt.axes([0.59, 0.95, 0.15, 0.04])
    ax_quality_button = plt.axes([0.76, 0.95, 0.15, 0.04])
    
    btn_raw = Button(ax_raw_button, 'Raw EEG')
    btn_power = Button(ax_power_button, 'Band Power')
    btn_spectral = Button(ax_spectral_button, '1/f Analysis')
    btn_quality = Button(ax_quality_button, 'Quality')
    
    btn_raw.on_clicked(switch_to_raw)
    btn_power.on_clicked(switch_to_power)
    btn_spectral.on_clicked(switch_to_spectral)
    
    def switch_to_quality(event):
        switch_tab(QUALITY_TAB_NAME)
    btn_quality.on_clicked(switch_to_quality)
    
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
        ax.set_ylabel('Normalized (z)', fontsize=10)
        ax.grid(True)
        
        # Fixed y-axis limits for normalized data (may be overridden by toggle)
        ax.set_ylim(-3, 3)
        # Fixed x-axis limits for time window so data is visible
        ax.set_xlim(-buffer_seconds, 0)
        
    # Set x-axis label for bottom EEG plot
    eeg_axes[-1].set_xlabel('Time (s)', fontsize=10)

    # Apply axis mode according to current toggle state
    apply_raw_axis_mode(eeg_axes, buffer_seconds)

    # Add toggle button for Raw scaling (after EEG axes exist)
    ax_toggle_button = plt.axes([0.06, 0.90, 0.15, 0.04])
    btn_toggle = Button(ax_toggle_button, 'Raw: Norm')

    def toggle_raw_mode(event):
        global raw_normalized
        raw_normalized = not raw_normalized
        btn_toggle.label.set_text('Raw: Norm' if raw_normalized else 'Raw: μV')
        apply_raw_axis_mode(eeg_axes, buffer_seconds)
        fig.canvas.draw_idle()
    btn_toggle.on_clicked(toggle_raw_mode)

    # Add Raw filter toggle button
    ax_filter_button = plt.axes([0.06, 0.85, 0.15, 0.04])
    btn_filter = Button(ax_filter_button, 'Filter: OFF')

    def toggle_filter(event):
        global raw_filter_on
        raw_filter_on = not raw_filter_on
        btn_filter.label.set_text('Filter: ON' if raw_filter_on else 'Filter: OFF')
        fig.canvas.draw_idle()
    btn_filter.on_clicked(toggle_filter)

    # Add Raw notch toggle button (60 Hz)
    ax_notch_button = plt.axes([0.06, 0.75, 0.15, 0.04])
    btn_notch = Button(ax_notch_button, 'Notch: OFF')

    def toggle_notch(event):
        global raw_notch_on
        raw_notch_on = not raw_notch_on
        btn_notch.label.set_text('Notch: 60' if raw_notch_on else 'Notch: OFF')
        fig.canvas.draw_idle()
    btn_notch.on_clicked(toggle_notch)

    # Reset zoom button restores default limits for active tab
    ax_reset_button = plt.axes([0.06, 0.80, 0.15, 0.04])
    btn_reset = Button(ax_reset_button, 'Reset Zoom')

    def reset_zoom(event):
        # Determine which tab is active and reset only visible axes
        if current_tab == 'raw':
            apply_raw_axis_mode(eeg_axes, buffer_seconds)
        elif current_tab == 'power':
            for ax in power_axes:
                if ax.get_visible():
                    ax.set_ylim(0, power_y_limit)
        elif current_tab == QUALITY_TAB_NAME:
            for ax in quality_axes:
                if ax.get_visible():
                    ax.set_ylim(0, 50)
        elif current_tab == 'spectral':
            for ax in spectral_axes:
                if ax.get_visible():
                    ax.set_xscale('log')
                    ax.set_yscale('log')
                    ax.set_xlim(1, 50)
                    ax.set_ylim(0.1, spectral_y_limit)
        fig.canvas.draw_idle()

    btn_reset.on_clicked(reset_zoom)

    # Scroll-to-zoom handler (trackpad/mouse wheel)
    def on_scroll(event):
        ax = event.inaxes
        if ax is None or not hasattr(ax, 'tab_type'):
            return
        # Only zoom active/visible axes
        if not ax.get_visible():
            return
        # Zoom factor
        factor = 1.2 if event.button == 'up' else (1/1.2)
        try:
            if ax.tab_type == 'raw':
                # Zoom both x and y
                # X
                xlim = list(ax.get_xlim())
                if event.xdata is not None:
                    cx = event.xdata
                    span = (xlim[1] - xlim[0]) / factor
                    ax.set_xlim(cx - span/2, cx + span/2)
                # Y
                ylim = list(ax.get_ylim())
                if event.ydata is not None:
                    cy = event.ydata
                    span = (ylim[1] - ylim[0]) / factor
                    min_span = 0.1 if raw_normalized else 10.0
                    span = max(span, min_span)
                    ax.set_ylim(cy - span/2, cy + span/2)
            elif ax.tab_type == 'power' or ax.tab_type == QUALITY_TAB_NAME:
                # Bars: only Y zoom
                ylim = list(ax.get_ylim())
                cy = event.ydata if event.ydata is not None else (ylim[0] + ylim[1]) / 2
                span = (ylim[1] - ylim[0]) / factor
                span = max(span, 1.0)
                new0 = max(0.0, cy - span/2)
                new1 = max(new0 + 0.5, cy + span/2)
                ax.set_ylim(new0, new1)
            elif ax.tab_type == 'spectral':
                # Log-log zoom, keep within bounds
                xmin, xmax = ax.get_xlim()
                ymin, ymax = ax.get_ylim()
                # X in log space
                if event.xdata is not None and event.xdata > 0:
                    import math
                    log_xmin, log_xmax = math.log10(xmin), math.log10(xmax)
                    c = math.log10(event.xdata)
                    span = (log_xmax - log_xmin) / factor
                    span = max(span, 0.1)
                    ax.set_xlim(max(1, 10**(c - span/2)), min(50, 10**(c + span/2)))
                # Y in log space
                if event.ydata is not None and event.ydata > 0:
                    import math
                    log_ymin, log_ymax = math.log10(ymin), math.log10(ymax)
                    c = math.log10(event.ydata)
                    span = (log_ymax - log_ymin) / factor
                    span = max(span, 0.2)
                    lo = 10**(c - span/2)
                    hi = 10**(c + span/2)
                    lo = max(1e-2, lo)
                    hi = min(spectral_y_limit, hi)
                    if hi > lo:
                        ax.set_ylim(lo, hi)
            fig.canvas.draw_idle()
        except Exception:
            pass

    fig.canvas.mpl_connect('scroll_event', on_scroll)

    # Snapshot button: write CSVs immediately for inspection
    ax_snap_button = plt.axes([0.06, 0.70, 0.15, 0.04])
    btn_snap = Button(ax_snap_button, 'Snapshot CSV')

    def do_snapshot(event=None):
        try:
            cur = board.get_current_board_data(max(buffer_size, window_size))
            if cur.size == 0 or cur.shape[1] == 0:
                print("Snapshot: no data available yet")
                return
            snap_win = min(int(10 * sample_rate), cur.shape[1])
            if snap_win < int(1 * sample_rate):
                print(f"Snapshot: insufficient data ({cur.shape[1]} samples)")
                return
            # raw μV CSV
            segs_uv = []
            for ch_idx in eeg_channels:
                if ch_idx < cur.shape[0]:
                    segs_uv.append(cur[ch_idx, -snap_win:] * 1e6)
            tvec = np.linspace(-snap_win / sample_rate, 0, snap_win)
            import csv
            with open('eeg_snapshot_raw.csv', 'w', newline='') as fcsv:
                writer = csv.writer(fcsv)
                writer.writerow(['time_s'] + channel_names)
                for k in range(snap_win):
                    row = [f"{tvec[k]:.4f}"] + [f"{segs_uv[c][k]:.3f}" for c in range(len(eeg_channels))]
                    writer.writerow(row)
            # band powers CSV (last 4 s)
            bp_win = min(int(4 * sample_rate), cur.shape[1])
            band_names_local = list(bands.keys())
            with open('eeg_snapshot_bands.csv', 'w', newline='') as fbp:
                writer = csv.writer(fbp)
                header = ['timestamp']
                for cname in channel_names:
                    for bname in band_names_local:
                        header.append(f"{cname}_{bname}")
                writer.writerow(header)
                vals = []
                for ch_idx in eeg_channels:
                    if ch_idx < cur.shape[0]:
                        seg_uv = cur[ch_idx, -bp_win:] * 1e6
                        powers = [compute_band_power(seg_uv, sample_rate, bands[b]) for b in band_names_local]
                        vals.extend([f"{p:.3f}" for p in powers])
                    else:
                        vals.extend(["0.000"] * len(band_names_local))
                writer.writerow([time.strftime('%Y-%m-%d %H:%M:%S')] + vals)
            print("Snapshot written: eeg_snapshot_raw.csv, eeg_snapshot_bands.csv")
        except Exception as e:
            print(f"Snapshot error: {e}")

    btn_snap.on_clicked(do_snapshot)
    
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

    # Create Quality axes (initially hidden)
    quality_axes = []
    quality_bars = []
    for i in range(4):
        ax = fig.add_subplot(gs[i, 0])
        ax.tab_type = QUALITY_TAB_NAME
        quality_axes.append(ax)
        # One bar per channel showing RMS amplitude over last window
        bars = ax.bar([channel_names[i]], [0.0], color=["#2ca02c"])  # start green
        quality_bars.append(bars)
        ax.set_ylim(0, 50)  # μV RMS scale; adjust dynamically
        ax.set_ylabel("RMS (μV)")
        ax.set_title(f"Channel {channel_names[i]} - Quality", fontsize=12)
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
        tab_names = {"raw": "Raw EEG", "power": "Band Power", "spectral": "1/f Analysis", QUALITY_TAB_NAME: "Quality"}
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
                    # Optional 60 Hz notch
                    if raw_notch_on and y_data.size > 8:
                        try:
                            nyq = 0.5 * sample_rate
                            from scipy.signal import iirnotch, filtfilt
                            b_notch, a_notch = iirnotch(60.0 / nyq, 30.0)
                            y_data = filtfilt(b_notch, a_notch, y_data)
                        except Exception:
                            pass
                    # Optional band-pass filter 1-40 Hz
                    if raw_filter_on and y_data.size > 8:
                        try:
                            nyq = 0.5 * sample_rate
                            b, a = signal.butter(4, [1.0/nyq, 40.0/nyq], btype='band')
                            y_data = signal.filtfilt(b, a, y_data)
                        except Exception:
                            pass
                    if raw_normalized:
                        # Per-channel normalization (z-score)
                        mu = np.mean(y_data)
                        sigma = np.std(y_data)
                        if sigma < 1e-6:
                            y_plot = y_data * 0.0
                        else:
                            y_plot = (y_data - mu) / sigma
                    else:
                        # Convert to microvolts for μV display
                        y_plot = y_data * 1e6
                    
                    # Update line data
                    eeg_lines[i].set_data(x_data[-len(y_plot):], y_plot)
        
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
        # Update Quality tab
        elif current_tab == QUALITY_TAB_NAME:
            if data.shape[1] >= sample_rate:  # at least 1 second
                window = min(2 * sample_rate, data.shape[1])
                # thresholds
                flat_eps_uv = 0.5  # µV std threshold for flatline
                for i, ch_idx in enumerate(eeg_channels):
                    if ch_idx < data.shape[0]:
                        seg = data[ch_idx, -window:]
                        # Compute RMS in μV
                        rms = float(np.sqrt(np.mean(seg ** 2)) * 1e6) if seg.size else 0.0
                        bar = quality_bars[i][0]
                        bar.set_height(rms)
                        # Dynamic y max
                        ymax = max(50.0, rms * 1.5)
                        quality_axes[i].set_ylim(0, ymax)
                        # Color coding: flatline, ok, noisy
                        std_uv = float(np.std(seg) * 1e6) if seg.size else 0.0
                        if std_uv < flat_eps_uv:
                            color = "#d62728"  # red: flat
                        elif rms < 3.0:
                            color = "#ff7f0e"  # orange: low amplitude
                        elif rms > 60.0:
                            color = "#d62728"  # red: noisy
                        else:
                            color = "#2ca02c"  # green
                        bar.set_color(color)
                        quality_axes[i].set_title(f"{channel_names[i]} - Quality | RMS {rms:.1f} μV (std {std_uv:.1f} μV)", fontsize=12)

        # Periodic logging (once per second) of RMS in μV for all channels, plus console stats and alpha auto-flag
        try:
            now = time.time()
            if data.shape[1] > 0 and (now - last_log_ts) >= 1.0 and log_file is not None:
                window = min(2 * sample_rate, data.shape[1])
                rms_vals = []
                for i, ch_idx in enumerate(eeg_channels):
                    if ch_idx < data.shape[0]:
                        seg = data[ch_idx, -window:]
                        rms_uv = float(np.sqrt(np.mean(seg ** 2)) * 1e6) if seg.size else 0.0
                        rms_vals.append(rms_uv)
                    else:
                        rms_vals.append(0.0)
                mode = 'Norm' if raw_normalized else 'μV'
                filt = 'ON' if raw_filter_on else 'OFF'
                notch = '60' if raw_notch_on else 'OFF'
                ts = time.strftime('%H:%M:%S')
                # Compose log line
                ch_names = channel_names if len(channel_names) == len(rms_vals) else [f"Ch{i+1}" for i in range(len(rms_vals))]
                parts = [f"{ch_names[i]}={rms_vals[i]:.1f}" for i in range(len(rms_vals))]
                samples = data.shape[1]
                line = f"{ts} | samples={samples} | RMS(μV) | " + ", ".join(parts) + f" | RawMode={mode} | Filter={filt} | Notch={notch}\n"
                log_file.write(line)
                log_file.flush()
                # Also print per-second stats to console
                print(line.strip())
                last_log_ts = now

                # Quick channel mean/std in μV for diagnostics
                try:
                    stats_uv = []
                    for i, ch_idx in enumerate(eeg_channels):
                        if ch_idx < data.shape[0]:
                            seg = data[ch_idx, -window:]
                            stats_uv.append((float(np.mean(seg) * 1e6), float(np.std(seg) * 1e6)))
                        else:
                            stats_uv.append((0.0, 0.0))
                    stats_str = ", ".join([f"{ch_names[i]}: mean={m:.1f}μV std={s:.1f}μV" for i,(m,s) in enumerate(stats_uv)])
                    print(f"{ts} | stats | {stats_str}")
                except Exception:
                    pass

                # Alpha auto-flag on occipital channels (O1/O2) if present
                try:
                    bp_win = min(int(4 * sample_rate), data.shape[1])
                    if bp_win >= int(1 * sample_rate):
                        # pick occipital indices by name if available, else last two channels
                        occ_idx = [i for i, nm in enumerate(ch_names) if 'O' in nm.upper()]
                        if not occ_idx:
                            occ_idx = list(range(max(0, len(eeg_channels)-2), len(eeg_channels)))
                        # compute band powers on µV data
                        for i in occ_idx:
                            ch_idx = eeg_channels[i]
                            if ch_idx < data.shape[0]:
                                seg_uv = data[ch_idx, -bp_win:] * 1e6
                                p_delta = compute_band_power(seg_uv, sample_rate, bands['delta'])
                                p_theta = compute_band_power(seg_uv, sample_rate, bands['theta'])
                                p_alpha = compute_band_power(seg_uv, sample_rate, bands['alpha'])
                                p_beta  = compute_band_power(seg_uv, sample_rate, bands['beta'])
                                # EMA baseline
                                base = alpha_baseline.get(i, p_alpha)
                                alpha_baseline[i] = 0.9 * base + 0.1 * p_alpha
                                # conditions: alpha dominates and exceeds baseline by 50%
                                dominates = (p_alpha > p_theta) and (p_alpha > p_beta)
                                if dominates and p_alpha > 1.5 * max(base, 1e-9):
                                    if (now - last_alpha_flag_ts) > 3.0:
                                        print(f"{ts} | Alpha burst likely (eyes closed?) on {ch_names[i]}: alpha={p_alpha:.2f}, baseline={base:.2f}, θ={p_theta:.2f}, β={p_beta:.2f}")
                                        last_alpha_flag_ts = now
                except Exception:
                    pass
        except Exception:
            pass

        # Periodic CSV snapshot (every 10 seconds): last 10s raw μV and band powers
        try:
            now2 = time.time()
            if data.shape[1] > 0 and (now2 - last_snapshot_ts) >= 10.0:
                snap_win = min(int(10 * sample_rate), data.shape[1])
                if snap_win >= int(1 * sample_rate):
                    # Build raw µV CSV (overwrite)
                    segs_uv = []
                    for ch_idx in eeg_channels:
                        if ch_idx < data.shape[0]:
                            seg = data[ch_idx, -snap_win:]
                            segs_uv.append(seg * 1e6)
                    if len(segs_uv) == len(eeg_channels):
                        tvec = np.linspace(-snap_win / sample_rate, 0, snap_win)
                        import csv
                        with open('eeg_snapshot_raw.csv', 'w', newline='') as fcsv:
                            writer = csv.writer(fcsv)
                            writer.writerow(['time_s'] + channel_names)
                            for k in range(snap_win):
                                row = [f"{tvec[k]:.4f}"] + [f"{segs_uv[c][k]:.3f}" for c in range(len(eeg_channels))]
                                writer.writerow(row)
                    # Build band power CSV for last 4 s window
                    bp_win = min(int(4 * sample_rate), data.shape[1])
                    band_names = list(bands.keys())
                    with open('eeg_snapshot_bands.csv', 'w', newline='') as fbp:
                        import csv
                        writer = csv.writer(fbp)
                        header = ['timestamp']
                        for cname in channel_names:
                            for bname in band_names:
                                header.append(f"{cname}_{bname}")
                        writer.writerow(header)
                        # compute on µV data for proper units
                        vals = []
                        for ch_idx in eeg_channels:
                            if ch_idx < data.shape[0]:
                                seg_uv = data[ch_idx, -bp_win:] * 1e6
                                powers = [compute_band_power(seg_uv, sample_rate, bands[b]) for b in band_names]
                                vals.extend([f"{p:.3f}" for p in powers])
                            else:
                                vals.extend(["0.000"] * len(band_names))
                        writer.writerow([time.strftime('%Y-%m-%d %H:%M:%S')] + vals)
                    last_snapshot_ts = now2
        except Exception:
            pass
    
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
