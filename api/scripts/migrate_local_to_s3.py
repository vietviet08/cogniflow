"""Migrate local source files and podcast audio to S3.

Usage:
    cd api && python -m scripts.migrate_local_to_s3

Requires:
    - STORAGE_BACKEND=s3 and S3_UPLOADS_BUCKET set in .env
    - DATABASE_URL pointing to the target database
    - Local files still present on disk at their original paths

This script is idempotent: it skips S3 paths only when the object exists.
"""

from __future__ import annotations

import mimetypes
import uuid
from pathlib import Path

from app.core.config import get_settings
from app.services.storage_backend import (
    S3_KEY_PREFIX,
    S3StorageBackend,
    build_s3_key,
    build_s3_podcast_key,
    is_s3_path,
)
from app.storage.db import SessionLocal
from app.storage.models import Source


def _content_type_for(path: Path) -> str | None:
    if path.suffix.lower() == ".mp3":
        return "audio/mpeg"
    guessed, _ = mimetypes.guess_type(path.name)
    return guessed


def _parse_s3_path(storage_path: str) -> tuple[str, str]:
    remainder = storage_path[len(S3_KEY_PREFIX) :]
    bucket, _, key = remainder.partition("/")
    return bucket, key


def _source_local_candidates(source: Source, storage_path: str, s3_key: str | None = None) -> list[Path]:
    candidates = [Path(storage_path)]
    filename = Path(s3_key or storage_path).name
    if filename:
        candidates.append(Path(get_settings().upload_dir) / str(source.id) / filename)

    unique: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate)
        if key not in seen:
            unique.append(candidate)
            seen.add(key)
    return unique


def _find_existing_path(candidates: list[Path]) -> Path | None:
    return next((path for path in candidates if path.exists()), None)


def _upload_verified(
    backend: S3StorageBackend,
    *,
    s3_key: str,
    local_path: Path,
    content_type: str | None = None,
) -> str:
    storage_path = backend.save_bytes(s3_key, local_path.read_bytes(), content_type=content_type)
    if not backend.exists(s3_key):
        raise RuntimeError(f"S3 object was not found after upload: {s3_key}")
    return storage_path


def _migrate_source_files(backend: S3StorageBackend, bucket: str) -> tuple[int, int, int]:
    db = SessionLocal()
    migrated = 0
    skipped = 0
    failed = 0

    try:
        sources = db.query(Source).filter(Source.storage_path.isnot(None)).all()
        total = len(sources)
        print(f"Found {total} sources with storage_path")

        for source in sources:
            storage_path = source.storage_path
            if not storage_path:
                continue

            if is_s3_path(storage_path):
                s3_bucket, s3_key = _parse_s3_path(storage_path)
                if s3_bucket != bucket:
                    print(f"  SKIP (different bucket): {storage_path}")
                    skipped += 1
                    continue
                if backend.exists(s3_key):
                    skipped += 1
                    continue

                local_path = _find_existing_path(_source_local_candidates(source, storage_path, s3_key))
                if local_path is None:
                    print(f"  FAIL (s3 missing, local missing): {storage_path}")
                    failed += 1
                    continue
            else:
                s3_key = build_s3_key(str(source.id), Path(storage_path).name)
                local_path = _find_existing_path(_source_local_candidates(source, storage_path))
                if local_path is None:
                    print(f"  SKIP (missing): {storage_path}")
                    skipped += 1
                    continue

            try:
                new_storage_path = _upload_verified(
                    backend,
                    s3_key=s3_key,
                    local_path=local_path,
                    content_type=_content_type_for(local_path),
                )
                source.storage_path = new_storage_path
                db.add(source)
                migrated += 1
                print(f"  OK: {storage_path} -> {new_storage_path}")
            except Exception as exc:
                failed += 1
                print(f"  FAIL: {storage_path} -> {exc}")

        db.commit()
    finally:
        db.close()

    return migrated, skipped, failed


def _migrate_podcast_audio(backend: S3StorageBackend, bucket: str) -> tuple[int, int, int]:
    settings = get_settings()
    podcast_dir = Path(settings.upload_dir) / "podcasts"
    if not podcast_dir.exists():
        print("No local podcasts directory found, skipping podcast migration")
        return 0, 0, 0

    migrated = 0
    skipped = 0
    failed = 0

    for mp3_file in podcast_dir.glob("*.mp3"):
        report_id_str = mp3_file.stem
        try:
            uuid.UUID(report_id_str)
        except ValueError:
            continue

        s3_key = build_s3_podcast_key(report_id_str)
        s3_path = f"{S3_KEY_PREFIX}{bucket}/{s3_key}"

        if backend.exists(s3_key):
            print(f"  SKIP (exists): {s3_path}")
            skipped += 1
            continue

        try:
            _upload_verified(
                backend,
                s3_key=s3_key,
                local_path=mp3_file,
                content_type="audio/mpeg",
            )
            migrated += 1
            print(f"  OK: {mp3_file} -> {s3_path}")
        except Exception as exc:
            failed += 1
            print(f"  FAIL: {mp3_file} -> {exc}")

    return migrated, skipped, failed


def main() -> int:
    settings = get_settings()

    if settings.storage_backend.lower() != "s3":
        print("ERROR: STORAGE_BACKEND must be 's3' for migration")
        print("Set STORAGE_BACKEND=s3 and S3_UPLOADS_BUCKET in your .env")
        return 1

    if not settings.s3_uploads_bucket:
        print("ERROR: S3_UPLOADS_BUCKET must be set")
        return 1

    bucket = settings.s3_uploads_bucket
    print(f"Migrating local files to S3 bucket: {bucket}")
    print(f"Region: {settings.aws_region}")
    print()

    backend = S3StorageBackend(
        bucket=bucket,
        region=settings.aws_region,
        access_key_id=settings.aws_access_key_id,
        secret_access_key=settings.aws_secret_access_key,
    )

    print("=== Source files ===")
    src_migrated, src_skipped, src_failed = _migrate_source_files(backend, bucket)
    print(f"  Migrated: {src_migrated}, Skipped: {src_skipped}, Failed: {src_failed}")
    print()

    print("=== Podcast audio ===")
    pod_migrated, pod_skipped, pod_failed = _migrate_podcast_audio(backend, bucket)
    print(f"  Migrated: {pod_migrated}, Skipped: {pod_skipped}, Failed: {pod_failed}")
    print()

    total_failed = src_failed + pod_failed
    if total_failed > 0:
        print(f"WARNING: {total_failed} files failed to migrate")
        return 1

    print("Migration complete!")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
