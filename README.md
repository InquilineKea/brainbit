# BrainBit EEG Visualization Tools

Real-time visualization and analysis tools for BrainBit Flex EEG headset using Python.

## Features

- **Real-time EEG visualization** for all 4 channels (T3, T4, O1, O2)
- **Filtered signal display** with independent channel normalization
- **Band power analysis** for delta, theta, alpha, and beta frequencies
- **1/f spectral analysis** with slope estimation (Voytek method)
- Multiple visualization options to assess signal quality and brainwave patterns

## Scripts

- `brainbit_very_basic.py` - Simple raw signal display with minimal processing
- `brainbit_simple_power.py` - Band power visualization for EEG frequency bands
- `brainbit_fixed_1f.py` - Multi-view analysis with normalized EEG, band power, and 1/f analysis
- `brainbit_only_1f.py` - Dedicated 1/f spectral analysis for all channels
- Many other specialized visualization scripts for different use cases

## Requirements

- Python 3.x
- BrainFlow library
- MNE Python
- NumPy, SciPy, Matplotlib

## Usage

Connect your BrainBit device via Bluetooth, then run any of the scripts:

```bash
python brainbit_only_1f.py
```

Each script provides different visualization options. Press 'q' or 'Escape' to exit any visualization.
