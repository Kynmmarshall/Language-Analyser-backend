"""Render the report's PlantUML sources through the public PlantUML server.

PlantUML is not installed locally, so each .puml file is deflate-compressed, encoded in
PlantUML's own base64 variant, and fetched as a PNG. Re-run after editing any diagram:

    python tools/render_diagrams.py
"""

from __future__ import annotations

import sys
import urllib.error
import urllib.request
import zlib
from pathlib import Path

SERVER = "https://www.plantuml.com/plantuml/png/"
ROOT = Path(__file__).resolve().parent.parent
DIAGRAMS = ROOT / "diagrams"
FIGURES = ROOT / "figures"

_ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz-_"


def _encode_byte(value: int) -> str:
    return _ALPHABET[value & 0x3F]


def _encode_triplet(b1: int, b2: int, b3: int) -> str:
    return (
        _encode_byte(b1 >> 2)
        + _encode_byte(((b1 & 0x3) << 4) | (b2 >> 4))
        + _encode_byte(((b2 & 0xF) << 2) | (b3 >> 6))
        + _encode_byte(b3 & 0x3F)
    )


def plantuml_encode(source: str) -> str:
    """PlantUML's URL encoding: raw deflate, then a base64 variant with its own alphabet."""
    raw = zlib.compress(source.encode("utf-8"))[2:-4]
    chunks = []
    for index in range(0, len(raw), 3):
        block = raw[index : index + 3]
        b1 = block[0]
        b2 = block[1] if len(block) > 1 else 0
        b3 = block[2] if len(block) > 2 else 0
        chunks.append(_encode_triplet(b1, b2, b3))
    return "".join(chunks)


def render(path: Path) -> bool:
    target = FIGURES / f"{path.stem}.png"
    url = SERVER + plantuml_encode(path.read_text(encoding="utf-8"))
    # The server answers 403 to requests that do not identify themselves.
    request = urllib.request.Request(url, headers={"User-Agent": "francanglais-report/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            payload = response.read()
    except (urllib.error.URLError, TimeoutError) as error:
        print(f"  FAILED {path.name}: {error}")
        return False
    # The server answers 200 with a PNG of the error text when a diagram does not parse.
    if not payload.startswith(b"\x89PNG"):
        print(f"  FAILED {path.name}: server did not return a PNG")
        return False
    target.write_bytes(payload)
    print(f"  {path.name} -> figures/{target.name} ({len(payload):,} bytes)")
    return True


def main() -> int:
    FIGURES.mkdir(exist_ok=True)
    sources = sorted(DIAGRAMS.glob("*.puml"))
    if not sources:
        print("No .puml sources found.")
        return 1
    print(f"Rendering {len(sources)} diagram(s) via {SERVER}")
    failures = [p.name for p in sources if not render(p)]
    if failures:
        print(f"\n{len(failures)} diagram(s) failed: {', '.join(failures)}")
        return 1
    print("\nAll diagrams rendered.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
