#!/bin/bash
#
# Test script to verify Prometheus metrics endpoint is working
#
# Usage: ./scripts/test_metrics.sh

set -e

echo "=== Prometheus Metrics Endpoint Test ==="
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
BACKEND_URL="${BACKEND_URL:-http://localhost:8000}"
METRICS_ENDPOINT="${BACKEND_URL}/api/v1/metrics"

echo "Testing metrics endpoint: ${METRICS_ENDPOINT}"
echo ""

# Test 1: Check if endpoint is accessible
echo -n "Test 1: Checking if metrics endpoint is accessible... "
if curl -s -o /dev/null -w "%{http_code}" "${METRICS_ENDPOINT}" | grep -q "200"; then
    echo -e "${GREEN}PASS${NC}"
else
    echo -e "${RED}FAIL${NC}"
    echo "Error: Metrics endpoint is not accessible"
    exit 1
fi

# Test 2: Check if metrics are in Prometheus format
echo -n "Test 2: Checking if response is in Prometheus format... "
RESPONSE=$(curl -s "${METRICS_ENDPOINT}")
if echo "${RESPONSE}" | grep -q "# HELP"; then
    echo -e "${GREEN}PASS${NC}"
else
    echo -e "${RED}FAIL${NC}"
    echo "Error: Response is not in Prometheus format"
    exit 1
fi

# Test 3: Check for standard HTTP metrics
echo -n "Test 3: Checking for standard HTTP metrics... "
if echo "${RESPONSE}" | grep -q "http_requests_total"; then
    echo -e "${GREEN}PASS${NC}"
else
    echo -e "${RED}FAIL${NC}"
    echo "Error: Standard HTTP metrics not found"
    exit 1
fi

# Test 4: Check for custom query processing metrics
echo -n "Test 4: Checking for custom query processing metrics... "
if echo "${RESPONSE}" | grep -q "query_processing_duration_seconds"; then
    echo -e "${GREEN}PASS${NC}"
else
    echo -e "${YELLOW}WARN${NC} (May not be present until first query is processed)"
fi

# Test 5: Check for embedding generation metrics
echo -n "Test 5: Checking for embedding generation metrics... "
if echo "${RESPONSE}" | grep -q "embedding_generation_duration_seconds"; then
    echo -e "${GREEN}PASS${NC}"
else
    echo -e "${YELLOW}WARN${NC} (May not be present until first embedding is generated)"
fi

# Test 6: Check for vector search metrics
echo -n "Test 6: Checking for vector search metrics... "
if echo "${RESPONSE}" | grep -q "vector_search_duration_seconds"; then
    echo -e "${GREEN}PASS${NC}"
else
    echo -e "${YELLOW}WARN${NC} (May not be present until first search is performed)"
fi

# Test 7: Check for LLM API metrics
echo -n "Test 7: Checking for LLM API metrics... "
if echo "${RESPONSE}" | grep -q "llm_api_requests_total\|llm_api_duration_seconds"; then
    echo -e "${GREEN}PASS${NC}"
else
    echo -e "${YELLOW}WARN${NC} (May not be present until first LLM API call)"
fi

echo ""
echo "=== Metrics Endpoint Test Summary ==="
echo -e "${GREEN}Metrics endpoint is working correctly!${NC}"
echo ""
echo "Sample metrics available:"
echo "${RESPONSE}" | grep "^# HELP" | head -10
echo ""
echo "To view all metrics, run:"
echo "  curl ${METRICS_ENDPOINT}"
echo ""
echo "To start Prometheus with the provided configuration:"
echo "  cd project-code/infrastructure/prometheus"
echo "  docker run -p 9090:9090 -v \$(pwd)/prometheus.yml:/etc/prometheus/prometheus.yml prom/prometheus"
echo ""
