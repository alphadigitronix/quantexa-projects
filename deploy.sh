#!/usr/bin/env bash
# ==============================================================================
# Fast Deployment & Cloudflare Tunnel Script for Quantum Traffic Brain
# ==============================================================================
# Usage:
#   ./deploy.sh          # Restart Streamlit and Cloudflare Tunnel
#   ./deploy.sh stop     # Terminate Streamlit and Cloudflare
#   ./deploy.sh status   # Show process status and current public URL
# ==============================================================================

set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

ACTION="${1:-start}"

if [ "$ACTION" = "stop" ]; then
    echo "[DEPLOY] Stopping running instances..."
    pkill -f cloudflared || true
    pkill -f "streamlit run dashboard.py" || true
    echo "[DEPLOY] All processes terminated."
    exit 0
fi

if [ "$ACTION" = "status" ]; then
    echo "[DEPLOY] Checking running processes:"
    ps aux | grep -E "streamlit|cloudflared" | grep -v grep || echo "No processes running."
    if [ -f "cloudflare.log" ]; then
        URL=$(grep -o "https://[a-zA-Z0-9-]*\.trycloudflare\.com" cloudflare.log | tail -n 1)
        if [ -n "$URL" ]; then
            echo "[DEPLOY] Current Public URL: $URL"
        fi
    fi
    exit 0
fi

echo "[DEPLOY] 1/4 Stopping existing Streamlit and Cloudflare processes..."
pkill -f cloudflared || true
pkill -f "streamlit run dashboard.py" || true
sleep 2

# Clean previous cloudflare log to ensure fresh URL parsing
rm -f cloudflare.log

echo "[DEPLOY] 2/4 Starting Streamlit in background on port 8501..."
nohup python -m streamlit run dashboard.py \
    --server.port 8501 \
    --server.address 0.0.0.0 \
    --server.enableCORS false \
    --server.enableXsrfProtection false \
    > streamlit.log 2>&1 &

STREAMLIT_PID=$!
echo "[DEPLOY] Streamlit started with PID: $STREAMLIT_PID"

# Wait a brief moment for Streamlit to initialize
sleep 3

echo "[DEPLOY] 3/4 Starting Cloudflare Tunnel in background..."
if [ -f "./cloudflared" ]; then
    nohup ./cloudflared tunnel --url http://localhost:8501 > cloudflare.log 2>&1 &
    CF_PID=$!
    echo "[DEPLOY] Cloudflare Tunnel started with PID: $CF_PID"
elif command -v cloudflared &> /dev/null; then
    nohup cloudflared tunnel --url http://localhost:8501 > cloudflare.log 2>&1 &
    CF_PID=$!
    echo "[DEPLOY] System cloudflared started with PID: $CF_PID"
else
    echo "[WARNING] './cloudflared' executable not found in current directory or PATH."
    echo "[INFO] Streamlit is running locally at http://localhost:8501"
    exit 0
fi

echo "[DEPLOY] 4/4 Waiting for Cloudflare Tunnel URL..."
URL=""
for i in $(seq 1 15); do
    if [ -f "cloudflare.log" ]; then
        URL=$(grep -o "https://[a-zA-Z0-9-]*\.trycloudflare\.com" cloudflare.log | tail -n 1 || true)
        if [ -n "$URL" ]; then
            break
        fi
    fi
    sleep 1
done

echo ""
echo "===================================================================="
if [ -n "$URL" ]; then
    echo "  🚀 Quantum Traffic Brain Deployed Successfully!"
    echo "  Public URL: $URL"
    echo "  Local URL:  http://localhost:8501"
else
    echo "  ⚠️ Cloudflare Tunnel URL took longer than 15s to appear."
    echo "  Check cloudflare.log manually: tail -n 20 cloudflare.log"
    echo "  Local URL: http://localhost:8501"
fi
echo "===================================================================="
