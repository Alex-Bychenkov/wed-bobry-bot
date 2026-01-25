#!/bin/bash

# Quick SSH tunnel script for Grafana access
# Usage: ./scripts/grafana-tunnel.sh

SERVER_IP="87.247.157.122"
LOCAL_PORT="3000"
REMOTE_PORT="3000"

echo "========================================="
echo "Grafana SSH Tunnel"
echo "========================================="
echo ""
echo "Creating SSH tunnel to Grafana..."
echo ""
echo "Server: $SERVER_IP"
echo "Local:  http://localhost:$LOCAL_PORT"
echo ""
echo "Keep this terminal open while using Grafana"
echo "Press Ctrl+C to stop the tunnel"
echo ""
echo "Opening Grafana in browser in 3 seconds..."
echo ""

# Wait a bit and then open browser
(sleep 3 && open "http://localhost:$LOCAL_PORT" 2>/dev/null || xdg-open "http://localhost:$LOCAL_PORT" 2>/dev/null || echo "Please open http://localhost:$LOCAL_PORT in your browser") &

# Create SSH tunnel
ssh -N -L $LOCAL_PORT:localhost:$REMOTE_PORT root@$SERVER_IP
