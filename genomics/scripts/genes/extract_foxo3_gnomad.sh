#!/bin/bash

# Create directory for gnomAD data
mkdir -p gnomad_data

# Download just the FOXO3 region from gnomAD using tabix
# Note: Adding some padding around the gene (10kb on each side)
tabix -h https://storage.googleapis.com/gcp-public-data--gnomad/release/3.1.2/vcf/genomes/gnomad.genomes.v3.1.2.sites.chr6.vcf.bgz 6:108554790-108693686 > gnomad_data/gnomad.v3.1.2.FOXO3.vcf

# Index the extracted VCF file
bgzip gnomad_data/gnomad.v3.1.2.FOXO3.vcf
tabix -p vcf gnomad_data/gnomad.v3.1.2.FOXO3.vcf.gz

echo "FOXO3 region extracted from gnomAD"
