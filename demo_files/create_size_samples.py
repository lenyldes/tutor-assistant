"""Создаёт два корректных PDF точно на границе ограничения размера."""

import argparse
from pathlib import Path

LIMIT = 20 * 1024 * 1024
CONTENT = b"BT /F1 14 Tf 72 750 Td (Synthetic observation diary) Tj ET\n"


def pdf_parts(stream_size: int) -> tuple[bytes, bytes]:
    """Собирает обрамление PDF с корректными смещениями объектов."""
    prefix = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    objects = (
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    )
    for index, body in enumerate(objects, start=1):
        offsets.append(len(prefix))
        prefix.extend(f"{index} 0 obj\n".encode())
        prefix.extend(body + b"\nendobj\n")
    offsets.append(len(prefix))
    prefix.extend(f"5 0 obj\n<< /Length {stream_size} >>\nstream\n".encode())

    suffix = bytearray(b"\nendstream\nendobj\n")
    xref_offset = len(prefix) + stream_size + len(suffix)
    suffix.extend(b"xref\n0 6\n0000000000 65535 f \n")
    for offset in offsets[1:]:
        suffix.extend(f"{offset:010} 00000 n \n".encode())
    suffix.extend(f"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode())
    return bytes(prefix), bytes(suffix)


def create_pdf(path: Path, target_size: int) -> None:
    """Записывает PDF с видимым текстом и потоком из допустимых пробелов."""
    stream_size = target_size
    while True:
        prefix, suffix = pdf_parts(stream_size)
        adjusted = target_size - len(prefix) - len(suffix)
        if adjusted == stream_size:
            break
        stream_size = adjusted
    if stream_size < len(CONTENT):
        raise ValueError("Целевой размер меньше служебных данных PDF")

    with path.open("wb") as output:
        output.write(prefix)
        output.write(CONTENT)
        remaining = stream_size - len(CONTENT)
        chunk = b" " * 1024 * 1024
        while remaining:
            count = min(remaining, len(chunk))
            output.write(chunk[:count])
            remaining -= count
        output.write(suffix)
    assert path.stat().st_size == target_size


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).parent / "size")
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    create_pdf(args.output_dir / "дневник_наблюдений_20МБ.pdf", LIMIT)
    create_pdf(args.output_dir / "дневник_наблюдений_20МБ_плюс_1.pdf", LIMIT + 1)


if __name__ == "__main__":
    main()
