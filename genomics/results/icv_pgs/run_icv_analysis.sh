#!/bin/bash

# Run the ICV Polygenic Score Analysis
cd /Users/simfish/Downloads/Genome/icv_pgs

# Make the Python script executable
chmod +x calculate_icv_pgs.py

# Check if bcftools is installed
if ! command -v bcftools &> /dev/null; then
    echo "bcftools not found. Attempting to install with Homebrew..."
    
    # Check if Homebrew is installed
    if ! command -v brew &> /dev/null; then
        echo "Homebrew not found. Please install Homebrew first:"
        echo '/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'
        exit 1
    fi
    
    # Install bcftools
    brew install bcftools
fi

# Check if pandas and numpy are installed
python3 -c "import pandas, numpy" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "Installing required Python packages..."
    pip3 install pandas numpy
fi

# Run the analysis
echo "Starting Intracranial Volume Polygenic Score analysis..."
python3 calculate_icv_pgs.py

echo "Analysis complete!"
