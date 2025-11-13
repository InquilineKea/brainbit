# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

This is a personal genomics and neuroscience research repository containing tools for:
1. **Genomic analysis** - VCF analysis, polygenic scores, structural variants, CNV analysis
2. **Neuroscience monitoring** - Real-time EEG (BrainBit) and fNIRS (Mendi) visualization
3. **Signal processing** - Spectrum analysis and frequency domain tools
4. **Data archival** - Slack/CopyClip backup utilities

## Core Analysis Domains

### 1. Genomic Variant Analysis

**VCF Files**: The repository contains whole genome sequencing (WGS) data in VCF format:
- Primary VCF: `WGS C3156486.vcf` (main variant calls)
- CNV data: `010625-WGS-C3156486.cnv.vcf.vcf`
- Structural variants: `010625-WGS-C3156486.sv.vcf.vcf`
- Repeats: `010625-WGS-C3156486.repeats.vcf.vcf`
- Reference genome: hg38/GRCh38

**Analysis Scripts**:
- CNV analysis: `cnv_analysis.sh` - Extracts losses, gains, and significant CNVs from VCF
- Structural variants: `sv_analysis.sh` - Analyzes deletions, duplications, insertions, inversions
- Repeats: `repeats_analysis.sh` - Analyzes repeat expansions

### 2. Polygenic Score (PGS) Analysis

The `longevity_pgs_toolkit.py` is the main tool for calculating polygenic scores.

**Key PGS Models**:
- PGS000906: Longevity PRS-5 (330 variants, GRCh37/hg19)
- PGS002795: Longevity (Deelen et al.)

**Common Commands**:
```bash
# Calculate longevity PGS with visualization
./longevity_pgs_toolkit.py --vcf "WGS C3156486.vcf" --pgs-id PGS000906 --output-prefix longevity --visualize

# Convert PGS model from hg19 to hg38
./convert_pgs_to_hg38.py --input pgs000906.txt.gz --output pgs000906.hg38.txt.gz

# Use converted model
./longevity_pgs_toolkit.py --vcf "WGS C3156486.vcf" --pgs pgs000906.hg38.txt.gz --output-prefix longevity
```

**Critical Note**: Many PGS models use GRCh37/hg19 while VCF files are in GRCh38/hg38. Always check genome build compatibility and convert if needed.

### 3. BrainBit EEG Analysis

BrainBit is a 4-channel EEG headset (T3, T4, O1, O2). Multiple visualization scripts are available:

**Recommended Script**: `brainbit_stable_view.py` - Multi-view interface with:
- Raw EEG visualization (4 channels)
- Band power analysis (delta, theta, alpha, beta)
- 1/f spectral analysis with slope estimation (Voytek method)

**Common Commands**:
```bash
# Run stable viewer with all analysis modes
python3 brainbit_stable_view.py

# Simple raw signal display
python3 brainbit_very_basic.py

# Band power visualization
python3 brainbit_simple_power.py

# 1/f spectral analysis only
python3 brainbit_only_1f.py
```

**Dependencies**: BrainFlow, MNE Python, NumPy, SciPy, Matplotlib

**Device Connection**: Connect BrainBit device via Bluetooth before running scripts. Press 'q' or 'Escape' to exit visualizations.

### 4. Mendi fNIRS Analysis

Mendi is a functional near-infrared spectroscopy (fNIRS) device for measuring brain hemodynamics.

**Main Script**: `mendi_fnirs_view.py` - Real-time visualization with:
- Red and IR channel raw signals
- HbO/HbR calculation using Modified Beer-Lambert Law (MBLL)
- Async BLE communication

**Common Commands**:
```bash
# Real-time fNIRS visualization
python3 mendi_fnirs_view.py

# Statistics view
python3 mendi_stats_view.py

# BLE device scanner
python3 mendi_ble_scanner.py
```

**BLE Configuration**:
- Service UUID: `fc3eabb0-c6c4-49e6-922a-6e551c455af5`
- RX characteristic: `fc3eabb1-c6c4-49e6-922a-6e551c455af5`

### 5. Spectrum Analysis

**Main Tool**: `spectrum_analyzer.py` - FFT-based frequency domain analysis

**Features**:
- Fast Fourier Transform (FFT) of time series
- Power spectral density calculation
- 1/f^n power law detection (pink noise, brown noise)
- Dominant frequency detection
- Multiple windowing functions (Hann, Hamming, Blackman)

**Common Commands**:
```bash
# Analyze CSV file
python3 spectrum_analyzer.py --file data.csv --column 1 --delimiter "," --skip-header 1

# Generate test signals
python3 spectrum_analyzer.py --test sine --frequency 10 --sampling-rate 1000 --length 10000
python3 spectrum_analyzer.py --test pink --sampling-rate 1000 --length 10000

# Save results
python3 spectrum_analyzer.py --file data.csv --output spectrum.png --report analysis.txt

# Run examples
python3 spectrum_analyzer_examples.py
```

**Interpreting 1/f^n exponents**:
- n ≈ 0: White noise (flat spectrum)
- n ≈ 1: Pink noise (1/f)
- n ≈ 2: Brown noise (1/f²)

## Python Environment

**Virtual Environment**: `.venv/` directory contains Python 3.x environment

**Activation**:
```bash
source .venv/bin/activate
```

**Key Dependencies**:
- Genomics: pyliftover (coordinate conversion)
- Neuroscience: BrainFlow, MNE, Bleak (BLE)
- Analysis: NumPy, SciPy, Matplotlib
- API: anthropic (v0.72.1)

## Claude API Tools

Custom CLI for Claude API interaction:

**Scripts**:
- `claude_api_example.py` - API connection test
- `claude_code_cli.py` - Full-featured CLI

**Usage**:
```bash
# Simple prompt
python3 claude_code_cli.py "Your question here"

# With file input
python3 claude_code_cli.py --file myfile.txt "Analyze this file"

# Custom parameters
python3 claude_code_cli.py --max-tokens 2000 --temperature 0.5 "Your question"

# Interactive mode
python3 claude_code_cli.py
```

## Data Organization

**Genomic Data**:
- VCF files: Root directory
- Reference data: `reference_data/`
- gnomAD data: `gnomad_data/`
- Analysis results: `foxo3_analysis/`, `sv_analysis/`, `neurexin_analysis/`

**Neuroscience Data**:
- BrainBit recordings: `brainbit_data/`, `.fif` files
- Raw recordings: `brainbit_recording_*.fif`
- Analysis logs: `eeg_log.txt`, `hrv_beats.txt`

**Backups**:
- CopyClip: `copyclip_backups/`
- Slack dumps: `slackdump_*/`

## Shell Script Patterns

Common pattern in analysis scripts:
```bash
#!/bin/bash
# Extract data from VCF
grep "PATTERN" file.vcf | awk -F'\t' '{...}' > output.txt
```

Key VCF filtering patterns:
- CNV types: `grep "DRAGEN:LOSS"`, `grep "DRAGEN:GAIN"`
- Quality: `grep "PASS"`, check QUAL column
- Specific genes: `grep -i "GENE_NAME"`

## Architecture Notes

### Genomic Analysis Pipeline
1. VCF files contain raw variant calls (SNPs, indels, SVs, CNVs)
2. Shell scripts extract specific variant types
3. Python scripts calculate scores or perform detailed analysis
4. Results saved as `.txt`, `.tsv`, or `.md` files

### Neuroscience Pipeline
1. BLE/Bluetooth connection to device
2. Real-time data streaming (async for fNIRS, BrainFlow for EEG)
3. Signal processing (filtering, FFT, band power)
4. Live visualization with matplotlib
5. Optional data logging to `.fif` (MNE format) or text files

### Analysis Workflow
1. Raw signal acquisition
2. Preprocessing (filtering, normalization)
3. Feature extraction (FFT, band power, 1/f slopes)
4. Visualization and reporting

## Important Patterns

### Genome Build Compatibility
Always verify genome builds match:
- VCF files: Check `##reference=` header
- PGS models: Check metadata for GRCh37 vs GRCh38
- Use `convert_pgs_to_hg38.py` when needed

### Signal Processing Best Practices
- EEG sampling rate: 250 Hz (BrainBit)
- fNIRS data format: Red and IR channels
- Use appropriate windowing (Hann for general use)
- Check signal quality before analysis

### BLE Device Connection
For Mendi and similar devices:
1. Scan for device: `BleakScanner`
2. Connect to service UUID
3. Subscribe to RX characteristic
4. Parse binary frames (struct.unpack)
5. Handle disconnections gracefully

## Gene-Specific Analysis Examples

The repository includes several focused gene analyses:
- FOXO3 (longevity): `analyze_foxo3_comprehensive.py`, `foxo3_analysis/`
- Collagen genes: `extract_collagen_variants.py`, `collagen_*.tsv`
- Elastin (ELN): `elastin_variants.vcf`, protein sequences
- Brain size (ICV): `extract_icv_variants.py`, `icv_pgs/`
- Neurexin: `neurexin_analysis/`

Pattern: Extract variants for specific genes, annotate with gnomAD frequencies, assess impact.

## Testing and Quality

**BrainBit Signal Quality**:
- Impedance check scripts: `brainbit_impedance_*.py`
- Signal verification: `brainbit_signal_check.py`

**Data Validation**:
- VCF files must be uncompressed or properly indexed (`.tbi`)
- Check for chromosome naming: "chr1" vs "1"
- Verify sampling rates match expected values

## Notes

- Git repository initialized on Apr 26, 2025
- Uses macOS (darwin platform)
- No standard build system (Python scripts, shell scripts)
- No automated tests present
- Results typically saved as text reports, CSVs, or visualizations
