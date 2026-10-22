import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "skills/omp-collab/scripts/omp_delegate.py"
SPEC = importlib.util.spec_from_file_location("omp_delegate", SCRIPT)
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


class ProcessTests(unittest.TestCase):
    def test_unicode_output_and_nonzero_status(self):
        with tempfile.TemporaryDirectory(prefix="omp test ") as directory:
            command = [sys.executable, "-X", "utf8", "-c",
                       "import sys; print('审查完成'); print('诊断', file=sys.stderr); sys.exit(7)"]
            code, stdout, stderr, stopped = runner.run_command(command, Path(directory), 5)
            self.assertEqual(code, 7)
            self.assertIn("审查完成", stdout)
            self.assertIn("诊断", stderr)
            self.assertIsNone(stopped)

    def test_timeout_retains_output_and_stops_process(self):
        with tempfile.TemporaryDirectory() as directory:
            started = time.monotonic()
            code, stdout, _, stopped = runner.run_command(
                [sys.executable, "-c", "import time; print('partial', flush=True); time.sleep(30)"],
                Path(directory), 0.5,
            )
            self.assertEqual(stopped, "timed_out")
            self.assertNotEqual(code, 0)
            self.assertIn("partial", stdout)
            self.assertLess(time.monotonic() - started, 10)

    def test_cleanup_timeout_preserves_partial_output(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(runner.subprocess, "Popen") as factory:
                process = factory.return_value
                process.communicate.side_effect = [
                    subprocess.TimeoutExpired("omp", 1, output=b"partial"),
                    subprocess.TimeoutExpired("omp", 5, output=b"partial output", stderr=b"diagnostic"),
                ]
                process.poll.return_value = -9
                process.pid = 12345
                with patch.object(runner.subprocess, "run", side_effect=subprocess.TimeoutExpired("kill", 5)), \
                     patch.object(runner.os, "killpg", create=True, side_effect=OSError("cleanup failed")):
                    _, stdout, stderr, stopped = runner.run_command(["omp"], Path(directory), 1)
        self.assertEqual(stopped, "timed_out")
        self.assertEqual(stdout, "partial output")
        self.assertIn("may be incomplete", stderr)
        self.assertIn("descendants may remain", stderr)

    def test_timeout_stops_descendant(self):
        with tempfile.TemporaryDirectory() as directory:
            child = "import time; from pathlib import Path; time.sleep(1.5); Path('survived.txt').write_text('unexpected')"
            parent = "import subprocess,sys,time; subprocess.Popen([sys.executable, '-c', " + repr(child) + "]); time.sleep(30)"
            _, _, _, stopped = runner.run_command([sys.executable, "-c", parent], Path(directory), 0.5)
            self.assertEqual(stopped, "timed_out")
            time.sleep(1.7)
            self.assertFalse((Path(directory) / "survived.txt").exists())

    def test_interrupt_preserves_output(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(runner.subprocess, "Popen") as factory:
                process = factory.return_value
                process.communicate.side_effect = [KeyboardInterrupt(), ("partial", "")]
                process.poll.return_value = -9
                process.pid = 12345
                with patch.object(runner.subprocess, "run"), patch.object(runner.os, "killpg", create=True):
                    _, stdout, _, stopped = runner.run_command(["omp"], Path(directory), 1)
        self.assertEqual(stopped, "interrupted")
        self.assertEqual(stdout, "partial")


class ArtifactTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="omp artifacts ")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.task = self.root / "任务 file.md"
        self.brief = "Review this literally: $(echo unsafe) `cmd` & ;\n中文 context.\n"
        self.task.write_text(self.brief, encoding="utf-8-sig")

    def run_result(self, result):
        with patch.object(runner, "run_command", return_value=result) as process:
            run_dir, meta = runner.delegate(self.task, "provider/model", self.root / "runs", "omp", 5)
        return run_dir, meta, process

    def test_isolated_artifacts_and_literal_task(self):
        run_dir, meta, process = self.run_result((0, "Answer", "Diagnostic", None))
        command, cwd, _ = process.call_args.args
        self.assertEqual(cwd, run_dir)
        self.assertNotEqual(cwd, self.task.parent)
        self.assertEqual(command[-1], "@" + str(run_dir / "request.md"))
        self.assertNotIn(self.brief, command)
        self.assertIn("--no-tools", command)
        self.assertIn("--no-extensions", command)
        self.assertEqual((run_dir / "request.md").read_text(encoding="utf-8"), self.brief)
        self.assertEqual((run_dir / "response.txt").read_text(), "Answer")
        self.assertEqual(json.loads((run_dir / "run.json").read_text()), meta)
        self.assertEqual(meta["status"], "returned")
        self.assertEqual(meta["review_status"], "pending")
        second, _, _ = self.run_result((0, "Another", "", None))
        self.assertNotEqual(run_dir, second)

    def test_failure_and_partial_timeout_are_not_success(self):
        for result, expected in [
            ((3, "Partial", "Authentication failed", None), "failed"),
            ((0, "   ", "No answer", None), "failed"),
            ((-9, "Partial", "", "timed_out"), "timed_out"),
            ((-9, "Partial", "", "interrupted"), "interrupted"),
        ]:
            with self.subTest(expected=expected, result=result):
                run_dir, meta, _ = self.run_result(result)
                self.assertEqual(meta["status"], expected)
                self.assertEqual((run_dir / "stderr.txt").read_text(), result[2])

    def test_launch_error_is_saved(self):
        with patch.object(runner, "run_command", side_effect=OSError("launch failed")):
            run_dir, meta = runner.delegate(self.task, "p/m", self.root / "runs", "omp", 5)
        self.assertEqual(meta["status"], "failed")
        self.assertIsNone(meta["returncode"])
        self.assertIn("launch failed", (run_dir / "stderr.txt").read_text())

    def test_empty_task_never_launches(self):
        self.task.write_text(" \n")
        with patch.object(runner, "run_command") as process:
            with self.assertRaises(ValueError):
                runner.delegate(self.task, "p/m", self.root / "runs", "omp", 5)
        process.assert_not_called()

    def test_cli_rejects_ambiguous_model_without_launching(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--task", str(self.task), "--model", "flash"],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("provider/model", result.stderr)


if __name__ == "__main__":
    unittest.main()
