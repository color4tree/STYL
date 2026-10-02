"""KNOW-014..018: document formats, general policies, scope identity and safe snapshots."""

import asyncio
from contextlib import closing
import hashlib
import io
import json
import os
from pathlib import Path
import sqlite3
import struct
from unittest.mock import patch
import warnings
import zipfile

import httpx

from app import knowledge, knowledge_extract as extraction, support
from test_knowledge import BASE, FACT, KnowledgeFixture, PNG, pdf


WORD_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
WORD_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
CONTENT_TYPES = (
    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.'
    'wordprocessingml.document.main+xml"/></Types>'
)
WORD_BODY = (
    '<w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr><w:r><w:t>Shipping policy</w:t></w:r></w:p>'
    '<w:p><w:r><w:t>Shipping takes five business days.</w:t></w:r></w:p>'
    '<w:tbl><w:tr><w:tc><w:p><w:r><w:t>Returns</w:t></w:r></w:p></w:tc>'
    '<w:tc><w:p><w:r><w:t>Request returns within thirty days.</w:t></w:r></w:p></w:tc></w:tr></w:tbl>'
    '<w:p><w:r><w:t>FINAL paragraph: warranty support requires an order reference.</w:t></w:r></w:p>'
    '<w:tbl><w:tr><w:tc><w:p><w:r><w:t>FINAL table: support reviews warranty claims.</w:t>'
    '</w:r></w:p></w:tc></w:tr></w:tbl>'
)
POLICY = {"text": "Shipping takes five business days.", "topic": "customer_service", "location": "Paragraph 2"}


def docx(body=WORD_BODY, entries=(), document=None, content_types=CONTENT_TYPES, compression=zipfile.ZIP_DEFLATED):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", compression=compression) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("word/document.xml", document if document is not None else
                         f'<w:document xmlns:w="{WORD_NS}"><w:body>{body}</w:body></w:document>')
        for name, data in entries:
            archive.writestr(name, data)
    return stream.getvalue()


def response(facts=None):
    return httpx.Response(200, json={
        "status": "completed",
        "output": [{"type": "message", "role": "assistant", "status": "completed",
                    "content": [{"type": "output_text", "text": json.dumps({
                        "facts": [POLICY] if facts is None else facts, "warnings": [],
                    })}]}],
    })


class DocumentFormatTests(KnowledgeFixture):
    def general(self, data=b"Shipping takes five business days.", filename="policy.txt", mime="text/plain"):
        result = self.upload(data, filename, mime, refs=[], scope="general", title="Customer service policy")
        self.assertEqual(result.status_code, 201, result.text)
        return result.json()

    def approve_general(self):
        source = self.general()
        with patch.dict(os.environ, {"STYL_SUPPORT_PROVIDER": "mock"}):
            self.queue(source)
            self.assertTrue(asyncio.run(knowledge.process_one()))
        result = self.review(self.get(source["id"]), facts=[POLICY])
        self.assertEqual(result.status_code, 200, result.text)
        return result.json()

    def test_know_014_supported_formats_metadata_and_private_attachment(self):
        for data, filename, mime, kind in (
            (pdf(1), "manual.PDF", "application/pdf", "pdf"),
            (docx(), "policy.docx", WORD_MIME, "docx"),
            (b"\xef\xbb\xbfSteel frame.\n\nFinal paragraph.", "readme.txt", "text/plain; charset=utf-8", "text"),
            (b"# Materials\n\nSteel frame.", "readme.md", "text/markdown", "text"),
            (b"# Materials\n\nSteel frame.", "readme.md", "text/plain", "text"),
        ):
            with self.subTest(filename=filename, mime=mime):
                result = self.upload(data, filename, mime)
                self.assertEqual(result.status_code, 201, result.text)
                source = result.json()
                self.assertEqual((source["kind"], source["scope"], source["format"], source["bytes"]),
                                 (kind, "products", Path(filename).suffix[1:].lower(), len(data)))
                downloaded = self.client.get(BASE + f"/sources/{source['id']}/file", headers=self.admin)
                self.assertEqual(downloaded.content, data)
                self.assertEqual(downloaded.headers["x-content-type-options"], "nosniff")
                self.assertIn("attachment", downloaded.headers["content-disposition"])
                self.assertEqual(downloaded.headers["cache-control"], "private, no-store")
        index = self.client.get(BASE, headers=self.admin).json()
        self.assertEqual(index["documentCount"], 5)
        self.assertEqual(index["approvedDocumentCount"], 0)
        self.assertIn("docx", index["routes"])
        self.assertIn("text", index["routes"])
        self.assertTrue(all(knowledge.BLOB_NAME.fullmatch(path.name)
                            for path in knowledge.configured_directory().iterdir()))

    def test_know_014_text_invalid_mime_utf8_binary_empty_and_bounds(self):
        for data in (b"", b" \n\t", b"\xff", b"hello\x00world", b"\x01bad", "a\u0085b".encode()):
            with self.subTest(data=data):
                self.assertEqual(self.upload(data, "policy.txt", "text/plain").status_code, 422)
        self.assertEqual(self.upload(b"Text", "policy.txt", "application/pdf").status_code, 422)
        self.assertEqual(self.upload(PNG, "policy.docx", WORD_MIME).status_code, 422)
        with patch.object(extraction, "MAX_TEXT", 4):
            self.assertEqual(self.upload(b"First\n\nLast", "policy.md", "text/markdown").status_code, 422)
        with patch.dict(knowledge.LIMITS, {"documentBytes": 4}):
            self.assertEqual(self.upload(b"12345", "policy.txt", "text/plain").status_code, 413)
        with patch.object(extraction, "MAX_FACTS", 1):
            self.assertEqual(self.upload(b"First\n\nLast", "policy.txt", "text/plain").status_code, 422)

    def test_know_014_docx_rejects_traversal_duplicate_encryption_macros_ole_and_unsafe_xml(self):
        bad_relationship = ('<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                            '<Relationship Id="rId1" Type="hyperlink" Target="https://example.invalid" '
                            'TargetMode="External"/></Relationships>')
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            duplicate = docx(entries=[("word/document.xml", "<bad/>")])
        encrypted = bytearray(docx())
        for marker, offset in ((b"PK\x03\x04", 6), (b"PK\x01\x02", 8)):
            cursor = 0
            while (cursor := encrypted.find(marker, cursor)) >= 0:
                struct.pack_into("<H", encrypted, cursor + offset,
                                 struct.unpack_from("<H", encrypted, cursor + offset)[0] | 1)
                cursor += 4
        cases = [
            docx(entries=[("../escape.xml", "<x/>")]),
            docx(entries=[("/absolute.xml", "<x/>")]),
            docx(entries=[("word/escape.xml", "<x/>")]).replace(b"word/escape.xml", b"word\\escape.xml"),
            docx(entries=[("word/./escape.xml", "<x/>")]),
            duplicate, bytes(encrypted), docx(entries=[("word/vbaProject.bin", b"not executed")]),
            docx(entries=[("word/_rels/document.xml.rels", bad_relationship.replace('Type="hyperlink"', 'Type="oleObject"'))]),
            docx(entries=[("word/embeddings/object.bin", b"unsafe object")]),
            docx(entries=[("word/_rels/document.xml.rels", bad_relationship.replace("https://example.invalid", "../escape"))]),
            docx(entries=[("word/_rels/document.xml.rels", bad_relationship.replace(
                'Target="https://example.invalid" TargetMode="External"', 'Target="%2e%2e/escape" TargetMode="Internal"'))]),
            docx(document=f'<!DOCTYPE w:document [<!ENTITY bad "expanded">]><w:document xmlns:w="{WORD_NS}"/>'),
            docx(document='<w:document malformed'),
            docx(content_types=CONTENT_TYPES.replace("wordprocessingml.document.main", "ms-word.document.macroEnabled.main")),
            docx(body="<w:sdt><w:sdtContent><w:p/></w:sdtContent></w:sdt>"),
            docx(body="<w:p><w:r><w:t> </w:t></w:r></w:p>"),
        ]
        for number, data in enumerate(cases):
            with self.subTest(number=number):
                result = self.upload(data, "unsafe.docx", WORD_MIME)
                self.assertEqual(result.status_code, 422, result.text)
        self.assertFalse(knowledge.configured_directory().exists())

    def test_know_014_docx_external_links_inert_and_linked_content_coverage_explicit(self):
        target = "https://example.invalid/EXTERNAL_TARGET_NOT_TO_BE_FETCHED"
        hyperlink = ('<w:p><w:hyperlink xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
                     'r:id="rId1"><w:r><w:t>Review return guidance.</w:t></w:r></w:hyperlink></w:p>')
        for relationship in ("hyperlink", "image", "attachedTemplate"):
            with self.subTest(relationship=relationship):
                relationships = (
                    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                    '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/'
                    f'{relationship}" Target="{target}" TargetMode="External"/></Relationships>'
                )
                data = docx(body=WORD_BODY + hyperlink,
                            entries=[("word/_rels/document.xml.rels", relationships)])
                with patch.object(extraction.httpx, "Client", side_effect=AssertionError("No link/provider HTTP")):
                    source = self.general(data, "policy.docx", WORD_MIME)
                    with knowledge._connection() as db:
                        path = knowledge._blob_path(knowledge._source(db, source["id"])["blob_name"])
                    with patch.dict(os.environ, {"STYL_SUPPORT_PROVIDER": "mock"}):
                        result = extraction.extract(path, "docx", scope="general")
                text = "\n".join(fact["text"] for fact in result.facts)
                self.assertIn("Review return guidance.", text)
                self.assertIn("FINAL table", text)
                self.assertNotIn(target, text)
                self.assertIn(extraction.DOCX_WARNING, result.warnings)
                self.assertEqual(extraction.DOCX_LINKED_WARNING in result.warnings, relationship != "hyperlink")
                calls = []

                def handler(request):
                    calls.append(request)
                    self.assertEqual(str(request.url), extraction.OPENAI_URL)
                    self.assertNotIn(target.encode(), request.content)
                    return response()

                with self.provider(handler):
                    remote = extraction.extract(path, "docx", scope="general")
                self.assertTrue(calls)
                self.assertEqual(extraction.DOCX_LINKED_WARNING in remote.warnings, relationship != "hyperlink")

    def test_know_014_docx_decompression_entry_and_total_limits(self):
        data = docx()
        for name, maximum in (("DOCX_ENTRIES", 1), ("DOCX_UNCOMPRESSED_BYTES", 64), ("DOCX_COMPRESSION_RATIO", 1)):
            with self.subTest(limit=name), patch.object(extraction, name, maximum):
                result = self.upload(data, "large.docx", WORD_MIME)
                self.assertEqual(result.status_code, 422, result.text)
        bomb = docx(entries=[("word/media/repeat.bin", b"A" * (1024 * 1024))])
        with self.assertRaisesRegex(extraction.ExtractionError, "decompression"):
            extraction.document_text(bomb, ".docx")

    def test_know_015_general_no_catalog_auth_and_scope_eligibility(self):
        self.products.clear()
        self.accessories.clear()
        with patch.object(extraction.httpx, "Client", side_effect=AssertionError("No provider HTTP")):
            source = self.general()
            self.assertEqual(source["itemRefs"], [])
            self.assertEqual(self.client.get(BASE, headers=self.admin).json()["items"], [])
            self.assertEqual(self.upload(b"Text", "a.txt", "text/plain", refs=[]).status_code, 422)
            self.assertEqual(self.upload(b"Text", "a.txt", "text/plain").status_code, 422)
            self.assertEqual(self.upload(PNG, refs=[], scope="general").status_code, 422)
            self.assertEqual(self.upload(b"Text", "a.txt", "text/plain", refs=[], scope="unknown").status_code, 422)
            self.assertEqual(self.upload(b"Text", "a.txt", "text/plain", refs=["product:1"], scope="general").status_code, 422)
        no_auth = self.client.post(BASE + "/documents", files={"file": ("a.txt", b"Text", "text/plain")},
                                   data={"title": "Policy", "itemRefs": "[]", "scope": "general"})
        self.assertEqual(no_auth.status_code, 401)
        download = self.client.get(BASE + f"/sources/{source['id']}/file")
        self.assertEqual(download.status_code, 401)

    def test_know_015_assignment_scope_cas_invalidates_facts_approval_and_history(self):
        source = self.approve_general()
        old = source["revision"]
        self.assertEqual(len(knowledge.approved_general_facts()), 1)
        url = BASE + f"/sources/{source['id']}/assignment"
        result = self.client.put(url, headers=self.admin, json={
            "expectedRevision": old, "scope": "products", "itemRefs": [],
        })
        self.assertEqual(result.status_code, 422)
        result = self.client.put(url, headers=self.admin, json={
            "expectedRevision": old, "scope": "products", "itemRefs": ["product:1"],
        })
        self.assertEqual(result.status_code, 200, result.text)
        changed = result.json()
        self.assertEqual((changed["scope"], changed["state"], changed["facts"]), ("products", "stale", []))
        self.assertIsNone(changed["provider"])
        self.assertGreater(changed["revision"], old)
        self.assertEqual(knowledge.approved_general_facts(), [])
        self.assertEqual(knowledge.approved_facts(self.catalog()), {})
        self.assertEqual(self.review(source, facts=[POLICY]).status_code, 409)
        with knowledge._connection() as db:
            snapshot = json.loads(db.execute("SELECT snapshot FROM knowledge_versions WHERE source_id=? AND revision=?",
                                            (source["id"], old)).fetchone()[0])
            self.assertEqual((snapshot["sourceScope"], snapshot["state"]), ("general", "approved"))
        result = self.client.put(url, headers=self.admin, json={
            "expectedRevision": changed["revision"], "scope": "general", "itemRefs": [],
        })
        self.assertEqual(result.status_code, 200)
        changed = result.json()
        result = self.client.put(url, headers=self.admin, json={
            "expectedRevision": changed["revision"], "itemRefs": [],
        })
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()["scope"], "general")
        catalog_source = self.source()
        self.assertEqual(self.client.put(BASE + f"/sources/{catalog_source['id']}/assignment", headers=self.admin,
                                        json={"expectedRevision": catalog_source["revision"], "scope": "general",
                                              "itemRefs": []}).status_code, 422)

    def test_know_015_queued_scope_change_fences_result(self):
        source = self.general()
        self.queue(source)
        job = knowledge._claim()
        self.assertIsNotNone(job)
        current = self.get(source["id"])
        result = self.client.put(BASE + f"/sources/{source['id']}/assignment", headers=self.admin, json={
            "expectedRevision": current["revision"], "scope": "products", "itemRefs": ["product:1"],
        })
        self.assertEqual(result.status_code, 200)
        with patch.object(extraction, "extract", return_value=extraction.ExtractionResult([POLICY], [])):
            knowledge._process(job)
        current = self.get(source["id"])
        self.assertEqual((current["scope"], current["state"], current["facts"]), ("products", "stale", []))

    def test_know_015_general_current_identity_independent_of_catalog_delete_and_sync(self):
        source = self.approve_general()
        with knowledge.catalog_delete_guard("product:1"):
            self.products.clear()
        self.accessories.clear()
        synced = self.sync()
        current = next(value for value in synced["sources"] if value["id"] == source["id"])
        self.assertEqual((current["state"], current["revision"]), ("approved", source["revision"]))
        self.assertTrue(current["approvedCurrent"])
        self.assertEqual(synced["approvedDocumentCount"], 1)
        self.assertEqual(knowledge.approved_facts([]), {})
        facts = knowledge.approved_general_facts()
        self.assertEqual(facts[0]["text"], POLICY["text"])
        self.assertEqual(set(facts[0]), {"text", "topic", "location", "sourceId", "sourceName", "sourceHash", "revision"})
        with knowledge._connection() as db:
            row = knowledge._source(db, source["id"])
            self.assertEqual(row["item_identities"], "{}")
            path = knowledge._blob_path(row["blob_name"])
        path.write_bytes(b"Changed source bytes.")
        self.assertEqual(knowledge.approved_general_facts(), [])
        changed = self.get(source["id"])
        self.assertGreater(changed["bytes"], 0)
        self.assertEqual(changed["state"], "approved")
        self.assertFalse(changed["approvedCurrent"])
        path.unlink()
        missing = self.get(source["id"])
        self.assertEqual(missing["bytes"], 0)
        self.assertIn("missing", missing["error"])
        self.assertEqual(self.client.get(BASE, headers=self.admin).json()["approvedDocumentCount"], 0)
        self.assertEqual(self.review(source, facts=[POLICY]).status_code, 409)

    def test_know_015_index_current_readiness_reuses_checks_without_changing_state_or_revision(self):
        general = self.approve_general()
        product = self.review(self.extracted(self.upload(b"Steel frame.", "frame.txt", "text/plain").json())).json()
        self.products[0]["name"] = "Changed product identity"
        catalog = self.catalog()
        with knowledge._connection() as db:
            before = [tuple(row) for row in db.execute("SELECT id,state,revision FROM knowledge_sources ORDER BY id")]
            with patch.object(knowledge, "_current", wraps=knowledge._current) as current:
                index = knowledge._index(db, catalog)
            self.assertEqual(current.call_count, 2)
            self.assertEqual(before, [tuple(row) for row in db.execute("SELECT id,state,revision FROM knowledge_sources ORDER BY id")])
        sources = {source["id"]: source for source in index["sources"]}
        self.assertTrue(sources[general["id"]]["approvedCurrent"])
        self.assertFalse(sources[product["id"]]["approvedCurrent"])
        self.assertEqual(sources[product["id"]]["state"], "approved")
        self.assertGreater(sources[product["id"]]["bytes"], 0)
        self.assertEqual(index["approvedDocumentCount"], 1)

    def test_know_015_partial_product_assignment_readiness_matches_available_retrieval(self):
        uploaded = self.upload(b"Steel frame.", "frame.txt", "text/plain", refs=["product:1", "product:3"]).json()
        approved = self.review(self.extracted(uploaded)).json()
        self.products[2]["publicationStatus"] = "draft"
        index = self.client.get(BASE, headers=self.admin).json()
        source = next(value for value in index["sources"] if value["id"] == approved["id"])
        self.assertEqual(source["itemRefs"], ["product:1", "product:3"])
        self.assertEqual(source["currentItemRefs"], ["product:1"])
        self.assertTrue(source["approvedCurrent"])
        self.assertEqual(source["state"], "approved")
        self.assertEqual(source["revision"], approved["revision"])
        self.assertEqual(index["approvedDocumentCount"], 1)
        facts = knowledge.approved_facts(self.catalog())
        self.assertEqual(set(facts), {"product:1"})
        self.assertEqual(facts["product:1"][0]["text"], FACT["text"])
        self.products[0]["publicationStatus"] = "draft"
        self.assertFalse(self.get(approved["id"])["approvedCurrent"])
        self.assertEqual(knowledge.approved_facts(self.catalog()), {})

    def test_know_016_readiness_and_retrieval_share_title_fact_and_scope_validation(self):
        general = self.approve_general()
        product = self.review(self.extracted(self.upload(b"Steel frame.", "frame.txt", "text/plain").json())).json()
        for source, valid_fact in ((general, POLICY), (product, FACT)):
            for field, value in (
                ("name", "private password"),
                ("facts", json.dumps([{**valid_fact, "topic": "unknown"}])),
                ("facts", json.dumps([{**valid_fact, "topic": "products" if source["scope"] == "general" else "customer_service"}])),
                ("facts", json.dumps([{**valid_fact, "location": "https://example.invalid"}])),
                ("facts", json.dumps([{**valid_fact, "extra": "unknown persisted field"}])),
                ("facts", "invalid json"), ("facts", "null"), ("facts", "{}"), ("facts", "[]"),
            ):
                with self.subTest(scope=source["scope"], field=field, value=value):
                    with knowledge._connection() as db:
                        original = knowledge._source(db, source["id"])[field]
                        db.execute(f"UPDATE knowledge_sources SET {field}=? WHERE id=?", (value, source["id"]))
                    response = self.client.get(BASE, headers=self.admin)
                    self.assertEqual(response.status_code, 200, response.text)
                    index = response.json()
                    changed = next(row for row in index["sources"] if row["id"] == source["id"])
                    self.assertFalse(changed["approvedCurrent"])
                    self.assertEqual(changed["state"], "approved")
                    self.assertEqual(changed["revision"], source["revision"])
                    self.assertEqual(index["approvedDocumentCount"], 1)
                    if source["scope"] == "general":
                        self.assertEqual(knowledge.approved_general_facts(), [])
                    else:
                        self.assertEqual(knowledge.approved_facts(self.catalog()), {})
                    with knowledge._connection() as db:
                        db.execute(f"UPDATE knowledge_sources SET {field}=? WHERE id=?", (original, source["id"]))

    def test_know_016_readonly_snapshot_without_schema_or_catalog_recursion(self):
        path = support.configured_path()
        self.assertEqual(knowledge.approved_general_facts(), [])
        self.assertFalse(path.exists())
        with closing(sqlite3.connect(path)) as db:
            db.execute("CREATE TABLE unrelated(id INTEGER)")
            db.commit()
        before = path.read_bytes()
        with patch.object(support, "get_store", side_effect=AssertionError("No writable store")), \
                patch.object(knowledge, "_current_catalog", side_effect=AssertionError("No catalog recursion")):
            self.assertEqual(knowledge.approved_general_facts(), [])
        self.assertEqual(path.read_bytes(), before)
        source = self.approve_general()
        with knowledge._connection() as db:
            revision = db.execute("SELECT SUM(revision) FROM knowledge_sources").fetchone()[0]
            with patch.object(support, "get_store", side_effect=AssertionError("No writable store")), \
                    patch.object(knowledge, "_current_catalog", side_effect=AssertionError("No catalog recursion")):
                self.assertEqual(knowledge.approved_general_facts()[0]["revision"], source["revision"])
            self.assertEqual(db.execute("SELECT SUM(revision) FROM knowledge_sources").fetchone()[0], revision)

    def test_know_016_legacy_scope_migration_preserves_rows_and_version_snapshots(self):
        source = self.extracted()
        source = self.review(source).json()
        with knowledge._connection() as db:
            original = dict(knowledge._source(db, source["id"]))
            history = db.execute("SELECT snapshot FROM knowledge_versions ORDER BY revision").fetchall()
            history = [value[0] for value in history]
            db.execute("ALTER TABLE knowledge_sources DROP COLUMN sourceScope")
        self.assertEqual(knowledge.approved_general_facts(), [])
        self.assertTrue(knowledge.approved_facts(self.catalog()))
        with knowledge._connection() as db:
            row = dict(knowledge._source(db, source["id"]))
            self.assertEqual(row, original)
            self.assertEqual([value[0] for value in db.execute("SELECT snapshot FROM knowledge_versions ORDER BY revision")], history)

    def test_know_016_malformed_general_sources_fail_closed(self):
        source = self.approve_general()
        for field, value in (
            ("item_refs", "null"), ("item_refs", '["product:1"]'), ("item_identities", '{"product:1":"bad"}'),
            ("facts", '{"bad":true}'), ("facts", json.dumps([FACT])), ("facts", json.dumps([{**POLICY, "location": "https://example.invalid"}])),
            ("source_hash", "0" * 64), ("blob_name", "../unsafe.txt"), ("kind", "image"),
            ("origin", "catalog"), ("sourceScope", "unknown"), ("name", "private password"),
        ):
            with self.subTest(field=field):
                with knowledge._connection() as db:
                    original = knowledge._source(db, source["id"])[field]
                    db.execute(f"UPDATE knowledge_sources SET {field}=? WHERE id=?", (value, source["id"]))
                self.assertEqual(knowledge.approved_general_facts(), [])
                self.assertEqual(knowledge.approved_facts(self.catalog()), {})
                with knowledge._connection() as db:
                    db.execute(f"UPDATE knowledge_sources SET {field}=? WHERE id=?", (original, source["id"]))

    def test_know_016_malformed_product_references_fail_closed(self):
        source = self.review(self.extracted()).json()
        for value in ("null", "{}", '"product:1"', "[{}]", "invalid json"):
            with self.subTest(value=value):
                with knowledge._connection() as db:
                    db.execute("UPDATE knowledge_sources SET item_refs=? WHERE id=?", (value, source["id"]))
                self.assertEqual(knowledge.approved_facts(self.catalog()), {})

    def test_know_016_policy_approval_allows_service_fees_not_prices_or_private_promises(self):
        source = self.general()
        with patch.dict(os.environ, {"STYL_SUPPORT_PROVIDER": "mock"}):
            self.queue(source)
            asyncio.run(knowledge.process_one())
        current = self.get(source["id"])
        for text in ("Shipping fee is CAD 15.", "Returns require prior approval.", "Warranty claims need an order reference.",
                     "Support reviews the submitted issue before arranging repair."):
            self.assertEqual(knowledge._validated_facts([{**POLICY, "text": text}], "general")[0]["text"], text)
        for fact in (
            FACT, {**POLICY, "text": "Product price is CAD 15."},
            {**POLICY, "text": "A discount is guaranteed."},
            {**POLICY, "text": "Medical treatment is provided."},
            {**POLICY, "text": "We provide legal advice."},
            {**POLICY, "text": "Contact service@example.invalid."},
            {**POLICY, "text": "Call 555-123-4567 for returns."},
            {**POLICY, "text": "Password is secret."},
            {**POLICY, "location": "https://example.invalid"},
            {**POLICY, "text": "The rack costs $500."},
            {**POLICY, "text": "Returns are accepted. The rack costs $500."},
        ):
            with self.subTest(fact=fact):
                self.assertEqual(self.review(current, facts=[fact]).status_code, 422)
        approved = self.review(current, facts=[{**POLICY, "text": "Shipping fee is CAD 15."}])
        self.assertEqual(approved.status_code, 200, approved.text)
        self.assertEqual(knowledge.approved_general_facts()[0]["text"], "Shipping fee is CAD 15.")
        with self.assertRaises(knowledge.HTTPException):
            knowledge._validated_facts([{**FACT, "text": "Shipping fee is CAD 15."}], "products")
        rejected = self.review(approved.json(), decision="reject")
        self.assertEqual(rejected.status_code, 200)
        self.assertEqual(knowledge.approved_general_facts(), [])

    def test_know_016_each_monetary_assertion_requires_its_own_service_fee_context(self):
        source = self.general()
        with patch.dict(os.environ, {"STYL_SUPPORT_PROVIDER": "mock"}):
            self.queue(source)
            self.assertTrue(asyncio.run(knowledge.process_one()))
        current = self.get(source["id"])
        invalid = (
            "The STYL Adjustable Bench costs CAD $1 and the delivery fee is CAD $20.",
            "The delivery fee is CAD $20 and the STYL Adjustable Bench costs CAD $1.",
            "The STYL Adjustable Bench is CAD $1, delivery fee CAD $20.",
            "The delivery fee is CAD $20; the STYL Adjustable Bench is CAD $1.",
            "The delivery fee is CAD $20. The bench is CAD $1.",
            "The bench is CAD1 and the delivery fee is CAD20.",
            "The bench is 1USD while a delivery fee of 20USD applies.",
            "A 1 dollar bench comes with a 20 dollar shipping fee.",
            "A CAD $20 delivery fee applies to the CAD $1 bench.",
            "Shipping fee quoted for the bench costing CAD $1.",
        )
        for text in invalid:
            with self.subTest(text=text):
                result = self.review(current, facts=[{**POLICY, "text": text}])
                self.assertEqual(result.status_code, 422, result.text)
                self.assertEqual(knowledge.approved_general_facts(), [])
        valid = (
            "Shipping fee is CAD $15.",
            "Delivery fee: CAD $20 and return shipping fee: USD $12.50.",
            "A CAD $20 delivery fee applies.",
            "A 20 dollar shipping fee applies.",
            "Shipping costs vary by destination.",
            "Delivery fee is between CAD $15 and CAD $20.",
            "Return shipping costs USD 15.",
            "Shipping fee is 15 CAD.",
        )
        for text in valid:
            with self.subTest(text=text):
                result = self.review(current, facts=[{**POLICY, "text": text}])
                self.assertEqual(result.status_code, 200, result.text)
                current = result.json()
                self.assertEqual(knowledge.approved_general_facts()[0]["text"], text)
                ready = self.get(source["id"])
                self.assertTrue(ready["approvedCurrent"])
        with knowledge._connection() as db:
            db.execute("UPDATE knowledge_sources SET facts=? WHERE id=?",
                       (json.dumps([{**POLICY, "text": invalid[0]}]), source["id"]))
        self.assertEqual(knowledge.approved_general_facts(), [])
        self.assertFalse(self.get(source["id"])["approvedCurrent"])

    def test_know_017_text_docx_all_content_and_deterministic_mock_no_http(self):
        text = "# Heading\n\nFirst paragraph.\n\n" + "x" * 3801 + "\n\nLAST paragraph."
        for filename, data, mime in (("manual.md", text.encode(), "text/markdown"), ("manual.docx", docx(), WORD_MIME)):
            for scope in ("products", "general"):
                with self.subTest(filename=filename, scope=scope):
                    source = self.upload(data, filename, mime, scope=scope, refs=[] if scope == "general" else ["product:1"]).json()
                    with knowledge._connection() as db:
                        path = knowledge._blob_path(knowledge._source(db, source["id"])["blob_name"])
                    with patch.dict(os.environ, {"STYL_SUPPORT_PROVIDER": "mock", "OPENAI_API_KEY": "inherited",
                                                 "GEMINI_API_KEY": "inherited"}), \
                            patch.object(extraction.httpx, "Client", side_effect=AssertionError("No mock HTTP")):
                        first = extraction.extract(path, source["kind"], scope=scope)
                        second = extraction.extract(path, source["kind"], scope=scope)
                        self.assertEqual(first, second)
                        self.assertEqual({fact["topic"] for fact in first.facts},
                                         {"customer_service" if scope == "general" else "products"})
                        content = "\n".join(fact["text"] for fact in first.facts)
                        if filename.endswith(".docx"):
                            self.assertIn("FINAL paragraph", content)
                            self.assertIn("FINAL table", first.facts[-1]["text"])
                            self.assertIn("Table 2, row 1", first.facts[-1]["location"])
                            self.assertIn(extraction.DOCX_WARNING, first.warnings)
                            self.assertLess(content.index("Shipping policy"), content.index("Returns"))
                            self.assertLess(content.index("Returns"), content.index("FINAL paragraph"))
                        else:
                            self.assertEqual(content.count("x"), 3801)
                            self.assertIn("LAST paragraph", first.facts[-1]["text"])
                            self.assertIn("Heading", first.facts[-1]["location"])

    def test_know_017_openai_input_text_schema_scope_prompt_and_complete_chunks(self):
        for filename, data, mime in (("service.docx", docx(), WORD_MIME),
                                     ("product.txt", b"First steel frame.\n\nLAST adjustable part.", "text/plain")):
            scope = "general" if filename.endswith(".docx") else "products"
            source = self.upload(data, filename, mime, refs=[] if scope == "general" else ["product:1"], scope=scope).json()
            with knowledge._connection() as db:
                path = knowledge._blob_path(knowledge._source(db, source["id"])["blob_name"])
            calls = []

            def handler(request):
                self.assertEqual(str(request.url), extraction.OPENAI_URL)
                body = json.loads(request.content)
                calls.append(body)
                expected = ["customer_service"] if scope == "general" else ["products", "compatibility"]
                self.assertEqual(body["text"]["format"]["schema"]["properties"]["facts"]["items"]["properties"]["topic"]["enum"], expected)
                self.assertIn("untrusted DATA", body["instructions"])
                return response([POLICY] if scope == "general" else [FACT])

            with self.provider(handler):
                result = extraction.extract(path, source["kind"], scope=scope)
            payload = json.dumps(calls)
            self.assertNotIn('"input_file"', payload)
            self.assertNotIn('"input_image"', payload)
            self.assertIn("FINAL table" if scope == "general" else "LAST adjustable part", payload)
            self.assertTrue(result.facts)
            self.assertTrue(all(part["type"] == "input_text" for call in calls for message in call["input"]
                                for part in message["content"]))

    def test_know_017_general_pdf_uses_full_pdf_pipeline_and_scope_topics(self):
        source = self.general(pdf(7), "policy.pdf", "application/pdf")
        with knowledge._connection() as db:
            path = knowledge._blob_path(knowledge._source(db, source["id"])["blob_name"])
        calls = []

        def handler(request):
            calls.append(json.loads(request.content))
            return response()

        with self.provider(handler):
            result = extraction.extract(path, "pdf", scope="general")
        self.assertEqual(len(calls), 2)
        self.assertIn("Synthetic feature on page 7", "\n".join(fact["text"] for fact in result.facts))
        self.assertEqual({fact["topic"] for fact in result.facts}, {"customer_service"})
        self.assertTrue(all("shipping" in call["instructions"] for call in calls))

    def test_know_017_new_formats_require_current_route_consent_and_gemini_is_video_only(self):
        source = self.general()
        for extra in ({}, {"expectedRouteFingerprint": "0" * 64}):
            result = self.client.post(BASE + f"/sources/{source['id']}/extract", headers=self.admin, json={
                "expectedRevision": source["revision"], "acknowledgeExternalProcessing": True, **extra,
            })
            self.assertEqual(result.status_code, 409)
        self.assertEqual(self.get(source["id"])["state"], "pending")
        self.queue(source)
        with patch.dict(os.environ, {"STYL_KNOWLEDGE_PROVIDER": "gemini", "STYL_KNOWLEDGE_MODEL": "gemini-3.8-flash"}), \
                patch.object(extraction.httpx, "Client", side_effect=AssertionError("No non-video Gemini traffic")):
            for kind in ("image", "pdf", "docx", "text"):
                with self.assertRaisesRegex(extraction.ExtractionError, "configuration"):
                    extraction._credentials(*extraction.provider_settings(kind), kind)
            self.assertIsNone(knowledge._claim())
        self.assertEqual(self.get(source["id"])["state"], "paused")

    def test_know_018_backup_includes_all_new_suffixes_current_and_historical(self):
        with closing(sqlite3.connect(":memory:")) as db:
            db.execute("CREATE TABLE knowledge_sources(blob_name TEXT, source_hash TEXT)")
            db.execute("CREATE TABLE knowledge_versions(snapshot TEXT)")
            expected = set()
            for index, suffix in enumerate(("pdf", "docx", "txt", "md")):
                digest = hashlib.sha256(str(index).encode()).hexdigest()
                blob = f"{digest}.{suffix}"
                expected.add(blob)
                db.execute("INSERT INTO knowledge_versions VALUES(?)", (json.dumps({"blob_name": blob, "source_hash": digest}),))
                if index % 2:
                    db.execute("INSERT INTO knowledge_sources VALUES(?,?)", (blob, digest))
            self.assertEqual(knowledge.backup_blob_names(db), expected)
            db.execute("INSERT INTO knowledge_sources VALUES(?,?)", ("../escape.txt", "bad"))
            with self.assertRaisesRegex(ValueError, "invalid source-copy"):
                knowledge.backup_blob_names(db)
