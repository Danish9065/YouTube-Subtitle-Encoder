#!/usr/bin/env python3
"""
Export YouTube video or playlist subtitles to PDF files.

This tool uses yt-dlp to discover YouTube subtitles/captions and ReportLab to
render the transcript locally. It does not use any paid API.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import ssl
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

try:
    import certifi
except ImportError:  # pragma: no cover - optional runtime improvement
    certifi = None

try:
    import yt_dlp
except ImportError:  # pragma: no cover - exercised by real CLI usage
    yt_dlp = None

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        PageBreak,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )
except ImportError:  # pragma: no cover - exercised by real CLI usage
    colors = None


VTT_TIMESTAMP_RE = re.compile(
    r"(?P<start>\d{1,2}:\d{2}(?::\d{2})?[.,]\d{3})\s+-->\s+"
    r"(?P<end>\d{1,2}:\d{2}(?::\d{2})?[.,]\d{3})"
)
TAG_RE = re.compile(r"<[^>]+>")
SPACES_RE = re.compile(r"\s+")
SAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9._ -]+")


@dataclass(frozen=True)
class CaptionLine:
    start: str
    end: str
    text: str


@dataclass(frozen=True)
class VideoJob:
    title: str
    url: str
    video_id: str


def require_dependencies() -> None:
    missing = []
    if yt_dlp is None:
        missing.append("yt-dlp")
    if colors is None:
        missing.append("reportlab")

    if missing:
        joined = " ".join(missing)
        raise SystemExit(
            f"Missing dependency: {', '.join(missing)}\n"
            f"Install with: python3 -m pip install {joined}"
        )


def require_pdf_dependency() -> None:
    if colors is None:
        raise SystemExit(
            "Missing dependency: reportlab\n"
            "Install with: python3 -m pip install reportlab"
        )


def require_youtube_dependency() -> None:
    if yt_dlp is None:
        raise SystemExit(
            "Missing dependency: yt-dlp\n"
            "Install with: python3 -m pip install yt-dlp"
        )


def clean_caption_text(value: str) -> str:
    value = TAG_RE.sub("", value)
    value = html.unescape(value)
    value = value.replace("\u200b", "")
    value = SPACES_RE.sub(" ", value)
    return value.strip()


def parse_vtt(content: str) -> list[CaptionLine]:
    captions: list[CaptionLine] = []
    current_start: str | None = None
    current_end: str | None = None
    current_text: list[str] = []

    def flush() -> None:
        nonlocal current_start, current_end, current_text
        if current_start and current_end and current_text:
            text = clean_caption_text(" ".join(current_text))
            if text:
                captions.append(CaptionLine(current_start, current_end, text))
        current_start = None
        current_end = None
        current_text = []

    for raw_line in content.splitlines():
        line = raw_line.strip()
        match = VTT_TIMESTAMP_RE.search(line)
        if match:
            flush()
            current_start = normalize_timestamp(match.group("start"))
            current_end = normalize_timestamp(match.group("end"))
            continue

        if not line or line == "WEBVTT" or line.startswith(("Kind:", "Language:", "NOTE")):
            flush()
            continue

        if current_start and not line.isdigit():
            current_text.append(line)

    flush()
    return dedupe_caption_lines(captions)


def parse_json3(content: str) -> list[CaptionLine]:
    data = json.loads(content)
    captions: list[CaptionLine] = []

    for event in data.get("events", []):
        segments = event.get("segs") or []
        text = clean_caption_text("".join(segment.get("utf8", "") for segment in segments))
        if not text:
            continue
        start_ms = int(event.get("tStartMs", 0))
        duration_ms = int(event.get("dDurationMs", 0))
        captions.append(
            CaptionLine(
                milliseconds_to_timestamp(start_ms),
                milliseconds_to_timestamp(start_ms + duration_ms),
                text,
            )
        )

    return dedupe_caption_lines(captions)


def dedupe_caption_lines(captions: Iterable[CaptionLine]) -> list[CaptionLine]:
    cleaned: list[CaptionLine] = []
    previous_text = ""

    for caption in captions:
        if caption.text == previous_text:
            continue
        cleaned.append(caption)
        previous_text = caption.text

    return cleaned


def normalize_timestamp(value: str) -> str:
    value = value.replace(",", ".")
    pieces = value.split(":")
    if len(pieces) == 2:
        minutes, seconds = pieces
        return f"00:{int(minutes):02d}:{seconds}"
    hours, minutes, seconds = pieces
    return f"{int(hours):02d}:{int(minutes):02d}:{seconds}"


def milliseconds_to_timestamp(milliseconds: int) -> str:
    total_seconds, ms = divmod(milliseconds, 1000)
    minutes_total, seconds = divmod(total_seconds, 60)
    hours, minutes = divmod(minutes_total, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{ms:03d}"


def safe_filename(value: str, fallback: str = "youtube-subtitles") -> str:
    value = SAFE_FILENAME_RE.sub("", value).strip(" .")
    return value[:120] or fallback


def get_ydl(quiet: bool = True):
    require_youtube_dependency()
    return yt_dlp.YoutubeDL(
        {
            "quiet": quiet,
            "no_warnings": quiet,
            "skip_download": True,
            "extract_flat": False,
            "ignoreerrors": True,
        }
    )


def resolve_video_jobs(url: str, limit: int | None = None) -> list[VideoJob]:
    with get_ydl() as ydl:
        info = ydl.extract_info(url, download=False)

    if not info:
        raise RuntimeError("Could not read video or playlist information.")

    entries = info.get("entries")
    if not entries:
        return [
            VideoJob(
                title=info.get("title") or info.get("id") or "YouTube video",
                url=info.get("webpage_url") or url,
                video_id=info.get("id") or "video",
            )
        ]

    jobs: list[VideoJob] = []
    for entry in entries:
        if not entry:
            continue
        video_url = entry.get("webpage_url") or entry.get("url")
        video_id = entry.get("id") or "video"
        if video_url and not str(video_url).startswith("http"):
            video_url = f"https://www.youtube.com/watch?v={video_id}"
        jobs.append(
            VideoJob(
                title=entry.get("title") or video_id,
                url=video_url,
                video_id=video_id,
            )
        )
        if limit and len(jobs) >= limit:
            break

    if not jobs:
        raise RuntimeError("No videos were found in that playlist.")
    return jobs


def list_languages(url: str) -> None:
    with get_ydl(quiet=False) as ydl:
        info = ydl.extract_info(url, download=False)

    subtitles = sorted((info.get("subtitles") or {}).keys())
    automatic = sorted((info.get("automatic_captions") or {}).keys())

    print("Manual subtitles:")
    print(", ".join(subtitles) if subtitles else "  none")
    print("\nAutomatic captions:")
    print(", ".join(automatic) if automatic else "  none")


def fetch_video_captions(video: VideoJob, language: str, allow_auto: bool) -> tuple[str, list[CaptionLine], bool]:
    with get_ydl() as ydl:
        info = ydl.extract_info(video.url, download=False)

    if not info:
        raise RuntimeError(f"Could not read video: {video.url}")

    manual = info.get("subtitles") or {}
    automatic = info.get("automatic_captions") or {}
    source = manual
    is_auto = False

    if language not in source:
        if allow_auto and language in automatic:
            source = automatic
            is_auto = True
        else:
            available = sorted(set(manual) | set(automatic))
            hint = f" Available languages: {', '.join(available)}" if available else ""
            raise RuntimeError(f"No subtitles found for '{language}' in {video.title}.{hint}")

    subtitle_format = choose_subtitle_format(source[language])
    raw = download_text(subtitle_format["url"])
    ext = subtitle_format.get("ext")

    if ext == "json3":
        captions = parse_json3(raw)
    else:
        captions = parse_vtt(raw)

    if not captions:
        raise RuntimeError(f"Subtitles were found for {video.title}, but no text could be parsed.")

    return info.get("title") or video.title, captions, is_auto


def choose_subtitle_format(formats: list[dict]) -> dict:
    for preferred_ext in ("vtt", "json3"):
        for item in formats:
            if item.get("ext") == preferred_ext and item.get("url"):
                return item

    for item in formats:
        if item.get("url"):
            return item

    raise RuntimeError("No downloadable subtitle format found.")


def download_text(url: str, retries: int = 3, retry_delay: int = 90) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    contexts: list[ssl.SSLContext | None] = [None]
    if certifi is not None:
        contexts.append(ssl.create_default_context(cafile=certifi.where()))

    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        for context in contexts:
            try:
                with urllib.request.urlopen(request, timeout=30, context=context) as response:
                    charset = response.headers.get_content_charset() or "utf-8"
                    return response.read().decode(charset, errors="replace")
            except urllib.error.HTTPError as exc:
                last_error = exc
                if exc.code == 429 and attempt < retries:
                    time.sleep(retry_delay)
                    break
                if exc.code == 429:
                    raise RuntimeError(
                        "YouTube returned HTTP 429 Too Many Requests. Wait 15-30 minutes, then run again. "
                        "Already-created PDFs will be skipped."
                    ) from exc
                raise
            except urllib.error.URLError as exc:
                last_error = exc
                if "CERTIFICATE_VERIFY_FAILED" not in str(exc):
                    raise

    try:
        fallback_context = ssl._create_unverified_context()
        with urllib.request.urlopen(request, timeout=30, context=fallback_context) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            return response.read().decode(charset, errors="replace")
    except Exception as exc:
        raise RuntimeError(
            "Could not download subtitle text because Python could not verify the SSL certificate. "
            "Try running: python3 -m pip install --upgrade certifi"
        ) from (last_error or exc)


def write_pdf(
    output_path: Path,
    title: str,
    url: str,
    captions: list[CaptionLine],
    language: str,
    include_timestamps: bool,
    auto_caption: bool,
) -> None:
    require_pdf_dependency()
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "TranscriptTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=19,
        leading=24,
        spaceAfter=8,
    )
    meta_style = ParagraphStyle(
        "TranscriptMeta",
        parent=styles["Normal"],
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#4B5563"),
        spaceAfter=8,
    )
    body_style = ParagraphStyle(
        "TranscriptBody",
        parent=styles["BodyText"],
        fontSize=10,
        leading=14,
        spaceAfter=5,
    )
    time_style = ParagraphStyle(
        "TranscriptTime",
        parent=styles["BodyText"],
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#374151"),
    )

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=16 * mm,
        rightMargin=16 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title=title,
    )

    story = [
        Paragraph(html.escape(title), title_style),
        Paragraph(
            f"Source: {html.escape(url)}<br/>Language: {html.escape(language)}"
            f"{' (automatic captions)' if auto_caption else ''}",
            meta_style,
        ),
        Spacer(1, 4),
    ]

    if include_timestamps:
        rows = []
        for caption in captions:
            rows.append(
                [
                    Paragraph(html.escape(caption.start), time_style),
                    Paragraph(html.escape(caption.text), body_style),
                ]
            )
        table = Table(rows, colWidths=[28 * mm, 138 * mm], repeatRows=0)
        table.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 2),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ("LINEBELOW", (0, 0), (-1, -1), 0.2, colors.HexColor("#E5E7EB")),
                ]
            )
        )
        story.append(table)
    else:
        for caption in captions:
            story.append(Paragraph(html.escape(caption.text), body_style))

    doc.build(story)


def write_combined_pdf(
    output_path: Path,
    rendered_videos: list[tuple[VideoJob, str, list[CaptionLine], bool]],
    language: str,
    include_timestamps: bool,
) -> None:
    require_pdf_dependency()
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("CombinedTitle", parent=styles["Title"], fontSize=18, leading=23)
    meta_style = ParagraphStyle(
        "CombinedMeta",
        parent=styles["Normal"],
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#4B5563"),
    )
    body_style = ParagraphStyle("CombinedBody", parent=styles["BodyText"], fontSize=9.5, leading=13)
    time_style = ParagraphStyle(
        "CombinedTime",
        parent=styles["BodyText"],
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#374151"),
    )

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=16 * mm,
        rightMargin=16 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title="YouTube Playlist Subtitles",
    )

    story = []
    for index, (video, title, captions, auto_caption) in enumerate(rendered_videos, start=1):
        if index > 1:
            story.append(PageBreak())
        story.append(Paragraph(html.escape(f"{index}. {title}"), title_style))
        story.append(
            Paragraph(
                f"Source: {html.escape(video.url)}<br/>Language: {html.escape(language)}"
                f"{' (automatic captions)' if auto_caption else ''}",
                meta_style,
            )
        )
        story.append(Spacer(1, 6))

        if include_timestamps:
            rows = [
                [
                    Paragraph(html.escape(caption.start), time_style),
                    Paragraph(html.escape(caption.text), body_style),
                ]
                for caption in captions
            ]
            table = Table(rows, colWidths=[28 * mm, 138 * mm])
            table.setStyle(
                TableStyle(
                    [
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 0),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                        ("TOPPADDING", (0, 0), (-1, -1), 2),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                        ("LINEBELOW", (0, 0), (-1, -1), 0.2, colors.HexColor("#E5E7EB")),
                    ]
                )
            )
            story.append(table)
        else:
            for caption in captions:
                story.append(Paragraph(html.escape(caption.text), body_style))

    doc.build(story)


def run(args: argparse.Namespace) -> int:
    require_pdf_dependency()
    require_youtube_dependency()
    output_dir = Path(args.output).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.list_languages:
        list_languages(args.url)
        return 0

    jobs = resolve_video_jobs(args.url, args.limit)
    print(f"Found {len(jobs)} video(s).")

    rendered_videos: list[tuple[VideoJob, str, list[CaptionLine], bool]] = []
    for index, video in enumerate(jobs, start=1):
        if not args.combined:
            existing_pdf = output_dir / f"{safe_filename(video.title, video.video_id)}.{args.lang}.pdf"
            if existing_pdf.exists():
                print(f"[{index}/{len(jobs)}] Skipping existing PDF: {existing_pdf}")
                continue

        print(f"[{index}/{len(jobs)}] Reading subtitles: {video.title}")
        title, captions, auto_caption = fetch_video_captions(video, args.lang, args.auto)
        rendered_videos.append((video, title, captions, auto_caption))

        if not args.combined:
            filename = f"{safe_filename(title, video.video_id)}.{args.lang}.pdf"
            output_path = output_dir / filename
            write_pdf(output_path, title, video.url, captions, args.lang, args.timestamps, auto_caption)
            print(f"  saved {output_path}")

    if args.combined:
        output_path = output_dir / args.combined
        write_combined_pdf(output_path, rendered_videos, args.lang, args.timestamps)
        print(f"Saved combined PDF: {output_path}")

    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Convert YouTube video or playlist subtitles into PDF files.",
    )
    parser.add_argument("url", help="YouTube video or playlist URL")
    parser.add_argument("-o", "--output", default="subtitles", help="Output folder for PDFs")
    parser.add_argument("-l", "--lang", default="en", help="Subtitle language code, such as en, hi, es")
    parser.add_argument("--auto", action="store_true", help="Use automatic captions if manual subtitles are missing")
    parser.add_argument("--timestamps", action="store_true", help="Include start timestamps in the PDF")
    parser.add_argument("--combined", metavar="FILE.pdf", help="Create one combined PDF instead of one PDF per video")
    parser.add_argument("--limit", type=int, help="Limit number of playlist videos processed")
    parser.add_argument("--list-languages", action="store_true", help="Show available subtitle languages for a video")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        return run(args)
    except KeyboardInterrupt:
        print("\nCancelled.", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
