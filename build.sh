#!/bin/bash
set -e

echo "======================================================"
echo "Starting build process for Whisper.cpp dependencies..."
echo "======================================================"

# Install system dependencies
apt-get update && apt-get install -y build-essential cmake ffmpeg

# Navigate to whisper.cpp directory
cd whisper.cpp

# Build whisper.cpp
echo "Building whisper.cpp..."
cmake -B build
cmake --build build --config Release -j

# Create binary directory if it doesn't exist
mkdir -p build/bin
cp build/whisper-cli build/bin/main

# Download the model
echo "Downloading whisper model..."
mkdir -p models
if [ ! -f models/ggml-base.en.bin ]; then
    bash ./models/download-ggml-model.sh base.en
fi

# Return to root directory
cd ..

echo "======================================================"
echo "Build process completed successfully!"
echo "======================================================" 