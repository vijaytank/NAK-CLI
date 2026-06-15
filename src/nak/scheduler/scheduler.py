import asyncio
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Callable, Any, Coroutine, Optional
from nak.core.errors import SchedulerError

class TaskStatus(Enum):
    """Represents the current state of a task in the execution graph."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"

@dataclass
class Task:
    """Represents a single execution unit within a task graph."""
    id: str
    kind: str
    depends_on: List[str]
    action: Callable[[], Coroutine[Any, Any, "TaskResult"]]
    read_paths: List[str] = field(default_factory=list)
    write_paths: List[str] = field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    progress_percentage: int = 0
    timeout_seconds: Optional[float] = None

@dataclass
class TaskResult:
    """The result of executing a Task."""
    success: bool
    output: Any | None
    error_message: str | None
    final_status: TaskStatus = TaskStatus.COMPLETED

class Scheduler:
    """Executes a directed acyclic graph (DAG) of Tasks concurrently with resource constraints."""
    def __init__(self, parallel_non_model_tasks: int = 8, parallel_model_tasks: int = 1) -> None:
        self.non_model_sem: asyncio.Semaphore = asyncio.Semaphore(parallel_non_model_tasks)
        self.model_sem: asyncio.Semaphore = asyncio.Semaphore(parallel_model_tasks)
        self.on_progress: Optional[Callable[[str, TaskStatus, int], None]] = None

    async def run(self, tasks: List[Task]) -> Dict[str, TaskResult]:
        """Runs the tasks in execution order, respecting dependencies and parallel limits."""
        loop = asyncio.get_running_loop()
        futures: Dict[str, asyncio.Future[TaskResult]] = {task.id: loop.create_future() for task in tasks}
        
        async def execute_task(task: Task) -> None:
            # Wait for all dependencies
            for dep_id in task.depends_on:
                if dep_id not in futures:
                    task.status = TaskStatus.FAILED
                    if self.on_progress:
                        self.on_progress(task.id, TaskStatus.FAILED, 0)
                    err = SchedulerError("missing_dependency", f"Unknown dependency '{dep_id}'")
                    futures[task.id].set_result(
                        TaskResult(success=False, output=None, error_message=str(err), final_status=TaskStatus.FAILED)
                    )
                    return
                
                dep_result = await futures[dep_id]
                if not dep_result.success:
                    task.status = TaskStatus.SKIPPED
                    if self.on_progress:
                        self.on_progress(task.id, TaskStatus.SKIPPED, 0)
                    futures[task.id].set_result(
                        TaskResult(
                            success=False,
                            output=None,
                            error_message=f"Skipped because dependency '{dep_id}' failed.",
                            final_status=TaskStatus.SKIPPED
                        )
                    )
                    return

            # Enforce concurrency bounds
            sem = self.model_sem if task.kind == "model" else self.non_model_sem
            async with sem:
                try:
                    task.status = TaskStatus.IN_PROGRESS
                    task.progress_percentage = 0
                    if self.on_progress:
                        self.on_progress(task.id, TaskStatus.IN_PROGRESS, 0)

                    if task.timeout_seconds is not None:
                        res = await asyncio.wait_for(task.action(), timeout=task.timeout_seconds)
                    else:
                        res = await task.action()

                    # Set final status on result and task based on success
                    if res.success:
                        task.status = TaskStatus.COMPLETED
                        task.progress_percentage = 100
                        res.final_status = TaskStatus.COMPLETED
                    else:
                        task.status = TaskStatus.FAILED
                        task.progress_percentage = 0
                        res.final_status = TaskStatus.FAILED

                    if self.on_progress:
                        self.on_progress(task.id, task.status, task.progress_percentage)

                    futures[task.id].set_result(res)
                except asyncio.TimeoutError:
                    task.status = TaskStatus.FAILED
                    task.progress_percentage = 0
                    if self.on_progress:
                        self.on_progress(task.id, TaskStatus.FAILED, 0)
                    err = SchedulerError("task_timeout", "Task execution timed out")
                    futures[task.id].set_result(
                        TaskResult(success=False, output=None, error_message=str(err), final_status=TaskStatus.FAILED)
                    )
                except Exception as e:
                    task.status = TaskStatus.FAILED
                    task.progress_percentage = 0
                    if self.on_progress:
                        self.on_progress(task.id, TaskStatus.FAILED, 0)
                    err = SchedulerError("task_exception", f"Exception: {str(e)}")
                    futures[task.id].set_result(
                        TaskResult(success=False, output=None, error_message=str(err), final_status=TaskStatus.FAILED)
                    )

        # Run all execute_task coroutines concurrently in a TaskGroup
        async with asyncio.TaskGroup() as tg:
            for task in tasks:
                tg.create_task(execute_task(task))

        # Build results map
        return {task_id: fut.result() for task_id, fut in futures.items()}
