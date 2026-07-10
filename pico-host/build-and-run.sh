#!/bin/bash
set -e

CONTAINER_NAME="pico-config"
IMAGE_NAME="pico-config"
PORT="9191"

echo "=== Pico Config Studio — Build and Run ==="
echo ""

# Stop and remove existing container if running
if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "→ Stopping existing container..."
    docker stop "${CONTAINER_NAME}" >/dev/null 2>&1 || true
    echo "→ Removing existing container..."
    docker rm "${CONTAINER_NAME}" >/dev/null 2>&1 || true
fi

# Build the image
echo "→ Building Docker image..."
docker build -t "${IMAGE_NAME}" .

# Run the container
echo "→ Starting container..."
docker run -d \
    -p "${PORT}:${PORT}" \
    --privileged \
    --name "${CONTAINER_NAME}" \
    "${IMAGE_NAME}"

echo ""
echo "✓ Container started successfully!"
echo ""
echo "Access the Config Studio at:"
echo "  http://localhost:${PORT}"
echo ""
echo "View logs:"
echo "  docker logs -f ${CONTAINER_NAME}"
echo ""
echo "Stop container:"
echo "  docker stop ${CONTAINER_NAME}"
echo ""
