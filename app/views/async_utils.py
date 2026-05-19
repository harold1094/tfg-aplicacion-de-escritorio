"""Helpers para ejecutar tareas en background en Qt."""

from __future__ import annotations

from typing import Any, Callable

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal


class TaskSignals(QObject):
    finished = Signal(object)
    failed = Signal(str)


class BackgroundTask(QRunnable):
    def __init__(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = TaskSignals()

    def run(self) -> None:
        try:
            result = self.fn(*self.args, **self.kwargs)
        except Exception as exc:  # pragma: no cover - Qt thread callback
            self.signals.failed.emit(str(exc))
            return
        self.signals.finished.emit(result)


class BackgroundRunner:
    def __init__(self) -> None:
        self.pool = QThreadPool.globalInstance()

    def submit(
        self,
        fn: Callable[..., Any],
        *args: Any,
        on_success: Callable[[Any], None] | None = None,
        on_error: Callable[[str], None] | None = None,
        **kwargs: Any,
    ) -> None:
        task = BackgroundTask(fn, *args, **kwargs)
        if on_success is not None:
            task.signals.finished.connect(on_success)
        if on_error is not None:
            task.signals.failed.connect(on_error)
        self.pool.start(task)
