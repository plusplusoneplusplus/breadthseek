cmake_minimum_required(VERSION 3.18)
project(cuda_particles CUDA CXX)

# Set C++ standard
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Set CUDA architectures (you can adjust these based on your GPU)
set(CMAKE_CUDA_ARCHITECTURES 60 70 75 80)
set(CMAKE_CUDA_FLAGS "${CMAKE_CUDA_FLAGS} -O3")

# Find SFML package
if(WIN32)
    set(SFML_DIR "C:/SFML/lib/cmake/SFML" CACHE PATH "Path to SFML CMake config file")
else()
    # For Linux, try to find SFML in standard locations
    set(SFML_DIR "/usr/lib/cmake/SFML" CACHE PATH "Path to SFML CMake config file")
endif()

find_package(SFML 2.5 COMPONENTS graphics window system REQUIRED)
if(NOT SFML_FOUND)
    message(FATAL_ERROR "SFML not found. Please install SFML 2.5 or later.")
endif()

# Include directories
include_directories(
    ${CMAKE_CURRENT_SOURCE_DIR}/include
    ${CMAKE_CUDA_TOOLKIT_INCLUDE_DIRECTORIES}
)

# Add source files
set(SOURCES
    src/main.cpp
    src/physics.cu
)

# Create executable
add_executable(particle_sim ${SOURCES})

# Link libraries
target_link_libraries(particle_sim
    sfml-graphics
    sfml-window
    sfml-system
)

# Set CUDA specific properties
set_target_properties(particle_sim PROPERTIES
    CUDA_SEPARABLE_COMPILATION ON
)

# Add CUDA include directories to target
target_include_directories(particle_sim PRIVATE ${CMAKE_CUDA_TOOLKIT_INCLUDE_DIRECTORIES}) 