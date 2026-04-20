#!/bin/bash

# Terminal Notes Docker Test Script - No Confirmation

set -e

echo "=========================================="
echo "Terminal Notes Docker Test Script"
echo "=========================================="

# Step 1: Stop and remove containers
echo ""
echo "[1/5] Stopping and removing containers..."
docker compose down -v

# Step 2: Clean SSH known_hosts
echo ""
echo "[2/5] Cleaning SSH known_hosts..."
ssh-keygen -f ~/.ssh/known_hosts -R "[localhost]:2222" 2>/dev/null || true
ssh-keygen -f ~/.ssh/known_hosts -R "localhost" 2>/dev/null || true
echo "  ✓ Done"

# Step 3: Clean data directory


# Step 4: Rebuild and start container
echo ""
echo "[4/5] Building and starting container..."
docker compose build
docker compose up -d

echo "  Waiting for container..."
sleep 3

# Step 5: SSH into container
echo ""
echo "[5/5] Connecting to container..."
echo ""
echo "=========================================="
echo "Container is running!"
echo "Password: tnpass"
echo "Run: cd /app/source && ./terminal_notes_ui.py"
echo "=========================================="
echo ""

ssh tnuser@localhost -p 2222
