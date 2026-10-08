"""Fixed regression fixtures; adding fleet dumps must not change expected counts."""
from pathlib import Path


def reference_files():
    examples = Path(__file__).resolve().parents[1] / "examples"
    tags = ("1BBFB94", "1CFV8D4", "1CNR994", "1CR7KD4", "1DXLCD4",
            "1F5GLD4", "1FFV8D4", "1GLZQ34", "1JFLVF4", "1KFLVF4")
    return [next(examples.glob(f"idrac-{tag}.*/redfish_full.json")) for tag in tags]
