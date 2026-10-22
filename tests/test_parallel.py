import json
from pathlib import Path
import sys
import tempfile
from threading import Barrier, Event, Lock, Timer
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "skills/omp-collab/scripts"
sys.path.insert(0, str(SCRIPTS))
import omp_parallel as parallel
import omp_delegate as single


class ParallelTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="omp parallel ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.tasks = []
        for index in range(4):
            task = self.root / f"task-{index}.md"
            task.write_text(f"Independent brief {index}", encoding="utf-8")
            self.tasks.append(task)

    def run_batch(self, jobs):
        return parallel.run_batch(self.tasks, "provider/model", self.root / "runs", "omp", 5, jobs)

    def test_parallel_overlap_and_concurrency_limit(self):
        lock = Lock()
        barrier = Barrier(2)
        active = peak = 0

        def fake(task, model, output, executable, timeout, cancel):
            nonlocal active, peak
            with lock:
                active += 1
                peak = max(peak, active)
            barrier.wait(timeout=5)  # A sequential implementation would fail here.
            with lock:
                active -= 1
            return output / task.stem, {"status": "returned", "review_status": "pending"}

        with patch.object(parallel, "delegate", side_effect=fake):
            batch_dir, summary = self.run_batch(2)
        self.assertEqual(peak, 2)
        self.assertEqual(summary["status"], "returned")
        self.assertEqual(len({item["run_dir"] for item in summary["tasks"]}), 4)
        self.assertEqual(json.loads((batch_dir / "batch.json").read_text()), summary)

    def test_failure_stops_queued_requests(self):
        with patch.object(parallel, "delegate", return_value=(self.root / "failed", {"status": "failed"})) as delegate:
            _, summary = self.run_batch(1)
        self.assertEqual(delegate.call_count, 1)
        self.assertEqual([item["status"] for item in summary["tasks"]], ["failed", "skipped", "skipped", "skipped"])

    def test_preflight_rejects_missing_brief_before_any_request(self):
        self.tasks.append(self.root / "missing.md")
        with patch.object(parallel, "delegate") as delegate:
            with self.assertRaises(FileNotFoundError):
                self.run_batch(2)
        delegate.assert_not_called()

    def test_interrupt_cancels_workers_and_saves_summary(self):
        def fake(task, model, output, executable, timeout, cancel):
            cancel.wait(timeout=5)
            return output / task.stem, {"status": "interrupted" if cancel.is_set() else "returned"}
        with patch.object(parallel, "delegate", side_effect=fake), \
             patch.object(parallel, "wait", side_effect=KeyboardInterrupt):
            _, summary = self.run_batch(2)
        self.assertEqual(summary["status"], "interrupted")
        self.assertTrue(all(item["status"] in {"interrupted", "skipped"} for item in summary["tasks"]))

    def test_cancel_event_stops_live_process(self):
        cancel = Event()
        timer = Timer(0.5, cancel.set)
        timer.start()
        try:
            _, _, _, reason = single.run_command(
                [sys.executable, "-c", "import time; time.sleep(30)"], self.root, 20, cancel,
            )
        finally:
            timer.cancel()
        self.assertEqual(reason, "interrupted")


if __name__ == "__main__":
    unittest.main()
