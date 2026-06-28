"""MinIO client singleton with automatic bucket creation."""

from minio import Minio
from minio.error import S3Error

from app.core.config import settings


import logging

logger = logging.getLogger(__name__)


def _create_minio_client() -> Minio:
    """Create and return a MinIO client instance with secure fallback."""
    endpoint = settings.MINIO_ENDPOINT
    is_secure = False
    
    # Strip protocol prefix if present (MinIO client expects bare host:port)
    if "://" in endpoint:
        protocol = endpoint.split("://")[0].lower()
        endpoint = endpoint.split("://")[-1]
        if protocol == "https":
            is_secure = True
            
    if "s3." in endpoint.lower() or endpoint.endswith(":443"):
        is_secure = True

    return Minio(
        endpoint=endpoint,
        access_key=settings.MINIO_ACCESS_KEY,
        secret_key=settings.MINIO_SECRET_KEY,
        secure=is_secure,
    )


minio_client = _create_minio_client()


def ensure_bucket_exists() -> None:
    """Create the evidence bucket if it does not already exist.

    Gracefully logs configuration/connection errors instead of crashing the server.
    """
    try:
        if not minio_client.bucket_exists(settings.MINIO_BUCKET):
            minio_client.make_bucket(settings.MINIO_BUCKET)
    except S3Error as exc:
        raise RuntimeError(
            f"Failed to initialise MinIO bucket '{settings.MINIO_BUCKET}': {exc}"
        ) from exc
    except Exception as exc:
        logger.error(
            "Failed to connect to storage endpoint %s. The application will continue to start up, "
            "but evidence uploads/downloads will fail until storage is correctly configured: %s",
            settings.MINIO_ENDPOINT,
            exc,
        )
