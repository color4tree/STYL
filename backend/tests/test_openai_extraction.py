"""SUP-013 / KNOW-013: split extraction routes, bounded drafts and consent fencing."""

import asyncio
import base64
import hashlib
import io
import json
import os
import struct
import subprocess
from threading import Event
from unittest.mock import patch
import zlib

import httpx
from imageio_ffmpeg import get_ffmpeg_exe
from pypdf import PdfReader

from app import knowledge, knowledge_extract as extraction
from test_knowledge import BASE, FACT, KnowledgeFixture, pdf


OPENAI_KEY = "synthetic-openai-key"
GEMINI_KEY = "synthetic-gemini-key"
VIDEO = b"\x00\x00\x00\x18ftypisom" + b"\x00" * 32


def valid_png() -> bytes:
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">2I5B", 1, 1, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(b"\x00\x00\x00\x00")) + chunk(b"IEND", b""))


def completed(facts=None, warnings=None) -> dict:
    return {
        "status": "completed",
        "output": [{"type": "message", "role": "assistant", "status": "completed",
                    "content": [{"type": "output_text", "text": json.dumps({
                        "facts": [FACT] if facts is None else facts, "warnings": warnings or [],
                    })}]}],
        "usage": {"input_tokens": 15, "output_tokens": 10, "total_tokens": 25},
    }


class OpenAIExtractionTests(KnowledgeFixture):
    def setUp(self):
        super().setUp()
        replacement = patch.dict(os.environ, {
            "STYL_SUPPORT_PROVIDER": "openai", "STYL_SUPPORT_MODEL": "gpt-6-luna",
            "STYL_KNOWLEDGE_PROVIDER": "openai", "STYL_KNOWLEDGE_MODEL": "gpt-6-luna",
            "STYL_KNOWLEDGE_VIDEO_PROVIDER": "gemini", "STYL_KNOWLEDGE_VIDEO_MODEL": "gemini-3.8-flash",
            "OPENAI_API_KEY": OPENAI_KEY, "GEMINI_API_KEY": GEMINI_KEY,
        })
        replacement.start()
        self.addCleanup(replacement.stop)
        self.path = self.uploads / "fixture.png"
        self.path.write_bytes(valid_png())

    def transport(self, handler):
        def checked(request):
            if request.url.host == "api.openai.com":
                self.assertEqual(str(request.url), extraction.OPENAI_URL)
                self.assertEqual(request.method, "POST")
                self.assertEqual(request.headers["authorization"], f"Bearer {OPENAI_KEY}")
                self.assertNotIn("x-goog-api-key", request.headers)
                self.assertNotIn(GEMINI_KEY, str(request.headers) + str(request.content))
            else:
                self.assertEqual(request.url.host, "generativelanguage.googleapis.com")
                self.assertEqual(request.headers["x-goog-api-key"], GEMINI_KEY)
                self.assertNotIn("authorization", request.headers)
                self.assertNotIn(OPENAI_KEY, str(request.headers) + str(request.content))
            return handler(request)
        return self.provider(checked)

    def test_know_013_defaults_are_kind_specific_and_independent_of_chat(self):
        with patch.dict(os.environ):
            for name in ("STYL_KNOWLEDGE_PROVIDER", "STYL_KNOWLEDGE_MODEL",
                         "STYL_KNOWLEDGE_VIDEO_PROVIDER", "STYL_KNOWLEDGE_VIDEO_MODEL"):
                os.environ.pop(name, None)
            os.environ["STYL_SUPPORT_MODEL"] = "different-chat-model"
            for kind in ("image", "pdf", "docx", "text"):
                self.assertEqual(extraction.provider_settings(kind), ("openai", "gpt-6-luna"))
            self.assertEqual(extraction.provider_settings("video"), ("gemini", "gemini-3.8-flash"))
            index = self.client.get(BASE, headers=self.admin).json()
            self.assertEqual(index["provider"], "openai")
            self.assertEqual(index["routes"], {
                "image": {"provider": "openai", "model": "gpt-6-luna"},
                "pdf": {"provider": "openai", "model": "gpt-6-luna"},
                "docx": {"provider": "openai", "model": "gpt-6-luna"},
                "text": {"provider": "openai", "model": "gpt-6-luna"},
                "video": {"provider": "gemini", "model": "gemini-3.8-flash"},
                "chat": {"provider": "openai", "model": "different-chat-model"},
            })
            self.assertNotIn(OPENAI_KEY, json.dumps(index))
            self.assertNotIn(GEMINI_KEY, json.dumps(index))

    def test_know_013_stale_viewed_route_cannot_queue_new_provider_at_same_revision(self):
        source = self.upload(valid_png()).json()
        with patch.dict(os.environ, {"STYL_KNOWLEDGE_PROVIDER": "gemini", "STYL_KNOWLEDGE_MODEL": "gemini-3.8-flash"}):
            viewed = self.client.get(BASE, headers=self.admin).json()
        body = {
            "expectedRevision": source["revision"], "acknowledgeExternalProcessing": True,
            "expectedRouteFingerprint": viewed["routeFingerprint"],
        }
        url = BASE + f"/sources/{source['id']}/extract"
        response = self.client.post(url, headers=self.admin, json=body)
        self.assertEqual(response.status_code, 409, response.text)
        self.assertIn("Reload and reconfirm", response.json()["detail"])
        self.assertEqual(response.headers["cache-control"], "private, no-store")
        current = self.get(source["id"])
        self.assertEqual((current["state"], current["revision"]), ("pending", source["revision"]))
        self.assertIsNone(current["provider"])
        fresh = self.client.get(BASE, headers=self.admin).json()
        self.assertNotEqual(fresh["routeFingerprint"], viewed["routeFingerprint"])
        body["expectedRouteFingerprint"] = fresh["routeFingerprint"]
        response = self.client.post(url, headers=self.admin, json=body)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["state"], "queued")
        self.assertEqual((response.json()["provider"], response.json()["model"]), ("openai", "gpt-6-luna"))

    def test_know_013_bulk_stale_consent_rejects_every_source_before_queueing(self):
        sources = [self.upload(valid_png()).json(), self.upload(pdf(1), "manual.pdf", "application/pdf").json(),
                   self.upload(VIDEO, "clip.mp4", "video/mp4").json()]
        viewed = self.client.get(BASE, headers=self.admin).json()
        body = {"acknowledgeExternalProcessing": True, "expectedRouteFingerprint": viewed["routeFingerprint"]}
        with patch.dict(os.environ, {"STYL_KNOWLEDGE_VIDEO_MODEL": "gemini-changed"}):
            response = self.client.post(BASE + "/extract-pending", headers=self.admin, json=body)
            self.assertEqual(response.status_code, 409, response.text)
            with knowledge._connection() as db:
                for source in sources:
                    row = knowledge._source(db, source["id"])
                    self.assertEqual((row["state"], row["revision"], row["attempts"]),
                                     ("pending", source["revision"], 0))
                    self.assertIsNone(row["extraction_provider"])
                self.assertEqual(db.execute("SELECT COUNT(*) FROM knowledge_versions").fetchone()[0], 0)
            body["expectedRouteFingerprint"] = self.route_fingerprint()
            response = self.client.post(BASE + "/extract-pending", headers=self.admin, json=body)
            self.assertEqual(response.status_code, 200, response.text)
            self.assertTrue(all(source["state"] == "queued" for source in response.json()["sources"]))
            video = next(source for source in response.json()["sources"] if source["kind"] == "video")
            self.assertEqual(video["model"], "gemini-changed")

    def test_know_013_missing_or_unknown_fingerprint_rejected_for_both_queue_endpoints(self):
        source = self.upload(valid_png()).json()
        for value in ({}, {"expectedRouteFingerprint": None}, {"expectedRouteFingerprint": ""},
                      {"expectedRouteFingerprint": "0" * 64}):
            for bulk in (False, True):
                with self.subTest(value=value, bulk=bulk):
                    body = {"acknowledgeExternalProcessing": True, **value}
                    suffix = "/extract-pending" if bulk else f"/sources/{source['id']}/extract"
                    if not bulk:
                        body["expectedRevision"] = source["revision"]
                    response = self.client.post(BASE + suffix, headers=self.admin, json=body)
                    self.assertEqual(response.status_code, 409, response.text)
                    current = self.get(source["id"])
                    self.assertEqual((current["state"], current["revision"]), ("pending", source["revision"]))
        self.assertFalse(asyncio.run(knowledge.process_one()))

    def test_know_013_route_fingerprint_canonical_private_and_stable_for_chat_only_changes(self):
        source = self.upload(valid_png()).json()
        viewed = self.client.get(BASE, headers=self.admin).json()
        tuples = [(kind, viewed["routes"][kind]["provider"], viewed["routes"][kind]["model"])
                  for kind in sorted(("image", "pdf", "docx", "text", "video"))]
        expected = hashlib.sha256(json.dumps(tuples, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()
        self.assertEqual(viewed["routeFingerprint"], expected)
        with patch.dict(os.environ, {"STYL_SUPPORT_PROVIDER": "gemini", "STYL_SUPPORT_MODEL": "gemini-chat-only",
                                     "OPENAI_API_KEY": "rotated-openai-key", "GEMINI_API_KEY": "rotated-gemini-key"}):
            current = self.client.get(BASE, headers=self.admin).json()
            self.assertNotEqual(current["routes"]["chat"], viewed["routes"]["chat"])
            self.assertEqual(current["routeFingerprint"], expected)
            self.assertNotIn("rotated-", json.dumps(current))
            response = self.client.post(BASE + f"/sources/{source['id']}/extract", headers=self.admin, json={
                "expectedRevision": source["revision"], "acknowledgeExternalProcessing": True,
                "expectedRouteFingerprint": expected,
            })
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()["provider"], "openai")

    def test_know_013_queue_pins_acknowledged_route_if_config_changes_after_consent_check(self):
        source = self.upload(valid_png()).json()
        viewed = self.client.get(BASE, headers=self.admin).json()
        original_queue = knowledge._queue

        def change_config(db, row, catalog, route):
            os.environ["STYL_KNOWLEDGE_MODEL"] = "gpt-changed"
            return original_queue(db, row, catalog, route)

        with patch.dict(os.environ), patch.object(knowledge, "_queue", side_effect=change_config):
            response = self.client.post(BASE + f"/sources/{source['id']}/extract", headers=self.admin, json={
                "expectedRevision": source["revision"], "acknowledgeExternalProcessing": True,
                "expectedRouteFingerprint": viewed["routeFingerprint"],
            })
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()["model"], "gpt-6-luna")
            with patch.object(extraction, "extract") as provider:
                self.assertFalse(asyncio.run(knowledge.process_one()))
                provider.assert_not_called()
            self.assertEqual(self.get(source["id"])["state"], "paused")

    def test_know_013_image_inline_strict_schema_without_remote_files(self):
        calls, tracked, removed = [], [], []

        def handler(request):
            calls.append(request)
            return httpx.Response(200, json=completed())

        with self.transport(handler):
            result = extraction.extract(self.path, "image", track=tracked.append, untrack=removed.append)
        self.assertEqual(result.facts, [FACT])
        self.assertEqual(tracked, [])
        self.assertEqual(removed, [])
        self.assertEqual(len(calls), 1)
        body = json.loads(calls[0].content)
        self.assertEqual(body["model"], "gpt-6-luna")
        self.assertIs(body["store"], False)
        self.assertEqual(body["reasoning"], {"effort": "none"})
        self.assertEqual(body["max_output_tokens"], 16384)
        self.assertNotIn("tools", body)
        schema = body["text"]["format"]
        self.assertTrue(schema["strict"])
        self.assertEqual(schema["type"], "json_schema")
        self.assertFalse(schema["schema"]["additionalProperties"])
        self.assertEqual(set(schema["schema"]["required"]), {"facts", "warnings"})
        image = body["input"][0]["content"][1]
        self.assertEqual(image["type"], "input_image")
        self.assertEqual(image["image_url"], "data:image/png;base64," + base64.b64encode(valid_png()).decode())
        self.assertNotIn(str(self.root), json.dumps(body))
        self.assertIn("untrusted DATA", body["instructions"])

    def test_know_013_jpeg_webp_decoding_and_mime_preserved(self):
        for extension, mime in ((".jpg", "image/jpeg"), (".webp", "image/webp")):
            with self.subTest(extension=extension):
                path = self.root / ("fixture" + extension)
                subprocess.run([get_ffmpeg_exe(), "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
                                "-i", str(self.path), "-frames:v", "1", "-update", "1", str(path)],
                               check=True, capture_output=True, timeout=30)
                calls = []
                with self.transport(lambda request: calls.append(request) or httpx.Response(200, json=completed())):
                    self.assertEqual(extraction.extract(path, "image").facts, [FACT])
                part = json.loads(calls[0].content)["input"][0]["content"][1]
                self.assertEqual(part["image_url"], f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode())

    def test_know_013_pdf_all_native_pages_and_visual_groups_retained(self):
        path = self.root / "private-name-not-to-send.pdf"
        path.write_bytes(pdf(7))
        calls = []
        with self.transport(lambda request: calls.append(request) or httpx.Response(200, json=completed())), \
                patch.object(extraction, "INLINE_BYTES", 1), \
                patch.object(extraction, "_upload", side_effect=AssertionError("OpenAI must use inline files")):
            result = extraction.extract(path, "pdf")
        self.assertEqual(len(calls), 2)
        self.assertEqual(len(result.facts), 9)
        for number in range(1, 8):
            self.assertIn(f"Synthetic feature on page {number}", "\n".join(fact["text"] for fact in result.facts))
        for number, (request, pages, context) in enumerate(zip(calls, (5, 2), ("1–5", "6–7")), 1):
            parts = json.loads(request.content)["input"][0]["content"]
            self.assertIn(context, parts[0]["text"])
            self.assertEqual(parts[1]["type"], "input_file")
            self.assertEqual(parts[1]["filename"], f"source-pages-{number}.pdf")
            prefix, encoded = parts[1]["file_data"].split(",", 1)
            self.assertEqual(prefix, "data:application/pdf;base64")
            self.assertEqual(len(PdfReader(io.BytesIO(base64.b64decode(encoded))).pages), pages)
            self.assertNotIn("private-name", request.content.decode())

    def test_know_013_refusal_truncation_and_invalid_drafts_fail_closed(self):
        refused = completed()
        refused["output"][0]["content"] = [{"type": "refusal", "refusal": "PRIVATE_REFUSAL_DETAIL"}]
        incomplete = {**completed(), "status": "incomplete", "incomplete_details": {"reason": "max_output_tokens"}}
        malformed = completed()
        malformed["output"][0]["content"][0]["text"] = "invalid json PRIVATE_PROVIDER_DETAIL"
        bad_message = completed()
        bad_message["output"][0]["status"] = "incomplete"
        for body in (refused, incomplete, malformed, bad_message, [],
                     completed(facts=[{**FACT, "unexpected": "field"}]),
                     completed(facts=[{**FACT, "topic": "pricing"}]),
                     completed(warnings=["x" * 501]), completed(facts=[])):
            with self.subTest(body_type=type(body).__name__), \
                    self.transport(lambda request: httpx.Response(200, json=body)):
                with self.assertRaises(extraction.ExtractionError) as failure:
                    extraction.extract(self.path, "image")
                self.assertFalse(failure.exception.retryable)
                self.assertNotIn("PRIVATE_", str(failure.exception))

    def test_know_013_bounded_response_and_timeout_safe(self):
        with patch.object(extraction, "RESPONSE_BYTES", 64), \
                self.transport(lambda request: httpx.Response(200, content=b"x" * 65)):
            with self.assertRaisesRegex(extraction.ExtractionError, "exceeds review limits"):
                extraction.extract(self.path, "image")

        def timeout(request):
            raise httpx.ReadTimeout("PRIVATE_NETWORK_DETAIL", request=request)

        with self.transport(timeout):
            with self.assertRaises(extraction.ExtractionError) as failure:
                extraction.extract(self.path, "image")
        self.assertTrue(failure.exception.retryable)
        self.assertNotIn("PRIVATE_", str(failure.exception))

    def test_know_013_quota_service_and_redirect_never_fall_back(self):
        for status in (429, 503, 401, 302):
            calls = []
            with self.subTest(status=status), self.transport(
                lambda request: calls.append(request) or httpx.Response(
                    status, headers={"retry-after": "99999", "location": extraction.HOST},
                    json={"error": "PRIVATE_ERROR"},
                )
            ):
                with self.assertRaises(extraction.ExtractionError) as failure:
                    extraction.extract(self.path, "image")
            self.assertEqual(len(calls), 1)
            self.assertEqual(failure.exception.retryable, status in (429, 503))
            self.assertEqual(failure.exception.retry_after, 3600 if status in (429, 503) else 60)
            self.assertNotIn("PRIVATE_ERROR", str(failure.exception))

    def test_know_013_missing_key_unsupported_video_and_model_do_not_send(self):
        for values, kind in (
            ({"OPENAI_API_KEY": ""}, "image"),
            ({"STYL_KNOWLEDGE_VIDEO_PROVIDER": "openai"}, "video"),
            ({"STYL_KNOWLEDGE_PROVIDER": "unknown"}, "image"),
            ({"STYL_KNOWLEDGE_MODEL": "gemini-3.8-flash"}, "pdf"),
        ):
            with self.subTest(values=values), patch.dict(os.environ, values), \
                    patch.object(extraction.httpx, "Client", side_effect=AssertionError("No network")):
                with self.assertRaises(extraction.ExtractionError):
                    extraction.extract(self.path, kind)

    def test_know_013_invalid_images_and_existing_conversion_limits(self):
        for extension, data, message in (
            (".svg", b"<svg></svg>", "PNG/JPEG rendering"),
            (".gif", b"GIF89a;", "multiple frames"),
            (".png", valid_png()[:-12], "signature"),
        ):
            path = self.root / ("invalid" + extension)
            path.write_bytes(data)
            with self.subTest(extension=extension), \
                    patch.object(extraction.httpx, "Client", side_effect=AssertionError("No network")):
                with self.assertRaisesRegex(extraction.ExtractionError, message):
                    extraction.extract(path, "image")
        with patch.object(extraction, "IMAGE_BYTES", 1), \
                patch.object(extraction.httpx, "Client", side_effect=AssertionError("No network")):
            with self.assertRaisesRegex(extraction.ExtractionError, "exceeds"):
                extraction.extract(self.path, "image")

    def test_know_013_mock_overrides_all_keys_and_cleanup_without_http(self):
        source = self.upload().json()
        knowledge._track(source["id"], source["revision"], "files/retained")
        paths = {"image": self.path, "pdf": self.root / "fixture.pdf", "video": self.root / "clip.mp4"}
        paths["pdf"].write_bytes(pdf(1))
        paths["video"].write_bytes(VIDEO)
        with patch.dict(os.environ, {"STYL_SUPPORT_PROVIDER": "mock"}), \
                patch.object(extraction, "_video"), \
                patch.object(extraction.httpx, "Client", side_effect=AssertionError("Mock must never use HTTP")):
            for kind, path in paths.items():
                self.assertEqual(extraction.provider_settings(kind), ("mock", "mock"))
                self.assertTrue(extraction.extract(path, kind).facts)
            self.assertFalse(knowledge._cleanup_one())
            with self.assertRaises(extraction.ExtractionError):
                extraction.cleanup_file("files/retained")
        with knowledge._connection() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM knowledge_uploads").fetchone()[0], 1)

    def test_know_013_video_uses_only_gemini_files_and_cleanup_with_openai_chat(self):
        path = self.root / "clip.mp4"
        path.write_bytes(VIDEO)
        calls, tracked, removed = [], [], []

        def handler(request):
            calls.append(request)
            if request.method == "DELETE":
                return httpx.Response(204)
            if request.url.path == "/upload/v1beta/files":
                if not request.url.query:
                    return httpx.Response(200, headers={"x-goog-upload-url": extraction.HOST + "/upload/v1beta/files?id=fixture"})
                self.assertEqual(request.content, VIDEO)
                return httpx.Response(200, json={"file": {"name": "files/clip", "state": "ACTIVE"}})
            self.assertEqual(request.url.path, "/v1beta/models/gemini-3.8-flash:generateContent")
            return self.generated()

        with self.transport(handler), patch.object(extraction, "_video"):
            self.assertEqual(extraction.extract(path, "video", track=tracked.append, untrack=removed.append).facts, [FACT])
        self.assertEqual(tracked, ["files/clip"])
        self.assertEqual(removed, tracked)
        self.assertEqual([request.method for request in calls], ["POST", "POST", "POST", "DELETE"])
        source = self.upload().json()
        knowledge._track(source["id"], source["revision"], "files/retained-gemini")
        with self.transport(handler):
            self.assertTrue(knowledge._cleanup_one())
        self.assertEqual(calls[-1].url.path, "/v1beta/files/retained-gemini")

    def test_know_013_video_route_switch_prevents_upload_or_generation_and_cleans_up(self):
        path = self.root / "clip.mp4"
        path.write_bytes(VIDEO)
        for stage in ("start", "processing"):
            calls, tracked, removed = [], [], []

            def handler(request):
                calls.append(request)
                if request.method == "DELETE":
                    return httpx.Response(204)
                if not request.url.query:
                    if stage == "start":
                        os.environ["STYL_KNOWLEDGE_VIDEO_MODEL"] = "gemini-changed"
                    return httpx.Response(200, headers={
                        "x-goog-upload-url": extraction.HOST + "/upload/v1beta/files?id=fixture",
                    })
                os.environ["STYL_KNOWLEDGE_VIDEO_MODEL"] = "gemini-changed"
                return httpx.Response(200, json={"file": {"name": "files/clip", "state": "PROCESSING"}})

            with self.subTest(stage=stage), patch.dict(os.environ), self.transport(handler), \
                    patch.object(extraction, "_video"):
                with self.assertRaises(extraction.ExtractionCancelled):
                    extraction.extract(path, "video", track=tracked.append, untrack=removed.append)
            if stage == "start":
                self.assertEqual(len(calls), 1)
                self.assertEqual(tracked, [])
            else:
                self.assertEqual([request.method for request in calls], ["POST", "POST", "DELETE"])
                self.assertEqual(tracked, ["files/clip"])
                self.assertEqual(removed, tracked)

    def test_know_013_openai_quota_pauses_images_and_pdfs_but_video_continues(self):
        image = self.upload(valid_png()).json()
        document = self.upload(pdf(1), "manual.pdf", "application/pdf").json()
        video = self.upload(VIDEO, "clip.mp4", "video/mp4").json()
        for source in (image, document, video):
            self.queue(source)

        def result(path, kind, **kwargs):
            if kind == "image":
                self.assertEqual(kwargs["expected_route"], ("openai", "gpt-6-luna"))
                raise extraction.ExtractionError("Quota", retryable=True)
            self.assertEqual(kind, "video")
            self.assertEqual(kwargs["expected_route"], ("gemini", "gemini-3.8-flash"))
            return extraction.ExtractionResult([FACT], [])

        with patch.object(extraction, "extract", side_effect=result) as provider:
            self.assertTrue(asyncio.run(knowledge.process_one()))
            self.assertTrue(asyncio.run(knowledge.process_one()))
            self.assertFalse(asyncio.run(knowledge.process_one()))
            self.assertEqual(provider.call_count, 2)
        self.assertEqual(self.get(image["id"])["state"], "paused")
        self.assertEqual(self.get(document["id"])["state"], "queued")
        self.assertEqual(self.get(video["id"])["state"], "review")
        with knowledge._connection() as db:
            self.assertEqual(tuple(db.execute("SELECT provider,model FROM knowledge_provider_cooldowns").fetchone()),
                             ("openai", "gpt-6-luna"))
            self.assertEqual(knowledge._source(db, document["id"])["attempts"], 0)

    def test_know_013_video_cooldown_does_not_block_nonvideo(self):
        first = self.upload(VIDEO, "first.mp4", "video/mp4").json()
        second = self.upload(VIDEO, "second.mp4", "video/mp4").json()
        image = self.upload(valid_png()).json()
        for source in (first, second, image):
            self.queue(source)

        def result(path, kind, **kwargs):
            if kind == "video":
                raise extraction.ExtractionError("Quota", retryable=True)
            return extraction.ExtractionResult([FACT], [])

        with patch.object(extraction, "extract", side_effect=result) as provider:
            self.assertTrue(asyncio.run(knowledge.process_one()))
            self.assertTrue(asyncio.run(knowledge.process_one()))
            self.assertFalse(asyncio.run(knowledge.process_one()))
            self.assertEqual(provider.call_count, 2)
        self.assertEqual(self.get(second["id"])["state"], "queued")
        self.assertEqual(self.get(image["id"])["state"], "review")
        with knowledge._connection() as db:
            self.assertEqual(tuple(db.execute("SELECT provider,model FROM knowledge_provider_cooldowns").fetchone()),
                             ("gemini", "gemini-3.8-flash"))

    def test_know_013_config_switch_requires_explicit_requeue_at_claim_and_runtime(self):
        for stage in ("queued", "claimed"):
            with self.subTest(stage=stage):
                source = self.upload(valid_png()).json()
                self.queue(source)
                job = knowledge._claim() if stage == "claimed" else None
                with patch.dict(os.environ, {"STYL_KNOWLEDGE_PROVIDER": "gemini", "STYL_KNOWLEDGE_MODEL": "gemini-3.8-flash"}), \
                        patch.object(extraction, "extract") as provider:
                    if job:
                        knowledge._process(job)
                    else:
                        self.assertIsNone(knowledge._claim())
                    provider.assert_not_called()
                    paused = self.get(source["id"])
                    self.assertEqual(paused["state"], "paused")
                    self.assertEqual(paused["provider"], "openai")
                    self.assertEqual(paused["facts"], [])
                    self.assertEqual(self.queue(paused)["provider"], "gemini")
                # Restore config: the newly acknowledged Gemini job must not silently use OpenAI.
                self.assertIsNone(knowledge._claim())
                self.assertEqual(self.get(source["id"])["state"], "paused")

    def test_know_013_legacy_queue_migrates_without_automatic_upload(self):
        source = self.upload(valid_png()).json()
        self.queue(source)
        with knowledge._connection() as db:
            db.execute("ALTER TABLE knowledge_sources DROP COLUMN extraction_provider")
            db.execute("ALTER TABLE knowledge_sources DROP COLUMN extraction_model")
        with patch.object(extraction, "extract") as provider:
            self.assertFalse(asyncio.run(knowledge.process_one()))
            provider.assert_not_called()
        paused = self.get(source["id"])
        self.assertEqual(paused["state"], "paused")
        self.assertIsNone(paused["provider"])
        self.assertIsNone(paused["model"])
        self.assertEqual(self.queue(paused)["provider"], "openai")

    def test_know_013_partial_pdf_refusal_cancellation_and_config_change_publish_nothing(self):
        for failure in ("refusal", "cancel", "config"):
            with self.subTest(failure=failure):
                source = self.upload(pdf(7), failure + ".pdf", "application/pdf").json()
                self.queue(source)
                job = knowledge._claim()
                interrupted = Event()
                calls = []

                def handler(request):
                    calls.append(request)
                    if len(calls) == 1:
                        if failure == "cancel":
                            interrupted.set()
                        elif failure == "config":
                            os.environ["STYL_KNOWLEDGE_MODEL"] = "gpt-other"
                        return httpx.Response(200, json=completed())
                    body = completed()
                    body["output"][0]["content"] = [{"type": "refusal", "refusal": "PRIVATE_DETAIL"}]
                    return httpx.Response(200, json=body)

                with patch.dict(os.environ), self.transport(handler):
                    knowledge._process(job, interrupted)
                current = self.get(source["id"])
                self.assertEqual(current["state"], "failed" if failure == "refusal" else "paused")
                self.assertEqual(current["facts"], [])
                self.assertEqual(len(calls), 2 if failure == "refusal" else 1)
                self.assertEqual(knowledge.approved_facts(self.catalog()), {})

    def test_know_013_review_restart_and_source_version_remain_human_gated(self):
        source = self.upload(valid_png()).json()
        queued = self.queue(source)
        self.assertEqual((queued["provider"], queued["model"]), ("openai", "gpt-6-luna"))
        self.assertEqual(knowledge.recover_interrupted(), 0)
        with self.transport(lambda request: httpx.Response(200, json=completed())):
            self.assertTrue(asyncio.run(knowledge.process_one()))
        current = self.get(source["id"])
        self.assertEqual(current["state"], "review")
        self.assertEqual(knowledge.approved_facts(self.catalog()), {})
        self.assertEqual(self.review(queued).status_code, 409)
        self.assertEqual(self.review(current).status_code, 200)
        self.assertTrue(knowledge.approved_facts(self.catalog()))
        with knowledge.catalog_delete_guard("product:1"):
            pass
        self.assertEqual(knowledge.approved_facts(self.catalog()), {})
