import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import portable_paths as paths


class PortablePathTests(unittest.TestCase):
    def test_classifies_common_os_path_shapes(self):
        cases = {
            "/Users/alice/Pictures/ref.png": "macos_absolute",
            "/Volumes/Studio/ref.png": "macos_absolute",
            "/home/alice/ref.png": "linux_absolute",
            "/mnt/c/Users/alice/ref.png": "wsl_mount",
            r"C:\Users\alice\ref.png": "windows_absolute",
            r"\\server\share\ref.png": "windows_unc",
            "refs/ref.png": "portable_relative",
        }
        for value, expected in cases.items():
            with self.subTest(value=value):
                self.assertEqual(paths.classify_path(value), expected)

    def test_windows_rejects_macos_and_linux_paths_without_guessing(self):
        for value, label in (
            ("/Users/alice/Pictures/ref.png", "macOS path"),
            ("/home/alice/ref.png", "POSIX path"),
        ):
            with self.subTest(value=value), self.assertRaisesRegex(paths.PathCompatibilityError, label):
                paths.normalize_local_path(value, platform="win32", field="reference")

    def test_posix_rejects_windows_paths_without_guessing(self):
        for value in (r"C:\Users\alice\ref.png", r"\\server\share\ref.png"):
            with self.subTest(value=value), self.assertRaisesRegex(paths.PathCompatibilityError, "Windows path"):
                paths.normalize_local_path(value, platform="darwin", field="reference")

    def test_wsl_and_windows_mount_mappings_are_deterministic(self):
        self.assertEqual(
            paths.normalize_local_path("/mnt/c/Users/alice/ref.png", platform="win32"),
            r"C:\Users\alice\ref.png",
        )
        self.assertEqual(
            paths.normalize_local_path(r"D:\assets\ref.png", platform="linux", wsl=True),
            "/mnt/d/assets/ref.png",
        )
        with self.assertRaisesRegex(paths.PathCompatibilityError, "Windows path"):
            paths.normalize_local_path(r"D:\assets\ref.png", platform="linux", wsl=False)

    def test_file_uri_unc_spaces_unicode_and_long_paths(self):
        self.assertEqual(
            paths.normalize_local_path("file:///C:/Users/Alice/My%20Images/%EC%83%81%ED%92%88.png", platform="win32"),
            "C:\\Users\\Alice\\My Images\\상품.png",
        )
        self.assertEqual(
            paths.normalize_local_path("file://server/share/folder/ref.png", platform="win32"),
            r"\\server\share\folder\ref.png",
        )
        long_path = "C:\\work\\" + ("nested\\" * 40) + "ref.png"
        self.assertTrue(paths.normalize_local_path(long_path, platform="win32").startswith("\\\\?\\C:\\"))

    def test_windows_reserved_names_and_trailing_dot_fail_closed(self):
        for value in (r"C:\work\CON.png", "C:\\work\\bad. "):
            with self.subTest(value=value), self.assertRaises(paths.PathCompatibilityError):
                paths.normalize_local_path(value, platform="win32")

    def test_reparse_attribute_is_detected(self):
        fake = SimpleNamespace(
            is_symlink=lambda: False,
            stat=lambda follow_symlinks=False: SimpleNamespace(st_file_attributes=0x400),
        )
        self.assertTrue(paths.is_symlink_or_reparse(fake))  # type: ignore[arg-type]

    def test_normal_local_path_is_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            value = str(Path(tmp) / "한글 image.png")
            self.assertEqual(paths.normalize_local_path(value, platform="darwin"), value)


if __name__ == "__main__":
    unittest.main()
