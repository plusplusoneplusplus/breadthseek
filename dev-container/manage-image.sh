#!/bin/bash
# manage-image.sh: Simple script to build, run, and clean up the dev container image
# Usage: ./manage-image.sh [build|run|stop|remove]


IMAGE_NAME="awesome-dev-container"
CONTAINER_NAME="awesome-dev-container"
DOCKERFILE_DIR="$(dirname "$0")"
WORKSPACE_DIR="$(cd "$DOCKERFILE_DIR/.." && pwd)"

print_help() {
  cat <<EOF
Usage: $0 [command]

Commands:
  build     Build the Docker image for the dev container
  run       Run the dev container interactively, mounting the workspace
  run-bg    Run the dev container in the background (detached, always stays alive)
  stop      Stop the running dev container
  remove    Remove the dev container image
  help      Show this help message

Notes:
  run-bg overrides the default entrypoint and uses 'tail -f /dev/null' to keep the container alive in detached mode.

Examples:
  $0 build
  $0 run
  $0 run-bg
  $0 stop
  $0 remove
  $0 help
EOF
}

check_and_remove_container() {
  if [ "$(docker ps -aq -f name="^${CONTAINER_NAME}$")" ]; then
    echo "A container named $CONTAINER_NAME already exists. Removing it..."
    docker stop "$CONTAINER_NAME" 2>/dev/null || true
    docker rm "$CONTAINER_NAME" 2>/dev/null || true
  fi
}

case "$1" in
  build)
    echo "Building Docker image..."
    docker build -t "$IMAGE_NAME" "$DOCKERFILE_DIR"
    ;;
  run)
    check_and_remove_container
    echo "Running Docker container..."
    docker run --rm -it \
      --name "$CONTAINER_NAME" \
      -v "$WORKSPACE_DIR:/workspace" \
      -w /workspace \
      --cap-add=NET_ADMIN --cap-add=NET_RAW \
      "$IMAGE_NAME"
    ;;
  run-bg)
    check_and_remove_container
    echo "Running Docker container in background (using tail -f /dev/null to keep alive)..."
    docker run -d \
      --name "$CONTAINER_NAME" \
      -v "$WORKSPACE_DIR:/workspace" \
      -w /workspace \
      --cap-add=NET_ADMIN --cap-add=NET_RAW \
      "$IMAGE_NAME" tail -f /dev/null
    ;;
  stop)
    echo "Stopping container..."
    docker stop "$CONTAINER_NAME"
    ;;
  remove)
    echo "Removing image..."
    docker rmi "$IMAGE_NAME"
    ;;
  help|--help|-h)
    print_help
    ;;
  *)
    echo "Unknown or missing command: $1"
    print_help
    ;;
esac
