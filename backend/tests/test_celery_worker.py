"""
Test Celery Worker and Broker Connectivity (TC-A3, TC-F*)

Tests for Redis broker connection, worker configuration, and health monitoring.
"""

import pytest
from tasks.celery import celery_app


class TestBrokerConnection:
    """Test Redis broker connectivity (TC-A3, TC-A4)"""

    def test_broker_connection(self):
        """TC-A3: Test Redis broker connection can be established"""
        # Get a broker connection
        with celery_app.connection() as conn:
            # Attempt to connect
            conn.ensure_connection(max_retries=3)
            
            # Verify connection is alive
            assert conn.connected, "Broker connection should be established"

    def test_result_backend_connection(self):
        """TC-A4: Test Redis result backend connection"""
        # Get result backend connection
        backend = celery_app.backend
        
        # Verify backend is configured
        assert backend is not None, "Result backend should be configured"
        
        # Backend type should be Redis
        backend_url = celery_app.conf.result_backend
        assert "redis" in backend_url.lower(), "Result backend should be Redis"


class TestWorkerConfiguration:
    """Test worker settings and configuration (TC-F1, TC-F2)"""

    def test_worker_prefetch_multiplier(self):
        """Verify worker prefetch multiplier is configured"""
        prefetch = celery_app.conf.worker_prefetch_multiplier
        assert prefetch == 4, f"Worker prefetch multiplier should be 4, got {prefetch}"

    def test_worker_max_tasks_per_child(self):
        """Verify worker max tasks per child is configured"""
        max_tasks = celery_app.conf.worker_max_tasks_per_child
        assert max_tasks == 1000, f"Worker max tasks per child should be 1000, got {max_tasks}"

    def test_task_acks_late_enabled(self):
        """Verify task acknowledgment is set to late (after completion)"""
        acks_late = celery_app.conf.task_acks_late
        assert acks_late is True, "task_acks_late should be enabled"

    def test_task_reject_on_worker_lost(self):
        """Verify tasks are rejected if worker dies"""
        reject_on_lost = celery_app.conf.task_reject_on_worker_lost
        assert reject_on_lost is True, "task_reject_on_worker_lost should be enabled"


class TestMonitoringSettings:
    """Test monitoring and event configuration (TC-F4)"""

    def test_task_events_enabled(self):
        """TC-F4: Verify task events are enabled for monitoring"""
        task_events = celery_app.conf.worker_send_task_events
        assert task_events is True, "Worker task events should be enabled for monitoring"

    def test_task_sent_events_enabled(self):
        """Verify task-sent events are enabled"""
        sent_events = celery_app.conf.task_send_sent_event
        assert sent_events is True, "Task sent events should be enabled"

    def test_task_tracking_enabled(self):
        """Verify task start tracking is enabled"""
        track_started = celery_app.conf.task_track_started
        assert track_started is True, "Task start tracking should be enabled"


class TestSerializationSettings:
    """Test serialization configuration"""

    def test_task_serializer(self):
        """Verify task serializer is JSON"""
        serializer = celery_app.conf.task_serializer
        assert serializer == "json", f"Task serializer should be 'json', got {serializer}"

    def test_result_serializer(self):
        """Verify result serializer is JSON"""
        serializer = celery_app.conf.result_serializer
        assert serializer == "json", f"Result serializer should be 'json', got {serializer}"

    def test_accept_content(self):
        """Verify only JSON content is accepted"""
        accept_content = celery_app.conf.accept_content
        assert "json" in accept_content, "Should accept JSON content"
        assert len(accept_content) == 1, "Should only accept JSON for security"


class TestTimezoneSettings:
    """Test timezone configuration"""

    def test_timezone_utc(self):
        """Verify timezone is set to UTC"""
        timezone = celery_app.conf.timezone
        assert timezone == "UTC", f"Timezone should be 'UTC', got {timezone}"

    def test_enable_utc(self):
        """Verify UTC is enabled"""
        enable_utc = celery_app.conf.enable_utc
        assert enable_utc is True, "UTC should be enabled"


class TestTaskLimits:
    """Test task time limits"""

    def test_hard_time_limit(self):
        """Verify hard time limit is set (1 hour)"""
        hard_limit = celery_app.conf.task_time_limit
        assert hard_limit == 3600, f"Hard time limit should be 3600s (1 hour), got {hard_limit}"

    def test_soft_time_limit(self):
        """Verify soft time limit is set (50 minutes)"""
        soft_limit = celery_app.conf.task_soft_time_limit
        assert soft_limit == 3000, f"Soft time limit should be 3000s (50 min), got {soft_limit}"


class TestResultPersistence:
    """Test result storage configuration"""

    def test_result_persistent(self):
        """Verify results are persisted to backend"""
        persistent = celery_app.conf.result_persistent
        assert persistent is True, "Results should be persisted"

    def test_task_ignore_result(self):
        """Verify task results are stored (not ignored)"""
        ignore = celery_app.conf.task_ignore_result
        assert ignore is False, "Task results should be stored, not ignored"


class TestCeleryAppInitialization:
    """Test Celery app initialization"""

    def test_celery_app_name(self):
        """Verify Celery app has correct name"""
        app_name = celery_app.main
        assert app_name == "knowledge_retrieval_tasks", f"Celery app name should be 'knowledge_retrieval_tasks', got {app_name}"

    def test_celery_app_instance(self):
        """Verify celery_app is a Celery instance"""
        from celery import Celery
        assert isinstance(celery_app, Celery), "celery_app should be an instance of Celery"
