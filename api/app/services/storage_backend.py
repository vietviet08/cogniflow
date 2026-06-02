from __future__ import annotations

import hashlib
import logging
import mimetypes
import os
import tempfile
from abc import ABC, abstractmethod
from collections.abc import Generator
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger("app.storage")

S3_KEY_PREFIX = "s3://"


def is_s3_path(storage_path: str) -> bool:
    return storage_path.startswith(S3_KEY_PREFIX)


def build_s3_key(source_id: str, filename: str) -> str:
    return f"sources/{source_id}/{filename}"


def build_s3_podcast_key(report_id: str) -> str:
    return f"podcasts/{report_id}.mp3"


class StorageBackend(ABC):
    @abstractmethod
    def get_bytes(self, storage_path: str) -> bytes:
        ...

    @abstractmethod
    def get_stream(self, storage_path: str, chunk_size: int = 8192):
        """Yield chunks of bytes for streaming."""
        ...

    @abstractmethod
    def save_bytes(self, s3_key: str, content: bytes, content_type: str | None = None) -> str:
        """Save bytes and return the canonical storage_path (s3://bucket/key)."""
        ...

    @abstractmethod
    def delete(self, storage_path: str) -> bool:
        ...

    @abstractmethod
    def exists(self, storage_path: str) -> bool:
        ...

    @abstractmethod
    def generate_presigned_url(self, storage_path: str, expires_in: int = 3600) -> str:
        ...

    def resolve_local_path(self, storage_path: str) -> Path | None:
        """Return local Path if this is a local file, else None."""
        return None

    @contextmanager
    def local_file(self, storage_path: str) -> Generator[Path, None, None]:
        """Yield a local Path for the stored file.

        For local backend this is zero-copy (returns existing path).
        For S3 backend this downloads to a temp file and cleans up after.
        """
        local = self.resolve_local_path(storage_path)
        if local is not None and local.exists():
            yield local
            return
        # S3 or missing local: download to temp
        content = self.get_bytes(storage_path)
        suffix = Path(storage_path).suffix or ".bin"
        fd, tmp_path = tempfile.mkstemp(suffix=suffix)
        try:
            os.write(fd, content)
            os.close(fd)
            yield Path(tmp_path)
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


class LocalStorageBackend(StorageBackend):
    def __init__(self, upload_dir: str) -> None:
        self._upload_dir = Path(upload_dir)
        self._upload_dir.mkdir(parents=True, exist_ok=True)

    def _resolve(self, storage_path: str) -> Path:
        path = Path(storage_path)
        if path.is_absolute():
            return path
        return self._upload_dir / path

    def get_bytes(self, storage_path: str) -> bytes:
        return self._resolve(storage_path).read_bytes()

    def get_stream(self, storage_path: str, chunk_size: int = 8192):
        with open(self._resolve(storage_path), "rb") as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                yield chunk

    def save_bytes(self, s3_key: str, content: bytes, content_type: str | None = None) -> str:
        # For local backend, s3_key is used as relative path under upload_dir
        destination = self._upload_dir / s3_key
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)
        return str(destination)

    def delete(self, storage_path: str) -> bool:
        path = self._resolve(storage_path)
        if path.exists():
            path.unlink()
            return True
        return False

    def exists(self, storage_path: str) -> bool:
        return self._resolve(storage_path).exists()

    def generate_presigned_url(self, storage_path: str, expires_in: int = 3600) -> str:
        raise NotImplementedError("Presigned URLs are not supported for local storage backend.")

    def resolve_local_path(self, storage_path: str) -> Path | None:
        return self._resolve(storage_path)


class S3StorageBackend(StorageBackend):
    def __init__(
        self,
        bucket: str,
        region: str = "ap-southeast-1",
        access_key_id: str = "",
        secret_access_key: str = "",
    ) -> None:
        import boto3
        from botocore.config import Config

        self._bucket = bucket
        kwargs: dict[str, object] = {
            "region_name": region,
            "endpoint_url": f"https://s3.{region}.amazonaws.com",
            "config": Config(
                signature_version="s3v4",
                s3={"addressing_style": "virtual"},
            ),
        }
        if access_key_id and secret_access_key:
            kwargs["aws_access_key_id"] = access_key_id
            kwargs["aws_secret_access_key"] = secret_access_key
        self._client = boto3.client("s3", **kwargs)

    def _parse(self, storage_path: str) -> tuple[str, str]:
        if storage_path.startswith(S3_KEY_PREFIX):
            remainder = storage_path[len(S3_KEY_PREFIX):]
            bucket, _, key = remainder.partition("/")
            return bucket or self._bucket, key
        return self._bucket, storage_path

    def get_bytes(self, storage_path: str) -> bytes:
        bucket, key = self._parse(storage_path)
        response = self._client.get_object(Bucket=bucket, Key=key)
        return response["Body"].read()

    def get_stream(self, storage_path: str, chunk_size: int = 8192):
        bucket, key = self._parse(storage_path)
        response = self._client.get_object(Bucket=bucket, Key=key)
        body = response["Body"]
        try:
            while True:
                chunk = body.read(chunk_size)
                if not chunk:
                    break
                yield chunk
        finally:
            body.close()

    def save_bytes(self, s3_key: str, content: bytes, content_type: str | None = None) -> str:
        extra_args: dict[str, str] = {}
        if content_type:
            extra_args["ContentType"] = content_type
        else:
            guessed, _ = mimetypes.guess_type(s3_key)
            if guessed:
                extra_args["ContentType"] = guessed
        self._client.put_object(Bucket=self._bucket, Key=s3_key, Body=content, **extra_args)
        return f"{S3_KEY_PREFIX}{self._bucket}/{s3_key}"

    def delete(self, storage_path: str) -> bool:
        bucket, key = self._parse(storage_path)
        try:
            self._client.delete_object(Bucket=bucket, Key=key)
            return True
        except Exception:
            logger.warning("s3_delete_failed", extra={"storage_path": storage_path})
            return False

    def exists(self, storage_path: str) -> bool:
        bucket, key = self._parse(storage_path)
        try:
            self._client.head_object(Bucket=bucket, Key=key)
            return True
        except self._client.exceptions.ClientError:
            return False

    def generate_presigned_url(self, storage_path: str, expires_in: int = 3600) -> str:
        bucket, key = self._parse(storage_path)
        return self._client.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=expires_in,
        )

    def compute_checksum(self, storage_path: str) -> str:
        bucket, key = self._parse(storage_path)
        response = self._client.get_object(Bucket=bucket, Key=key)
        data = response["Body"].read()
        return hashlib.sha256(data).hexdigest()


@lru_cache(maxsize=1)
def get_storage_backend() -> StorageBackend:
    from app.core.config import get_settings

    settings = get_settings()
    backend = settings.storage_backend.lower()
    if backend == "s3":
        if not settings.s3_uploads_bucket:
            raise ValueError("S3_UPLOADS_BUCKET is required when STORAGE_BACKEND=s3")
        return S3StorageBackend(
            bucket=settings.s3_uploads_bucket,
            region=settings.aws_region,
            access_key_id=settings.aws_access_key_id,
            secret_access_key=settings.aws_secret_access_key,
        )
    return LocalStorageBackend(upload_dir=settings.upload_dir)
