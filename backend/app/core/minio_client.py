"""MinIO client singleton with automatic bucket creation."""

from minio import Minio
from minio.error import S3Error

from app.core.config import settings


def _create_minio_client() -> Minio:
    """Create and return a MinIO client instance."""
    return Minio(
        endpoint=settings.MINIO_ENDPOINT,
        access_key=settings.MINIO_ACCESS_KEY,
        secret_key=settings.MINIO_SECRET_KEY,
        secure=False,  # Local development — no TLS
    )


minio_client = _create_minio_client()


def ensure_bucket_exists() -> None:
    """Create the evidence bucket if it does not already exist.

    Call this function during application startup.
    """
    try:
        if not minio_client.bucket_exists(settings.MINIO_BUCKET):
            minio_client.make_bucket(settings.MINIO_BUCKET)
    except S3Error as exc:
        raise RuntimeError(
            f"Failed to initialise MinIO bucket '{settings.MINIO_BUCKET}': {exc}"
        ) from exc
