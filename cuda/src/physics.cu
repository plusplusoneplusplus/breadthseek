#include "../include/physics.cuh"
#include <cuda_runtime.h>
#include <stdio.h>

// Helper function for CUDA error checking
#define checkCudaError(ans) { gpuAssert((ans), __FILE__, __LINE__); }
inline void gpuAssert(cudaError_t code, const char *file, int line, bool abort=true)
{
    if (code != cudaSuccess) 
    {
        fprintf(stderr,"GPUassert: %s %s %d\n", cudaGetErrorString(code), file, line);
        if (abort) exit(code);
    }
}

// Initialize particle system
void initParticleSystem(ParticleSystem& ps, int numParticles) {
    ps.numParticles = numParticles;
    
    // Allocate device memory
    checkCudaError(cudaMalloc(&ps.d_posX, numParticles * sizeof(float)));
    checkCudaError(cudaMalloc(&ps.d_posY, numParticles * sizeof(float)));
    checkCudaError(cudaMalloc(&ps.d_velX, numParticles * sizeof(float)));
    checkCudaError(cudaMalloc(&ps.d_velY, numParticles * sizeof(float)));
    checkCudaError(cudaMalloc(&ps.d_forceX, numParticles * sizeof(float)));
    checkCudaError(cudaMalloc(&ps.d_forceY, numParticles * sizeof(float)));

    // Create temporary host arrays for initialization
    std::vector<float> h_posX(numParticles);
    std::vector<float> h_posY(numParticles);
    std::vector<float> h_velX(numParticles);
    std::vector<float> h_velY(numParticles);

    // Initialize particles in a grid pattern
    for (int i = 0; i < numParticles; i++) {
        h_posX[i] = -0.5f + (float)(i % 100) / 100.0f;
        h_posY[i] = -0.5f + (float)(i / 100) / 100.0f;
        h_velX[i] = 0.0f;
        h_velY[i] = 0.0f;
    }

    // Copy initial data to device
    checkCudaError(cudaMemcpy(ps.d_posX, h_posX.data(), numParticles * sizeof(float), cudaMemcpyHostToDevice));
    checkCudaError(cudaMemcpy(ps.d_posY, h_posY.data(), numParticles * sizeof(float), cudaMemcpyHostToDevice));
    checkCudaError(cudaMemcpy(ps.d_velX, h_velX.data(), numParticles * sizeof(float), cudaMemcpyHostToDevice));
    checkCudaError(cudaMemcpy(ps.d_velY, h_velY.data(), numParticles * sizeof(float), cudaMemcpyHostToDevice));
}

// Free particle system resources
void freeParticleSystem(ParticleSystem& ps) {
    checkCudaError(cudaFree(ps.d_posX));
    checkCudaError(cudaFree(ps.d_posY));
    checkCudaError(cudaFree(ps.d_velX));
    checkCudaError(cudaFree(ps.d_velY));
    checkCudaError(cudaFree(ps.d_forceX));
    checkCudaError(cudaFree(ps.d_forceY));
}

// Compute forces kernel
__global__ void computeForces(float* posX, float* posY,
                            float* velX, float* velY,
                            float* forceX, float* forceY,
                            int numParticles) {
    int idx = blockIdx.x * blockDim.x + threadIdx.x;
    if (idx >= numParticles) return;

    float fx = 0.0f;
    float fy = GRAVITY; // Apply gravity

    // Compute forces with neighboring particles
    for (int j = 0; j < numParticles; j++) {
        if (j == idx) continue;

        float dx = posX[j] - posX[idx];
        float dy = posY[j] - posY[idx];
        float dist = sqrtf(dx * dx + dy * dy);

        if (dist < PARTICLE_RADIUS * 2.0f) {
            // Repulsive force when particles are too close
            float force = (PARTICLE_RADIUS * 2.0f - dist) * 0.5f;
            fx += force * dx / dist;
            fy += force * dy / dist;
        }
    }

    forceX[idx] = fx;
    forceY[idx] = fy;
}

// Integrate particles kernel
__global__ void integrateParticles(float* posX, float* posY,
                                  float* velX, float* velY,
                                  float* forceX, float* forceY,
                                  int numParticles,
                                  float deltaTime) {
    int idx = blockIdx.x * blockDim.x + threadIdx.x;
    if (idx >= numParticles) return;

    // Semi-implicit Euler integration
    velX[idx] = velX[idx] * DAMPING + forceX[idx] * deltaTime;
    velY[idx] = velY[idx] * DAMPING + forceY[idx] * deltaTime;
    
    posX[idx] += velX[idx] * deltaTime;
    posY[idx] += velY[idx] * deltaTime;
}

// Handle boundary collisions kernel
__global__ void handleBoundaryCollisions(float* posX, float* posY,
                                       float* velX, float* velY,
                                       int numParticles) {
    int idx = blockIdx.x * blockDim.x + threadIdx.x;
    if (idx >= numParticles) return;

    // Boundary checks with elastic collisions
    if (posX[idx] < -BOUNDARY_SIZE) {
        posX[idx] = -BOUNDARY_SIZE;
        velX[idx] = -velX[idx] * COLLISION_ELASTICITY;
    }
    if (posX[idx] > BOUNDARY_SIZE) {
        posX[idx] = BOUNDARY_SIZE;
        velX[idx] = -velX[idx] * COLLISION_ELASTICITY;
    }
    if (posY[idx] < -BOUNDARY_SIZE) {
        posY[idx] = -BOUNDARY_SIZE;
        velY[idx] = -velY[idx] * COLLISION_ELASTICITY;
    }
    if (posY[idx] > BOUNDARY_SIZE) {
        posY[idx] = BOUNDARY_SIZE;
        velY[idx] = -velY[idx] * COLLISION_ELASTICITY;
    }
}

// Update particles (called from host)
void updateParticles(ParticleSystem& ps, float deltaTime) {
    int blockSize = 256;
    int numBlocks = (ps.numParticles + blockSize - 1) / blockSize;

    computeForces<<<numBlocks, blockSize>>>(
        ps.d_posX, ps.d_posY,
        ps.d_velX, ps.d_velY,
        ps.d_forceX, ps.d_forceY,
        ps.numParticles
    );

    integrateParticles<<<numBlocks, blockSize>>>(
        ps.d_posX, ps.d_posY,
        ps.d_velX, ps.d_velY,
        ps.d_forceX, ps.d_forceY,
        ps.numParticles,
        deltaTime
    );

    handleBoundaryCollisions<<<numBlocks, blockSize>>>(
        ps.d_posX, ps.d_posY,
        ps.d_velX, ps.d_velY,
        ps.numParticles
    );

    // Check for errors
    checkCudaError(cudaGetLastError());
    checkCudaError(cudaDeviceSynchronize());
}

// Copy particle positions back to host for visualization
void copyParticlesToHost(ParticleSystem& ps, std::vector<float>& posX, std::vector<float>& posY) {
    checkCudaError(cudaMemcpy(posX.data(), ps.d_posX, ps.numParticles * sizeof(float), cudaMemcpyDeviceToHost));
    checkCudaError(cudaMemcpy(posY.data(), ps.d_posY, ps.numParticles * sizeof(float), cudaMemcpyDeviceToHost));
} 