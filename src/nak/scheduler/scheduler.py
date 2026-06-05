import asyncio
from dataclasses import dataclass, field
from typing import List, Dict, Callable, Any, Coroutine

@dataclass
class Task:
    id: str
    kind: str
    depends_on: List[str]
    action: Callable[[], Coroutine[Any, Any, "TaskResult"]]
    read_paths: List[str] = field(default_factory=list)
    write_paths: List[str] = field(default_factory=list)

@dataclass
class TaskResult:
    success: bool
    output: Any | None
    error_message: str | None

class Scheduler:
    def __init__(self, parallel_non_model_tasks: int = 8, parallel_model_tasks: int = 1) -> None:
        self.non_model_sem = asyncio.Semaphore(parallel_non_model_tasks)
        self.model_sem = asyncio.Semaphore(parallel_model_tasks)

    async def run(self, tasks: List[Task]) -> Dict[str, TaskResult]:
        loop = asyncio.get_running_loop()
        futures: Dict[str, asyncio.Future[TaskResult]] = {task.id: loop.create_future() for task in tasks}
        
        async def execute_task(task: Task) -> None:
            # Wait for all dependencies
            for dep_id in task.depends_on:
                if dep_id not in futures:
                    futures[task.id].set_result(
                        TaskResult(success=False, output=None, error_message=f"Unknown dependency '{dep_id}'")
                    )
                    return
                
                dep_result = await futures[dep_id]
                if not dep_result.success:
                    futures[task.id].set_result(
                        TaskResult(success=False, output=None, error_message=f"Skipped because dependency '{dep_id}' failed.")
                    )
                    return

            # Enforce concurrency bounds
            sem = self.model_sem if task.kind == "model" else self.non_model_sem
            async with sem:
                try:
                    res = await task.action()
                    futures[task.id].set_result(res)
                except Exception as e:
                    futures[task.id].set_result(
                        TaskResult(success=False, output=None, error_message=f"Exception: {str(e)}")
                    )

        # Run all execute_task coroutines concurrently in a TaskGroup
        async with asyncio.TaskGroup() as tg:
            for task in tasks:
                tg.create_task(execute_task(task))

        # Build results map
        return {task_id: fut.result() for task_id, fut in futures.items()}
