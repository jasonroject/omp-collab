#!/usr/bin/env python3
"""Run independent OMP briefs with bounded concurrency and separate artifacts."""

from __future__ import annotations

import argparse
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from threading import Event
import time
import uuid

from omp_delegate import delegate, resolve_omp


def run_batch(tasks: list[Path], model: str, output: Path, executable: str,
              timeout: int, jobs: int) -> tuple[Path, dict]:
    if not tasks or jobs < 1 or timeout < 1:
        raise ValueError("Provide tasks and positive jobs/timeout values.")
    # Validate every brief before making any paid request.
    for task in tasks:
        if not task.read_text(encoding="utf-8-sig").strip():
            raise ValueError(f"Empty task file: {task}")
    stamp = datetime.now(timezone.utc)
    batch_dir = output.resolve() / ("batch-" + stamp.strftime("%Y%m%dT%H%M%SZ-") + uuid.uuid4().hex[:10])
    batch_dir.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    cancel = Event()
    summary = {
        "schema_version": 1, "started_at_utc": stamp.isoformat(),
        "requested_model": model, "max_parallel": min(jobs, len(tasks)),
        "status": "running", "review_status": "pending",
        "tasks": [{"index": i + 1, "task": str(task.resolve()), "status": "queued"}
                  for i, task in enumerate(tasks)],
    }

    def save():
        summary["elapsed_seconds"] = round(time.monotonic() - started, 3)
        temporary = batch_dir / "batch.json.tmp"
        temporary.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(batch_dir / "batch.json")

    def worker(index):
        if cancel.is_set():
            return {"status": "skipped", "reason": "Batch interrupted before launch."}
        try:
            run_dir, metadata = delegate(tasks[index], model, batch_dir, executable, timeout, cancel)
            return {"run_dir": str(run_dir), **metadata}
        except Exception as error:
            return {"status": "failed", "error": f"{type(error).__name__}: {error}"}

    def collect(future, index):
        summary["tasks"][index].update(future.result())

    next_index = 0
    stop_launching = False
    interrupted = False
    save()
    with ThreadPoolExecutor(max_workers=summary["max_parallel"]) as pool:
        pending = {}
        try:
            while next_index < len(tasks) or pending:
                while not stop_launching and next_index < len(tasks) and len(pending) < summary["max_parallel"]:
                    summary["tasks"][next_index]["status"] = "running"
                    pending[pool.submit(worker, next_index)] = next_index
                    next_index += 1
                save()
                if not pending:
                    break
                done, _ = wait(pending, return_when=FIRST_COMPLETED)
                for future in done:
                    index = pending.pop(future)
                    collect(future, index)
                    if summary["tasks"][index]["status"] != "returned":
                        stop_launching = True
                save()
        except KeyboardInterrupt:
            interrupted = True
            cancel.set()
            # Workers notice cancellation and clean up their own OMP process trees.
            for future, index in pending.items():
                collect(future, index)
    for item in summary["tasks"]:
        if item["status"] == "queued":
            item.update(status="skipped", reason="Batch interrupted." if interrupted else "An earlier task failed; no new requests launched.")
    summary["status"] = "interrupted" if interrupted else (
        "returned" if all(item["status"] == "returned" for item in summary["tasks"]) else "failed"
    )
    save()
    return batch_dir, summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", type=Path, action="append", required=True, help="UTF-8 brief; repeat for each independent assignment")
    parser.add_argument("--model", required=True, help="Exact configured provider/model")
    parser.add_argument("--jobs", type=int, default=2, help="Maximum concurrent OMP processes (default: 2)")
    parser.add_argument("--timeout", type=int, default=180, help="Per-task time limit, excluding queue time")
    parser.add_argument("--output", type=Path, default=Path(".omp-collab-runs"))
    parser.add_argument("--omp", default="omp")
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*/\S+", args.model):
        parser.error("--model must be a complete provider/model identifier")
    try:
        executable = resolve_omp(args.omp)
        batch_dir, summary = run_batch(args.task, args.model, args.output, executable, args.timeout, args.jobs)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(json.dumps({"batch_dir": str(batch_dir), **summary}, ensure_ascii=True))
    return {"returned": 0, "interrupted": 130}.get(summary["status"], 1)


if __name__ == "__main__":
    raise SystemExit(main())
