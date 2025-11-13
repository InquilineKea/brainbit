#!/usr/bin/env python3
"""
BrainBit Web Display

A web-based visualization for BrainBit data that shows all data in a browser window.
"""

import time
import threading
import numpy as np
from scipy import signal
import json
from flask import Flask, Response, render_template_string, jsonify

# BrainFlow imports
import brainflow
from brainflow.board_shim import BoardShim, BrainFlowInputParams, BoardIds, LogLevels
from brainflow.data_filter import DataFilter, FilterTypes, DetrendOperations

# Initialize Flask app
app = Flask(__name__)

# Global variables
buffer_size = 1250  # 5 seconds at 250 Hz
eeg_buffers = {}
filtered_buffers = {}
psd_data = {}
band_powers = {}
power_law_data = {}
active_channels = []

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

# HTML template
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>BrainBit Web Visualizer</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f0f0f0;
        }
        .container {
            display: flex;
            flex-wrap: wrap;
            gap: 20px;
        }
        .chart-container {
            background-color: white;
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            padding: 15px;
            width: calc(50% - 40px);
            min-width: 400px;
            margin-bottom: 20px;
        }
        h1, h2 {
            color: #333;
        }
        .channel-info {
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            margin-top: 10px;
        }
        .info-box {
            background-color: #f8f9fa;
            border-radius: 5px;
            padding: 10px;
            margin-bottom: 10px;
            flex: 1;
            min-width: 150px;
        }
        .dominant {
            font-weight: bold;
            color: #d62728;
        }
    </style>
</head>
<body>
    <h1>BrainBit Real-time EEG Monitoring</h1>
    
    <div class="container">
        <!-- EEG Signal Charts -->
        <div class="chart-container">
            <h2>T3 EEG Signal (Normalized)</h2>
            <canvas id="t3-chart"></canvas>
            <div class="channel-info" id="t3-info"></div>
        </div>
        
        <div class="chart-container">
            <h2>T4 EEG Signal (Normalized)</h2>
            <canvas id="t4-chart"></canvas>
            <div class="channel-info" id="t4-info"></div>
        </div>
        
        <div class="chart-container">
            <h2>O1 EEG Signal (Normalized)</h2>
            <canvas id="o1-chart"></canvas>
            <div class="channel-info" id="o1-info"></div>
        </div>
        
        <div class="chart-container">
            <h2>O2 EEG Signal (Normalized)</h2>
            <canvas id="o2-chart"></canvas>
            <div class="channel-info" id="o2-info"></div>
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
        
        <!-- 1/f Analysis Charts -->
        <div class="chart-container">
            <h2>T3 1/f Analysis</h2>
            <canvas id="t3-loglog-chart"></canvas>
        </div>
        
        <div class="chart-container">
            <h2>T4 1/f Analysis</h2>
            <canvas id="t4-loglog-chart"></canvas>
        </div>
        
        <div class="chart-container">
            <h2>O1 1/f Analysis</h2>
            <canvas id="o1-loglog-chart"></canvas>
        </div>
        
        <div class="chart-container">
            <h2>O2 1/f Analysis</h2>
            <canvas id="o2-loglog-chart"></canvas>
        </div>
    </div>

    <script>
        // Time axis labels
        const timeLabels = Array.from({length: {{ buffer_size }}}, (_, i) => -5 + i * (5 / {{ buffer_size }}));
        
        // Initialize all charts
        const channelIds = ['t3', 't4', 'o1', 'o2'];
        const eegCharts = {};
        const psdCharts = {};
        const loglogCharts = {};
        
        function getRandomColor() {
            const letters = '0123456789ABCDEF';
            let color = '#';
            for (let i = 0; i < 6; i++) {
                color += letters[Math.floor(Math.random() * 16)];
            }
            return color;
        }
        
        function initCharts() {
            // Initialize EEG charts
            channelIds.forEach(channel => {
                const ctx = document.getElementById(`${channel}-chart`).getContext('2d');
                eegCharts[channel] = new Chart(ctx, {
                    type: 'line',
                    data: {
                        labels: timeLabels,
                        datasets: [{
                            label: 'Raw',
                            data: Array({{ buffer_size }}).fill(0),
                            borderColor: 'rgba(75, 192, 192, 0.3)',
                            borderWidth: 1,
                            pointRadius: 0,
                            fill: false
                        }, {
                            label: 'Filtered',
                            data: Array({{ buffer_size }}).fill(0),
                            borderColor: 'rgba(75, 192, 192, 1)',
                            borderWidth: 1.5,
                            pointRadius: 0,
                            fill: false
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        animation: false,
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
                                    text: 'Normalized Amplitude'
                                },
                                min: -120,
                                max: 120
                            }
                        }
                    }
                });
                
                // Initialize PSD charts
                const psdCtx = document.getElementById(`${channel}-psd-chart`).getContext('2d');
                psdCharts[channel] = new Chart(psdCtx, {
                    type: 'line',
                    data: {
                        labels: Array(100).fill(0).map((_, i) => i),
                        datasets: [{
                            label: 'PSD',
                            data: Array(100).fill(0),
                            borderColor: 'rgba(255, 99, 132, 1)',
                            borderWidth: 1.5,
                            pointRadius: 0,
                            fill: false
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        animation: false,
                        scales: {
                            x: {
                                title: {
                                    display: true,
                                    text: 'Frequency (Hz)'
                                },
                                min: 0,
                                max: 60
                            },
                            y: {
                                title: {
                                    display: true,
                                    text: 'Power'
                                },
                                beginAtZero: true
                            }
                        }
                    }
                });
                
                // Initialize Log-Log charts
                const loglogCtx = document.getElementById(`${channel}-loglog-chart`).getContext('2d');
                loglogCharts[channel] = new Chart(loglogCtx, {
                    type: 'scatter',
                    data: {
                        datasets: [{
                            label: 'Data',
                            data: [],
                            backgroundColor: 'rgba(54, 162, 235, 0.5)',
                            pointRadius: 2
                        }, {
                            label: 'Fit',
                            data: [],
                            borderColor: 'rgba(255, 99, 132, 1)',
                            borderWidth: 2,
                            pointRadius: 0,
                            showLine: true,
                            fill: false
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        animation: false,
                        scales: {
                            x: {
                                type: 'logarithmic',
                                title: {
                                    display: true,
                                    text: 'Frequency (Hz)'
                                },
                                min: 1,
                                max: 100
                            },
                            y: {
                                type: 'logarithmic',
                                title: {
                                    display: true,
                                    text: 'Power'
                                }
                            }
                        }
                    }
                });
            });
        }
        
        // Update channel info display
        function updateChannelInfo(channel, data) {
            if (!data) return;
            
            const infoDiv = document.getElementById(`${channel}-info`);
            
            // Create HTML for band powers
            let infoHtml = `<div class="info-box">
                <strong>1/f Slope:</strong> α = ${data.alpha ? data.alpha.toFixed(2) : 'N/A'}<br>
                <strong>Dominant:</strong> ${data.dominant || 'N/A'}
            </div>`;
            
            infoHtml += '<div class="info-box">';
            for (const [band, power] of Object.entries(data.band_powers || {})) {
                if (band === data.dominant) {
                    infoHtml += `<span class="dominant">${band}: ${power.toFixed(1)}</span><br>`;
                } else {
                    infoHtml += `${band}: ${power.toFixed(1)}<br>`;
                }
            }
            infoHtml += '</div>';
            
            infoDiv.innerHTML = infoHtml;
        }
        
        // Initialize charts when page loads
        document.addEventListener('DOMContentLoaded', initCharts);
        
        // Function to update charts with new data
        function updateCharts(data) {
            if (!data) return;
            
            // Update EEG charts
            Object.entries(data.eeg || {}).forEach(([channel, channelData]) => {
                const chart = eegCharts[channel.toLowerCase()];
                if (chart && channelData) {
                    chart.data.datasets[0].data = channelData.raw || Array({{ buffer_size }}).fill(0);
                    chart.data.datasets[1].data = channelData.filtered || Array({{ buffer_size }}).fill(0);
                    chart.update();
                }
            });
            
            // Update PSD charts
            Object.entries(data.psd || {}).forEach(([channel, psdData]) => {
                const chart = psdCharts[channel.toLowerCase()];
                if (chart && psdData && psdData.freqs && psdData.powers) {
                    chart.data.labels = psdData.freqs;
                    chart.data.datasets[0].data = psdData.powers;
                    chart.update();
                }
            });
            
            // Update Log-Log charts
            Object.entries(data.loglog || {}).forEach(([channel, loglogData]) => {
                const chart = loglogCharts[channel.toLowerCase()];
                if (chart && loglogData) {
                    // Update data points
                    if (loglogData.data && loglogData.data.x && loglogData.data.y) {
                        chart.data.datasets[0].data = loglogData.data.x.map((x, i) => ({x: x, y: loglogData.data.y[i]}));
                    }
                    
                    // Update fit line
                    if (loglogData.fit && loglogData.fit.x && loglogData.fit.y) {
                        chart.data.datasets[1].data = loglogData.fit.x.map((x, i) => ({x: x, y: loglogData.fit.y[i]}));
                    }
                    chart.update();
                }
            });
            
            // Update channel info boxes
            Object.entries(data.channel_info || {}).forEach(([channel, info]) => {
                updateChannelInfo(channel.toLowerCase(), info);
            });
        }
        
        // Fetch data every 100ms
        setInterval(() => {
            fetch('/api/data')
                .then(response => response.json())
                .then(data => updateCharts(data))
                .catch(error => console.error('Error fetching data:', error));
        }, 100);
    </script>
</body>
</html>
'''

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
            
            # Sleep a bit to avoid overloading the CPU
            time.sleep(0.05)
            
        except Exception as e:
            print(f"Error in data acquisition: {e}")
            import traceback
            traceback.print_exc()
            time.sleep(1)

@app.route('/')
def index():
    """Render the main visualization page."""
    return render_template_string(HTML_TEMPLATE, buffer_size=buffer_size)

@app.route('/api/data')
def get_data():
    """API endpoint to get the latest data for visualization."""
    with data_lock:
        # Prepare data for each channel
        eeg_data = {}
        psd_output = {}
        loglog_output = {}
        channel_info = {}
        
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
            eeg_data[ch_name] = {
                'raw': normalized_raw.tolist(),
                'filtered': normalized_filtered.tolist()
            }
            
            # Store PSD data
            psd_output[ch_name] = psd_data[ch_name]
            
            # Prepare log-log data for 1/f analysis
            freqs = psd_data[ch_name]['freqs']
            powers = psd_data[ch_name]['powers']
            
            if freqs and powers:
                # Data points (skip DC component)
                mask = np.array(freqs) > 0
                loglog_output[ch_name] = {
                    'data': {
                        'x': np.array(freqs)[mask].tolist(),
                        'y': np.array(powers)[mask].tolist()
                    }
                }
                
                # Fit line
                if power_law_data[ch_name]['alpha'] is not None:
                    alpha = power_law_data[ch_name]['alpha']
                    offset = power_law_data[ch_name]['offset']
                    
                    # Generate predicted values for visualization
                    pred_freqs = np.logspace(np.log10(1), np.log10(100), 100)
                    pred_psd = offset * pred_freqs ** (-alpha)
                    
                    loglog_output[ch_name]['fit'] = {
                        'x': pred_freqs.tolist(),
                        'y': pred_psd.tolist()
                    }
            
            # Prepare channel info
            bp = band_powers[ch_name]
            dominant_band = max(bp.items(), key=lambda x: x[1])[0] if bp else None
            
            channel_info[ch_name] = {
                'alpha': power_law_data[ch_name]['alpha'],
                'band_powers': bp,
                'dominant': dominant_band
            }
        
        return jsonify({
            'eeg': eeg_data,
            'psd': psd_output,
            'loglog': loglog_output,
            'channel_info': channel_info
        })

def start_server():
    """Start the Flask web server."""
    app.run(host='0.0.0.0', port=8080, debug=False, threaded=True)

def main():
    """Main function to run the application."""
    # Connect to BrainBit
    if not connect_to_brainbit():
        print("Failed to connect to BrainBit. Exiting.")
        return
    
    try:
        # Start data acquisition thread
        acquisition_thread = threading.Thread(target=data_acquisition_thread)
        acquisition_thread.daemon = True
        acquisition_thread.start()
        
        # Start web server
        print("Starting web server on http://127.0.0.1:8080")
        start_server()
        
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
