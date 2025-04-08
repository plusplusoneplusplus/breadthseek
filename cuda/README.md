# CUDA Hello World

A simple CUDA program that demonstrates printing from both the CPU and GPU.

## Prerequisites

- NVIDIA CUDA Toolkit (https://developer.nvidia.com/cuda-downloads)
- NVIDIA GPU with CUDA support
- CMake (version 3.18 or later)

## Building with CMake (Recommended)

```bash
# Create and enter build directory
mkdir -p build
cd build

# Configure
cmake ..

# Build
cmake --build .

# Run
./bin/hello
```

## Building with Makefile (Alternative)

To compile the program using the provided Makefile:

```bash
make
```

Or manually compile with:

```bash
nvcc -O2 -o hello hello.cu
```

## Running (Makefile build)

After compilation with Makefile, run the program with:

```bash
./hello
```

You should see output from both the CPU and multiple GPU threads.

## Clean Up

For CMake build:
```bash
rm -rf build/
```

For Makefile build:
```bash
make clean
``` 