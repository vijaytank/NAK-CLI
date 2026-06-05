import asyncio
import pytest
from nak.scheduler.scheduler import Scheduler, Task, TaskResult

@pytest.mark.asyncio
async def test_scheduler_dag_execution_order():
    # Setup a simple graph:
    # t1 (no deps) -> t2 (depends on t1)
    # t3 (no deps)
    # t4 (depends on t2 and t3)
    
    execution_order = []
    
    async def run_task(task_id, delay=0.01):
        await asyncio.sleep(delay)
        execution_order.append(task_id)
        return TaskResult(success=True, output=f"result-{task_id}", error_message=None)
        
    tasks = [
        Task(id="t1", kind="read", depends_on=[], action=lambda: run_task("t1")),
        Task(id="t2", kind="read", depends_on=["t1"], action=lambda: run_task("t2")),
        Task(id="t3", kind="read", depends_on=[], action=lambda: run_task("t3")),
        Task(id="t4", kind="read", depends_on=["t2", "t3"], action=lambda: run_task("t4")),
    ]
    
    scheduler = Scheduler(parallel_non_model_tasks=4, parallel_model_tasks=1)
    results = await scheduler.run(tasks)
    
    # Verify all succeeded
    assert all(r.success for r in results.values())
    
    # Verify dependency constraints
    t1_idx = execution_order.index("t1")
    t2_idx = execution_order.index("t2")
    t3_idx = execution_order.index("t3")
    t4_idx = execution_order.index("t4")
    
    assert t1_idx < t2_idx
    assert t2_idx < t4_idx
    assert t3_idx < t4_idx

@pytest.mark.asyncio
async def test_scheduler_one_model_hot_enforced():
    # Enforces that only 1 model task executes at any given time
    active_model_tasks = 0
    max_concurrent_model_tasks = 0
    lock = asyncio.Lock()
    
    async def run_model_task(task_id):
        nonlocal active_model_tasks, max_concurrent_model_tasks
        async with lock:
            active_model_tasks += 1
            max_concurrent_model_tasks = max(max_concurrent_model_tasks, active_model_tasks)
        await asyncio.sleep(0.02)
        async with lock:
            active_model_tasks -= 1
        return TaskResult(success=True, output=f"result-{task_id}", error_message=None)
        
    tasks = [
        Task(id="m1", kind="model", depends_on=[], action=lambda: run_model_task("m1")),
        Task(id="m2", kind="model", depends_on=[], action=lambda: run_model_task("m2")),
        Task(id="m3", kind="model", depends_on=[], action=lambda: run_model_task("m3")),
    ]
    
    scheduler = Scheduler(parallel_non_model_tasks=4, parallel_model_tasks=1)
    await scheduler.run(tasks)
    
    # Since parallel_model_tasks=1, max concurrent model tasks should be exactly 1
    assert max_concurrent_model_tasks == 1

@pytest.mark.asyncio
async def test_scheduler_skips_dependents_on_failure():
    execution_calls = []
    
    async def success_action(task_id):
        execution_calls.append(task_id)
        return TaskResult(success=True, output="ok", error_message=None)
        
    async def fail_action(task_id):
        execution_calls.append(task_id)
        return TaskResult(success=False, output=None, error_message="failed task")
        
    tasks = [
        Task(id="t1", kind="read", depends_on=[], action=lambda: fail_action("t1")),
        Task(id="t2", kind="read", depends_on=["t1"], action=lambda: success_action("t2")),
    ]
    
    scheduler = Scheduler(parallel_non_model_tasks=4, parallel_model_tasks=1)
    results = await scheduler.run(tasks)
    
    assert results["t1"].success is False
    # t2 should not have been executed, and should be marked as failed/skipped
    assert "t2" not in execution_calls
    assert results["t2"].success is False
    assert "skipped" in results["t2"].error_message.lower()
