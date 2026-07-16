import base64
from pathlib import Path


def image_to_base64(image_path: Path) -> str:
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def base64_to_image(base64_str: str, output_path: Path) -> Path:
    image_bytes = base64.b64decode(base64_str)
    with open(output_path, "wb") as f:
        f.write(image_bytes)
    return output_path
