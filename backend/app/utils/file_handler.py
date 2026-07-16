from pathlib import Path

from app.config import settings

UPLOAD_DIR = Path(settings.upload_dir)
IMAGE_DIR = Path(settings.image_dir)


def ensure_dirs():
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)


def save_uploaded_file(filename: str, content: bytes) -> Path:
    safe_name = Path(filename).name
    path = UPLOAD_DIR / safe_name
    counter = 1
    while path.exists():
        stem = path.stem
        ext = path.suffix
        path = UPLOAD_DIR / f"{stem}_{counter}{ext}"
        counter += 1
    with open(path, "wb") as f:
        f.write(content)
    return path


def save_image(chunk_id: str, image_bytes: bytes) -> Path:
    path = IMAGE_DIR / f"{chunk_id}.jpg"
    with open(path, "wb") as f:
        f.write(image_bytes)
    return path


def get_image_path(chunk_id: str) -> Path:
    return IMAGE_DIR / f"{chunk_id}.jpg"


def get_uploaded_file_path(filename: str) -> Path | None:
    safe_name = Path(filename).name
    path = UPLOAD_DIR / safe_name
    resolved = path.resolve()
    if not str(resolved).startswith(str(UPLOAD_DIR.resolve())):
        return None
    return path if path.exists() else None
