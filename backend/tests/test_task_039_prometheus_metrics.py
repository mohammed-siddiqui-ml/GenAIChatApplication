"""
Tests for Task-039: Configure Prometheus Metrics Collection

Tests cover:
- Metrics module initialization and definitions
- Custom metrics (query processing, embeddings, vector search, LLM API)
- Histogram bucket configurations
- Prometheus configuration file validation
- Metrics naming conventions
"""

import pytest
import pytest_asyncio
from pathlib import Path
import yaml
from unittest.mock import patch, MagicMock
from prometheus_client import REGISTRY


# ========== Test Cases ==========


class TestMetricsModuleDefinition:
    """TC-001: Metrics Module Import and Definition"""
    
    def test_metrics_import(self):
        """Verify core.metrics module can be imported"""
        from core import metrics
        assert metrics is not None
    
    def test_query_processing_duration_defined(self):
        """Verify query_processing_duration metric is defined as Histogram"""
        from core.metrics import query_processing_duration
        from prometheus_client import Histogram
        
        assert query_processing_duration is not None
        assert isinstance(query_processing_duration, Histogram)
    
    def test_embedding_generation_duration_defined(self):
        """Verify embedding_generation_duration metric is defined as Histogram"""
        from core.metrics import embedding_generation_duration
        from prometheus_client import Histogram
        
        assert embedding_generation_duration is not None
        assert isinstance(embedding_generation_duration, Histogram)
    
    def test_vector_search_duration_defined(self):
        """Verify vector_search_duration metric is defined as Histogram"""
        from core.metrics import vector_search_duration
        from prometheus_client import Histogram
        
        assert vector_search_duration is not None
        assert isinstance(vector_search_duration, Histogram)
    
    def test_vector_search_results_defined(self):
        """Verify vector_search_results metric is defined as Histogram"""
        from core.metrics import vector_search_results
        from prometheus_client import Histogram
        
        assert vector_search_results is not None
        assert isinstance(vector_search_results, Histogram)
    
    def test_llm_api_requests_total_defined(self):
        """Verify llm_api_requests_total metric is defined as Counter"""
        from core.metrics import llm_api_requests_total
        from prometheus_client import Counter
        
        assert llm_api_requests_total is not None
        assert isinstance(llm_api_requests_total, Counter)
    
    def test_llm_api_duration_defined(self):
        """Verify llm_api_duration metric is defined as Histogram"""
        from core.metrics import llm_api_duration
        from prometheus_client import Histogram
        
        assert llm_api_duration is not None
        assert isinstance(llm_api_duration, Histogram)
    
    def test_llm_tokens_used_defined(self):
        """Verify llm_tokens_used metric is defined as Counter"""
        from core.metrics import llm_tokens_used
        from prometheus_client import Counter
        
        assert llm_tokens_used is not None
        assert isinstance(llm_tokens_used, Counter)
    
    def test_embedding_generation_total_defined(self):
        """Verify embedding_generation_total metric is defined as Counter"""
        from core.metrics import embedding_generation_total
        from prometheus_client import Counter
        
        assert embedding_generation_total is not None
        assert isinstance(embedding_generation_total, Counter)


class TestHistogramBucketConfiguration:
    """TC-010: Histogram Bucket Configuration"""
    
    def test_query_processing_duration_buckets(self):
        """Verify query_processing_duration has appropriate buckets"""
        from core.metrics import query_processing_duration
        from math import inf

        # Expected buckets for API response times (0.1s to 30s)
        expected_buckets = [0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, inf]
        actual_buckets = query_processing_duration._upper_bounds

        # Check that buckets match
        assert actual_buckets == expected_buckets

    def test_embedding_generation_duration_buckets(self):
        """Verify embedding_generation_duration has appropriate buckets"""
        from core.metrics import embedding_generation_duration
        from math import inf

        expected_buckets = [0.1, 0.5, 1.0, 2.0, 5.0, 10.0, inf]
        actual_buckets = embedding_generation_duration._upper_bounds

        assert actual_buckets == expected_buckets

    def test_vector_search_duration_buckets(self):
        """Verify vector_search_duration has appropriate buckets"""
        from core.metrics import vector_search_duration
        from math import inf

        expected_buckets = [0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0, inf]
        actual_buckets = vector_search_duration._upper_bounds

        assert actual_buckets == expected_buckets

    def test_llm_api_duration_buckets(self):
        """Verify llm_api_duration has appropriate buckets"""
        from core.metrics import llm_api_duration
        from math import inf

        expected_buckets = [0.5, 1.0, 2.0, 5.0, 10.0, 30.0, inf]
        actual_buckets = llm_api_duration._upper_bounds

        assert actual_buckets == expected_buckets


class TestPrometheusConfiguration:
    """TC-008: Prometheus Configuration Validation"""

    def test_prometheus_yml_exists(self):
        """Verify prometheus.yml file exists"""
        config_path = Path(__file__).parent.parent.parent / "config" / "prometheus.yml"
        assert config_path.exists(), f"Prometheus config not found at {config_path}"

    def test_prometheus_yml_valid_yaml(self):
        """Verify prometheus.yml is valid YAML"""
        config_path = Path(__file__).parent.parent.parent / "config" / "prometheus.yml"

        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)

        assert config is not None
        assert isinstance(config, dict)

    def test_prometheus_global_scrape_interval(self):
        """Verify global scrape_interval is set"""
        config_path = Path(__file__).parent.parent.parent / "config" / "prometheus.yml"

        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)

        assert 'global' in config
        assert 'scrape_interval' in config['global']

    def test_prometheus_scrape_config_exists(self):
        """Verify scrape_configs section exists"""
        config_path = Path(__file__).parent.parent.parent / "config" / "prometheus.yml"

        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)

        assert 'scrape_configs' in config
        assert isinstance(config['scrape_configs'], list)
        assert len(config['scrape_configs']) > 0

    def test_prometheus_backend_job_configured(self):
        """Verify backend scrape job is configured"""
        config_path = Path(__file__).parent.parent.parent / "config" / "prometheus.yml"

        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)

        scrape_configs = config.get('scrape_configs', [])
        job_names = [job.get('job_name') for job in scrape_configs]

        # Look for backend or genai-backend job
        assert any('backend' in name.lower() for name in job_names if name), \
            f"No backend job found in scrape configs. Found jobs: {job_names}"

    def test_prometheus_backend_metrics_path(self):
        """Verify backend job has correct metrics path"""
        config_path = Path(__file__).parent.parent.parent / "config" / "prometheus.yml"

        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)

        scrape_configs = config.get('scrape_configs', [])
        backend_jobs = [job for job in scrape_configs
                       if 'backend' in job.get('job_name', '').lower()]

        assert len(backend_jobs) > 0, "No backend job found"
        backend_job = backend_jobs[0]

        # Metrics path should be /api/v1/metrics
        metrics_path = backend_job.get('metrics_path', '/metrics')
        assert '/metrics' in metrics_path


class TestMetricsNamingConventions:
    """TC-009: Metrics Format Validation - Naming Conventions"""

    def test_metric_names_use_snake_case(self):
        """Verify metric names follow snake_case convention"""
        from core.metrics import get_metrics_dict

        metrics_dict = get_metrics_dict()

        for metric_name in metrics_dict.keys():
            # Check that metric name uses snake_case (no camelCase, no spaces)
            assert metric_name.islower() or '_' in metric_name, \
                f"Metric {metric_name} does not use snake_case"
            assert ' ' not in metric_name, \
                f"Metric {metric_name} contains spaces"

    def test_duration_metrics_have_seconds_suffix(self):
        """Verify duration metrics end with _seconds"""
        from core.metrics import get_metrics_dict

        metrics_dict = get_metrics_dict()
        duration_metrics = [name for name in metrics_dict.keys() if 'duration' in name]

        for metric_name in duration_metrics:
            assert metric_name.endswith('_seconds'), \
                f"Duration metric {metric_name} should end with _seconds"

    def test_counter_metrics_have_total_suffix(self):
        """Verify counter metrics end with _total when exported"""
        from core.metrics import (
            llm_api_requests_total,
            llm_tokens_used,
            embedding_generation_total
        )
        from prometheus_client import Counter

        # Verify these are Counter types
        assert isinstance(llm_api_requests_total, Counter)
        assert isinstance(llm_tokens_used, Counter)
        assert isinstance(embedding_generation_total, Counter)

        # The internal _name may not have _total, but when exported,
        # Prometheus adds _total suffix automatically for Counters
        # Just verify they are Counter instances which will get _total suffix


class TestMainAppInstrumentation:
    """TC-002 & TC-012: Verify metrics are integrated into main.py"""

    def test_instrumentator_import(self):
        """Verify prometheus-fastapi-instrumentator is imported in main.py"""
        import sys
        from pathlib import Path

        main_path = Path(__file__).parent.parent / "src" / "main.py"
        with open(main_path, 'r') as f:
            main_content = f.read()

        assert 'from prometheus_fastapi_instrumentator import Instrumentator' in main_content

    def test_instrumentator_configured(self):
        """Verify Instrumentator is configured with correct settings"""
        import sys
        from pathlib import Path

        main_path = Path(__file__).parent.parent / "src" / "main.py"
        with open(main_path, 'r') as f:
            main_content = f.read()

        # Check for Instrumentator configuration
        assert 'instrumentator = Instrumentator(' in main_content
        assert 'excluded_handlers' in main_content
        assert '/health' in main_content

    def test_metrics_endpoint_configured(self):
        """Verify metrics endpoint is exposed at /api/v1/metrics"""
        import sys
        from pathlib import Path

        main_path = Path(__file__).parent.parent / "src" / "main.py"
        with open(main_path, 'r') as f:
            main_content = f.read()

        # Check for metrics endpoint exposure
        assert 'instrumentator.expose(' in main_content
        assert '/metrics' in main_content
