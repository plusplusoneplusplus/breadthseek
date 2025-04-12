# CUDA Particle Simulation

A GPU-accelerated 2D particle simulation using CUDA and SFML for visualization. The simulation features thousands of particles interacting with each other through gravity, collision, and repulsion forces.

## Features

- Real-time simulation of 10,000 particles
- GPU-accelerated physics calculations
- Particle-particle interactions
- Elastic boundary collisions
- Gravity and damping effects
- SFML-based visualization

## Requirements

- CUDA Toolkit (11.0 or later)
- CMake (3.18 or later)
- SFML (2.5 or later)
- C++17 compatible compiler

## Building the Project

1. Create a build directory:
```bash
mkdir build
cd build
```

2. Configure with CMake:
```bash
cmake ..
```

3. Build the project:
```bash
make
```

## Running the Simulation

After building, run the executable:
```bash
./particle_sim
```

## Implementation Details

The simulation uses a Structure of Arrays (SoA) approach for better memory coalescing on the GPU. The main components are:

- `physics.cuh`: Header file containing particle system structure and function declarations
- `physics.cu`: CUDA implementation of particle physics
- `main.cpp`: Main application loop and visualization using SFML

### Physics Implementation

The simulation includes the following forces:
- Gravity
- Particle-particle repulsion
- Boundary collisions with elastic reflection
- Velocity damping

### Performance Optimization

- Uses CUDA for parallel computation of particle forces and updates
- Efficient memory layout with Structure of Arrays
- Coalesced memory access patterns
- Configurable block and grid sizes for optimal GPU utilization

## Controls

- Close window to exit the simulation

## License

This project is open source and available under the MIT License. 