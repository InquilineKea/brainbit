#!/bin/bash
# Script to download gene annotation data for hg38/GRCh38

# Create data directory
mkdir -p /Users/simfish/Downloads/Genome/reference_data

# Download gene annotation data from UCSC
echo "Downloading gene annotation data..."
curl -s "https://hgdownload.soe.ucsc.edu/goldenPath/hg38/database/refGene.txt.gz" -o /Users/simfish/Downloads/Genome/reference_data/refGene.txt.gz
gunzip -f /Users/simfish/Downloads/Genome/reference_data/refGene.txt.gz

# Download regulatory elements data (enhancers, promoters)
echo "Downloading regulatory elements data..."
curl -s "https://hgdownload.soe.ucsc.edu/goldenPath/hg38/database/enhancer.txt.gz" -o /Users/simfish/Downloads/Genome/reference_data/enhancer.txt.gz
gunzip -f /Users/simfish/Downloads/Genome/reference_data/enhancer.txt.gz

# Download CpG islands data (potential promoter regions)
echo "Downloading CpG islands data..."
curl -s "https://hgdownload.soe.ucsc.edu/goldenPath/hg38/database/cpgIslandExt.txt.gz" -o /Users/simfish/Downloads/Genome/reference_data/cpgIslandExt.txt.gz
gunzip -f /Users/simfish/Downloads/Genome/reference_data/cpgIslandExt.txt.gz

echo "Download complete!"
