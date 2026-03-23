import os
import uuid
import logging
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
from typing import List

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="Internal Media Storage")

MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE", 10485760))  # 10 MB default
ALLOWED_EXTENSIONS = set(
    os.getenv("ALLOWED_EXTENSIONS", "pdf,doc,docx,xls,xlsx,ppt,pptx,txt").split(",")
)
MEDIA_ROOT = Path(os.getenv("MEDIA_ROOT", "/app/data/media"))
BASE_URL = os.getenv("BASE_URL", "http://media.local/files")

MEDIA_ROOT.mkdir(parents=True, exist_ok=True)


async def _save_file(file: UploadFile) -> str:
    ext = Path(file.filename).suffix.lstrip(".").lower() if file.filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Invalid file type: .{ext}")

    month_dir = datetime.now().strftime("%Y-%m")
    dest_dir = MEDIA_ROOT / month_dir
    dest_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{uuid.uuid4()}.{ext}"
    dest = dest_dir / filename

    size = 0
    chunk_size = 1024 * 64  # 64 KB

    with dest.open("wb") as f:
        while True:
            chunk = await file.read(chunk_size)
            if not chunk:
                break
            size += len(chunk)
            if size > MAX_FILE_SIZE:
                dest.unlink(missing_ok=True)
                raise HTTPException(status_code=400, detail=f"File too large: {file.filename}")
            f.write(chunk)

    logger.info("Uploaded: %s/%s (%d bytes)", month_dir, filename, size)
    return f"{BASE_URL}/{month_dir}/{filename}"


@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    url = await _save_file(file)
    return JSONResponse({"url": url})


@app.post("/upload/batch")
async def upload_files(files: List[UploadFile] = File(...)):
    saved_urls: List[str] = []
    try:
        for file in files:
            url = await _save_file(file)
            saved_urls.append(url)
    except HTTPException:
        for url in saved_urls:
            relative = url[len(BASE_URL):].lstrip("/")  # e.g. "2026-03/abc.pdf"
            (MEDIA_ROOT / relative).unlink(missing_ok=True)
        raise
    return JSONResponse({"urls": saved_urls})


@app.get("/health")
def health():
    return {"status": "ok"}
