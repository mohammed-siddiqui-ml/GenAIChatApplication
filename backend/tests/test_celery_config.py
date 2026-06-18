"""
Test Celery Configuration (TC-A*, TC-B*, TC-E*)

Tests for Celery app initialization, broker/backend URLs, task queues,
routing configuration, and beat schedule.
"""

import pytest
from tasks.celery import celery_app


class TestCeleryConfiguration:
    """Test Celery app configuration settings (TC-A1, TC-A2)"""

    def test_broker_url_configured(self):
        """TC-A1: Verify Celery broker URL is configured correctly"""
        broker_url = celery_app.conf.broker_url
        assert broker_url is not None, "Broker URL is not configured"
        assert "redis://" in broker_url, "Broker URL should use Redis protocol"
        # Verify it uses database 1
        assert "/1" in broker_url or broker_url.endswith("/1"), "Broker should use Redis database 1"

    def test_result_backend_configured(self):
        """TC-A2: Verify Celery result backend URL is configured correctly"""
        result_backend = celery_app.conf.result_backend
        assert result_backend is not None, "Result backend is not configured"
        assert "redis://" in result_backend, "Result backend should use Redis protocol"
        # Verify it uses database 2
        assert "/2" in result_backend or result_backend.endswith("/2"), "Result backend should use Redis database 2"

    def test_broker_and_backend_different(self):
        """Verify broker and result backend use different Redis databases"""
        broker_url = celery_app.conf.broker_url
        result_backend = celery_app.conf.result_backend
        # Extract database numbers
        broker_db = broker_url.split("/")[-1]
        backend_db = result_backend.split("/")[-1]
        assert broker_db != backend_db, "Broker and result backend should use different databases"


class TestTaskQueues:
    """Test task queue configuration (TC-B1)"""

    def test_task_queues_configured(self):
        """TC-B1: Verify all four task queues are configured"""
        queues = celery_app.conf.task_queues
        queue_names = [q.name for q in queues]
        
        expected_queues = ["default", "confluence_queue", "jira_queue", "embeddings_queue"]
        for expected_queue in expected_queues:
            assert expected_queue in queue_names, f"Queue '{expected_queue}' not configured"

    def test_default_queue_configured(self):
        """Verify default queue is set correctly"""
        assert celery_app.conf.task_default_queue == "default", "Default queue should be 'default'"


class TestTaskRouting:
    """Test task routing configuration (TC-B2, TC-B3, TC-B4)"""

    def test_confluence_task_routing(self):
        """TC-B2: Verify Confluence tasks route to confluence_queue"""
        routes = celery_app.conf.task_routes
        confluence_route = routes.get("tasks.ingestion.confluence.*")
        
        assert confluence_route is not None, "Confluence routing not configured"
        assert confluence_route["queue"] == "confluence_queue", "Confluence tasks should route to confluence_queue"

    def test_jira_task_routing(self):
        """TC-B3: Verify Jira tasks route to jira_queue"""
        routes = celery_app.conf.task_routes
        jira_route = routes.get("tasks.ingestion.jira.*")
        
        assert jira_route is not None, "Jira routing not configured"
        assert jira_route["queue"] == "jira_queue", "Jira tasks should route to jira_queue"

    def test_embeddings_task_routing(self):
        """TC-B4: Verify embeddings tasks route to embeddings_queue"""
        routes = celery_app.conf.task_routes
        embeddings_route = routes.get("tasks.embeddings.*")
        
        assert embeddings_route is not None, "Embeddings routing not configured"
        assert embeddings_route["queue"] == "embeddings_queue", "Embeddings tasks should route to embeddings_queue"

    def test_onboarding_task_routing(self):
        """TC-B5: Verify onboarding tasks route to default queue"""
        routes = celery_app.conf.task_routes
        onboarding_route = routes.get("tasks.ingestion.onboarding.*")
        
        assert onboarding_route is not None, "Onboarding routing not configured"
        assert onboarding_route["queue"] == "default", "Onboarding tasks should route to default queue"


class TestTaskSettings:
    """Test task configuration settings (TC-C3, TC-D1)"""

    def test_result_expiration(self):
        """TC-C3: Verify task results expire after 24 hours"""
        result_expires = celery_app.conf.result_expires
        assert result_expires == 86400, f"Result expiration should be 86400 seconds (24 hours), got {result_expires}"

    def test_max_retries_configured(self):
        """TC-D1: Verify max retries is set to 3"""
        max_retries = celery_app.conf.task_max_retries
        assert max_retries == 3, f"Max retries should be 3, got {max_retries}"


class TestBeatSchedule:
    """Test Celery Beat periodic task schedule (TC-E1, TC-E2)"""

    def test_beat_schedule_configured(self):
        """TC-E1: Verify Celery Beat schedule contains periodic tasks"""
        beat_schedule = celery_app.conf.beat_schedule
        
        expected_tasks = [
            "refresh-confluence-data",
            "refresh-jira-data",
            "cleanup-task-results"
        ]
        
        for task_name in expected_tasks:
            assert task_name in beat_schedule, f"Periodic task '{task_name}' not in beat schedule"

    def test_confluence_refresh_schedule(self):
        """TC-E2: Verify Confluence refresh runs daily at 2:00 AM UTC"""
        beat_schedule = celery_app.conf.beat_schedule
        confluence_task = beat_schedule.get("refresh-confluence-data")
        
        assert confluence_task is not None, "Confluence refresh task not scheduled"
        schedule = confluence_task["schedule"]
        # Check it's a crontab schedule with hour=2, minute=0
        assert hasattr(schedule, "hour"), "Schedule should be a crontab"
        assert schedule.hour == {2}, f"Confluence refresh should run at hour 2, got {schedule.hour}"
        assert schedule.minute == {0}, f"Confluence refresh should run at minute 0, got {schedule.minute}"

    def test_jira_refresh_schedule(self):
        """TC-E2: Verify Jira refresh runs daily at 2:30 AM UTC"""
        beat_schedule = celery_app.conf.beat_schedule
        jira_task = beat_schedule.get("refresh-jira-data")
        
        assert jira_task is not None, "Jira refresh task not scheduled"
        schedule = jira_task["schedule"]
        assert schedule.hour == {2}, f"Jira refresh should run at hour 2, got {schedule.hour}"
        assert schedule.minute == {30}, f"Jira refresh should run at minute 30, got {schedule.minute}"
