#!/bin/bash

# Railway Deployment Monitor
# Checks health endpoint every 30 seconds for changes

ENDPOINT="https://litellm-production-a013.up.railway.app/health"
AUTH_HEADER="Authorization: Bearer sk-1234567890abcdef1234567890abcdef"

echo "====================================="
echo "Railway Deployment Monitor"
echo "====================================="
echo "Endpoint: $ENDPOINT"
echo "Started: $(date)"
echo ""
echo "Checking every 30 seconds for 10 minutes..."
echo "Press Ctrl+C to stop"
echo ""

for i in {1..20}; do
    echo "Check #$i at $(date +%H:%M:%S)"

    response=$(curl -s -w "\nHTTP_CODE:%{http_code}" "$ENDPOINT" -H "$AUTH_HEADER" 2>&1)
    http_code=$(echo "$response" | grep "HTTP_CODE:" | cut -d: -f2)
    body=$(echo "$response" | grep -v "HTTP_CODE:")

    echo "  HTTP Code: $http_code"
    echo "  Response: $body"

    # Check if deployment is healthy
    if echo "$body" | grep -q "healthy" || echo "$body" | grep -q "llama3"; then
        echo ""
        echo "SUCCESS! New deployment is live!"
        echo "Models loaded successfully"
        exit 0
    fi

    # Check if still showing old error
    if echo "$body" | grep -q "Model list not initialized"; then
        echo "  Status: Old deployment still running"
    elif echo "$body" | grep -q "Authentication Error"; then
        echo "  Status: Auth working, checking with token..."
    fi

    echo ""

    if [ $i -lt 20 ]; then
        sleep 30
    fi
done

echo ""
echo "Monitoring complete. Check Railway dashboard for build status:"
echo "https://railway.app/project/532ff751-f7a1-4f7e-81fa-57cdf1504771"
