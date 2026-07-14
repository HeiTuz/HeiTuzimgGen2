import contextlib
import io
import os
import tempfile
import unittest
from unittest.mock import patch

import cleanup_temp_outputs
import output_lifecycle


class CleanupTempOutputsCliTests(unittest.TestCase):
    def test_cli_is_quiet_and_removes_expired_jobs(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(
            output_lifecycle.tempfile, "gettempdir", return_value=tmp
        ):
            old = output_lifecycle.create_job_dir("single")
            artifact = old / "artifact.png"
            artifact.write_bytes(b"x")
            for item in old.rglob("*"):
                os.utime(item, (100, 100))
            os.utime(old, (100, 100))
            stdout = io.StringIO()

            with contextlib.redirect_stdout(stdout):
                status = cleanup_temp_outputs.main(
                    ["--retention-hours", "1", "--now", "10000"]
                )

            self.assertEqual(status, 0)
            self.assertEqual(stdout.getvalue(), "")
            self.assertFalse(old.exists())

    def test_cli_rejects_arbitrary_cleanup_root(self):
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                cleanup_temp_outputs.main(["--root", tmp])


if __name__ == "__main__":
    unittest.main()
