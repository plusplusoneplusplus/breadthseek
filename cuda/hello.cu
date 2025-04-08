#include <stdio.h>
#include <cuda_runtime.h>

// CUDA kernel function to print a message from the GPU
__global__ void helloFromGPU()
{
    printf("Hello World from GPU! (Thread %d, Block %d)\n", threadIdx.x, blockIdx.x);
}

int main()
{
    // Print from CPU
    printf("Hello World from CPU!\n");

    // Configure kernel launch parameters
    int numBlocks = 2;
    int threadsPerBlock = 4;
    
    // Launch kernel to print from GPU
    helloFromGPU<<<numBlocks, threadsPerBlock>>>();
    
    // Wait for GPU to finish before accessing on host
    cudaDeviceSynchronize();
    
    // Check for any errors
    cudaError_t error = cudaGetLastError();
    if (error != cudaSuccess)
    {
        fprintf(stderr, "CUDA error: %s\n", cudaGetErrorString(error));
        return -1;
    }

    return 0;
} 