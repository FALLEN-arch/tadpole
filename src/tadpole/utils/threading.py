"""Threading utilities for background tasks."""
from __future__ import annotations

import queue
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any, Callable, Optional, TypeVar

T = TypeVar("T")


@dataclass
class BackgroundTask:
    """Represents a background task with result handling."""
    func: Callable[[], T]
    on_done: Optional[Callable[[T], None]] = None
    on_error: Optional[Callable[[Exception], None]] = None
    name: str = ""


class TaskQueue:
    """Thread-safe queue for running background tasks and delivering results to the main thread."""

    def __init__(self, max_workers: int = 4):
        self._queue: queue.Queue[BackgroundTask] = queue.Queue()
        self._result_queue: queue.Queue[Callable[[], None]] = queue.Queue()
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="tadpole")
        self._running = True
        self._worker_thread = threading.Thread(target=self._worker, daemon=True, name="task-queue")
        self._worker_thread.start()

    def _worker(self) -> None:
        while self._running:
            try:
                task = self._queue.get(timeout=0.1)
            except queue.Empty:
                continue

            try:
                result = task.func()
                if task.on_done:
                    self._result_queue.put(lambda: task.on_done(result))
            except Exception as e:
                if task.on_error:
                    self._result_queue.put(lambda: task.on_error(e))
            finally:
                self._queue.task_done()

    def submit(self, task: BackgroundTask) -> None:
        """Submit a task for background execution."""
        self._queue.put(task)

    def submit_simple(
        self,
        func: Callable[[], T],
        on_done: Optional[Callable[[T], None]] = None,
        on_error: Optional[Callable[[Exception], None]] = None,
        name: str = "",
    ) -> None:
        """Submit a simple function as a background task."""
        self.submit(BackgroundTask(func, on_done, on_error, name))

    def pump_results(self) -> int:
        """Process completed tasks. Returns number of tasks processed."""
        count = 0
        while True:
            try:
                callback = self._result_queue.get_nowait()
            except queue.Empty:
                break
            try:
                callback()
            except Exception:
                pass  # Errors in UI callbacks shouldn't crash the pump
            count += 1
        return count

    def shutdown(self, wait: bool = True) -> None:
        """Shutdown the task queue."""
        self._running = False
        self._executor.shutdown(wait=wait)


# Global task queue instance
_task_queue: Optional[TaskQueue] = None


def get_task_queue() -> TaskQueue:
    """Get or create the global task queue."""
    global _task_queue
    if _task_queue is None:
        _task_queue = TaskQueue()
    return _task_queue


def run_in_background(
    func: Callable[[], T],
    on_done: Optional[Callable[[T], None]] = None,
    on_error: Optional[Callable[[Exception], None]] = None,
    name: str = "",
) -> None:
    """Run a function in the background and call callbacks on the main thread."""
    get_task_queue().submit_simple(func, on_done, on_error, name)
