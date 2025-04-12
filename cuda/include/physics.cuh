#pragma once

#include <cuda_runtime.h>
#include <vector>

// Constants for simulation
constexpr float GRAVITY = -9.81f;
constexpr float DAMPING = 0.99f;
constexpr float PARTICLE_RADIUS = 0.01f;
constexpr float COLLISION_ELASTICITY = 0.8f;
constexpr float TIME_STEP = 0.001f;
constexpr float BOUNDARY_SIZE = 1.0f;

// Structure to hold particle data (Structure of Arrays approach for better memory coalescing)
struct ParticleSystem {
    float* d_posX;  // Position X component
    float* d_posY;  // Position Y component
    float* d_velX;  // Velocity X component
    float* d_velY;  // Velocity Y component
    float* d_forceX;  // Force X component
    float* d_forceY;  // Force Y component
    int numParticles;
};

// Host-side functions
void initParticleSystem(ParticleSystem& ps, int numParticles);
void freeParticleSystem(ParticleSystem& ps);
void updateParticles(ParticleSystem& ps, float deltaTime);
void copyParticlesToHost(ParticleSystem& ps, std::vector<float>& posX, std::vector<float>& posY);

// Device kernels (declared here, defined in physics.cu)
__global__ void computeForces(float* posX, float* posY,
                            float* velX, float* velY,
                            float* forceX, float* forceY,
                            int numParticles);

__global__ void integrateParticles(float* posX, float* posY,
                                  float* velX, float* velY,
                                  float* forceX, float* forceY,
                                  int numParticles,
                                  float deltaTime);

__global__ void handleBoundaryCollisions(float* posX, float* posY,
                                       float* velX, float* velY,
                                       int numParticles); 