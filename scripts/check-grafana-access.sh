#!/bin/bash

# Script to diagnose and fix Grafana access issues
# Usage: ./scripts/check-grafana-access.sh

set -e

SERVER_IP="87.247.157.122"
GRAFANA_PORT="3000"

echo "========================================="
echo "Grafana Access Diagnostics"
echo "========================================="
echo ""

# Check if we can SSH to the server
echo "1. Checking SSH access to server..."
if ssh -o ConnectTimeout=5 root@$SERVER_IP "echo 'SSH OK'" 2>/dev/null; then
    echo "✅ SSH access: OK"
    SSH_OK=true
else
    echo "❌ SSH access: FAILED"
    echo "   Cannot connect to server. Please check:"
    echo "   - Network connectivity"
    echo "   - SSH credentials"
    echo "   - Server is online"
    SSH_OK=false
fi
echo ""

if [ "$SSH_OK" = true ]; then
    # Check if Grafana container is running
    echo "2. Checking if Grafana container is running..."
    if ssh root@$SERVER_IP "docker ps | grep grafana" >/dev/null 2>&1; then
        echo "✅ Grafana container: RUNNING"
    else
        echo "❌ Grafana container: NOT RUNNING"
        echo "   Starting Grafana..."
        ssh root@$SERVER_IP "cd /opt/monitoring && docker-compose -f docker-compose.monitoring.yml up -d grafana"
    fi
    echo ""

    # Check if Grafana is accessible locally on server
    echo "3. Checking if Grafana responds locally on server..."
    if ssh root@$SERVER_IP "curl -s http://localhost:$GRAFANA_PORT/api/health" | grep -q "ok"; then
        echo "✅ Grafana responds locally: OK"
    else
        echo "❌ Grafana not responding locally"
        echo "   Check Grafana logs:"
        ssh root@$SERVER_IP "cd /opt/monitoring && docker-compose -f docker-compose.monitoring.yml logs --tail=50 grafana"
    fi
    echo ""

    # Check which interface Grafana is listening on
    echo "4. Checking which interface Grafana listens on..."
    LISTEN_INFO=$(ssh root@$SERVER_IP "ss -tlnp | grep :$GRAFANA_PORT" 2>/dev/null || echo "")
    if echo "$LISTEN_INFO" | grep -q "0.0.0.0:$GRAFANA_PORT"; then
        echo "✅ Grafana listening on: 0.0.0.0:$GRAFANA_PORT (all interfaces)"
    elif echo "$LISTEN_INFO" | grep -q ":::$GRAFANA_PORT"; then
        echo "✅ Grafana listening on: :::$GRAFANA_PORT (all interfaces, IPv6)"
    else
        echo "⚠️  Grafana listening on: $LISTEN_INFO"
    fi
    echo ""

    # Check firewall status
    echo "5. Checking firewall (UFW)..."
    UFW_STATUS=$(ssh root@$SERVER_IP "ufw status | grep $GRAFANA_PORT" 2>/dev/null || echo "")
    if [ -z "$UFW_STATUS" ]; then
        echo "⚠️  Port $GRAFANA_PORT is NOT allowed in firewall"
        echo ""
        echo "   Do you want to allow port $GRAFANA_PORT in firewall? (y/n)"
        read -r answer
        if [ "$answer" = "y" ]; then
            echo "   Opening port $GRAFANA_PORT..."
            ssh root@$SERVER_IP "ufw allow $GRAFANA_PORT/tcp"
            echo "✅ Port $GRAFANA_PORT opened in firewall"
        fi
    else
        echo "✅ Firewall rules for port $GRAFANA_PORT:"
        echo "$UFW_STATUS"
    fi
    echo ""

    # Show UFW status
    echo "6. Current firewall status:"
    ssh root@$SERVER_IP "ufw status numbered | head -20"
    echo ""
fi

# Check if Grafana is accessible from this machine
echo "7. Checking if Grafana is accessible from this machine..."
if curl -s -m 5 http://$SERVER_IP:$GRAFANA_PORT/api/health | grep -q "ok"; then
    echo "✅ Grafana is accessible from this machine!"
    echo "   URL: http://$SERVER_IP:$GRAFANA_PORT"
    echo "   Login: admin / admin"
else
    echo "❌ Cannot access Grafana from this machine"
    echo ""
    echo "   Possible reasons:"
    echo "   1. Firewall on server blocks port $GRAFANA_PORT"
    echo "   2. Corporate firewall/proxy blocks port $GRAFANA_PORT"
    echo "   3. Network routing issues"
    echo ""
    echo "   Solutions:"
    echo "   A. Open port in server firewall (see above)"
    echo "   B. Use SSH tunnel: ssh -L $GRAFANA_PORT:localhost:$GRAFANA_PORT root@$SERVER_IP"
    echo "   C. Setup nginx reverse proxy on standard HTTPS port (443)"
    echo ""
    echo "   See GRAFANA_ACCESS.md for detailed instructions"
fi
echo ""

# Check ping
echo "8. Checking network connectivity to server..."
if ping -c 3 $SERVER_IP >/dev/null 2>&1; then
    echo "✅ Server is reachable (ping OK)"
else
    echo "❌ Server is not reachable (ping FAILED)"
fi
echo ""

# Check port with nc/telnet
echo "9. Checking if port $GRAFANA_PORT is open..."
if command -v nc >/dev/null 2>&1; then
    if nc -zv -w 5 $SERVER_IP $GRAFANA_PORT 2>&1 | grep -q "succeeded\|open"; then
        echo "✅ Port $GRAFANA_PORT is open"
    else
        echo "❌ Port $GRAFANA_PORT is closed or filtered"
        echo "   This usually means:"
        echo "   - Firewall on server is blocking the port"
        echo "   - Corporate firewall is blocking the port"
    fi
elif command -v telnet >/dev/null 2>&1; then
    if timeout 5 telnet $SERVER_IP $GRAFANA_PORT 2>&1 | grep -q "Connected"; then
        echo "✅ Port $GRAFANA_PORT is open"
    else
        echo "❌ Port $GRAFANA_PORT is closed or filtered"
    fi
else
    echo "⚠️  nc/telnet not available, skipping port check"
fi
echo ""

echo "========================================="
echo "Summary"
echo "========================================="
echo ""
echo "Grafana URL: http://$SERVER_IP:$GRAFANA_PORT"
echo "Default credentials: admin / admin"
echo ""
echo "If you cannot access Grafana, try:"
echo "1. SSH Tunnel: ssh -L $GRAFANA_PORT:localhost:$GRAFANA_PORT root@$SERVER_IP"
echo "   Then open: http://localhost:$GRAFANA_PORT"
echo ""
echo "2. Setup nginx reverse proxy (recommended for production)"
echo "   See GRAFANA_ACCESS.md for instructions"
echo ""
echo "3. Contact network admin to check corporate firewall rules"
echo ""
