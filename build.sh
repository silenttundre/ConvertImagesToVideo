#!/bin/bash
set -o errexit

# Install Poppler
apt-get update
apt-get install -y poppler-utils

# Install Python dependencies
pip install -r requirements.txt
