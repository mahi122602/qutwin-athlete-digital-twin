"""Verify dependencies, download/repair the model and test actual image inference."""
from pathlib import Path
import argparse
from io import BytesIO
import platform
import sys
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--photo", type=Path, help="Optional local JPEG/PNG to test; it is never uploaded or saved.")
    args = parser.parse_args()
    print("Python:", sys.executable, flush=True)
    print("Version:", platform.python_version(), platform.machine(), flush=True)
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("_qutwin_portrait_setup", ROOT / "services" / "profile_portrait.py")
        portrait = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(portrait)
        print("Processor:", portrait.PROCESSOR_BUILD, flush=True)
        import onnxruntime as ort
        import numpy
        import PIL
        import scipy
        import streamlit
        print("Packages:", "onnxruntime=" + ort.__version__, "numpy=" + numpy.__version__,
              "Pillow=" + PIL.__version__, "scipy=" + scipy.__version__, "streamlit=" + streamlit.__version__, flush=True)
        print("Model:", portrait.model_path(), flush=True)
        print("Checking model. A missing/incomplete download is repaired (about 176 MB).", flush=True)
        last = [-1]

        def progress(received, total):
            step = received // (16 * 1024 * 1024)
            if step != last[0]:
                last[0] = step
                print("Downloaded:", round(received / 1024 / 1024), "MB", flush=True)

        portrait.ensure_model(download=True, progress=progress)
        portrait.get_session()
        from PIL import Image, ImageDraw
        if args.photo:
            data = args.photo.read_bytes()
            print("Testing your local image (not saved or uploaded).", flush=True)
        else:
            # A synthetic human silhouette tests the real model pipeline without
            # bundling or disclosing a personal photograph.
            image = Image.new("RGB", (320, 400), (202, 220, 232))
            draw = ImageDraw.Draw(image)
            draw.rectangle((0, 280, 320, 400), fill=(112, 145, 111))
            draw.ellipse((115, 30, 205, 145), fill=(50, 33, 28))
            draw.ellipse((125, 42, 195, 142), fill=(208, 157, 121))
            draw.rectangle((148, 128, 172, 170), fill=(208, 157, 121))
            draw.rounded_rectangle((86, 152, 234, 327), radius=42, fill=(33, 57, 49))
            draw.rounded_rectangle((63, 173, 98, 329), radius=16, fill=(208, 157, 121))
            draw.rounded_rectangle((222, 173, 257, 329), radius=16, fill=(208, 157, 121))
            draw.rectangle((99, 310, 145, 399), fill=(38, 46, 55))
            draw.rectangle((175, 310, 221, 399), fill=(38, 46, 55))
            output = BytesIO()
            image.save(output, "JPEG")
            data = output.getvalue()
            print("Running end-to-end image self-test...", flush=True)
        result = portrait.prepare_portrait(data)
        if not portrait.portrait_info(result)["prepared"]:
            raise RuntimeError("Image self-test did not produce a transparent portrait.")
        placed = portrait.position_portrait(result, {"x": 1, "y": 2, "scale": .9})
        if portrait.portrait_info(placed)["layout"] != {"x": 1.0, "y": 2.0, "scale": .9}:
            raise RuntimeError("Portrait position self-test failed.")
        print("PHOTO SELF-TEST PASSED: image decoded, background removed, transparent PNG and placement verified.", flush=True)
        print("Start the app using this same Python: python -m streamlit run app.py", flush=True)
        return 0
    except Exception:
        print("\nPHOTO SETUP FAILED. The complete error follows:", file=sys.stderr, flush=True)
        traceback.print_exc()
        print("\nCopy the complete output from this window if you need help. Do not retry different photos until setup passes.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
