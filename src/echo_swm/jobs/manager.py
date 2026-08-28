from __future__ import annotations

import json
import threading
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from echo_swm.core.ids import new_id
from echo_swm.jobs.contracts import JobDecisionPreview, JobKind, JobRecord

MODEL_VERSION = "interactive-job-orchestrator-v1"
DATA_VERSION = "job-metadata-v1"


class ProgressReporter(Protocol):
    def __call__(
        self,
        progress: int,
        stage: str,
        processed_agents: int,
        latest_trace: str,
        details: dict[str, Any] | None = None,
    ) -> None: ...


JobRunner = Callable[[ProgressReporter, threading.Event], dict[str, Any]]


class JobCancelledError(RuntimeError):
    """Internal cooperative-cancellation signal."""


@dataclass
class _JobState:
    record: JobRecord
    cancel_event: threading.Event
    future: Future[None] | None = None


class JobManager:
    def __init__(self, artifact_dir: Path, *, max_workers: int = 2) -> None:
        self.root = artifact_dir / "jobs"
        self.root.mkdir(parents=True, exist_ok=True)
        self.executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="echo-job")
        self.lock = threading.RLock()
        self.jobs: dict[str, _JobState] = {}

    def submit(
        self,
        kind: JobKind,
        total_agents: int,
        runner: JobRunner,
        *,
        total_rounds: int = 0,
        total_decisions: int = 0,
    ) -> JobRecord:
        record = JobRecord(
            job_id=new_id("job"),
            kind=kind,
            status="queued",
            progress=0,
            stage="任务已进入队列",
            processed_agents=0,
            total_agents=total_agents,
            current_round=0,
            total_rounds=total_rounds,
            processed_decisions=0,
            total_decisions=total_decisions,
            latest_trace="等待加载稳定人格与事件条件",
        )
        state = _JobState(record=record, cancel_event=threading.Event())
        with self.lock:
            self.jobs[record.job_id] = state
            self._persist_record(state.record)
            state.future = self.executor.submit(self._execute, record.job_id, runner)
        return record

    def _execute(self, job_id: str, runner: JobRunner) -> None:
        state = self.jobs[job_id]

        def report(
            progress: int,
            stage: str,
            processed_agents: int,
            latest_trace: str,
            details: dict[str, Any] | None = None,
        ) -> None:
            if state.cancel_event.is_set():
                raise JobCancelledError("job cancellation requested")
            extra: dict[str, Any] = {}
            if details:
                for key in (
                    "current_round",
                    "total_rounds",
                    "processed_decisions",
                    "total_decisions",
                ):
                    if key in details:
                        extra[key] = max(0, int(details[key]))
                preview = details.get("preview")
                if preview is not None:
                    feed = [*state.record.decision_feed, JobDecisionPreview.model_validate(preview)]
                    extra["decision_feed"] = feed[-10:]
            self._update(
                job_id,
                status="running",
                progress=max(0, min(progress, 99)),
                stage=stage,
                processed_agents=max(0, min(processed_agents, state.record.total_agents)),
                latest_trace=latest_trace,
                **extra,
            )

        try:
            self._update(
                job_id,
                status="running",
                progress=0,
                stage="正在加载稳定人格与事件条件",
                latest_trace="尚未开始 Agent 决策",
            )
            result = runner(report, state.cancel_event)
            if state.cancel_event.is_set():
                raise JobCancelledError("job cancellation requested")
            self._persist_result(job_id, result)
            completed_trace = (
                "所有独立决策已完成，真实结果已聚合"
                if state.record.total_decisions > 0
                else "全部 Agent 计算已完成，结果已汇总"
            )
            self._update(
                job_id,
                status="complete",
                progress=100,
                stage="运行完成",
                processed_agents=state.record.total_agents,
                current_round=state.record.total_rounds,
                processed_decisions=state.record.total_decisions,
                latest_trace=completed_trace,
                result_available=True,
            )
        except JobCancelledError:
            self._update(
                job_id,
                status="cancelled",
                stage="任务已终止",
                latest_trace="终止请求已生效；未发布不完整结果",
            )
        except Exception as exc:  # noqa: BLE001 - job boundary records safe error metadata
            self._update(
                job_id,
                status="failed",
                stage="运行失败",
                latest_trace="后端未能形成有效结果",
                error=f"{type(exc).__name__}: {exc}",
            )

    def _update(self, job_id: str, **updates: Any) -> JobRecord:
        with self.lock:
            state = self.jobs[job_id]
            state.record = state.record.model_copy(
                update={**updates, "updated_at": datetime.now(UTC)}
            )
            self._persist_record(state.record)
            return state.record

    def cancel(self, job_id: str) -> JobRecord:
        with self.lock:
            state = self._state(job_id)
            if state.record.status in {"complete", "cancelled", "failed"}:
                return state.record
            state.cancel_event.set()
            cancelled_before_start = state.future.cancel() if state.future is not None else False
            status = "cancelled" if cancelled_before_start else "cancelling"
            return self._update(
                job_id,
                status=status,
                stage="正在终止任务" if status == "cancelling" else "任务已终止",
                cancellation_requested=True,
                latest_trace="已停止接收新的 Agent 计算",
            )

    def get(self, job_id: str) -> JobRecord:
        with self.lock:
            if job_id in self.jobs:
                return self.jobs[job_id].record
        path = self._job_dir(job_id) / "job.json"
        if not path.exists():
            raise FileNotFoundError(f"job not found: {job_id}")
        return JobRecord.model_validate_json(path.read_text(encoding="utf-8"))

    def result(self, job_id: str) -> dict[str, Any]:
        record = self.get(job_id)
        if record.status != "complete" or not record.result_available:
            raise ValueError(f"job result is not available: {record.status}")
        path = self._job_dir(job_id) / "result.json"
        if not path.exists():
            raise FileNotFoundError(f"job result not found: {job_id}")
        payload: Any = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("job result must be a JSON object")
        return payload

    def _state(self, job_id: str) -> _JobState:
        try:
            return self.jobs[job_id]
        except KeyError as exc:
            raise FileNotFoundError(f"job not found: {job_id}") from exc

    def _job_dir(self, job_id: str) -> Path:
        root = self.root.resolve()
        directory = (root / job_id).resolve()
        if not directory.is_relative_to(root):
            raise FileNotFoundError(f"job not found: {job_id}")
        return directory

    def _persist_record(self, record: JobRecord) -> None:
        directory = self._job_dir(record.job_id)
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / "job.json"
        temporary = directory / "job.json.tmp"
        temporary.write_text(record.model_dump_json(indent=2), encoding="utf-8")
        temporary.replace(path)

    def _persist_result(self, job_id: str, result: dict[str, Any]) -> None:
        directory = self._job_dir(job_id)
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / "result.json"
        temporary = directory / "result.json.tmp"
        temporary.write_text(
            json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
        )
        temporary.replace(path)

    def shutdown(self) -> None:
        self.executor.shutdown(wait=False, cancel_futures=True)


__all__ = [
    "DATA_VERSION",
    "MODEL_VERSION",
    "JobCancelledError",
    "JobManager",
    "JobRunner",
    "ProgressReporter",
]
