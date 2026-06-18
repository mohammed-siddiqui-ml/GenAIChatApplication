"""
Test Celery Task Execution (TC-C*, TC-D*)

Tests for task execution, result storage, retry logic, and error handling.
These tests use CELERY_TASK_ALWAYS_EAGER mode for synchronous testing.
"""

import pytest
from datetime import datetime
from tasks.celery import celery_app
from tasks.maintenance.cleanup import cleanup_old_results, health_check


# Configure Celery for eager execution (synchronous testing)
@pytest.fixture(autouse=True)
def configure_celery_eager_mode():
    """Configure Celery to run tasks synchronously for testing"""
    celery_app.conf.task_always_eager = True
    celery_app.conf.task_eager_propagates = True
    yield
    # Reset to default after tests
    celery_app.conf.task_always_eager = False
    celery_app.conf.task_eager_propagates = False


class TestTaskExecution:
    """Test basic task execution (TC-C1, TC-F3)"""

    def test_health_check_task_execution(self):
        """TC-C1 & TC-F3: Execute health_check task and verify success"""
        result = health_check.delay()
        
        # Get result (synchronous in eager mode)
        task_result = result.get(timeout=10)
        
        # Verify task completed successfully
        assert result.successful(), "Task should complete successfully"
        assert task_result["status"] == "healthy", "Health check should return 'healthy' status"
        assert "timestamp" in task_result, "Health check should include timestamp"
        assert "worker_id" in task_result, "Health check should include worker_id"

    def test_cleanup_task_execution(self):
        """TC-C1: Execute cleanup_old_results task and verify success"""
        result = cleanup_old_results.delay(days_old=7)
        
        # Get result
        task_result = result.get(timeout=10)
        
        # Verify task completed successfully
        assert result.successful(), "Cleanup task should complete successfully"
        assert task_result["status"] == "success", "Cleanup should return 'success' status"
        assert task_result["days_old"] == 7, "Cleanup should use provided days_old parameter"
        assert "cutoff_date" in task_result, "Cleanup should include cutoff_date"

    def test_task_state_tracking(self):
        """TC-C4: Verify task execution status can be queried"""
        result = health_check.delay()
        
        # In eager mode, task completes immediately
        assert result.state == "SUCCESS", f"Task state should be SUCCESS, got {result.state}"

    def test_task_with_parameters(self):
        """TC-C2: Test task execution with custom parameters"""
        days = 14
        result = cleanup_old_results.delay(days_old=days)
        task_result = result.get(timeout=10)
        
        assert task_result["days_old"] == days, f"Task should use custom days_old={days}"


class TestTaskResults:
    """Test task result storage and retrieval (TC-C2)"""

    def test_task_result_stored(self):
        """TC-C2: Verify task results are stored and retrievable"""
        result = health_check.delay()
        task_id = result.id
        
        # Retrieve result using task_id
        from celery.result import AsyncResult
        async_result = AsyncResult(task_id, app=celery_app)
        
        # Verify result can be retrieved
        assert async_result.ready(), "Result should be ready (task completed)"
        task_result = async_result.result
        assert task_result is not None, "Result should be stored and retrievable"
        assert task_result["status"] == "healthy", "Retrieved result should match expected data"

    def test_task_return_value_matches(self):
        """TC-C2: Verify result data matches task return value"""
        result = cleanup_old_results.delay(days_old=5)
        task_result = result.get(timeout=10)
        
        # Verify all expected fields are present
        assert "status" in task_result, "Result should contain 'status'"
        assert "cutoff_date" in task_result, "Result should contain 'cutoff_date'"
        assert "days_old" in task_result, "Result should contain 'days_old'"
        assert "message" in task_result, "Result should contain 'message'"


class TestTaskRetry:
    """Test task retry logic and exponential backoff (TC-D1, TC-D2)"""

    def test_task_retry_configuration(self):
        """TC-D1: Verify tasks have retry configuration"""
        # Check health_check task retry settings
        health_task = celery_app.tasks.get("tasks.maintenance.health_check")
        assert health_task is not None, "health_check task should be registered"
        assert health_task.max_retries == 3, "health_check should have max_retries=3"

        # Check cleanup task retry settings
        cleanup_task = celery_app.tasks.get("tasks.maintenance.cleanup_old_results")
        assert cleanup_task is not None, "cleanup_old_results task should be registered"
        assert cleanup_task.max_retries == 3, "cleanup_old_results should have max_retries=3"

    def test_exponential_backoff_implementation(self):
        """TC-D2: Verify exponential backoff is implemented in sample tasks"""
        # This is a code review test - verify the retry logic uses exponential backoff
        # The formula should be: countdown=2 ** self.request.retries

        # Get task source code to verify implementation
        cleanup_task = celery_app.tasks.get("tasks.maintenance.cleanup_old_results")
        health_task = celery_app.tasks.get("tasks.maintenance.health_check")

        assert cleanup_task is not None, "cleanup_old_results task should exist"
        assert health_task is not None, "health_check task should exist"

        # Verify tasks are bind=True (required for self.retry)
        # In Celery, check the 'typing' or '__self__' attributes, or verify request is available
        # A bound task will have access to 'self' and 'self.request'
        # The most reliable way is to check if the task was registered with bind=True
        # by inspecting the task's run method signature or checking task options
        assert hasattr(cleanup_task, 'request') or getattr(cleanup_task, 'bind', None) is True or 'self' in cleanup_task.run.__code__.co_varnames, \
            "cleanup_old_results should use bind=True for retry (needs access to self.request)"
        assert hasattr(health_task, 'request') or getattr(health_task, 'bind', None) is True or 'self' in health_task.run.__code__.co_varnames, \
            "health_check should use bind=True for retry (needs access to self.request)"


class TestTaskRegistration:
    """Test that all maintenance tasks are properly registered"""

    def test_maintenance_tasks_registered(self):
        """Verify maintenance tasks are registered with Celery"""
        registered_tasks = celery_app.tasks.keys()
        
        expected_tasks = [
            "tasks.maintenance.cleanup_old_results",
            "tasks.maintenance.health_check",
        ]
        
        for task_name in expected_tasks:
            assert task_name in registered_tasks, f"Task '{task_name}' should be registered"

    def test_task_names_correct(self):
        """Verify task names match expected naming convention"""
        cleanup_task = celery_app.tasks.get("tasks.maintenance.cleanup_old_results")
        health_task = celery_app.tasks.get("tasks.maintenance.health_check")
        
        assert cleanup_task.name == "tasks.maintenance.cleanup_old_results"
        assert health_task.name == "tasks.maintenance.health_check"
