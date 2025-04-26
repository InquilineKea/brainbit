#!/usr/bin/env python3
"""
Convert a PGS Catalog scoring file from GRCh37/hg19 to GRCh38/hg38 coordinates.

This script uses the UCSC liftOver chain files to convert the genomic coordinates
in a PGS Catalog scoring file from GRCh37 to GRCh38.

Requirements:
- pyliftover package: pip install pyliftover
"""

import argparse
import gzip
import os
import sys
from pyliftover import LiftOver

def download_chain_file():
    """Download the UCSC liftOver chain file if not already present"""
    import urllib.request
    
    chain_file = "hg19ToHg38.over.chain.gz"
    if not os.path.exists(chain_file):
        print(f"Downloading {chain_file}...")
        url = f"https://hgdownload.soe.ucsc.edu/goldenPath/hg19/liftOver/{chain_file}"
        urllib.request.urlretrieve(url, chain_file)
        print(f"Downloaded {chain_file}")
    
    return chain_file

def convert_pgs_file(input_file, output_file):
    """Convert PGS file from GRCh37 to GRCh38"""
    # Initialize liftOver
    try:
        chain_file = download_chain_file()
        lo = LiftOver(chain_file)
    except Exception as e:
        print(f"Error initializing liftOver: {e}", file=sys.stderr)
        return False
    
    # Determine if file is gzipped
    input_open_func = gzip.open if input_file.endswith('.gz') else open
    input_mode = 'rt' if input_file.endswith('.gz') else 'r'
    
    output_open_func = gzip.open if output_file.endswith('.gz') else open
    output_mode = 'wt' if output_file.endswith('.gz') else 'w'
    
    successful_conversions = 0
    failed_conversions = 0
    
    with input_open_func(input_file, input_mode) as fin, output_open_func(output_file, output_mode) as fout:
        header = None
        header_lines = []
        
        for line in fin:
            # Copy header lines, updating genome_build
            if line.startswith('#'):
                if line.startswith('#genome_build='):
                    line = '#genome_build=GRCh38\n'
                header_lines.append(line)
                continue
            
            if header is None:
                header = line.strip().split('\t')
                fout.write(''.join(header_lines))
                fout.write(line)
                continue
            
            fields = line.strip().split('\t')
            data = dict(zip(header, fields))
            
            # Convert chromosome name if needed (e.g., "23" to "X")
            chrom = data['chr_name']
            if chrom == '23':
                chrom = 'X'
            elif chrom == '24':
                chrom = 'Y'
            
            # Convert position
            position = int(data['chr_position'])
            new_positions = lo.convert_coordinate(f"chr{chrom}", position)
            
            if new_positions and len(new_positions) > 0:
                # Use the first mapped position
                new_chrom = new_positions[0][0].replace('chr', '')
                new_position = new_positions[0][1]
                
                # Update the data
                data['chr_name'] = new_chrom
                data['chr_position'] = str(new_position)
                
                # Write the updated line
                fout.write('\t'.join([data[col] for col in header]) + '\n')
                successful_conversions += 1
            else:
                failed_conversions += 1
    
    print(f"Conversion complete: {successful_conversions} variants converted, {failed_conversions} failed")
    return True

def main():
    parser = argparse.ArgumentParser(description='Convert PGS Catalog scoring file from GRCh37 to GRCh38')
    parser.add_argument('--input', required=True, help='Input PGS Catalog scoring file (GRCh37)')
    parser.add_argument('--output', required=True, help='Output PGS Catalog scoring file (GRCh38)')
    
    args = parser.parse_args()
    
    # Check if input file exists
    if not os.path.exists(args.input):
        print(f"Error: Input file {args.input} not found", file=sys.stderr)
        return 1
    
    # Convert the file
    if convert_pgs_file(args.input, args.output):
        print(f"Successfully converted {args.input} to {args.output}")
        return 0
    else:
        print(f"Failed to convert {args.input}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    sys.exit(main())
