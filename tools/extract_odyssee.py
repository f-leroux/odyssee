#!/usr/bin/env python3
"""Transforme le PDF de L'Odyssée en données paginées pour le lecteur web."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import tempfile
from pathlib import Path


PAGE_FOOTER = re.compile(r"^\s*[–—-]\s*\d+\s*[–—-]\s*$")
CHANT_HEADING = re.compile(r"^\s*(\d{1,2})\s*[.:]\s*$")


def roman(number: int) -> str:
    values = (
        (10, "X"),
        (9, "IX"),
        (5, "V"),
        (4, "IV"),
        (1, "I"),
    )
    result = []
    for value, glyph in values:
        while number >= value:
            result.append(glyph)
            number -= value
    return "".join(result)


def clean_lines(lines: list[str]) -> str:
    """Réunit les lignes visuelles du PDF en paragraphes lisibles."""
    paragraphs: list[str] = []
    current = ""

    for original in lines:
        line = original.strip()
        if not line:
            if current:
                paragraphs.append(current.strip())
                current = ""
            continue

        if PAGE_FOOTER.fullmatch(line):
            continue

        line = re.sub(r"\s+", " ", line)
        if not current:
            current = line
        elif current.endswith("-") and re.match(r"^[a-zà-öø-ÿœæ]", line):
            current = current[:-1] + line
        else:
            current += " " + line

    if current:
        paragraphs.append(current.strip())

    return "\n\n".join(paragraphs).strip()


def extract_pages(pdf_path: Path) -> list[dict]:
    with tempfile.TemporaryDirectory(prefix="odyssee-") as temporary:
        text_path = Path(temporary) / "odyssee.txt"
        subprocess.run(
            ["pdftotext", "-layout", str(pdf_path), str(text_path)],
            check=True,
        )
        physical_pages = text_path.read_text(encoding="utf-8").split("\f")

    output: list[dict] = []
    current_chant = 0

    # Les pages 1-3 sont la couverture et la table des matières. La page 348
    # ouvre les mentions de l'édition électronique, qui ne font pas partie du poème.
    for printed_page in range(4, 348):
        lines = physical_pages[printed_page - 1].splitlines()
        segments: list[tuple[int, list[str]]] = []
        segment_start = 0

        for index, line in enumerate(lines):
            match = CHANT_HEADING.fullmatch(line.strip())
            if not match:
                continue

            if index > segment_start and current_chant:
                segments.append((current_chant, lines[segment_start:index]))
            current_chant = int(match.group(1))
            segment_start = index + 1

        if current_chant:
            segments.append((current_chant, lines[segment_start:]))

        for chant, segment_lines in segments:
            text = clean_lines(segment_lines)
            if not text:
                continue

            notes: list[dict] = []
            if printed_page == 4 and chant == 1:
                text = text.replace("Muse,", "Muse[^1],", 1)
                notes.append(
                    {
                        "n": 1,
                        "note_html": (
                            "<strong>Muse :</strong> le poète invoque ici la divinité "
                            "qui inspire le chant épique, traditionnellement identifiée "
                            "à Calliope. Cette adresse inaugurale place le récit sous une "
                            "autorité divine. L’action commence <em>in medias res</em> : "
                            "Troie est déjà tombée et Odysseus erre encore loin d’Ithakè."
                        ),
                    }
                )

            output.append(
                {
                    "chant": chant,
                    "chapterTitle": f"Chant {roman(chant)}",
                    "pageNum": printed_page,
                    "text": text,
                    "notes": notes,
                }
            )

    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    pages = extract_pages(args.pdf)
    chants = sorted({page["chant"] for page in pages})
    if chants != list(range(1, 25)):
        raise SystemExit(f"Chants incomplets : {chants}")
    if not pages or pages[0]["pageNum"] != 4 or pages[-1]["pageNum"] != 347:
        raise SystemExit("Pagination inattendue dans le PDF source")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(pages, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"{len(pages)} pages/segments, {len(chants)} chants -> {args.output}")


if __name__ == "__main__":
    main()
