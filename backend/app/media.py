from pathlib import Path
import re
import subprocess
from collections.abc import Iterator
from tempfile import TemporaryDirectory
from threading import Lock
from uuid import uuid4

from fastapi import HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from imageio_ffmpeg import get_ffmpeg_exe

MAX_VIDEO_SIZE = 50 * 1024 * 1024
VIDEO_FORMATS = {".mov": "mov", ".mp4": "mov", ".m4v": "mov", ".webm": "matroska", ".mkv": "matroska", ".avi": "avi"}
VIDEO_LOCK = Lock()


def video_response(path: Path, byte_range: str | None) -> StreamingResponse:
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Video not found.")
    size = path.stat().st_size
    start, end = 0, size - 1
    status = 200
    headers = {"Accept-Ranges": "bytes"}
    if byte_range:
        match = re.fullmatch(r"bytes=(\d{0,20})-(\d{0,20})", byte_range.strip())
        if not match or not any(match.groups()):
            raise HTTPException(status_code=416, headers={"Content-Range": f"bytes */{size}"})
        first, last = match.groups()
        if first:
            start = int(first)
            end = min(int(last), size - 1) if last else size - 1
        else:
            start = max(0, size - int(last))
        if start > end or start >= size:
            raise HTTPException(status_code=416, headers={"Content-Range": f"bytes */{size}"})
        status = 206
        headers["Content-Range"] = f"bytes {start}-{end}/{size}"
    headers["Content-Length"] = str(end - start + 1)

    def chunks() -> Iterator[bytes]:
        with path.open("rb") as stream:
            stream.seek(start)
            remaining = end - start + 1
            while remaining > 0:
                chunk = stream.read(min(64 * 1024, remaining))
                if not chunk:
                    break
                remaining -= len(chunk)
                yield chunk

    return StreamingResponse(chunks(), status_code=status, media_type="video/mp4", headers=headers)


def upload_video(video: UploadFile, upload_path: Path) -> dict[str, str]:
    extension = Path(video.filename or "").suffix.lower()
    if extension not in VIDEO_FORMATS:
        video.file.close()
        raise HTTPException(status_code=415, detail="Upload an MP4, MOV, M4V, WebM, MKV, or AVI video.")
    if not VIDEO_LOCK.acquire(blocking=False):
        video.file.close()
        raise HTTPException(status_code=503, detail="Another video is processing. Please try again shortly.")
    identifier = uuid4().hex
    destination = upload_path / f"{identifier}.mp4"
    poster_destination = upload_path / f"{identifier}.poster.jpg"
    try:
        with TemporaryDirectory(prefix="styl-video-") as temporary:
            source = Path(temporary) / f"input{extension}"
            output = Path(temporary) / "output.mp4"
            poster = Path(temporary) / "poster.jpg"
            size = 0
            with source.open("wb") as stream:
                while chunk := video.file.read(1024 * 1024):
                    size += len(chunk)
                    if size > MAX_VIDEO_SIZE:
                        raise HTTPException(status_code=413, detail="Video must be 50 MB or smaller.")
                    stream.write(chunk)
            if not size:
                raise HTTPException(status_code=422, detail="Video is empty.")
            executable = get_ffmpeg_exe()
            subprocess.run([
                executable, "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
                "-protocol_whitelist", "file,pipe", "-threads", "2", "-f", VIDEO_FORMATS[extension], "-i", str(source),
                "-map", "0:v:0", "-map", "0:a:0?", "-sn", "-dn", "-map_metadata", "-1",
                "-vf", "scale=w='min(1280,iw)':h='min(1280,ih)':force_original_aspect_ratio=decrease:force_divisible_by=2",
                "-c:v", "libx264", "-threads", "2", "-preset", "fast", "-crf", "23", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", "-fs", str(MAX_VIDEO_SIZE + 1), str(output),
            ], check=True, capture_output=True, timeout=180)
            if output.stat().st_size >= MAX_VIDEO_SIZE:
                raise HTTPException(status_code=413, detail="Converted video exceeds 50 MB. Upload a shorter or compressed clip.")
            subprocess.run([
                executable, "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
                "-protocol_whitelist", "file,pipe", "-threads", "2", "-i", str(output),
                "-frames:v", "1", "-update", "1", str(poster),
            ], check=True, capture_output=True, timeout=30)
            upload_path.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(output.read_bytes())
            poster_destination.write_bytes(poster.read_bytes())
        return {"video": f"/api/uploads/{destination.name}", "poster": f"/api/uploads/{poster_destination.name}"}
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=422, detail="Video processing timed out. Upload a shorter clip.") from None
    except subprocess.CalledProcessError:
        raise HTTPException(status_code=422, detail="Video cannot be decoded. Export it as MP4 or MOV and try again.") from None
    except (OSError, RuntimeError):
        destination.unlink(missing_ok=True)
        poster_destination.unlink(missing_ok=True)
        raise HTTPException(status_code=503, detail="Video processing is unavailable. Please try again later.") from None
    finally:
        video.file.close()
        VIDEO_LOCK.release()