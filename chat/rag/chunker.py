"""
Semantic chunker for scripture PDFs.

Splits page-level text into semantic units:
- Sanskrit shlokas (Devanagari text blocks)
- Hindi translations
- Narration / dialogue / other content

This is critical because Sanskrit shlokas and their Hindi translations
carry different semantic meanings and should be indexed separately
for better retrieval quality.
"""

import logging
import re
from typing import Any

logger = logging.getLogger("chat.rag.chunker")

# Devanagari Unicode range: U+0900 to U+097F
DEVANAGARI_PATTERN = re.compile(r"[ऀ-ॿ]+")
# Pattern to detect shloka-like lines (Devanagari with possible verse markers)
SHLOKA_PATTERN = re.compile(r"[ऀ-ॿ\s]+[।॥\d]+", re.MULTILINE)
VERSE_MARKER_RE = re.compile(r"[।॥]\s*[0-9०-९]+\s*[।॥]?\s*$")
HINDI_PROSE_MARKERS = {
    "का",
    "के",
    "की",
    "को",
    "से",
    "में",
    "ने",
    "है",
    "हैं",
    "था",
    "थी",
    "थे",
    "यह",
    "इस",
    "उस",
    "उन",
    "लिए",
    "कर",
    "और",
    "परंतु",
    "किया",
    "दिया",
    "लिया",
    "हुआ",
    "लगा",
    "लगे",
    "देखकर",
    "कारण",
    "जिसके",
    "इसी",
    "उसने",
}


class ScriptureChunker:
    """Split scripture pages into semantic chunks."""

    def __init__(self, max_chunk_size: int = 1000):
        self.max_chunk_size = max_chunk_size

    def chunk_page(
        self,
        text: str,
        scripture_name: str,
        file_name: str,
        page_num: int,
        total_pages: int,
    ) -> list[dict[str, Any]]:
        """
        Split a page of text into semantic chunks.

        Args:
            text: Raw page text
            scripture_name: Name of the scripture
            file_name: PDF file name
            page_num: 1-indexed page number
            total_pages: Total pages in the PDF

        Returns:
            List of chunk dicts
        """
        chunks: list[dict[str, Any]] = []
        sections = self._pair_shloka_translations(self._split_sections(text))

        for section_type, section_text in sections:
            if not section_text.strip():
                continue

            # Further split long sections
            sub_chunks = self._split_long_text(section_text)

            for sub_text in sub_chunks:
                language = self._detect_language(sub_text, section_type)
                chunks.append(
                    {
                        "scripture": scripture_name,
                        "file_name": file_name,
                        "page": page_num,
                        "text": sub_text.strip(),
                        "chunk_type": section_type,
                        "language": language,
                    }
                )

        return chunks

    def _pair_shloka_translations(
        self,
        sections: list[tuple[str, str]],
    ) -> list[tuple[str, str]]:
        """Keep adjacent verse and translation together for citation display."""
        paired: list[tuple[str, str]] = []
        index = 0
        while index < len(sections):
            section_type, section_text = sections[index]
            if section_type == "shloka":
                verse_lines = [section_text.strip()]
                lookahead = index + 1
                while lookahead < len(sections) and sections[lookahead][0] == "shloka":
                    verse_lines.append(sections[lookahead][1].strip())
                    lookahead += 1
                next_section = (
                    sections[lookahead] if lookahead < len(sections) else None
                )
                if (
                    next_section is not None
                    and next_section[0] in {"translation", "narration"}
                    and len(next_section[1]) <= self.max_chunk_size
                ):
                    paired.append(
                        (
                            "verse_with_translation",
                            (
                                "Sanskrit verse:\n"
                                f"{'\n'.join(verse_lines)}\n\n"
                                "Translation:\n"
                                f"{next_section[1].strip()}"
                            ),
                        )
                    )
                    index = lookahead + 1
                    continue
                paired.append(("shloka", "\n".join(verse_lines)))
                index = lookahead
                continue
            next_section = sections[index + 1] if index + 1 < len(sections) else None
            if (
                section_type == "shloka"
                and next_section is not None
                and next_section[0] in {"translation", "narration"}
                and len(next_section[1]) <= self.max_chunk_size
            ):
                paired.append(
                    (
                        "verse_with_translation",
                        (
                            "Sanskrit verse:\n"
                            f"{section_text.strip()}\n\n"
                            "Translation:\n"
                            f"{next_section[1].strip()}"
                        ),
                    )
                )
                index += 2
                continue
            paired.append((section_type, section_text))
            index += 1
        return paired

    def _split_sections(self, text: str) -> list[tuple[str, str]]:
        """
        Split text into typed sections.

        Returns:
            List of (section_type, text) tuples
        """
        sections: list[tuple[str, str]] = []
        lines = text.split("\n")
        current_type = "narration"
        current_lines: list[str] = []

        for line in lines:
            line = _clean_ocr_line(line.strip())
            if not line:
                if current_lines:
                    sections.append((current_type, "\n".join(current_lines)))
                    current_lines = []
                continue

            line_type = self._classify_line(line)

            # Start a new section if type changes
            if line_type != current_type and current_lines:
                sections.append((current_type, "\n".join(current_lines)))
                current_lines = []

            current_type = line_type
            current_lines.append(line)

        # Don't forget the last section
        if current_lines:
            sections.append((current_type, "\n".join(current_lines)))

        return sections

    def _classify_line(self, line: str) -> str:
        """Classify a line as shloka, translation, or narration."""
        devanagari_chars = _devanagari_char_count(line)
        total_chars = len(line.strip())

        if total_chars == 0:
            return "narration"

        devanagari_ratio = devanagari_chars / total_chars
        has_danda = (
            "।" in line
            or "॥" in line
            or "|" in line
            or bool(VERSE_MARKER_RE.search(line))
        )

        # Devanagari is shared by Sanskrit and Hindi. Only explicit verse
        # punctuation/numbering is strong enough to label source text a shloka.
        if devanagari_chars >= 8 and has_danda and not _looks_like_hindi_prose(line):
            return "shloka"
        if devanagari_ratio > 0.6:
            return "translation"

        # If some Devanagari but mixed, likely translation
        if devanagari_ratio > 0.1:
            return "translation"

        return "narration"

    def _detect_language(self, text: str, chunk_type: str) -> str:
        """Detect the primary language of a text chunk."""
        devanagari_chars = _devanagari_char_count(text)
        total_chars = len(text.strip())

        if total_chars == 0:
            return "unknown"

        ratio = devanagari_chars / total_chars
        if chunk_type in {"shloka", "verse_with_translation"}:
            return "sa"
        if ratio > 0.5:
            return "hi"
        if ratio > 0.1:
            return "hi"  # Hindi (mixed Devanagari)
        return "en"  # English or other

    def _split_long_text(self, text: str) -> list[str]:
        """Split text that exceeds max_chunk_size."""
        if len(text) <= self.max_chunk_size:
            return [text]

        chunks = []
        sentences = re.split(r"(?<=[.!?।॥])\s+", text)
        current_chunk = ""

        for sentence in sentences:
            if len(current_chunk) + len(sentence) > self.max_chunk_size:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = sentence
            else:
                current_chunk += " " + sentence if current_chunk else sentence

        if current_chunk:
            chunks.append(current_chunk.strip())

        return chunks


def _devanagari_char_count(text: str) -> int:
    return sum(len(match.group(0)) for match in DEVANAGARI_PATTERN.finditer(text))


def _clean_ocr_line(line: str) -> str:
    if not DEVANAGARI_PATTERN.search(line):
        return line
    return re.sub(r"^(?:[A-Za-z]{1,12}\s+)+(?=[\u0900-\u097F])", "", line).strip()


def _looks_like_hindi_prose(line: str) -> bool:
    words = re.findall(r"[\u0900-\u097F]+", line)
    if not words:
        return False
    marker_count = sum(word in HINDI_PROSE_MARKERS for word in words)
    marker_count += sum(
        1
        for word in words
        if len(word) > 3
        and word.endswith(("का", "के", "की", "को", "से", "में", "ने", "कर"))
    )
    joined = " ".join(words)
    if marker_count >= 1 and len(words) <= 4:
        return True
    if marker_count >= 2:
        return True
    if len(words) >= 6 and marker_count >= 1:
        return True
    return any(
        phrase in joined
        for phrase in (
            "के लिये",
            "के लिए",
            "इस प्रकार",
            "यह सब",
            "उन्होंने",
            "उस समय",
        )
    )
