#!/bin/bash
# Integration tests for Grafana dashboard provisioning
# Tests container startup, provisioning, and API accessibility

set -e

GRAFANA_URL="http://localhost:3001"
GRAFANA_AUTH="admin:admin123"
TESTS_PASSED=0
TESTS_FAILED=0

# Color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

test_result() {
    local test_id=$1
    local test_name=$2
    local result=$3
    local details=$4
    
    if [ "$result" = "PASS" ]; then
        echo -e "${GREEN}✓ PASSED${NC} [$test_id] $test_name"
        [ -n "$details" ] && echo "    $details"
        TESTS_PASSED=$((TESTS_PASSED + 1))
    else
        echo -e "${RED}✗ FAILED${NC} [$test_id] $test_name"
        [ -n "$details" ] && echo "    $details"
        TESTS_FAILED=$((TESTS_FAILED + 1))
    fi
}

echo "========================================================================"
echo "PHASE 2: GRAFANA INTEGRATION TESTING"
echo "========================================================================"

# TC-006: Start Grafana Container
echo -e "\n[TC-006] Starting Grafana container..."
docker compose up -d grafana 2>&1 | grep -v "Warning"

echo "Waiting 30 seconds for Grafana to start..."
sleep 30

# Check container status
container_status=$(docker compose ps grafana 2>&1 | grep grafana | awk '{print $4}' || echo "Down")
if [[ "$container_status" == *"Up"* ]] || [[ "$container_status" == *"running"* ]]; then
    test_result "TC-006" "Grafana container startup" "PASS" "Container is running"
else
    # Try alternate check
    container_running=$(docker compose ps --format json grafana 2>/dev/null | jq -r '.State' || echo "unknown")
    if [ "$container_running" = "running" ]; then
        test_result "TC-006" "Grafana container startup" "PASS" "Container is running"
    else
        test_result "TC-006" "Grafana container startup" "FAIL" "Container status: $container_status"
        exit 1
    fi
fi

# Check health endpoint
health_response=$(curl -s -w "\n%{http_code}" "$GRAFANA_URL/api/health" 2>/dev/null || echo "000")
http_code=$(echo "$health_response" | tail -n1)
if [ "$http_code" = "200" ]; then
    test_result "TC-006-health" "Grafana health check" "PASS" "HTTP $http_code"
else
    test_result "TC-006-health" "Grafana health check" "FAIL" "HTTP $http_code"
fi

# TC-007: Verify Dashboard Auto-Provisioning
echo -e "\n[TC-007] Verifying dashboard auto-provisioning..."

# Give provisioning a moment to complete
sleep 5

# List all dashboards via API
dashboards_json=$(curl -s -u "$GRAFANA_AUTH" "$GRAFANA_URL/api/search?type=dash-db" 2>/dev/null || echo "[]")
dashboard_count=$(echo "$dashboards_json" | jq '. | length' 2>/dev/null || echo "0")

echo "Found $dashboard_count dashboards"

if [ "$dashboard_count" -ge 4 ]; then
    test_result "TC-007" "Dashboard provisioning" "PASS" "Found $dashboard_count dashboards"
    
    # List dashboard titles
    echo "$dashboards_json" | jq -r '.[] | "    - \(.title) (UID: \(.uid))"' 2>/dev/null
else
    test_result "TC-007" "Dashboard provisioning" "FAIL" "Expected 4, found $dashboard_count"
fi

# TC-008: Verify Prometheus Data Source Configuration
echo -e "\n[TC-008] Verifying Prometheus data source..."

datasources_json=$(curl -s -u "$GRAFANA_AUTH" "$GRAFANA_URL/api/datasources" 2>/dev/null || echo "[]")
prometheus_found=$(echo "$datasources_json" | jq '.[] | select(.type=="prometheus") | .name' 2>/dev/null || echo "")

if [ -n "$prometheus_found" ]; then
    test_result "TC-008" "Prometheus data source" "PASS" "Data source configured"
else
    test_result "TC-008" "Prometheus data source" "FAIL" "Prometheus not found in data sources"
fi

# TC-009: Verify Dashboard Accessibility
echo -e "\n[TC-009] Verifying dashboard accessibility..."

expected_dashboards=(
    "API Performance"
    "System Resources"
    "Database Performance"
    "Celery Tasks"
)

accessible_count=0
for dashboard_name in "${expected_dashboards[@]}"; do
    encoded_name=$(echo "$dashboard_name" | sed 's/ /%20/g')
    search_result=$(curl -s -u "$GRAFANA_AUTH" "$GRAFANA_URL/api/search?query=$encoded_name" 2>/dev/null || echo "[]")
    found_count=$(echo "$search_result" | jq '. | length' 2>/dev/null || echo "0")
    
    if [ "$found_count" -gt 0 ]; then
        echo "  ✓ $dashboard_name: Found"
        accessible_count=$((accessible_count + 1))
    else
        echo "  ✗ $dashboard_name: Not found"
    fi
done

if [ "$accessible_count" -eq ${#expected_dashboards[@]} ]; then
    test_result "TC-009" "Dashboard accessibility" "PASS" "All $accessible_count dashboards accessible"
else
    test_result "TC-009" "Dashboard accessibility" "FAIL" "Only $accessible_count/${#expected_dashboards[@]} accessible"
fi

# TC-012: PromQL Query Execution Smoke Test
echo -e "\n[TC-012] Testing PromQL query execution..."

# Test a simple query
test_query="up"
encoded_query=$(echo "$test_query" | jq -sRr @uri)
query_response=$(curl -s -u "$GRAFANA_AUTH" "$GRAFANA_URL/api/datasources/proxy/1/api/v1/query?query=$encoded_query" 2>/dev/null || echo "{}")
query_status=$(echo "$query_response" | jq -r '.status' 2>/dev/null || echo "error")

if [ "$query_status" = "success" ]; then
    test_result "TC-012" "PromQL query execution" "PASS" "Query executed successfully"
else
    # This might fail if Prometheus is not fully running, which is acceptable
    test_result "TC-012" "PromQL query execution" "WARN" "Query execution issue (Prometheus may not be fully initialized)"
fi

# Summary
echo ""
echo "========================================================================"
echo "INTEGRATION TEST SUMMARY"
echo "========================================================================"
echo "Total Tests: $((TESTS_PASSED + TESTS_FAILED))"
echo -e "${GREEN}Passed: $TESTS_PASSED${NC}"
echo -e "${RED}Failed: $TESTS_FAILED${NC}"

if [ $TESTS_FAILED -eq 0 ]; then
    exit 0
else
    exit 1
fi
