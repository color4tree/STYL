import asyncio
from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import check_ai
from app import support_ai


class AIConfigurationTests(unittest.TestCase):
    def test_provider_probe_cannot_pass_via_direct_catalog_shortcut(self) -> None:
        calls = []

        class ProbeProvider:
            async def decide(self, messages, catalog, topics, model, item_ref=None):
                calls.append((model, len(catalog)))
                return support_ai.Decision(topic="pricing", references=["product:1"], fields=[],
                                           needsHuman=False, requestedModel="", evidenceIds=[]), {"total_tokens": 20}

        output = io.StringIO()
        with patch.object(support_ai, "configured", return_value=True), \
                patch.dict(support_ai.PROVIDERS, {"openai": ProbeProvider}), \
                patch.object(support_ai, "direct_catalog_answer", side_effect=AssertionError("Probe must call provider")), \
                redirect_stdout(output):
            result = asyncio.run(check_ai.check("openai", "gpt-6-luna"))
        self.assertEqual(result, 0)
        self.assertEqual(calls, [("gpt-6-luna", 1)])
        self.assertTrue(json.loads(output.getvalue())["providerDecisionVerified"])

    @unittest.skipUnless(os.name == "nt", "Windows DPAPI local-helper check")
    def test_private_provider_loaders_keep_keys_separate_and_never_print_them(self) -> None:
        root = Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory(prefix="styl-ai-key-test-") as temporary:
            directory = Path(temporary) / "STYL" / "AI"
            directory.mkdir(parents=True)
            # Native Windows PowerShell cannot load PowerShell 7's inherited security module.
            environment = {key: value for key, value in os.environ.items() if key.upper() != "PSMODULEPATH"}
            environment["LOCALAPPDATA"] = temporary
            environment.pop("OPENAI_API_KEY", None)
            environment.pop("GEMINI_API_KEY", None)
            command = """
$ErrorActionPreference = 'Stop'
$folder = Join-Path $env:LOCALAPPDATA 'STYL\\AI'
foreach ($provider in @('gemini','openai')) {
    $value = ConvertTo-SecureString ('synthetic-' + $provider + '-unit-test-only') -AsPlainText -Force
    [IO.File]::WriteAllText((Join-Path $folder ($provider + '-key.dpapi')), (ConvertFrom-SecureString $value))
    $value.Dispose()
}
& '.\\configure-local-gemini.ps1' -Action Load
if ($env:GEMINI_API_KEY -ne 'synthetic-gemini-unit-test-only' -or $env:OPENAI_API_KEY) { throw 'Gemini isolation failed' }
& '.\\configure-local-ai.ps1' -Provider OpenAI -Action Load
if ($env:OPENAI_API_KEY -ne 'synthetic-openai-unit-test-only' -or $env:GEMINI_API_KEY -ne 'synthetic-gemini-unit-test-only') { throw 'OpenAI isolation failed' }
Write-Output 'Private provider loaders verified.'
"""
            result = subprocess.run(["powershell.exe", "-NoProfile", "-Command", command], cwd=root,
                                    env=environment, capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Private provider loaders verified.", result.stdout)
            self.assertNotIn("synthetic-openai-unit-test-only", result.stdout + result.stderr)
            self.assertNotIn("synthetic-gemini-unit-test-only", result.stdout + result.stderr)
            for name in ("openai", "gemini"):
                saved = (directory / f"{name}-key.dpapi").read_text()
                self.assertNotIn(f"synthetic-{name}-unit-test-only", saved)


if __name__ == "__main__":
    unittest.main()
