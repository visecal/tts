"""Utilities for rendering subtitle (SRT) files into concurrent TTS audio batches."""

from __future__ import annotations

import os
import tempfile
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Iterable, List, Tuple

import srt

from handle_text import prepare_tts_input_with_context
from tts_handler import generate_speech
from utils import DETAILED_ERROR_LOGGING

# Allow the worker count to be configured via env var while providing
# a sensible default for multi-request, multi-segment workloads.
DEFAULT_WORKERS = int(os.getenv("SUBTITLE_WORKERS", os.cpu_count() or 4))


def parse_srt_content(srt_content: str) -> List[srt.Subtitle]:
    """Parse SRT text into subtitle objects."""
    return list(srt.parse(srt_content))


def _render_segment(
    subtitle: srt.Subtitle,
    voice: str,
    response_format: str,
    speed: float,
    sanitize_text: bool,
) -> Tuple[int, str]:
    """Render an individual subtitle line to an audio file."""
    text = subtitle.content
    if sanitize_text:
        text = prepare_tts_input_with_context(text)

    output_path = generate_speech(text, voice, response_format, speed)
    return subtitle.index, output_path


def render_subtitles_to_zip(
    subtitles: Iterable[srt.Subtitle],
    voice: str,
    response_format: str,
    speed: float,
    sanitize_text: bool = True,
    max_workers: int = DEFAULT_WORKERS,
) -> Tuple[str, int]:
    """Generate audio for each subtitle concurrently and package into a zip.

    Returns the path to the zip archive and the number of generated clips.
    """

    results: List[Tuple[int, str]] = []
    errors: List[str] = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_map = {
            executor.submit(
                _render_segment, subtitle, voice, response_format, speed, sanitize_text
            ): subtitle
            for subtitle in subtitles
        }

        for future in as_completed(future_map):
            subtitle = future_map[future]
            try:
                index, path = future.result()
                results.append((index, path))
            except Exception as exc:  # pragma: no cover - logging path
                error_message = (
                    f"Failed to render subtitle {subtitle.index} "
                    f"({subtitle.start} -> {subtitle.end}): {exc}"
                )
                errors.append(error_message)
                if DETAILED_ERROR_LOGGING:
                    print(error_message)

    if errors:
        raise RuntimeError("; ".join(errors))

    zip_path = tempfile.NamedTemporaryFile(delete=False, suffix=".zip").name
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for index, path in sorted(results, key=lambda item: item[0]):
            clip_path = Path(path)
            arcname = f"{index:04d}.{response_format}"
            archive.write(clip_path, arcname=arcname)
            clip_path.unlink(missing_ok=True)

    return zip_path, len(results)

