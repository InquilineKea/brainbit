#!/usr/bin/env python3
"""
BrainBit Lite Monitor

A lightweight Python script that saves BrainBit data to a JSON file,
which is then visualized by a standalone HTML/JavaScript application.
"""

import os
import time
import threading
import json
import numpy as np
from scipy import signal

# BrainFlow imports
import brainflow
from brainflow.board_shim import BoardShim, BrainFlowInputParams, BoardIds, LogLevels
from brainflow.data_filter import DataFilter, FilterTypes, DetrendOperations

# Global variables
buffer_size = 1250  # 5 seconds at 250 Hz
eeg_buffers = {}
filtered_buffers = {}
psd_data = {}
band_powers = {}
power_law_data = {}

# Frequency bands
freq_bands = {
    'Delta': (0.5, 4),
    'Theta': (4, 8),
    'Alpha': (8, 13),
    'Beta': (13, 30),
    'Gamma': (30, 50)
}

# Board configuration
board = None
board_id = None
sampling_rate = None
eeg_channels = None
ch_names = None

# Lock for thread safety
data_lock = threading.Lock()

# Output file
output_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'brainbit_data.json')
html_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'brainbit_viewer.html')

def write_html_file():
    """Write the HTML file for visualization."""
    html_content = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>BrainBit Lite Visualizer</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 0;
            background-color: #f0f0f0;
        }
        .container {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 15px;
            padding: 15px;
            max-width: 1600px;
            margin: 0 auto;
        }
        .chart-container {
            background-color: white;
            border-radius: 8px;
            box-shadow: 0 2px 6px rgba(0,0,0,0.1);
            padding: 15px;
            height: 250px;
        }
        h1, h2 {
            color: #333;
            margin-top: 0;
        }
        h1 {
            text-align: center;
            padding: 15px;
            background-color: #2c3e50;
            color: white;
            margin: 0;
            margin-bottom: 15px;
        }
        .stats {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 10px;
            margin-top: 10px;
        }
        .stat-box {
            background-color: #f8f9fa;
            padding: 8px;
            border-radius: 4px;
            font-size: 14px;
        }
        .dominant {
            font-weight: bold;
            color: #e74c3c;
        }
        .buttons {
            display: flex;
            justify-content: center;
            margin: 15px 0;
            gap: 10px;
        }
        button {
            padding: 8px 15px;
            background-color: #3498db;
            color: white;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 14px;
        }
        button:hover {
            background-color: #2980b9;
        }
        .status {
            text-align: center;
            margin-bottom: 15px;
            font-weight: bold;
        }
        #status-indicator {
            display: inline-block;
            width: 12px;
            height: 12px;
            border-radius: 50%;
            background-color: #e74c3c;
            margin-right: 5px;
        }
        #status-indicator.connected {
            background-color: #2ecc71;
        }
    </style>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
</head>
<body>
    <h1>BrainBit Lite Visualizer</h1>
    
    <div class="status">
        <span id="status-indicator"></span>
        <span id="status-text">Disconnected</span>
    </div>
    
    <div class="buttons">
        <button id="btn-zoom-reset">Reset Zoom</button>
        <button id="btn-pause">Pause</button>
    </div>
    
    <div class="container">
        <!-- EEG Signal Charts -->
        <div class="chart-container">
            <h2>T3 EEG Signal</h2>
            <canvas id="t3-chart"></canvas>
            <div class="stats" id="t3-stats"></div>
        </div>
        
        <div class="chart-container">
            <h2>T4 EEG Signal</h2>
            <canvas id="t4-chart"></canvas>
            <div class="stats" id="t4-stats"></div>
        </div>
        
        <div class="chart-container">
            <h2>O1 EEG Signal</h2>
            <canvas id="o1-chart"></canvas>
            <div class="stats" id="o1-stats"></div>
        </div>
        
        <div class="chart-container">
            <h2>O2 EEG Signal</h2>
            <canvas id="o2-chart"></canvas>
            <div class="stats" id="o2-stats"></div>
        </div>
        
        <!-- PSD Charts -->
        <div class="chart-container">
            <h2>T3 Power Spectral Density</h2>
            <canvas id="t3-psd-chart"></canvas>
        </div>
        
        <div class="chart-container">
            <h2>T4 Power Spectral Density</h2>
            <canvas id="t4-psd-chart"></canvas>
        </div>
        
        <div class="chart-container">
            <h2>O1 Power Spectral Density</h2>
            <canvas id="o1-psd-chart"></canvas>
        </div>
        
        <div class="chart-container">
            <h2>O2 Power Spectral Density</h2>
            <canvas id="o2-psd-chart"></canvas>
        </div>
    </div>

    <script>
        // Global variables
        const eegCharts = {};
        const psdCharts = {};
        let isPaused = false;
        let lastData = null;
        let updateInterval;
        
        // Format the time axis labels (5 seconds window)
        const timeLabels = Array.from({length: 1250}, (_, i) => -5 + i * (5 / 1250));
        
        // Channel configuration
        const channels = ['T3', 'T4', 'O1', 'O2'];
        const colors = {
            'T3': '#3498db',
            'T4': '#e74c3c',
            'O1': '#2ecc71',
            'O2': '#f39c12'
        };
        
        // Initialize all charts
        function initCharts() {
            // Initialize EEG charts
            channels.forEach(channel => {
                const ctx = document.getElementById(`${channel.toLowerCase()}-chart`).getContext('2d');
                eegCharts[channel] = new Chart(ctx, {
                    type: 'line',
                    data: {
                        labels: timeLabels,
                        datasets: [{
                            label: 'Raw',
                            data: Array(1250).fill(0),
                            borderColor: `${colors[channel]}33`,
                            borderWidth: 1,
                            pointRadius: 0,
                            fill: false
                        }, {
                            label: 'Filtered',
                            data: Array(1250).fill(0),
                            borderColor: colors[channel],
                            borderWidth: 1.5,
                            pointRadius: 0,
                            fill: false
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        animation: {
                            duration: 0
                        },
                        scales: {
                            x: {
                                title: {
                                    display: true,
                                    text: 'Time (s)'
                                }
                            },
                            y: {
                                title: {
                                    display: true,
                                    text: 'Amplitude'
                                },
                                min: -120,
                                max: 120
                            }
                        },
                        plugins: {
                            legend: {
                                display: false
                            }
                        }
                    }
                });
                
                // Initialize PSD charts
                const psdCtx = document.getElementById(`${channel.toLowerCase()}-psd-chart`).getContext('2d');
                psdCharts[channel] = new Chart(psdCtx, {
                    type: 'line',
                    data: {
                        labels: Array(100).fill(0).map((_, i) => i),
                        datasets: [{
                            label: 'PSD',
                            data: Array(100).fill(0),
                            borderColor: colors[channel],
                            borderWidth: 1.5,
                            pointRadius: 0,
                            fill: false
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        animation: {
                            duration: 0
                        },
                        scales: {
                            x: {
                                title: {
                                    display: true,
                                    text: 'Frequency (Hz)'
                                },
                                min: 0,
                                max: 40
                            },
                            y: {
                                title: {
                                    display: true,
                                    text: 'Power'
                                },
                                beginAtZero: true
                            }
                        },
                        plugins: {
                            legend: {
                                display: false
                            }
                        }
                    }
                });
            });
        }
        
        // Update channel statistics display
        function updateStats(channel, data) {
            if (!data) return;
            
            const statsDiv = document.getElementById(`${channel.toLowerCase()}-stats`);
            
            // Create HTML for power law info
            let statsHtml = `<div class="stat-box">
                <strong>1/f Slope:</strong> α = ${data.alpha ? data.alpha.toFixed(2) : 'N/A'}<br>
                <strong>Dominant:</strong> ${data.dominant || 'N/A'}
            </div>`;
            
            // Create HTML for band powers
            statsHtml += '<div class="stat-box">';
            if (data.band_powers) {
                for (const [band, power] of Object.entries(data.band_powers)) {
                    if (band === data.dominant) {
                        statsHtml += `<span class="dominant">${band}: ${power.toFixed(1)}</span><br>`;
                    } else {
                        statsHtml += `${band}: ${power.toFixed(1)}<br>`;
                    }
                }
            }
            statsHtml += '</div>';
            
            statsDiv.innerHTML = statsHtml;
        }
        
        // Update the charts with new data
        function updateCharts(data) {
            if (!data) return;
            
            // Update connection status
            document.getElementById('status-indicator').className = 'connected';
            document.getElementById('status-text').textContent = 'Connected';
            
            // Update EEG charts
            channels.forEach(channel => {
                if (data.eeg && data.eeg[channel]) {
                    eegCharts[channel].data.datasets[0].data = data.eeg[channel].raw;
                    eegCharts[channel].data.datasets[1].data = data.eeg[channel].filtered;
                    eegCharts[channel].update();
                }
                
                if (data.psd && data.psd[channel]) {
                    psdCharts[channel].data.labels = data.psd[channel].freqs;
                    psdCharts[channel].data.datasets[0].data = data.psd[channel].powers;
                    psdCharts[channel].update();
                }
                
                if (data.channel_info && data.channel_info[channel]) {
                    updateStats(channel, data.channel_info[channel]);
                }
            });
        }
        
        // Fetch and update data
        function fetchData() {
            if (isPaused) {
                return;
            }
            
            fetch('brainbit_data.json')
                .then(response => response.json())
                .then(data => {
                    lastData = data;
                    updateCharts(data);
                })
                .catch(error => {
                    console.error('Error fetching data:', error);
                    document.getElementById('status-indicator').className = '';
                    document.getElementById('status-text').textContent = 'Disconnected';
                });
        }
        
        // Initialize the application
        function init() {
            initCharts();
            
            // Setup event listeners
            document.getElementById('btn-zoom-reset').addEventListener('click', () => {
                channels.forEach(channel => {
                    eegCharts[channel].options.scales.y.min = -120;
                    eegCharts[channel].options.scales.y.max = 120;
                    eegCharts[channel].update();
                    
                    psdCharts[channel].options.scales.x.min = 0;
                    psdCharts[channel].options.scales.x.max = 40;
                    psdCharts[channel].update();
                });
            });
            
            document.getElementById('btn-pause').addEventListener('click', () => {
                isPaused = !isPaused;
                document.getElementById('btn-pause').textContent = isPaused ? 'Resume' : 'Pause';
            });
            
            // Start fetching data
            fetchData();
            updateInterval = setInterval(fetchData, 100);
        }
        
        // Start the application when the page loads
        document.addEventListener('DOMContentLoaded', init);
    </script>
</body>
</html>
"""
    
    with open(html_file, 'w') as f:
        f.write(html_content)
    
    print(f"Created HTML viewer at: {html_file}")
    return html_file

def connect_to_brainbit():
    """Connect to BrainBit device."""
    global board, board_id, sampling_rate, eeg_channels, ch_names
    
    params = BrainFlowInputParams()
    
    # Set log level
    BoardShim.enable_dev_board_logger()
    BoardShim.set_log_level(LogLevels.LEVEL_INFO.value)
    
    try:
        print("Attempting to connect to BrainBit...")
        board = BoardShim(BoardIds.BRAINBIT_BOARD, params)
        board.prepare_session()
        board_id = BoardIds.BRAINBIT_BOARD
        print("Successfully connected to BrainBit!")
    except brainflow.board_shim.BrainFlowError as e:
        print(f"Failed to connect to BrainBit: {e}")
        try:
            print("Attempting to connect to BrainBit BLED...")
            board = BoardShim(BoardIds.BRAINBIT_BLED_BOARD, params)
            board.prepare_session()
            board_id = BoardIds.BRAINBIT_BLED_BOARD
            print("Successfully connected to BrainBit BLED!")
        except brainflow.board_shim.BrainFlowError as e2:
            print(f"Failed to connect to BrainBit BLED: {e2}")
            return False
    
    # Get device info
    sampling_rate = BoardShim.get_sampling_rate(board_id)
    eeg_channels = BoardShim.get_eeg_channels(board_id)
    ch_names = BoardShim.get_eeg_names(board_id)
    
    print(f"EEG Channels: {ch_names}")
    print(f"Sampling Rate: {sampling_rate} Hz")
    
    # Initialize data buffers for all channels
    for i, ch in enumerate(eeg_channels):
        eeg_buffers[ch] = np.zeros(buffer_size)
        filtered_buffers[ch] = np.zeros(buffer_size)
        ch_name = ch_names[i]
        psd_data[ch_name] = {'freqs': [], 'powers': []}
        band_powers[ch_name] = {band: 0 for band in freq_bands}
        power_law_data[ch_name] = {'alpha': None, 'offset': None}
    
    # Start data stream
    board.start_stream()
    print("Data streaming started")
    return True

def apply_filters(data):
    """Apply filters to EEG data."""
    filtered = np.copy(data)
    
    try:
        # Remove DC offset
        DataFilter.detrend(filtered, DetrendOperations.CONSTANT.value)
        
        # Apply a notch filter at 50/60 Hz to remove power line noise
        DataFilter.perform_bandstop(filtered, sampling_rate,
                                  58, 62, 
                                  2, FilterTypes.BUTTERWORTH.value, 0)
        
        # Apply bandpass filter to keep only relevant brain frequencies
        DataFilter.perform_bandpass(filtered, sampling_rate,
                                  1, 30,
                                  2, FilterTypes.BUTTERWORTH.value, 0)
    except Exception as e:
        print(f"Error in filtering: {e}")
    
    return filtered

def compute_psd(data):
    """Compute power spectral density for given data."""
    if np.all(data == 0):
        return None, None
    
    # Use scipy's welch method
    freqs, psd = signal.welch(
        data, fs=sampling_rate, nperseg=min(256, len(data)),
        scaling='density', detrend='constant'
    )
    
    return freqs, psd

def fit_power_law(freqs, psd, freq_range=(2, 50)):
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

def calculate_band_powers(psd, freqs):
    """Calculate power in each frequency band."""
    band_powers = {}
    
    for band_name, (low_freq, high_freq) in freq_bands.items():
        # Find indices corresponding to this band
        band_mask = (freqs >= low_freq) & (freqs <= high_freq)
        
        if np.any(band_mask):
            # Calculate average power in this band
            band_powers[band_name] = float(np.mean(psd[band_mask]))
        else:
            band_powers[band_name] = 0.0
    
    return band_powers

def data_acquisition_thread():
    """Thread function to continuously acquire and process BrainBit data."""
    while True:
        try:
            # Get latest data from board
            new_data = board.get_current_board_data(sampling_rate // 10)
            
            if new_data.size == 0 or new_data.shape[1] == 0:
                time.sleep(0.1)
                continue
            
            with data_lock:
                # Process each channel
                for i, ch in enumerate(eeg_channels):
                    ch_name = ch_names[i]
                    
                    # Skip if channel is not available
                    if ch >= new_data.shape[0]:
                        continue
                    
                    # Get channel data
                    channel_data = new_data[ch]
                    if len(channel_data) == 0:
                        continue
                    
                    # Update buffer with new data (sliding window)
                    if len(channel_data) < len(eeg_buffers[ch]):
                        eeg_buffers[ch] = np.roll(eeg_buffers[ch], -len(channel_data))
                        eeg_buffers[ch][-len(channel_data):] = channel_data
                    else:
                        # If we got more data than buffer size, just take the latest buffer_size worth
                        eeg_buffers[ch] = channel_data[-buffer_size:]
                    
                    # Apply filtering
                    filtered_buffers[ch] = apply_filters(eeg_buffers[ch])
                    
                    # Compute PSD
                    freqs, psd = compute_psd(filtered_buffers[ch])
                    
                    if freqs is not None and psd is not None:
                        # Store PSD data
                        psd_data[ch_name]['freqs'] = freqs.tolist()
                        psd_data[ch_name]['powers'] = psd.tolist()
                        
                        # Fit power law (1/f^α)
                        fit_result = fit_power_law(freqs, psd)
                        
                        if fit_result is not None:
                            offset, alpha = fit_result
                            power_law_data[ch_name]['offset'] = float(offset)
                            power_law_data[ch_name]['alpha'] = float(alpha)
                            
                            # Calculate band powers
                            bp = calculate_band_powers(psd, freqs)
                            band_powers[ch_name] = bp
                
                # Create output data structure
                output_data = {
                    'eeg': {},
                    'psd': {},
                    'channel_info': {}
                }
                
                for i, ch in enumerate(eeg_channels):
                    ch_name = ch_names[i]
                    
                    # Normalize the EEG data for visualization
                    raw_data = eeg_buffers[ch]
                    filtered_data = filtered_buffers[ch]
                    
                    # Normalize each signal to its own maximum
                    raw_max = np.max(np.abs(raw_data))
                    filtered_max = np.max(np.abs(filtered_data))
                    
                    # Avoid division by zero
                    if raw_max > 0 and filtered_max > 0:
                        normalized_raw = (raw_data / raw_max) * 100
                        normalized_filtered = (filtered_data / filtered_max) * 100
                    else:
                        normalized_raw = raw_data
                        normalized_filtered = filtered_data
                    
                    # Store normalized EEG data
                    output_data['eeg'][ch_name] = {
                        'raw': normalized_raw.tolist(),
                        'filtered': normalized_filtered.tolist()
                    }
                    
                    # Store PSD data
                    output_data['psd'][ch_name] = psd_data[ch_name]
                    
                    # Store channel info (1/f, band powers)
                    bp = band_powers[ch_name]
                    dominant_band = max(bp.items(), key=lambda x: x[1])[0] if bp else None
                    
                    output_data['channel_info'][ch_name] = {
                        'alpha': power_law_data[ch_name]['alpha'],
                        'band_powers': bp,
                        'dominant': dominant_band
                    }
                
                # Save data to file
                with open(output_file, 'w') as f:
                    json.dump(output_data, f)
            
            # Sleep a bit to avoid overloading the CPU
            time.sleep(0.05)
            
        except Exception as e:
            print(f"Error in data acquisition: {e}")
            import traceback
            traceback.print_exc()
            time.sleep(1)

def main():
    """Main function to run the application."""
    # Generate the HTML viewer file
    html_path = write_html_file()
    
    # Connect to BrainBit
    if not connect_to_brainbit():
        print("Failed to connect to BrainBit. Exiting.")
        return
    
    try:
        # Start data acquisition thread
        acquisition_thread = threading.Thread(target=data_acquisition_thread)
        acquisition_thread.daemon = True
        acquisition_thread.start()
        
        print(f"\n**** BrainBit Lite Monitor is running ****")
        print(f"Data is being written to: {output_file}")
        print(f"Open this file in your browser to view the data: {html_path}")
        print(f"Press Ctrl+C to exit.")
        
        # Keep the main thread alive
        while True:
            time.sleep(1)
        
    except KeyboardInterrupt:
        print("Application interrupted by user")
    finally:
        # Disconnect from BrainBit
        if board:
            board.stop_stream()
            board.release_session()
            print("BrainBit disconnected")

if __name__ == "__main__":
    main()
