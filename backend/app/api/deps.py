from fastapi import HTTPException, UploadFile, Security, Depends
from fastapi.security import APIKeyHeader
from app.core.config import settings

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

async def validate_upload(file: UploadFile) -> bytes:
    """Rejects files > 20MB or unsupported types. Returns raw bytes."""
    # 20MB limit
    MAX_SIZE = 20 * 1024 * 1024
    
    # We need to read the file to check its size accurately if the header is missing
    # But for efficiency, we first check the content-type
    allowed_types = {"application/pdf", "text/plain", "text/csv"}
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=415, detail=f"Unsupported file type: {file.content_type}")

    content = await file.read()
    if len(content) > MAX_SIZE:
        raise HTTPException(status_code=413, detail="File too large (max 20MB)")
    
    return content

async def verify_api_key(api_key: str = Security(api_key_header)):
    """Verifies the X-API-Key header against settings.API_KEY."""
    if not settings.API_KEY:
        return  # Dev mode: skip check
    
    if api_key != settings.API_KEY:
        raise HTTPException(status_code=403, detail="Invalid or missing API Key")
