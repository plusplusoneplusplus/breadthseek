#include <SFML/Graphics.hpp>
#include <vector>
#include <chrono>
#include <thread>
#include "../include/physics.cuh"

const int WINDOW_WIDTH = 800;
const int WINDOW_HEIGHT = 800;
const int NUM_PARTICLES = 10000;
const float PARTICLE_DISPLAY_RADIUS = 2.0f;

// Convert simulation coordinates to screen coordinates
sf::Vector2f simToScreen(float x, float y) {
    return sf::Vector2f(
        (x + 1.0f) * WINDOW_WIDTH * 0.5f,
        (1.0f - y) * WINDOW_HEIGHT * 0.5f
    );
}

int main() {
    // Create window
    sf::RenderWindow window(sf::VideoMode(WINDOW_WIDTH, WINDOW_HEIGHT), "CUDA Particle Simulation");
    window.setFramerateLimit(60);

    // Initialize particle system
    ParticleSystem particleSystem;
    initParticleSystem(particleSystem, NUM_PARTICLES);

    // Create vectors for particle positions
    std::vector<float> posX(NUM_PARTICLES);
    std::vector<float> posY(NUM_PARTICLES);

    // Create particle shape for rendering
    sf::CircleShape particleShape(PARTICLE_DISPLAY_RADIUS);
    particleShape.setFillColor(sf::Color(100, 150, 255, 200));

    // Main loop
    sf::Clock clock;
    while (window.isOpen()) {
        // Handle events
        sf::Event event;
        while (window.pollEvent(event)) {
            if (event.type == sf::Event::Closed)
                window.close();
        }

        // Update simulation
        float deltaTime = clock.restart().asSeconds();
        updateParticles(particleSystem, deltaTime);

        // Copy particle positions from device to host
        copyParticlesToHost(particleSystem, posX, posY);

        // Clear window
        window.clear(sf::Color::Black);

        // Draw particles
        for (int i = 0; i < NUM_PARTICLES; i++) {
            sf::Vector2f screenPos = simToScreen(posX[i], posY[i]);
            particleShape.setPosition(screenPos.x - PARTICLE_DISPLAY_RADIUS, 
                                   screenPos.y - PARTICLE_DISPLAY_RADIUS);
            window.draw(particleShape);
        }

        // Display frame
        window.display();

        // Cap frame rate
        std::this_thread::sleep_for(std::chrono::milliseconds(16));
    }

    // Cleanup
    freeParticleSystem(particleSystem);
    return 0;
} 