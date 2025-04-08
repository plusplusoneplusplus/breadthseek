#!/bin/bash

# Create build directory if it doesn't exist
mkdir -p build

# Move to build directory
cd build

# Configure CMake
cmake ..

# Build the project
cmake --build .

echo "Build complete. Executable is in build/bin/hello"
echo "Run with: ./build/bin/hello" 