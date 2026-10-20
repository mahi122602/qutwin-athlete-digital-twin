"""Local portrait segmentation and PNG layout metadata for existing profile_photo bytes.

Faces and clothing are retained from the uploaded photograph. The model estimates
an alpha mask; it does not generate a new face. No external image API is used.
"""
from __future__ import annotations

import base64
from functools import lru_cache
import hashlib
from io import BytesIO
import json
import logging
import math
import os
from pathlib import Path
import tempfile
import threading
import urllib.request

from PIL import Image, ImageOps, PngImagePlugin, UnidentifiedImageError

MODEL_NAME = "u2net_human_seg"
MODEL_URL = "https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2net_human_seg.onnx"
MODEL_SHA256 = "01eb6a29a5c4d8edb30b56adad9bb3a2a0535338e480724a213e0acfd2d1c73c"
PROCESSOR_BUILD = "qutwin-portrait-cpu-20261019-3"
_INFERENCE_LOCK = threading.Lock()
_log = logging.getLogger(__name__)
_META = "qutwin_portrait_v1"
DEFAULT_LAYOUT = {"x": 0.0, "y": 0.0, "scale": 1.0}


class PortraitProcessingError(RuntimeError):
    """An actionable setup/runtime error, safe to display in the profile editor."""

    def __init__(self, code, message):
        self.code = code
        super().__init__(f"[{code}] {message}")


def model_path():
    override = os.environ.get("QUTWIN_PORTRAIT_MODEL")
    if override:
        return Path(override).expanduser().resolve()
    cache = Path(os.environ.get("U2NET_HOME") or Path.home() / ".u2net").expanduser()
    return cache / (MODEL_NAME + ".onnx")


def _model_verified(path):
    if not path.is_file():
        return False
    checksum = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            checksum.update(chunk)
    return checksum.hexdigest() == MODEL_SHA256


def ensure_model(download=False, progress=None):
    """Reuse a verified model; setup may atomically repair a partial download."""
    path = model_path()
    try:
        valid = _model_verified(path)
    except OSError as exc:
        raise PortraitProcessingError("MODEL_ACCESS", "The portrait model cannot be read. Run the photo repair setup from your project terminal.") from exc
    if valid:
        return path
    if not download:
        code = "MODEL_INVALID" if path.exists() else "MODEL_MISSING"
        raise PortraitProcessingError(code, "The portrait model is missing or incomplete. Run python utils/setup_profile_portrait.py, then restart the app.")
    temporary = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        request = urllib.request.Request(MODEL_URL, headers={"User-Agent": "QUTwin-Profile-Setup/3"})
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=MODEL_NAME + "-", suffix=".download", delete=False) as output:
            temporary = Path(output.name)
            checksum = hashlib.sha256()
            with urllib.request.urlopen(request, timeout=30) as response:
                total = int(response.headers.get("Content-Length", "0"))
                received = 0
                for chunk in iter(lambda: response.read(1024 * 1024), b""):
                    output.write(chunk)
                    checksum.update(chunk)
                    received += len(chunk)
                    if progress:
                        progress(received, total)
        if checksum.hexdigest() != MODEL_SHA256:
            raise PortraitProcessingError("MODEL_INVALID", "The model download was incomplete. Run setup again on a working internet connection.")
        temporary.replace(path)
        return path
    except PortraitProcessingError:
        raise
    except OSError as exc:
        raise PortraitProcessingError("MODEL_DOWNLOAD", "The portrait model could not be downloaded or saved. Check the setup terminal for the network or folder error, then run setup again.") from exc
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def clean_layout(value):
    if value is None:
        return dict(DEFAULT_LAYOUT)
    if not isinstance(value, dict):
        raise ValueError("Check your portrait position.")
    layout = {}
    for key, lower, upper in [("x", -12, 12), ("y", 0, 12), ("scale", .75, 1)]:
        raw = value.get(key, DEFAULT_LAYOUT[key])
        try:
            number = float(raw)
        except (ValueError, TypeError, OverflowError) as exc:
            raise ValueError("Check your portrait position.") from exc
        if isinstance(raw, bool) or not math.isfinite(number) or not lower <= number <= upper:
            raise ValueError("Check your portrait position.")
        layout[key] = round(number, 4)
    return layout


def portrait_info(data):
    with Image.open(BytesIO(bytes(data))) as image:
        transparent = image.mode in ("RGBA", "LA") or "transparency" in image.info
        alpha = image.convert("RGBA").getchannel("A")
        low, high = alpha.getextrema()
        transparent = transparent and low < 240 and high > 128
        raw = image.info.get(_META)
        try:
            layout = clean_layout(json.loads(raw)) if raw else dict(DEFAULT_LAYOUT)
        except (ValueError, TypeError, json.JSONDecodeError):
            layout = dict(DEFAULT_LAYOUT)
        return {"cutout": transparent, "layout": layout, "prepared": bool(raw) and transparent}


@lru_cache(maxsize=1)
def get_session():
    try:
        import onnxruntime as ort
    except (ImportError, OSError) as exc:
        code = "RUNTIME_LOAD" if "DLL" in str(exc) or isinstance(exc, OSError) else "DEPENDENCY_MISSING"
        raise PortraitProcessingError(code, "The photo processor is unavailable in the Python environment running this app. Run the photo repair setup and start the app with python -m streamlit run app.py. The terminal has the full error.") from exc
    # Use the verified ONNX model directly. The previous rembg import also loaded
    # Numba/PyMatting even when only segmentation was needed, making every upload
    # depend on additional native/JIT libraries. No face synthesis is performed.
    path = ensure_model()
    options = ort.SessionOptions()
    options.intra_op_num_threads = 4
    options.inter_op_num_threads = 1
    try:
        return ort.InferenceSession(str(path), sess_options=options, providers=["CPUExecutionProvider"])
    except Exception as exc:
        raise PortraitProcessingError("MODEL_LOAD", "The portrait model could not start. Run the photo repair setup; its self-test will show the exact runtime error.") from exc


def _remove_background(image):
    """U-2-Net human mask, using the original model's input normalization."""
    import numpy as np

    session = get_session()
    pixels = np.asarray(image.convert("RGB").resize((320, 320), Image.Resampling.LANCZOS), dtype=np.float32)
    pixels = pixels / max(float(pixels.max()), 1e-6)
    pixels = (pixels - np.array([.485, .456, .406], dtype=np.float32)) / np.array([.229, .224, .225], dtype=np.float32)
    tensor = np.ascontiguousarray(pixels.transpose(2, 0, 1)[None], dtype=np.float32)
    try:
        with _INFERENCE_LOCK:
            prediction = session.run(None, {session.get_inputs()[0].name: tensor})[0][0, 0]
    except Exception as exc:
        raise PortraitProcessingError("INFERENCE_FAILED", "The photo processor stopped while reading this image. Run python utils/setup_profile_portrait.py to check the processor, then retry.") from exc
    if prediction.shape != (320, 320) or not np.isfinite(prediction).all():
        raise PortraitProcessingError("MODEL_OUTPUT", "The photo processor returned an invalid mask. Run the photo repair setup before trying again.")
    low, high = float(prediction.min()), float(prediction.max())
    if high - low < 1e-6:
        raise ValueError("No clear person was found in this photo. Choose a portrait with one visible person.")
    mask = Image.fromarray(np.clip((prediction - low) / (high - low) * 255, 0, 255).astype("uint8"))
    mask = mask.resize(image.size, Image.Resampling.LANCZOS)
    # Keep soft edges while removing very faint background haze. This avoids the
    # optional JIT alpha-matting stage that could fail independently of the model.
    mask = mask.point([max(0, min(255, round((value - 8) * 255 / 239))) for value in range(256)])
    result = image.convert("RGBA")
    result.putalpha(mask)
    return result


def _encode(image, layout):
    metadata = PngImagePlugin.PngInfo()
    metadata.add_text(_META, json.dumps(clean_layout(layout), separators=(",", ":")))
    out = BytesIO()
    image.save(out, "PNG", pnginfo=metadata, optimize=True)
    data = out.getvalue()
    if len(data) > 5 * 1024 * 1024:
        image = image.copy()
        image.thumbnail((900, 1250), Image.Resampling.LANCZOS)
        out = BytesIO(); image.save(out, "PNG", pnginfo=metadata, optimize=True)
        data = out.getvalue()
    if len(data) > 5 * 1024 * 1024:
        raise ValueError("This portrait is too large after processing. Choose a smaller photo.")
    return data


def _validate_photo(data):
    # Keep the processor usable by setup before the project UI is installed.
    if not isinstance(data, (bytes, bytearray, memoryview)) or not data:
        raise ValueError("Choose a PNG or JPEG photo.")
    data = bytes(data)
    if len(data) > 5 * 1024 * 1024:
        raise ValueError("Choose a photo no larger than 5 MB.")
    try:
        with Image.open(BytesIO(data)) as image:
            if image.format not in ("PNG", "JPEG"):
                raise ValueError("Choose a PNG or JPEG photo.")
            if image.width * image.height > 20_000_000:
                raise ValueError("Choose a photo smaller than 20 megapixels.")
            image.verify()
        with Image.open(BytesIO(data)) as image:
            image.load()
    except (UnidentifiedImageError, OSError, SyntaxError, Image.DecompressionBombError) as exc:
        raise ValueError("This image could not be opened. Choose another PNG or JPEG.") from exc
    return data


@lru_cache(maxsize=6)
def prepare_portrait(data):
    """Return a tightly framed, transparent PNG. Results are cached in process memory."""
    data = _validate_photo(data)
    info = portrait_info(data)
    if info["prepared"]:
        return data
    with Image.open(BytesIO(data)) as source:
        image = ImageOps.exif_transpose(source).convert("RGBA")
    image.thumbnail((1400, 1800), Image.Resampling.LANCZOS)
    if not info["cutout"]:
        try:
            image = _remove_background(image)
        except (PortraitProcessingError, ValueError):
            raise
        except ImportError as exc:
            raise PortraitProcessingError("DEPENDENCY_MISSING", "A photo-processing package is missing. Run the photo repair setup in the same Python environment as this app.") from exc
        except Exception as exc:
            raise PortraitProcessingError("PROCESSING_FAILED", "Photo processing failed. Run python utils/setup_profile_portrait.py; the terminal will show the exact cause.") from exc
    try:
        import numpy as np
        from scipy import ndimage
    except ImportError as exc:
        raise PortraitProcessingError("DEPENDENCY_MISSING", "A photo-processing package is missing. Run the photo repair setup in the same Python environment as this app.") from exc
    alpha = image.getchannel("A")
    labels, count = ndimage.label(np.asarray(alpha) > 80)
    if not count:
        raise ValueError("No clear subject was found. Choose another portrait.")
    sizes = np.bincount(labels.ravel()); sizes[0] = 0
    rows, columns = np.nonzero(labels == sizes.argmax())
    padding = 18
    bbox = (max(0, int(columns.min())-padding), max(0, int(rows.min())-padding),
            min(image.width, int(columns.max())+1+padding), min(image.height, int(rows.max())+1+padding))
    image = image.crop(bbox)
    return _encode(image, info["layout"])


def position_portrait(data, layout):
    data = prepare_portrait(bytes(data))
    with Image.open(BytesIO(data)) as source:
        image = source.convert("RGBA")
    return _encode(image, clean_layout(layout))


def avatar_uri(data):
    """Crop the upper subject area for the small account and identity avatars."""
    with Image.open(BytesIO(bytes(data))) as source:
        image = ImageOps.exif_transpose(source).convert("RGBA")
    width, height = image.size
    crop_side = min(width, max(1, round(height * .52)))
    alpha = image.getchannel("A")
    upper_bbox = alpha.crop((0, 0, width, min(height, crop_side))).point(lambda p: 255 if p > 80 else 0).getbbox()
    center = (upper_bbox[0] + upper_bbox[2]) / 2 if upper_bbox else width / 2
    left = max(0, min(width - crop_side, round(center - crop_side / 2)))
    image = image.crop((left, 0, left + crop_side, crop_side))
    image.thumbnail((200, 200), Image.Resampling.LANCZOS)
    out = BytesIO(); image.save(out, "PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(out.getvalue()).decode("ascii")
