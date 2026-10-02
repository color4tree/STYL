"""OPS-LOG/OPS-012: isolated installer parsing, preservation and retention gates.

No Linux service commands are executed. Live permission, notification, listener,
signal and off-server recovery coverage remains the deployment operator's gate.
"""

from copy import deepcopy
from contextlib import redirect_stderr
from datetime import datetime, timezone
import gzip
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import uuid
import zipfile


DEPLOY = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("logging_installer", DEPLOY / "install-records-logging.py")
installer = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = installer
SPEC.loader.exec_module(installer)
TEMPLATE = (DEPLOY / "website-logging.caddy").read_text()
PRODUCTION_SHAPE = """{
    email administrator@example.invalid
}

https://54.156.37.31 {
    tls internal
    handle /health {
        reverse_proxy 127.0.0.1:8000 {
            header_up X-Forwarded-For {http.request.remote.host}
        }
    }
    handle {
        reverse_proxy 127.0.0.1:3000
    }
}

stylfitness.com {
    encode zstd gzip
    reverse_proxy 127.0.0.1:3000
}

www.stylfitness.com {
    redir https://stylfitness.com{uri} permanent
}
"""


class CaddyTests(unittest.TestCase):
    def test_production_shape_preserves_every_original_byte_and_listener(self):
        merged, companion = installer.merge_caddy(PRODUCTION_SHAPE, TEMPLATE)
        self.assertEqual(merged.count("import website_access"), 3)
        self.assertEqual(merged.count("import website-logging.caddy"), 1)
        self.assertEqual(companion, TEMPLATE[TEMPLATE.index("(website_access)") :])
        before = installer.canonical_caddy(PRODUCTION_SHAPE)
        after = iter(installer.canonical_caddy(merged))
        self.assertTrue(all(any(candidate == token for candidate in after) for token in before))
        for line in PRODUCTION_SHAPE.splitlines():
            if line.strip():
                self.assertIn(line, merged)
        self.assertEqual(len([node for node in installer.parse_caddy(merged) if not node.words]), 1)

    def test_merge_is_byte_idempotent(self):
        first, companion = installer.merge_caddy(PRODUCTION_SHAPE, TEMPLATE)
        self.assertEqual(installer.merge_caddy(first, TEMPLATE), (first, companion))

    def test_missing_global_block_is_created_once(self):
        text = "example.invalid {\n    respond \"ok\" 200\n}\n"
        first, companion = installer.merge_caddy(text, TEMPLATE)
        self.assertIn(text.replace("{\n", "{\n    import website_access\n"), first)
        self.assertEqual(installer.merge_caddy(first, TEMPLATE), (first, companion))

    def test_existing_explicit_http_redirect_keeps_target_and_status(self):
        original = PRODUCTION_SHAPE + "\nhttp://stylfitness.com {\n    redir https://stylfitness.com{uri} 308\n}\n"
        merged, _ = installer.merge_caddy(original, TEMPLATE)
        self.assertIn("redir https://stylfitness.com{uri} 308", merged)
        self.assertEqual(merged.count("import website_access"), 4)

    def test_comments_quoted_braces_and_placeholders_are_not_structure(self):
        original = '# comment { }\nexample.invalid {\n    header X-Test "quoted } # value"\n    redir https://example.invalid{uri} 308\n}\n'
        merged, _ = installer.merge_caddy(original, TEMPLATE)
        self.assertIn('header X-Test "quoted } # value"', merged)
        self.assertIn("https://example.invalid{uri}", merged)
        self.assertIn("# comment { }", merged)

    def test_multi_host_site_preserves_addresses(self):
        original = "example.invalid, www.example.invalid {\n    respond ok\n}\n"
        merged, _ = installer.merge_caddy(original, TEMPLATE)
        self.assertIn("example.invalid, www.example.invalid {", merged)
        self.assertEqual(merged.count("import website_access"), 1)

    def test_unsupported_shapes_refuse_without_partial_result(self):
        cases = (
            "import /etc/caddy/sites/*\n",
            "example.invalid {\n    import unknown\n}\n",
            "example.invalid {\n    log {\n        output file /var/log/access.log\n    }\n}\n",
            "{\n    log default {\n        output discard\n    }\n}\nexample.invalid {\n    respond ok\n}\n",
            "{\n}\n{\n}\nexample.invalid {\n    respond ok\n}\n",
            "example.invalid {\n    respond ok\n}\n{\n}\n",
            "(unknown) {\n    respond ok\n}\n",
            "example.invalid {\n    respond <<END\nhi\nEND\n}\n",
            "example.invalid {\n    respond `unquoted`\n}\n",
            "example.invalid {\n    respond \"unterminated\n}\n",
            "example.invalid {\n",
            "example.invalid {\n    handle {\n        import website_access\n    }\n}\n",
            "example.invalid {\n    import website_access\n    import website_access\n}\n",
        )
        for text in cases:
            with self.subTest(text=text[:35]), self.assertRaises(installer.Refused):
                installer.merge_caddy(text, TEMPLATE)

    def test_unexpected_repository_template_refuses(self):
        with self.assertRaises(installer.Refused):
            installer.merge_caddy(PRODUCTION_SHAPE, "unreviewed {\n}\n")


class HTTPRedirectTests(unittest.TestCase):
    HOSTS = ("stylfitness.com", "www.stylfitness.com", "54.156.37.31")

    def test_current_three_hosts_get_only_exact_scoped_308_listeners(self):
        merged, _ = installer.merge_caddy(PRODUCTION_SHAPE, TEMPLATE, self.HOSTS)
        nodes = installer.parse_caddy(merged)
        http = [node for node in nodes if node.words and node.words[0].startswith("http://")]
        self.assertEqual({node.words for node in http}, {("http://" + host,) for host in self.HOSTS})
        for node in http:
            self.assertEqual([child.words for child in node.children], [
                ("import", "website_access"), ("redir", "https://{host}{uri}", "308"),
            ])
        self.assertEqual(merged.count("import website_access"), 6)
        self.assertNotIn("http://*", merged)
        self.assertNotIn("http://:80", merged)
        self.assertIn("redir https://stylfitness.com{uri} permanent", merged)
        for line in PRODUCTION_SHAPE.splitlines():
            if line.strip():
                self.assertIn(line, merged)

    def test_explicit_redirect_merge_is_byte_idempotent(self):
        merged, companion = installer.merge_caddy(PRODUCTION_SHAPE, TEMPLATE, self.HOSTS)
        self.assertEqual(installer.merge_caddy(merged, TEMPLATE, self.HOSTS), (merged, companion))

    def test_one_selected_host_does_not_create_other_http_listeners(self):
        merged, _ = installer.merge_caddy(PRODUCTION_SHAPE, TEMPLATE, ("stylfitness.com",))
        http = [node.words for node in installer.parse_caddy(merged)
                if node.words and node.words[0].startswith("http://")]
        self.assertEqual(http, [("http://stylfitness.com",)])
        with self.assertRaises(installer.Refused):
            installer.merge_caddy(PRODUCTION_SHAPE, TEMPLATE, ("unowned.example",))

    def test_preexisting_normal_explicit_http_route_is_not_replaced_or_duplicated(self):
        for header in ("http://stylfitness.com", "http://stylfitness.com:80", "stylfitness.com:80"):
            original = PRODUCTION_SHAPE + f"\n{header} {{\n    redir https://stylfitness.com{{uri}} 308\n}}\n"
            merged, companion = installer.merge_caddy(original, TEMPLATE, self.HOSTS)
            self.assertIn(header + " {", merged)
            self.assertEqual(merged.count("redir https://stylfitness.com{uri} 308"), 1)
            self.assertEqual(merged.count("redir https://{host}{uri} 308"), 2)
            self.assertEqual(installer.merge_caddy(merged, TEMPLATE, self.HOSTS), (merged, companion))

    def test_existing_http_custom_route_or_redirect_conflict_requires_manual_review(self):
        routes = (
            "respond custom 200", "reverse_proxy 127.0.0.1:3000",
            "redir https://stylfitness.com{uri} permanent",
            "redir https://another.example{uri} 308",
            "redir https://{host}{uri} 307",
            "header X-Test custom\n    redir https://{host}{uri} 308",
        )
        for route in routes:
            original = PRODUCTION_SHAPE + "\nhttp://stylfitness.com {\n    " + route + "\n}\n"
            with self.subTest(route=route), self.assertRaises(installer.Refused):
                installer.merge_caddy(original, TEMPLATE, self.HOSTS)

    def test_catchall_duplicate_mixed_and_nonstandard_servers_refuse(self):
        additions = (
            "\n:80 {\n    redir https://{host}{uri} 308\n}\n",
            "\nhttp://*.stylfitness.com {\n    redir https://{host}{uri} 308\n}\n",
            "\nhttp://stylfitness.com:8080 {\n    redir https://{host}{uri} 308\n}\n",
            "\nhttp://stylfitness.com, https://stylfitness.com {\n    redir https://{host}{uri} 308\n}\n",
            "\nhttp://stylfitness.com {\n    redir https://{host}{uri} 308\n}\n" * 2,
        )
        for addition in additions:
            with self.subTest(addition=addition[:45]), self.assertRaises(installer.Refused):
                installer.merge_caddy(PRODUCTION_SHAPE + addition, TEMPLATE, self.HOSTS)

    def test_custom_global_automatic_https_and_ports_need_manual_review(self):
        for setting in ("auto_https off", "auto_https disable_redirects", "http_port 8080", "https_port 8443"):
            original = PRODUCTION_SHAPE.replace("{\n", "{\n    " + setting + "\n", 1)
            with self.subTest(setting=setting), self.assertRaises(installer.Refused):
                installer.merge_caddy(original, TEMPLATE, self.HOSTS)

    def test_hostname_input_rejects_injection_ports_paths_schemes_and_duplicates(self):
        values = (
            "", "stylfitness.com,", ",stylfitness.com", "stylfitness.com,,54.156.37.31",
            "https://stylfitness.com", "stylfitness.com/path", "stylfitness.com:80",
            "stylfitness.com\nrespond hacked", "{host}", "*.stylfitness.com", ":80",
            "stylfitness.com;echo", "user@stylfitness.com", "stylfitness.com?x=1",
            "stylfitness.com#fragment", " stylfitness.com", "stylfitness.com ",
            "stylfitness.com,STYLFITNESS.COM", "54.156.37.31,54.156.37.31",
            "256.156.37.31", "054.156.37.31", "-bad.example", "bad-.example", "bad..example",
            "[::1]", "::1", "x" * 64 + ".example",
        )
        for value in values:
            with self.subTest(value=value), self.assertRaises(installer.Refused):
                installer.parse_http_redirect_hosts(value)
        self.assertEqual(installer.parse_http_redirect_hosts("STYLFITNESS.COM,www.stylfitness.com,54.156.37.31"),
                         tuple(sorted(self.HOSTS)))

    def test_prepare_selection_is_persistable_and_cannot_drift_at_cutover(self):
        hosts = installer.prepared_redirect_hosts({}, ",".join(self.HOSTS))
        state = json.loads(json.dumps({"httpRedirectHosts": list(hosts)}))
        self.assertEqual(installer.prepared_redirect_hosts(state), hosts)
        self.assertEqual(installer.prepared_redirect_hosts(state, ",".join(reversed(self.HOSTS))), hosts)
        with self.assertRaises(installer.Refused):
            installer.prepared_redirect_hosts(state, "stylfitness.com")
        with self.assertRaises(installer.Refused):
            installer.prepared_redirect_hosts({"httpRedirectHosts": "not-a-list"})
        self.assertEqual(installer.prepared_redirect_hosts({}), ())


class EnvironmentTests(unittest.TestCase):
    def test_only_two_managed_keys_change(self):
        text = "# Keep comments\nSTYL_SMTP_PASSWORD=\"do not print # literal\"\nSTYL_ANALYTICS_ENABLED=true\nSTYL_WEBSITE_LOG_DIR=/old\nSTYL_RECORDS_DIR=/other\nSTYL_GEOIP_DATABASE=/preserved\n"
        merged = installer.merge_environment(text)
        before = [line for line in text.splitlines() if not line.startswith(("STYL_WEBSITE_LOG_DIR=", "STYL_RECORDS_DIR="))]
        after = [line for line in merged.splitlines() if not line.startswith(("STYL_WEBSITE_LOG_DIR=", "STYL_RECORDS_DIR="))]
        self.assertEqual(before, after)
        self.assertIn("STYL_WEBSITE_LOG_DIR=/var/log/styl-website\n", merged)
        self.assertIn("STYL_RECORDS_DIR=/var/lib/styl-records\n", merged)
        self.assertEqual(installer.merge_environment(merged), merged)

    def test_missing_keys_are_appended_without_losing_last_line(self):
        text = "STYL_ADMIN_TOKEN=fixture-only"
        self.assertTrue(installer.merge_environment(text).startswith(text + "\n"))
        self.assertEqual(installer.merge_environment("").count("\n"), 2)

    def test_unmanaged_crlf_bytes_are_preserved(self):
        text = "STYL_SMTP_HOST=example.invalid\r\nSTYL_RECORDS_DIR=/old\r\n"
        self.assertTrue(installer.merge_environment(text).startswith("STYL_SMTP_HOST=example.invalid\r\n"))

    def test_duplicate_and_unsupported_assignments_refuse(self):
        for text in (
            "STYL_RECORDS_DIR=/old\nSTYL_RECORDS_DIR=/new\n",
            "export STYL_RECORDS_DIR=/old\n",
            "UNRELATED=continued\\\nvalue\n",
            "UNRELATED=\x00\n",
        ):
            with self.subTest(text=text[:25]), self.assertRaises(installer.Refused):
                installer.merge_environment(text)

    def test_effective_journal_policy_rejects_later_overrides(self):
        policy = (DEPLOY / "journald-operational.conf").read_text()
        installer.check_journal_policy("# installed file\n" + policy)
        for override in ("MaxRetentionSec=1day", "SystemMaxUse=20M", "Storage=volatile"):
            with self.subTest(override=override), self.assertRaises(installer.Refused):
                installer.check_journal_policy(policy + "\n[Journal]\n" + override + "\n")


class IsolatedFiles(unittest.TestCase):
    def setUp(self):
        self.directory = Path(__file__).resolve().parent / (".logging-config-test-" + uuid.uuid4().hex)
        self.directory.mkdir()
        self.addCleanup(self.cleanup)

    def cleanup(self):
        for path in self.directory.rglob("*"):
            if path.is_file() and not path.is_symlink():
                path.chmod(0o600)
        shutil.rmtree(self.directory)


class ProofTests(IsolatedFiles):
    def setUp(self):
        super().setUp()
        self.identifier = "a" * 32
        self.created = "2020-01-01T00:00:00+00:00"
        self.history = {"version": 1, "release": "release-abcdef0", "histories": []}
        self.contents = {"analytics.sqlite3": b"isolated database fixture", "restore_records.py": b"fixture"}
        for stage in ("initial", "tail"):
            name = f"journal-{stage}-fixture.gz"
            data = gzip.compress(f"__CURSOR={stage}\nMESSAGE=fixture\n\n".encode(), mtime=0)
            self.contents["website-logs/" + name] = data
            self.history["histories"].append({
                "stage": stage, "name": name, "bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest(), "capturedAt": self.created,
            })
        self.path = self.directory / f"styl-records-{self.identifier}.zip"
        self.metadata = self.write_archive()

    def write_archive(self, edit=None):
        manifest = {
            "format": "styl-private-records", "version": 1, "id": self.identifier,
            "createdAt": self.created, "cutoff": self.created,
            "websiteLogsConfigured": True,
            "files": [
                {"path": name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
                 "removable": name.startswith("website-logs/")}
                for name, data in self.contents.items()
            ],
        }
        if edit:
            edit(manifest)
        with zipfile.ZipFile(self.path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name, data in self.contents.items():
                archive.writestr(name, data)
            archive.writestr("manifest.json", json.dumps(manifest))
        size, checksum = installer.file_digest(self.path)
        return {"id": self.identifier, "filename": self.path.name, "bytes": size, "sha256": checksum,
                "createdAt": self.created, "verifiedAt": "2020-01-01T00:05:00+00:00", "archiveDeletedAt": None}

    def verify(self, metadata=None, history=None):
        return installer.verify_download_proof(
            self.path, self.metadata if metadata is None else metadata,
            self.history if history is None else history,
        )

    def test_verified_complete_archive_with_both_sealed_histories_passes_read_only(self):
        before = self.path.read_bytes()
        self.assertEqual(self.verify(), self.identifier)
        self.assertEqual(self.path.read_bytes(), before)

    def test_missing_download_acknowledgement_blocks_retention(self):
        for value in (None, "", "2020-01-01", "2999-01-01T00:00:00+00:00"):
            metadata = dict(self.metadata, verifiedAt=value)
            with self.subTest(value=value), self.assertRaises((installer.Refused, ValueError)):
                self.verify(metadata)

    def test_deleted_or_mismatched_archive_blocks_retention(self):
        for change in (
            {"archiveDeletedAt": self.created}, {"bytes": 1}, {"sha256": "0" * 64},
            {"filename": "other.zip"}, {"id": "b" * 32},
        ):
            with self.subTest(change=next(iter(change))), self.assertRaises(installer.Refused):
                self.verify(dict(self.metadata, **change))

    def test_missing_initial_or_tail_is_not_download_proof(self):
        for stage in ("initial", "tail"):
            history = deepcopy(self.history)
            history["histories"] = [item for item in history["histories"] if item["stage"] != stage]
            with self.subTest(stage=stage), self.assertRaises(installer.Refused):
                self.verify(history=history)

    def test_active_unsafe_duplicate_or_changed_history_refuses(self):
        for field, value in (
            ("name", "journal-initial.gz.active"), ("name", "../journal.gz"),
            ("sha256", "0" * 64), ("bytes", 0), ("bytes", True),
            ("stage", "tail"), ("capturedAt", None),
        ):
            history = deepcopy(self.history)
            history["histories"][0][field] = value
            with self.subTest(field=field, value=value), self.assertRaises((installer.Refused, ValueError)):
                self.verify(history=history)

    def test_zip_missing_tail_or_containing_different_tail_refuses(self):
        del self.contents["website-logs/journal-tail-fixture.gz"]
        self.metadata = self.write_archive()
        with self.assertRaises(installer.Refused):
            self.verify()
        self.contents["website-logs/journal-tail-fixture.gz"] = b"different history"
        self.metadata = self.write_archive()
        with self.assertRaises(installer.Refused):
            self.verify()

    def test_manifest_identity_format_and_coverage_are_checked(self):
        for change in (
            {"id": "b" * 32}, {"format": "other"}, {"version": 2}, {"websiteLogsConfigured": False},
            {"createdAt": "2020-01-02T00:00:00+00:00"}, {"files": []},
        ):
            self.metadata = self.write_archive(lambda manifest: manifest.update(change))
            with self.subTest(change=next(iter(change))), self.assertRaises(installer.Refused):
                self.verify()

    def test_every_entry_not_only_history_is_checksum_verified(self):
        self.metadata = self.write_archive(lambda manifest: manifest["files"][0].update(sha256="0" * 64))
        with self.assertRaises(installer.Refused):
            self.verify()

    def test_unsealed_manifest_flag_and_traversal_refuse(self):
        self.metadata = self.write_archive(lambda manifest: manifest["files"][-1].update(removable=False))
        with self.assertRaises(installer.Refused):
            self.verify()
        self.contents["../unsafe"] = b"outside"
        self.metadata = self.write_archive()
        with self.assertRaises(installer.Refused):
            self.verify()

    def test_duplicate_json_fields_refuse(self):
        with self.assertRaises(installer.Refused):
            installer.load_json('{"verifiedAt":null,"verifiedAt":"anything"}')

    def test_symlink_archive_refuses(self):
        link = self.directory / "linked.zip"
        try:
            link.symlink_to(self.path)
        except OSError:
            self.skipTest("Host does not permit symlink creation.")
        with self.assertRaises(installer.Refused):
            installer.file_digest(link)


class CommandContractTests(unittest.TestCase):
    def test_failure_does_not_expose_arguments_or_claim_journal_expiry_was_undone(self):
        output = io.StringIO()
        with (
            patch.object(sys, "argv", ["installer", "retention", "--release-dir", "private-fixture-argument"]),
            patch.object(sys, "platform", "win32"),
            redirect_stderr(output),
        ):
            self.assertEqual(installer.main(), 78)
        self.assertNotIn("private-fixture-argument", output.getvalue())
        self.assertIn("Journal limits may already have taken effect", output.getvalue())

    def test_subprocesses_are_checked_and_errors_are_not_echoed(self):
        with patch.object(installer.subprocess, "run") as command:
            installer.run(["test-command"])
        self.assertTrue(command.call_args.kwargs["check"])
        self.assertEqual(command.call_args.kwargs["stderr"], installer.subprocess.PIPE)

    def test_prepare_after_success_cannot_pause_timers(self):
        instance = object.__new__(installer.Installer)
        instance.state = {"cutover": True}
        with (
            patch.object(instance, "protect_originals"),
            patch.object(instance, "check_sources"),
            patch.object(instance, "pause_jobs") as pause,
        ):
            with self.assertRaises(installer.Refused):
                instance.prepare()
        pause.assert_not_called()

    def test_retention_without_cutover_or_coverage_never_runs_commands(self):
        instance = object.__new__(installer.Installer)
        for state, confirmed in (({}, True), ({"cutover": True}, False)):
            instance.state = state
            with (
                patch.object(instance, "check_sources"),
                patch.object(installer, "run") as command,
                self.assertRaises(installer.Refused),
            ):
                instance.retention("a" * 32, confirmed)
            command.assert_not_called()

    def test_timer_resume_preserves_enabled_but_inactive_state(self):
        instance = object.__new__(installer.Installer)
        instance.state = {"units": {
            "styl-backup.timer": {"ActiveState": "active", "UnitFileState": "enabled"},
            "styl-analytics-report.timer": {"ActiveState": "inactive", "UnitFileState": "enabled"},
        }}
        with (
            patch.object(instance, "unit_state", return_value={"UnitFileState": "enabled"}),
            patch.object(installer, "run") as command,
        ):
            instance.resume_jobs()
        command.assert_called_once_with(["systemctl", "start", "styl-backup.timer"])

    def test_no_timer_is_enabled_by_installer(self):
        source = (DEPLOY / "install-records-logging.py").read_text()
        self.assertNotIn('"enable"', source)
        self.assertNotIn('"disable"', source)
        self.assertNotIn('"vacuum', source)

    def test_changed_timer_enablement_cannot_partially_resume_jobs(self):
        instance = object.__new__(installer.Installer)
        instance.state = {"units": {
            name: {"ActiveState": "active", "UnitFileState": "enabled"} for name in installer.TIMERS
        }}
        with (
            patch.object(instance, "unit_state", side_effect=[
                {"UnitFileState": "enabled"}, {"UnitFileState": "disabled"},
            ]),
            patch.object(installer, "run") as command,
            self.assertRaises(installer.Refused),
        ):
            instance.resume_jobs()
        command.assert_not_called()

    def test_waiting_for_oneshots_does_not_kill_mail(self):
        instance = object.__new__(installer.Installer)
        instance.wait_seconds = 30
        with (
            patch.object(instance, "unit_state", side_effect=[
                {"ActiveState": "activating"}, {"ActiveState": "inactive"}, {"ActiveState": "inactive"},
            ]),
            patch.object(installer, "run") as command,
            patch.object(installer.time, "sleep"),
        ):
            instance.pause_jobs()
        self.assertEqual([call.args[0] for call in command.call_args_list], [
            ["systemctl", "stop", name] for name in installer.TIMERS
        ])

    def test_oneshot_timeout_leaves_jobs_running_and_timers_paused(self):
        instance = object.__new__(installer.Installer)
        instance.wait_seconds = 30
        with (
            patch.object(instance, "unit_state", return_value={"ActiveState": "active"}),
            patch.object(installer.time, "monotonic", side_effect=[0, 31]),
            patch.object(installer, "run") as command,
            self.assertRaises(installer.Refused),
        ):
            instance.pause_jobs()
        self.assertEqual(len(command.call_args_list), 2)
        self.assertTrue(all(call.args[0][-1].endswith(".timer") for call in command.call_args_list))

    def test_effective_override_cannot_bypass_capture(self):
        instance = object.__new__(installer.Installer)
        with (
            patch.object(installer, "run", return_value=SimpleNamespace(
                stdout=b"ExecStart={ argv[]=/unwrapped/command ; }\nKillMode=mixed\n",
            )),
            self.assertRaises(installer.Refused),
        ):
            instance.effective_capture()


class PreservationTests(IsolatedFiles):
    def setUp(self):
        super().setUp()
        self.instance = object.__new__(installer.Installer)
        self.instance.release = self.directory / "release-abcdef0"
        self.instance.history_path = self.directory / "history.json"
        self.instance.wait_seconds = 900
        self.logs = self.directory / "logs"
        self.logs.mkdir()

    def fixture_json(self, path, value):
        path.write_text(json.dumps(value), encoding="utf-8")

    def exported(self, command, **kwargs):
        if command[0] == "/bin/bash":
            kwargs["stdout"].write(gzip.compress(b"__CURSOR=fixture\nMESSAGE=private fixture\n\n", mtime=0))
        return SimpleNamespace(stdout=b"")

    def capture_patches(self):
        # Only Linux ownership/directory sync are stubbed. Gzip, hardlink,
        # publication, checksums, manifest/retry logic use real isolated files.
        from contextlib import ExitStack

        stack = ExitStack()
        stack.enter_context(patch.object(installer, "LOGS", self.logs))
        stack.enter_context(patch.object(installer, "save_json", side_effect=self.fixture_json))
        stack.enter_context(patch.object(installer, "sync_directory"))
        stack.enter_context(patch.object(installer.os, "fchmod", create=True))
        stack.enter_context(patch.object(installer.os, "chmod"))
        stack.enter_context(patch.object(installer.shutil, "disk_usage", return_value=SimpleNamespace(free=2**40)))
        return stack

    def test_history_exports_seal_hash_and_retry_without_overwrite(self):
        with self.capture_patches(), patch.object(installer, "run", side_effect=self.exported) as command:
            self.instance.capture_history("initial")
            self.instance.capture_history("initial")
            self.instance.capture_history("tail")
        self.assertEqual(len(command.call_args_list), 4)
        history = installer.load_json(self.instance.history_path.read_bytes())
        self.assertEqual(set(item["stage"] for item in history["histories"]), {"initial", "tail"})
        self.assertFalse(list(self.logs.glob("*.active")))
        for name, item in installer.history_records(history).items():
            self.assertEqual(installer.file_digest(self.logs / name), (item["bytes"], item["sha256"]))
        export_command = command.call_args_list[1].args[0]
        self.assertIn("pipefail", export_command)
        self.assertIn("--namespace='*'", export_command[-1])

    def test_failed_cutover_retry_refreshes_tail_but_preserves_prior_file_and_hash(self):
        with self.capture_patches(), patch.object(installer, "run", side_effect=self.exported):
            self.instance.capture_history("initial")
            self.instance.capture_history("tail")
            first = installer.load_json(self.instance.history_path.read_bytes())["histories"][-1]
            self.instance.capture_history("tail", refresh=True)
        history = installer.load_json(self.instance.history_path.read_bytes())
        self.assertEqual(history["supersededHistories"], [first])
        self.assertTrue((self.logs / first["name"]).is_file())
        self.assertEqual(len(list(self.logs.glob("*.gz"))), 3)
        self.assertNotEqual(history["histories"][-1]["name"], first["name"])

    def test_export_failure_never_seals_or_discards_partial_history(self):
        def fail(command, **kwargs):
            if command[0] == "/bin/bash":
                kwargs["stdout"].write(b"partial export")
                raise installer.subprocess.CalledProcessError(1, "fixture-command")
            return SimpleNamespace(stdout=b"")

        with (
            self.capture_patches(), patch.object(installer, "run", side_effect=fail),
            self.assertRaises(installer.subprocess.CalledProcessError),
        ):
            self.instance.capture_history("initial")
        self.assertFalse(self.instance.history_path.exists())
        self.assertFalse(list(self.logs.glob("*.gz")))
        self.assertEqual(len(list(self.logs.glob("*.active"))), 1)

    def test_modified_preserved_export_refuses_retry(self):
        with self.capture_patches(), patch.object(installer, "run", side_effect=self.exported):
            self.instance.capture_history("initial")
            next(self.logs.glob("*.gz")).write_bytes(b"changed")
            with self.assertRaises(installer.Refused):
                self.instance.capture_history("initial")

    def test_failed_config_transaction_restores_bytes_and_only_removes_new_config(self):
        old = self.directory / "Caddyfile"
        new = self.directory / "logging.caddy"
        history = self.directory / "retained.gz"
        old.write_bytes(b"original exact configuration")
        history.write_bytes(b"never delete")
        restored = []

        def write(path, data, mode, uid, gid):
            restored.append((path, mode, uid, gid))
            path.write_bytes(data)

        with patch.object(installer, "atomic_write", side_effect=write), patch.object(installer, "sync_directory"):
            with self.assertRaises(installer.Refused):
                with installer.configuration_transaction((old, new)):
                    old.write_bytes(b"bad candidate")
                    new.write_bytes(b"new configuration")
                    raise installer.Refused("fixture validation failure")
        self.assertEqual(old.read_bytes(), b"original exact configuration")
        self.assertFalse(new.exists())
        self.assertEqual(history.read_bytes(), b"never delete")
        self.assertEqual(restored[0][0], old)

    def test_changed_baseline_blocks_cutover(self):
        path = self.directory / "Caddyfile"
        path.write_bytes(b"original")
        self.instance.state = {"cutoverBaseline": {str(path): installer.file_digest(path)[1]}}
        self.instance.check_baseline()
        path.write_bytes(b"later independent change")
        with self.assertRaises(installer.Refused):
            self.instance.check_baseline()

    def test_installer_only_change_invalidates_pinned_phase_sources(self):
        self.assertIn("install-records-logging.py", installer.SOURCE_FILES)
        source = self.directory / "deploy"
        source.mkdir()
        for name in installer.SOURCE_FILES:
            (source / name).write_bytes(("reviewed fixture " + name).encode())
        self.instance.state = {
            "originalsSaved": True,
            "sources": {name: installer.file_digest(source / name)[1] for name in installer.SOURCE_FILES},
        }
        before = dict(self.instance.state["sources"])
        with patch.object(installer, "SOURCE", source):
            self.instance.check_sources()
            (source / "install-records-logging.py").write_bytes(b"changed installer only")
            with self.assertRaises(installer.Refused):
                self.instance.check_sources()
            for phase in (self.instance.cutover, lambda: self.instance.retention("a" * 32, True)):
                with patch.object(installer, "run") as command, self.assertRaises(installer.Refused):
                    phase()
                command.assert_not_called()
        self.assertEqual(self.instance.state["sources"], before)
        self.assertTrue(all(installer.file_digest(source / name)[1] == checksum
                            for name, checksum in before.items() if name != "install-records-logging.py"))


if __name__ == "__main__":
    unittest.main()
