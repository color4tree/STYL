from io import BytesIO
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from fastapi import HTTPException, UploadFile
from fastapi.testclient import TestClient

from app import main, media


class VideoUploadTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name)
        self.addCleanup(self.directory.cleanup)

    def test_auth_is_required(self) -> None:
        with patch.object(main, "ADMIN_TOKEN", "secret"):
            response = TestClient(main.app).post("/api/uploads/product-video", files={"video": ("clip.mov", b"video", "video/quicktime")})
        self.assertEqual(response.status_code, 401)

    def test_file_limit_and_invalid_format(self) -> None:
        for name, content, expected in [("clip.exe", b"video", 415), ("clip.mov", b"", 422), ("clip.MOV", b"12345", 413)]:
            with self.subTest(name=name, expected=expected), patch.object(media, "MAX_VIDEO_SIZE", 4), patch.object(media.subprocess, "run") as run:
                with self.assertRaises(HTTPException) as caught:
                    media.upload_video(UploadFile(filename=name, file=BytesIO(content)), self.path)
                self.assertEqual(caught.exception.status_code, expected)
                run.assert_not_called()
        self.assertEqual(list(self.path.iterdir()), [])

    def test_conversion_and_poster_for_supported_formats(self) -> None:
        def convert(command, **kwargs):
            self.assertFalse(kwargs.get("shell", False))
            self.assertIn("-protocol_whitelist", command)
            Path(command[-1]).write_bytes(b"converted")

        for extension in media.VIDEO_FORMATS:
            with self.subTest(extension=extension), patch.object(media, "get_ffmpeg_exe", return_value="ffmpeg"), patch.object(media.subprocess, "run", side_effect=convert) as run:
                result = media.upload_video(UploadFile(filename=f"iphone{extension.upper()}", file=BytesIO(b"input")), self.path)
                self.assertTrue(result["video"].endswith(".mp4"))
                self.assertTrue((self.path / Path(result["poster"]).name).exists())
                self.assertIn("libx264", run.call_args_list[0].args[0])
                self.assertIn("-map_metadata", run.call_args_list[0].args[0])

    def test_invalid_video_and_timeout_leave_no_files(self) -> None:
        for failure in (subprocess.CalledProcessError(1, "ffmpeg"), subprocess.TimeoutExpired("ffmpeg", 180)):
            with patch.object(media, "get_ffmpeg_exe", return_value="ffmpeg"), patch.object(media.subprocess, "run", side_effect=failure):
                with self.assertRaises(HTTPException) as caught:
                    media.upload_video(UploadFile(filename="clip.mov", file=BytesIO(b"invalid")), self.path)
                self.assertEqual(caught.exception.status_code, 422)
        self.assertEqual(list(self.path.iterdir()), [])
        self.assertFalse(media.VIDEO_LOCK.locked())

    def test_gallery_keeps_video_order_and_uses_photo_or_poster_as_cover(self) -> None:
        video = "/api/uploads/clip.mp4"
        photo = "/images/rack.jpg"
        request = main.ProductPayload(name="Rack", category="Racks", price=1, photos=[video, photo])
        details = main.catalog_details(request, {}, "")
        self.assertEqual(details["photos"], [video, photo])
        self.assertEqual(details["image"], photo)
        request.photos = [video]
        self.assertEqual(main.catalog_details(request, {}, "")["image"], "/api/uploads/clip.poster.jpg")

    def test_legacy_update_preserves_video_order_without_inserting_poster(self) -> None:
        previous = {"photos": ["/api/uploads/clip.mp4"], "image": "/api/uploads/clip.poster.jpg"}
        request = main.ProductPayload(name="Rack", category="Racks", price=1, image=previous["image"])
        self.assertEqual(main.catalog_details(request, previous, "")["photos"], previous["photos"])

    def test_video_and_poster_are_kept_until_last_reference_is_removed(self) -> None:
        video = self.path / "clip.mp4"
        poster = self.path / "clip.poster.jpg"
        video.write_bytes(b"video")
        poster.write_bytes(b"poster")
        shared = {"photos": ["/api/uploads/clip.mp4"], "image": "/api/uploads/clip.poster.jpg"}
        with patch.object(main, "UPLOAD_PATH", self.path), patch.object(main, "load_products", return_value=[]), patch.object(main, "load_accessories", return_value=[shared]) as accessories, patch.object(main, "load_hero", return_value={}):
            main.delete_catalog_images(shared)
            self.assertTrue(video.exists())
            self.assertTrue(poster.exists())
            accessories.return_value = [{"photos": shared["photos"], "image": "/images/another.jpg"}]
            main.delete_catalog_images(shared)
            self.assertTrue(video.exists())
            self.assertTrue(poster.exists())
            accessories.return_value = []
            main.delete_catalog_images(shared)
            self.assertFalse(video.exists())
            self.assertFalse(poster.exists())

    def test_streaming_supports_browser_byte_ranges(self) -> None:
        filename = "a" * 32 + ".mp4"
        (self.path / filename).write_bytes(b"0123456789")
        client = TestClient(main.app)
        with patch.object(main, "UPLOAD_PATH", self.path):
            for byte_range, expected in [("bytes=2-5", b"2345"), ("bytes=7-", b"789"), ("bytes=-3", b"789")]:
                response = client.get(f"/api/uploads/{filename}", headers={"Range": byte_range})
                self.assertEqual(response.status_code, 206)
                self.assertEqual(response.content, expected)
                self.assertEqual(response.headers["content-type"], "video/mp4")
            self.assertEqual(client.get(f"/api/uploads/{filename}").content, b"0123456789")
            self.assertEqual(client.get(f"/api/uploads/{filename}", headers={"Range": "bytes=99-"}).status_code, 416)

    def test_converted_size_limit(self) -> None:
        def oversized(command, **kwargs):
            Path(command[-1]).write_bytes(b"12345")

        with patch.object(media, "MAX_VIDEO_SIZE", 4), patch.object(media, "get_ffmpeg_exe", return_value="ffmpeg"), patch.object(media.subprocess, "run", side_effect=oversized):
            with self.assertRaises(HTTPException) as caught:
                media.upload_video(UploadFile(filename="clip.mov", file=BytesIO(b"in")), self.path)
            self.assertEqual(caught.exception.status_code, 413)
        self.assertEqual(list(self.path.iterdir()), [])

    def test_real_10_bit_hevc_mov_converts_to_playable_mp4_and_poster(self) -> None:
        executable = media.get_ffmpeg_exe()
        source = self.path / "iphone.MOV"
        subprocess.run([
            executable, "-y", "-f", "lavfi", "-i", "testsrc2=size=96x160:rate=10", "-t", "0.4",
            "-c:v", "libx265", "-threads", "2", "-pix_fmt", "yuv420p10le", "-tag:v", "hvc1", str(source),
        ], check=True, capture_output=True, timeout=30)
        with source.open("rb") as stream:
            result = media.upload_video(UploadFile(filename=source.name, file=stream), self.path)
        converted = self.path / Path(result["video"]).name
        decoded = subprocess.run([executable, "-i", str(converted), "-f", "null", "-"], check=True, capture_output=True, timeout=30)
        self.assertIn(b"Video: h264", decoded.stderr)
        self.assertIn(b"yuv420p", decoded.stderr)
        self.assertTrue((self.path / Path(result["poster"]).name).read_bytes().startswith(b"\xff\xd8"))


if __name__ == "__main__":
    unittest.main()