"""OPS-LOG: isolated deployment tests; fixtures stay inside this directory."""

from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
import io
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tarfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import uuid

DEPLOY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DEPLOY))
import capture_website_logs as logs
import check_logging_install as preflight


class IsolatedFiles(unittest.TestCase):
    def setUp(self):
        self.directory = Path(__file__).resolve().parent / f".log-test-{uuid.uuid4().hex}"
        self.directory.mkdir()
        self.addCleanup(self.clean_files)

    def clean_files(self):
        for path in self.directory.rglob("*"):
            if path.is_file() and not path.is_symlink():
                path.chmod(0o600)
        shutil.rmtree(self.directory)

    def content(self):
        return b"".join(path.read_bytes() for path in sorted(self.directory.glob("*.log")))


class WriterTests(IsolatedFiles):
    def test_size_rotation_preserves_every_byte_without_copytruncate(self):
        data = bytes(range(256)) * 5
        writer = logs.LogWriter(self.directory, "api", max_bytes=73)
        writer.write(data[:100])
        writer.write(data[100:])
        writer.seal()
        self.assertEqual(self.content(), data)
        self.assertEqual(len(list(self.directory.glob("*.log"))), 18)
        self.assertFalse(list(self.directory.glob("*.active")))
        self.assertTrue(all(path.stat().st_size <= 73 for path in self.directory.glob("*.log")))
        if os.name == "posix":
            self.assertTrue(all(path.stat().st_mode & 0o777 == 0o440
                                for path in self.directory.glob("*.log")))

    def test_utc_midnight_seals_idle_file_and_never_expires_history(self):
        old = self.directory / "api-old.log"
        old.write_bytes(b"old retained")
        os.utime(old, (946684800, 946684800))
        stamp = datetime(2026, 1, 1, 23, 59, tzinfo=timezone.utc)
        writer = logs.LogWriter(self.directory, "api", max_bytes=10, clock=lambda: stamp)
        writer.write(b"first")
        stamp = datetime(2026, 2, 1, tzinfo=timezone.utc)
        writer.rotate_if_due()
        self.assertFalse(list(self.directory.glob("*.active")))
        writer.write(b"second")
        writer.seal()
        self.assertEqual(old.read_bytes(), b"old retained")
        self.assertEqual(len(list(self.directory.glob("*.log"))), 3)

    def test_new_writers_do_not_reopen_or_delete_abandoned_active_files(self):
        first = logs.LogWriter(self.directory, "web")
        first.write(b"crash tail")
        first.abort()
        second = logs.LogWriter(self.directory, "web")
        self.assertNotEqual(first.active, second.active)
        second.write(b"restart")
        second.seal()
        self.assertEqual(first.active.read_bytes(), b"crash tail")
        self.assertEqual(self.content(), b"restart")

    def test_short_writes_are_retried(self):
        writer = logs.LogWriter(self.directory, "api")
        real_write = os.write
        with patch.object(logs.os, "write", side_effect=lambda fd, data: real_write(fd, data[:2])):
            writer.write(b"unbroken bytes")
        writer.seal()
        self.assertEqual(self.content(), b"unbroken bytes")

    def test_write_failure_and_no_progress_leave_active_not_sealed(self):
        for failure in (OSError("secret error detail"), 0):
            with self.subTest(failure=type(failure).__name__):
                writer = logs.LogWriter(self.directory, "api")
                writer.write(b"saved prefix")
                with patch.object(logs.os, "write") as write:
                    if isinstance(failure, OSError):
                        write.side_effect = failure
                    else:
                        write.return_value = failure
                    with self.assertRaises(OSError):
                        writer.write(b"unwritten")
                writer.abort()
                self.assertEqual(writer.active.read_bytes(), b"saved prefix")
        self.assertFalse(list(self.directory.glob("*.log")))

    def test_sync_failure_does_not_publish_sealed_file(self):
        writer = logs.LogWriter(self.directory, "api")
        writer.write(b"retained")
        with patch.object(logs.os, "fsync", side_effect=OSError("disk failed")):
            with self.assertRaises(OSError):
                writer.seal()
        writer.abort()
        self.assertEqual(writer.active.read_bytes(), b"retained")
        self.assertFalse(list(self.directory.glob("*.log")))

    def test_seal_collision_cannot_overwrite_history(self):
        writer = logs.LogWriter(self.directory, "api")
        writer.write(b"new")
        target = writer.active.with_suffix("")
        target.write_bytes(b"original")
        with self.assertRaises(FileExistsError):
            writer.seal()
        writer.abort()
        self.assertEqual(target.read_bytes(), b"original")
        self.assertEqual(writer.active.read_bytes(), b"new")

    def test_invalid_directory_and_prefix_are_rejected(self):
        for directory, prefix in (
            (Path("."), "api"),
            (self.directory / "missing", "api"),
            (self.directory, "../escape"),
        ):
            with self.subTest(prefix=prefix), self.assertRaises(ValueError):
                logs.LogWriter(directory, prefix)
        with self.assertRaises(ValueError):
            logs.LogWriter(self.directory, "api", max_bytes=0)

    def test_symlink_directory_is_rejected(self):
        link = self.directory / "linked"
        try:
            link.symlink_to(self.directory, target_is_directory=True)
        except OSError:
            self.skipTest("Creating symlinks requires host permission.")
        with self.assertRaises(ValueError):
            logs.LogWriter(link, "api")


class CaptureTests(IsolatedFiles):
    def test_both_output_streams_binary_bytes_and_child_exit_status(self):
        code = (
            "import os,sys; os.write(1,b'out\\x00\\xff');"
            "os.write(2,b'err\\xfe'); sys.exit(23)"
        )
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            result = logs.capture(self.directory, "web", [sys.executable, "-c", code], max_bytes=3)
        self.assertEqual(result, 23)
        self.assertEqual(self.content(), b"out\x00\xfferr\xfe")
        self.assertEqual(stdout.getvalue() + stderr.getvalue(), "")

    def test_large_output_drains_before_exit_and_keeps_argument_boundaries(self):
        result = logs.capture(
            self.directory, "api",
            [sys.executable, "-c", "import os,sys; os.write(1,sys.argv[1].encode()*100000)",
             "a b"],
            max_bytes=100000,
        )
        self.assertEqual(result, 0)
        self.assertEqual(self.content(), b"a b" * 100000)

    def test_spawn_failure_is_explicit_and_does_not_print_argv(self):
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            result = logs.capture(self.directory, "api", ["nonexistent-secret-command-438472"])
        self.assertEqual(result, 74)
        self.assertIn("capture failed", stderr.getvalue())
        self.assertNotIn("secret", stderr.getvalue())
        self.assertEqual(len(list(self.directory.glob("*.active"))), 1)

    def test_unwritable_capture_never_starts_service_or_prints_failure_details(self):
        stderr = io.StringIO()
        with (
            redirect_stderr(stderr),
            patch.object(logs.os, "open", side_effect=PermissionError("secret-path")),
            patch.object(logs.subprocess, "Popen") as spawn,
        ):
            result = logs.capture(self.directory, "api", ["must-not-run"])
        self.assertEqual(result, 74)
        spawn.assert_not_called()
        self.assertNotIn("secret-path", stderr.getvalue())

    def test_capture_failure_stops_child_and_preserves_active_file(self):
        stderr = io.StringIO()
        with (
            redirect_stderr(stderr),
            patch.object(logs.LogWriter, "write", side_effect=OSError("secret-failure")),
            patch.object(logs, "signal_child", wraps=logs.signal_child) as forward,
        ):
            result = logs.capture(
                self.directory, "api",
                [sys.executable, "-c", "import os,time; os.write(1,b'test'); time.sleep(60)"],
                shutdown_seconds=1,
            )
        self.assertEqual(result, 74)
        child = forward.call_args_list[0].args[0]
        self.assertIsNotNone(child.poll())
        self.assertNotIn("secret", stderr.getvalue())
        self.assertTrue(list(self.directory.glob("*.active")))
        self.assertFalse(list(self.directory.glob("*.log")))

    @unittest.skipUnless(os.name == "posix", "Requires Linux process-group signals.")
    def test_sigterm_reaches_process_group_and_shutdown_tails_are_sealed(self):
        pid_file = self.directory / "grandchild.pid"
        grandchild_code = (
            "import os,signal,time,sys,pathlib;"
            "signal.signal(signal.SIGTERM,lambda s,f:(os.write(1,b'grand-tail'),sys.exit(0)));"
            "pathlib.Path(sys.argv[1]).write_text(str(os.getpid()));time.sleep(60)"
        )
        child_code = (
            "import os,signal,time,sys,pathlib,subprocess\n"
            "signal.signal(signal.SIGTERM,lambda s,f:(os.write(1,b'child-tail'),sys.exit(0)))\n"
            f"subprocess.Popen([sys.executable,'-c',{grandchild_code!r},sys.argv[1]])\n"
            "while not pathlib.Path(sys.argv[1]).exists(): time.sleep(.01)\n"
            "os.write(1,b'ready');time.sleep(60)"
        )
        child = subprocess.Popen([
            sys.executable, str(DEPLOY / "capture_website_logs.py"),
            "--directory", str(self.directory), "--prefix", "api", "--",
            sys.executable, "-c", child_code, str(pid_file),
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                active = list(self.directory.glob("*.active"))
                if active and active[0].read_bytes() == b"ready":
                    break
                time.sleep(0.05)
            else:
                self.fail("Child did not become ready.")
            child.send_signal(signal.SIGTERM)
            out, err = child.communicate(timeout=5)
            self.assertEqual(child.returncode, 0, err)
            self.assertEqual(out + err, b"")
            content = self.content()
            self.assertTrue(content.startswith(b"ready"))
            self.assertEqual(content.count(b"child-tail"), 1)
            self.assertEqual(content.count(b"grand-tail"), 1)
        finally:
            if child.poll() is None:
                child.kill()
                child.wait()
            if pid_file.exists():
                try:
                    os.kill(int(pid_file.read_text()), signal.SIGKILL)
                except ProcessLookupError:
                    pass

    @unittest.skipUnless(os.name == "posix", "Requires Linux process-group signals.")
    def test_stubborn_child_is_killed_after_grace_and_output_is_drained(self):
        child_code = (
            "import os,signal,time;"
            "signal.signal(signal.SIGTERM,signal.SIG_IGN);"
            "os.write(1,b'ready');time.sleep(60)"
        )
        wrapper = subprocess.Popen([
            sys.executable, str(DEPLOY / "capture_website_logs.py"),
            "--directory", str(self.directory), "--prefix", "api",
            "--shutdown-seconds", "1", "--", sys.executable, "-c", child_code,
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                active = list(self.directory.glob("*.active"))
                if active and active[0].read_bytes() == b"ready":
                    break
                time.sleep(0.05)
            else:
                self.fail("Child did not become ready.")
            wrapper.send_signal(signal.SIGTERM)
            out, err = wrapper.communicate(timeout=5)
            self.assertEqual(wrapper.returncode, 128 + signal.SIGKILL, err)
            self.assertEqual(out + err, b"")
            self.assertEqual(self.content(), b"ready")
            self.assertFalse(list(self.directory.glob("*.active")))
        finally:
            if wrapper.poll() is None:
                wrapper.kill()
                wrapper.wait()


class InstallationTests(IsolatedFiles):
    """OPS-012: real isolated paths, simulated Linux ownership/systemd identities."""

    def setUp(self):
        super().setUp()
        self.expected = {
            self.directory / "usr/local/lib/styl": (0, 0, 0o755),
            self.directory / preflight.CAPTURE.lstrip("/"): (0, 0, 0o644),
            self.directory / preflight.BACKUP.lstrip("/"): (0, 0, 0o755),
            self.directory / "var/log/styl-website": (0, 103, 0o2770),
            self.directory / "var/lib/styl-records": (101, 101, 0o700),
        }
        for path in self.expected:
            if path.suffix in (".py", ".sh"):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("installed tool fixture")
            else:
                path.mkdir(parents=True, exist_ok=True)
        self.ids = patch.object(preflight, "service_ids", return_value=(101, 101, 103))
        self.ids.start()
        self.addCleanup(self.ids.stop)
        mode = patch.object(preflight, "metadata", side_effect=lambda path: self.expected[path])
        mode.start()
        self.addCleanup(mode.stop)

    def test_complete_prerequisites_pass_without_changing_files(self):
        before = {path: path.read_bytes() for path in self.expected if path.is_file()}
        preflight.check_installation(self.directory, True, True)
        self.assertEqual(before, {path: path.read_bytes() for path in before})

    def test_missing_tool_or_private_directory_refuses_installation(self):
        for path in list(self.expected)[1:]:
            with self.subTest(path=path.name):
                is_file = path.is_file()
                path.unlink() if is_file else path.rmdir()
                with self.assertRaises(preflight.IncompleteInstallation):
                    preflight.check_installation(self.directory, True, True)
                path.write_text("installed tool fixture") if is_file else path.mkdir()

    def test_wrong_owner_group_or_modes_refuse_installation(self):
        for path, original in list(self.expected.items()):
            for index in range(3):
                with self.subTest(path=path.name, metadata_field=index):
                    incorrect = list(original)
                    incorrect[index] += 1
                    self.expected[path] = tuple(incorrect)
                    with self.assertRaises(preflight.IncompleteInstallation):
                        preflight.check_installation(self.directory, True, True)
                    self.expected[path] = original

    def test_symlink_tool_refuses_installation(self):
        path = self.directory / preflight.CAPTURE.lstrip("/")
        target = self.directory / "other.py"
        target.write_text("untrusted tool")
        path.unlink()
        try:
            path.symlink_to(target)
        except OSError:
            self.skipTest("Creating symlinks requires host permission.")
        with self.assertRaises(preflight.IncompleteInstallation):
            preflight.check_installation(self.directory, True, True)

    def test_missing_service_group_membership_refuses_installation(self):
        self.ids.stop()
        group = SimpleNamespace(getgrnam=lambda name: SimpleNamespace(gr_gid=103))
        users = SimpleNamespace(getpwnam=lambda name: SimpleNamespace(pw_uid=101, pw_gid=101))
        with (
            patch.dict(sys.modules, {"grp": group, "pwd": users}),
            patch.object(preflight.os, "getgrouplist", return_value=[101], create=True),
        ):
            with self.assertRaises(preflight.IncompleteInstallation):
                preflight.check_installation(self.directory, True, True)

    def test_installed_unit_detection_preserves_legacy_and_detects_reload(self):
        def show(*args, **kwargs):
            unit = args[0][2]
            output = "LoadState=loaded\n"
            if unit == "caddy.service":
                output += f"ExecReload={preflight.CAPTURE}\n"
            if unit == "styl-backup.service":
                output += f"ExecStart={preflight.BACKUP}\n"
            return SimpleNamespace(returncode=0, stdout=output)
        with patch.object(preflight.subprocess, "run", side_effect=show):
            self.assertEqual(preflight.installed_requirements(), (True, True))
        with patch.object(preflight.subprocess, "run", return_value=SimpleNamespace(
            returncode=0, stdout="LoadState=loaded\nExecStart=/legacy\n"
        )):
            self.assertEqual(preflight.installed_requirements(), (False, False))
        with patch.object(preflight.subprocess, "run", return_value=SimpleNamespace(
            returncode=1, stdout="LoadState=not-found\nExecStart=\n"
        )):
            self.assertEqual(preflight.installed_requirements(), (False, False))
        with patch.object(preflight, "metadata") as inspect:
            preflight.check_installation(self.directory / "nonexistent", False, False)
            inspect.assert_not_called()

    def test_unreadable_systemd_configuration_is_not_treated_as_legacy(self):
        with patch.object(preflight.subprocess, "run", return_value=SimpleNamespace(
            returncode=1, stdout="sensitive-command-argument"
        )):
            with self.assertRaises(preflight.IncompleteInstallation) as failure:
                preflight.installed_requirements()
        self.assertNotIn("sensitive", str(failure.exception))

    def test_require_gate_checks_all_paths_before_new_units_exist(self):
        with (
            patch.object(preflight, "os", SimpleNamespace(name="posix", geteuid=lambda: 0)),
            patch.object(sys, "argv", ["preflight", "--require"]),
            patch.object(preflight, "installed_requirements") as installed,
            patch.object(preflight, "check_installation") as check,
        ):
            self.assertEqual(preflight.main(), 0)
            installed.assert_not_called()
            self.assertEqual(check.call_args.args[1:], (True, True))

    def test_failure_is_explicit_without_printing_secret_details(self):
        stderr = io.StringIO()
        with (
            redirect_stderr(stderr),
            patch.object(preflight, "os", SimpleNamespace(name="posix", geteuid=lambda: 0)),
            patch.object(sys, "argv", ["preflight", "--require"]),
            patch.object(preflight, "check_installation", side_effect=OSError("secret-detail")),
        ):
            self.assertEqual(preflight.main(), 78)
        self.assertIn("preflight failed", stderr.getvalue())
        self.assertNotIn("secret-detail", stderr.getvalue())


class DeploymentContractTests(unittest.TestCase):
    def test_website_services_capture_output_and_do_not_log_environment(self):
        for name in ("styl-api.service", "styl-web.service", "styl-analytics-report.service",
                     "caddy-website-logs.conf"):
            with self.subTest(service=name):
                text = (DEPLOY / name).read_text()
                self.assertIn("capture_website_logs.py --directory /var/log/styl-website", text)
                self.assertIn("/usr/local/lib/styl/capture_website_logs.py", text)
                self.assertIn("KillMode=mixed", text)
                self.assertNotIn("--environ", text)
        self.assertIn("--no-access-log", (DEPLOY / "styl-api.service").read_text())
        self.assertIn("NotifyAccess=all", (DEPLOY / "caddy-website-logs.conf").read_text())

    def test_journal_retention_is_not_installed_by_normal_deploy(self):
        text = (DEPLOY / "journald-operational.conf").read_text()
        self.assertIn("MaxRetentionSec=14day", text)
        self.assertIn("SystemMaxUse=250M", text)
        deploy = (DEPLOY / "deploy.sh").read_text()
        self.assertNotIn("journald", deploy)
        self.assertNotIn("vacuum", deploy)
        self.assertLess(deploy.index("check_logging_install.py"), deploy.index("pull --ff-only"))
        guide = (DEPLOY.parent / "docs/lightsail-deployment.md").read_text()
        self.assertIn("if sudo /usr/bin/python3 /opt/styl/deploy/check_logging_install.py --require; then",
                      guide)
        self.assertLess(guide.index("check_logging_install.py --require"),
                        guide.index("install -m 0644 /opt/styl/deploy/caddy-website-logs.conf"))

    def test_backup_has_no_age_cleanup_and_uses_incomplete_suffix(self):
        text = (DEPLOY / "backup.sh").read_text()
        self.assertNotIn("-mtime", text)
        self.assertNotIn("-delete", text)
        self.assertIn('> "$archive.active"', text)
        self.assertIn('ln "$archive.active" "$archive"', text)
        self.assertIn("set -o noclobber", text)
        self.assertIn("/usr/local/lib/styl/backup.sh", (DEPLOY / "styl-backup.service").read_text())

    def test_caddy_drops_identifying_request_objects_without_sampling(self):
        text = (DEPLOY / "website-logging.caddy").read_text()
        self.assertEqual(text.count("request delete"), 2)
        self.assertEqual(text.count("resp_headers delete"), 2)
        self.assertEqual(text.count("user_id delete"), 2)
        for setting in ("log_credentials", "sampling", "output file", "output discard"):
            self.assertNotIn(setting, text)
        self.assertIn("http://example.com, http://www.example.com", (DEPLOY / "Caddyfile").read_text())


class BackupTests(IsolatedFiles):
    def setUp(self):
        super().setUp()
        if os.name == "posix":
            self.bash = shutil.which("bash")
        else:
            candidate = Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Git/bin/bash.exe"
            self.bash = str(candidate) if candidate.is_file() else None
        if self.bash is None:
            self.skipTest("Bash is required for isolated backup-script execution.")
        self.data = self.directory / "data"
        self.data.mkdir()
        self.backups = self.directory / "backups"
        self.backups.mkdir()
        self.old = self.backups / "styl-20000101.tar.gz"
        self.old.write_bytes(b"business history")
        os.utime(self.old, (946684800, 946684800))

    def run_backup(self):
        env = dict(os.environ, STYL_DATA_DIR=self.data.as_posix(),
                   STYL_BACKUP_DIR=self.backups.as_posix())
        args = [self.bash, str(DEPLOY / "backup.sh")]
        if os.name != "posix":
            # NTFS/OneDrive cannot enact install(1)'s POSIX ownership/mode.
            # Only provisioning is stubbed; run the real tar/link/script logic.
            args = [
                self.bash, "-c",
                'install() { mkdir -p -- "${@: -1}"; }; export -f install; "$BASH" "$1"',
                "test-backup", (DEPLOY / "backup.sh").as_posix(),
            ]
        return subprocess.run(args, env=env,
                              capture_output=True, timeout=15)

    def test_old_business_backups_survive_new_unique_complete_archives(self):
        (self.data / "products.json").write_text('{"preserved": true}')
        for _ in range(2):
            result = self.run_backup()
            self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.old.read_bytes(), b"business history")
        archives = [path for path in self.backups.glob("*.tar.gz") if path != self.old]
        self.assertEqual(len(archives), 2)
        self.assertFalse(list(self.backups.glob("*.active")))
        with tarfile.open(archives[0]) as archive:
            self.assertEqual(archive.extractfile("./products.json").read(), b'{"preserved": true}')

    def test_standard_install_guide_is_valid_gated_bash(self):
        guide = (DEPLOY.parent / "docs/lightsail-deployment.md").read_text()
        section = guide.split("## 6. Install services", 1)[1]
        block = section.split("```bash\n", 1)[1].split("```", 1)[0]
        result = subprocess.run([self.bash, "-n"], input=block.encode(),
                                capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_failed_backup_keeps_old_archives_and_marks_partial(self):
        self.data.rmdir()
        result = self.run_backup()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.old.read_bytes(), b"business history")
        self.assertEqual(list(self.backups.glob("*.tar.gz")), [self.old])
        self.assertEqual(len(list(self.backups.glob("*.active"))), 1, result.stderr)


if __name__ == "__main__":
    unittest.main()
