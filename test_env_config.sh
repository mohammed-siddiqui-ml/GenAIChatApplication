#!/bin/bash

# Test script for Environment Configuration Template (task-003)
# Test Plan: Testing Report from artifacts/tasks/task-003/testing.md

set -e

# Color codes for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Counters
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

# Test result arrays
declare -a PASSED_TESTS_LIST
declare -a FAILED_TESTS_LIST

# Function to print test result
print_test_result() {
    local test_id=$1
    local test_name=$2
    local result=$3
    local details=$4
    
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    
    if [ "$result" = "PASS" ]; then
        echo -e "${GREEN}✓ PASS${NC} - ${test_id}: ${test_name}"
        PASSED_TESTS=$((PASSED_TESTS + 1))
        PASSED_TESTS_LIST+=("${test_id}: ${test_name}")
    else
        echo -e "${RED}✗ FAIL${NC} - ${test_id}: ${test_name}"
        echo -e "  ${YELLOW}Details: ${details}${NC}"
        FAILED_TESTS=$((FAILED_TESTS + 1))
        FAILED_TESTS_LIST+=("${test_id}: ${test_name} - ${details}")
    fi
}

echo "=========================================="
echo "Environment Configuration Template Tests"
echo "Task: task-003"
echo "Date: $(date '+%Y-%m-%d %H:%M:%S')"
echo "=========================================="
echo ""

# TC-001: File Existence Validation
echo "Running TC-001: File Existence Validation..."
if [ -f ".env.example" ] && [ -r ".env.example" ] && [ -s ".env.example" ]; then
    file_size=$(stat -f%z ".env.example" 2>/dev/null || stat -c%s ".env.example" 2>/dev/null)
    print_test_result "TC-001" "File Existence Validation" "PASS" "File exists, readable, size: ${file_size} bytes"
else
    print_test_result "TC-001" "File Existence Validation" "FAIL" "File missing, unreadable, or empty"
fi

# TC-002: Environment Variable Count
echo "Running TC-002: Environment Variable Count..."
var_count=$(grep -E '^[A-Z_]+=' .env.example | wc -l | tr -d ' ')
if [ "$var_count" -ge 20 ]; then
    print_test_result "TC-002" "Environment Variable Count" "PASS" "Found ${var_count} variables (minimum 20 required)"
else
    print_test_result "TC-002" "Environment Variable Count" "FAIL" "Found ${var_count} variables, expected >= 20"
fi

# TC-003: Required Sections Validation
echo "Running TC-003: Required Sections Validation..."
sections_found=0
missing_sections=""

for section in "Database" "Redis" "MinIO" "OpenAI" "Auth\|Security" "Service"; do
    if grep -qi "$section" .env.example; then
        sections_found=$((sections_found + 1))
    else
        missing_sections="${missing_sections} ${section}"
    fi
done

if [ "$sections_found" -ge 6 ]; then
    print_test_result "TC-003" "Required Sections Validation" "PASS" "Found ${sections_found}/6 required sections"
else
    print_test_result "TC-003" "Required Sections Validation" "FAIL" "Found ${sections_found}/6 sections. Missing:${missing_sections}"
fi

# TC-004: Variable Documentation Validation
echo "Running TC-004: Variable Documentation Validation..."
total_vars=$(grep -E '^[A-Z_]+=' .env.example | wc -l | tr -d ' ')
documented_vars=$(grep -B3 -E '^[A-Z_]+=' .env.example | grep -c '#' || echo 0)
doc_coverage=$((documented_vars * 100 / total_vars))

if [ "$doc_coverage" -ge 95 ]; then
    print_test_result "TC-004" "Variable Documentation Validation" "PASS" "Documentation coverage: ${doc_coverage}%"
else
    print_test_result "TC-004" "Variable Documentation Validation" "FAIL" "Documentation coverage: ${doc_coverage}%, expected >= 95%"
fi

# TC-005: Security Placeholder Validation
echo "Running TC-005: Security Placeholder Validation..."
has_placeholders=$(grep -E 'YOUR_.*_HERE|CHANGE_IN_PRODUCTION|your-.*-here' .env.example | wc -l | tr -d ' ')
if [ "$has_placeholders" -gt 0 ]; then
    print_test_result "TC-005" "Security Placeholder Validation" "PASS" "Found ${has_placeholders} placeholder patterns"
else
    print_test_result "TC-005" "Security Placeholder Validation" "FAIL" "No security placeholders found"
fi

# TC-006: README Environment Configuration Section
echo "Running TC-006: README Environment Configuration Section..."
readme_checks=0
if grep -q "Environment Configuration\|Environment Setup" README.md; then readme_checks=$((readme_checks + 1)); fi
if grep -q "\.env\.example" README.md; then readme_checks=$((readme_checks + 1)); fi
if grep -q "SECRET_KEY\|secret" README.md; then readme_checks=$((readme_checks + 1)); fi

if [ "$readme_checks" -ge 2 ]; then
    print_test_result "TC-006" "README Environment Configuration Section" "PASS" "Found ${readme_checks}/3 README elements"
else
    print_test_result "TC-006" "README Environment Configuration Section" "FAIL" "Found ${readme_checks}/3 README elements"
fi

# TC-007: Variable Naming Convention
echo "Running TC-007: Variable Naming Convention..."
invalid_vars=$(grep -E '^[^#]' .env.example | grep '=' | grep -v -E '^[A-Z_]+=' | wc -l | tr -d ' ')
if [ "$invalid_vars" -eq 0 ]; then
    print_test_result "TC-007" "Variable Naming Convention" "PASS" "All variables use UPPERCASE_SNAKE_CASE"
else
    print_test_result "TC-007" "Variable Naming Convention" "FAIL" "Found ${invalid_vars} variables with invalid naming"
fi

# TC-008: Copy Template to .env
echo "Running TC-008: Copy Template to .env..."
cp .env.example .env.test 2>/dev/null
if [ $? -eq 0 ] && [ -f ".env.test" ]; then
    rm -f .env.test
    print_test_result "TC-008" "Copy Template to .env" "PASS" "Template can be copied successfully"
else
    print_test_result "TC-008" "Copy Template to .env" "FAIL" "Failed to copy template"
fi

# TC-009: Critical Variables Present
echo "Running TC-009: Critical Variables Present..."
critical_vars_found=0
critical_vars_missing=""

# Check for DATABASE_URL or DB_HOST
if grep -qE '^(DATABASE_URL|DB_HOST)' .env.example; then
    critical_vars_found=$((critical_vars_found + 1))
else
    critical_vars_missing="${critical_vars_missing} DATABASE"
fi

# Check for REDIS_HOST or REDIS_URL
if grep -qE '^(REDIS_HOST|REDIS_URL)' .env.example; then
    critical_vars_found=$((critical_vars_found + 1))
else
    critical_vars_missing="${critical_vars_missing} REDIS"
fi

# Check for MINIO variables
if grep -qE '^MINIO' .env.example; then
    critical_vars_found=$((critical_vars_found + 1))
else
    critical_vars_missing="${critical_vars_missing} MINIO"
fi

# Check for OPENAI_API_KEY
if grep -qE '^OPENAI_API_KEY' .env.example; then
    critical_vars_found=$((critical_vars_found + 1))
else
    critical_vars_missing="${critical_vars_missing} OPENAI_API_KEY"
fi

# Check for SECRET_KEY
if grep -qE '^SECRET_KEY' .env.example; then
    critical_vars_found=$((critical_vars_found + 1))
else
    critical_vars_missing="${critical_vars_missing} SECRET_KEY"
fi

if [ "$critical_vars_found" -ge 5 ]; then
    print_test_result "TC-009" "Critical Variables Present" "PASS" "Found ${critical_vars_found}/5 critical variable groups"
else
    print_test_result "TC-009" "Critical Variables Present" "FAIL" "Found ${critical_vars_found}/5 critical variables. Missing:${critical_vars_missing}"
fi

# TC-010: Visual Section Separators
echo "Running TC-010: Visual Section Separators..."
separator_count=$(grep -E '^#.*===|^#.*---' .env.example | wc -l | tr -d ' ')
if [ "$separator_count" -ge 6 ]; then
    print_test_result "TC-010" "Visual Section Separators" "PASS" "Found ${separator_count} section separators"
else
    print_test_result "TC-010" "Visual Section Separators" "FAIL" "Found ${separator_count} separators, expected >= 6"
fi

echo ""
echo "=========================================="
echo "Test Execution Summary"
echo "=========================================="
echo "Total Tests: ${TOTAL_TESTS}"
echo -e "${GREEN}Passed: ${PASSED_TESTS}${NC}"
echo -e "${RED}Failed: ${FAILED_TESTS}${NC}"
echo "Success Rate: $(( PASSED_TESTS * 100 / TOTAL_TESTS ))%"
echo ""

if [ "$FAILED_TESTS" -gt 0 ]; then
    echo -e "${RED}Failed Tests:${NC}"
    for failed in "${FAILED_TESTS_LIST[@]}"; do
        echo "  - $failed"
    done
    echo ""
    exit 1
else
    echo -e "${GREEN}All tests passed!${NC}"
    exit 0
fi
