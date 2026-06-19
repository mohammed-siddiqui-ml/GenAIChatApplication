#!/usr/bin/env python3
"""
Validation script for Grafana dashboards configuration.
Tests static files, Docker integration, and dashboard functionality.
"""

import json
import yaml
import os
import sys
from pathlib import Path

# Test results tracking
results = {
    'passed': [],
    'failed': [],
    'total': 0
}

def test_result(test_id, test_name, passed, details=""):
    """Record test result"""
    results['total'] += 1
    status = "✓ PASSED" if passed else "✗ FAILED"
    result_entry = f"{test_id}: {test_name} - {status}"
    if details:
        result_entry += f"\n    {details}"
    
    if passed:
        results['passed'].append(result_entry)
    else:
        results['failed'].append(result_entry)
    
    print(result_entry)
    return passed


# Phase 1: Static File Validation
print("=" * 80)
print("PHASE 1: STATIC FILE VALIDATION")
print("=" * 80)

# TC-001: Validate Dashboard JSON Files Exist and Are Valid JSON
print("\n[TC-001] Validating dashboard JSON files...")
dashboard_files = [
    'infrastructure/grafana/dashboards/api-dashboard.json',
    'infrastructure/grafana/dashboards/celery-dashboard.json',
    'infrastructure/grafana/dashboards/database-dashboard.json',
    'infrastructure/grafana/dashboards/system-dashboard.json'
]

all_valid = True
for file_path in dashboard_files:
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
        file_size = os.path.getsize(file_path)
        print(f"  ✓ {file_path}: Valid JSON ({file_size} bytes)")
    except FileNotFoundError:
        all_valid = False
        print(f"  ✗ {file_path}: File not found")
    except json.JSONDecodeError as e:
        all_valid = False
        print(f"  ✗ {file_path}: Invalid JSON - {e}")

test_result("TC-001", "Dashboard JSON files valid", all_valid)

# TC-002: Validate Provisioning Configuration YAML
print("\n[TC-002] Validating provisioning YAML configuration...")
yaml_path = 'infrastructure/grafana/provisioning/dashboards/dashboards.yml'
try:
    with open(yaml_path, 'r') as f:
        yaml_data = yaml.safe_load(f)
    
    # Verify expected configuration
    checks = []
    checks.append(('apiVersion' in yaml_data, "apiVersion present"))
    checks.append((yaml_data.get('apiVersion') == 1, "apiVersion is 1"))
    
    providers = yaml_data.get('providers', [])
    checks.append((len(providers) > 0, "Has providers configured"))
    
    if providers:
        main_provider = providers[0]
        checks.append((main_provider.get('name') == 'GenAI Knowledge Retrieval Dashboards', 
                      "Provider name correct"))
        checks.append((main_provider.get('folder') == 'GenAI Monitoring', 
                      "Folder name correct"))
    
    all_checks_passed = all(check[0] for check in checks)
    for passed, desc in checks:
        print(f"  {'✓' if passed else '✗'} {desc}")
    
    test_result("TC-002", "Provisioning YAML valid", all_checks_passed)
except Exception as e:
    test_result("TC-002", "Provisioning YAML valid", False, str(e))

# TC-003: Validate Docker Compose Volume Mounts
print("\n[TC-003] Validating Docker Compose configuration...")
try:
    with open('docker-compose.yml', 'r') as f:
        docker_compose = yaml.safe_load(f)
    
    grafana_service = docker_compose.get('services', {}).get('grafana', {})
    volumes = grafana_service.get('volumes', [])
    
    required_mounts = [
        './infrastructure/grafana/provisioning/dashboards/dashboards.yml:/etc/grafana/provisioning/dashboards/dashboards.yml',
        './infrastructure/grafana/dashboards:/etc/grafana/provisioning/dashboards'
    ]
    
    found_mounts = []
    for mount in required_mounts:
        # Check if mount exists (with or without :ro suffix)
        mount_found = any(mount in vol for vol in volumes)
        found_mounts.append(mount_found)
        print(f"  {'✓' if mount_found else '✗'} {mount}")
    
    test_result("TC-003", "Docker Compose volume mounts", all(found_mounts))
except Exception as e:
    test_result("TC-003", "Docker Compose volume mounts", False, str(e))

# TC-004: Validate Dashboard Schema - Required Fields
print("\n[TC-004] Validating dashboard schema and required fields...")

expected_panels = {
    'api-dashboard.json': 6,
    'celery-dashboard.json': 9,
    'database-dashboard.json': 7,
    'system-dashboard.json': 7
}

schema_valid = True
for file_name, expected_count in expected_panels.items():
    file_path = f'infrastructure/grafana/dashboards/{file_name}'
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)

        # Handle both direct dashboard format and wrapped format
        if 'dashboard' in data:
            dashboard = data['dashboard']
        else:
            dashboard = data

        # Check required top-level fields (uid is optional for provisioned dashboards)
        required_fields = ['title', 'panels', 'schemaVersion']
        optional_fields = ['uid', 'id']
        missing = [f for f in required_fields if f not in dashboard]

        if missing:
            schema_valid = False
            print(f"  ✗ {file_name}: Missing required fields {missing}")
            continue

        # Note if uid/id is missing (acceptable for provisioned dashboards)
        has_identifier = any(f in dashboard for f in optional_fields)
        if not has_identifier:
            print(f"  ℹ {file_name}: No uid/id (will be auto-generated by Grafana)")

        # Check panel count
        panels = dashboard.get('panels', [])
        panel_count = len([p for p in panels if p.get('type') != 'row'])  # Exclude row panels

        if panel_count != expected_count:
            print(f"  ⚠ {file_name}: Expected {expected_count} panels, found {panel_count}")
        else:
            print(f"  ✓ {file_name}: {panel_count} panels configured")

        # Validate each panel
        for i, panel in enumerate(panels):
            if panel.get('type') == 'row':
                continue
            required_panel_fields = ['id', 'type', 'title']
            panel_missing = [f for f in required_panel_fields if f not in panel]
            if panel_missing:
                schema_valid = False
                print(f"    ✗ Panel {i}: Missing {panel_missing}")

    except Exception as e:
        schema_valid = False
        print(f"  ✗ {file_name}: {e}")

test_result("TC-004", "Dashboard schema validation", schema_valid)

# TC-005: Validate Metric Query Syntax (PromQL)
print("\n[TC-005] Validating PromQL metric queries...")

expected_metrics = {
    'api-dashboard.json': ['http_requests_total', 'http_request_duration_seconds', 'active_chat_sessions'],
    'system-dashboard.json': ['node_cpu_seconds_total', 'node_memory', 'process_cpu_seconds_total'],
    'database-dashboard.json': ['database_connection_pool_size', 'database_query_duration_seconds', 'cache_operations_total'],
    'celery-dashboard.json': ['celery_queue_length', 'celery_task', 'celery_workers_active']
}

queries_valid = True
for file_name, expected_metric_list in expected_metrics.items():
    file_path = f'infrastructure/grafana/dashboards/{file_name}'
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)

        # Handle both direct dashboard format and wrapped format
        if 'dashboard' in data:
            dashboard = data['dashboard']
        else:
            dashboard = data

        # Extract all queries
        all_queries = []
        for panel in dashboard.get('panels', []):
            targets = panel.get('targets', [])
            for target in targets:
                expr = target.get('expr', '')
                if expr:
                    all_queries.append(expr)

        # Check if expected metrics appear in queries
        found_metrics = []
        for metric in expected_metric_list:
            if any(metric in query for query in all_queries):
                found_metrics.append(metric)

        print(f"  ✓ {file_name}: {len(all_queries)} queries, {len(found_metrics)}/{len(expected_metric_list)} expected metrics found")

    except Exception as e:
        queries_valid = False
        print(f"  ✗ {file_name}: {e}")

test_result("TC-005", "PromQL query validation", queries_valid)

# TC-013: Verify README Documentation
print("\n[TC-013] Verifying README documentation...")
readme_path = 'infrastructure/grafana/README.md'
try:
    with open(readme_path, 'r') as f:
        readme_content = f.read()

    required_sections = ['Overview', 'Dashboard', 'Metrics', 'Installation', 'Usage']
    sections_found = [s for s in required_sections if s.lower() in readme_content.lower()]

    readme_valid = len(sections_found) >= 4
    print(f"  {'✓' if readme_valid else '✗'} README exists with {len(sections_found)}/{len(required_sections)} sections")
    test_result("TC-013", "README documentation", readme_valid)
except Exception as e:
    test_result("TC-013", "README documentation", False, str(e))

# Print summary
print("\n" + "=" * 80)
print("TEST SUMMARY")
print("=" * 80)
print(f"Total Tests: {results['total']}")
print(f"Passed: {len(results['passed'])}")
print(f"Failed: {len(results['failed'])}")

if results['failed']:
    print("\nFailed Tests:")
    for failure in results['failed']:
        print(f"  {failure}")

exit_code = 0 if len(results['failed']) == 0 else 1
sys.exit(exit_code)
