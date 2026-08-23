"""Real, evidence-gated YouTube transcription — the nkama way.

Pulls a video's OWN official/auto captions via yt-dlp (never an LLM guess at
what was said), scaffolds a real nkama run package around the result, and
writes an evidence manifest that checks the transcript is real substantial
content, not a stub or a hallucinated placeholder.

This does NOT use an LLM to transcribe. yt-dlp reads YouTube's own caption
track. The "nkama way" part is wrapping that real artifact in a re-runnable,
independently-checkable evidence package instead of just pasting a summary
into a chat and calling it done.
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

from .workflow import AI_OUTPUT_DIR, create_run_package

TRANSCRIPT_FILENAME = "transcript.txt"
VTT_FILENAME = "video.en.vtt"
MIN_WORDS = 200  # below this, treat it as a stub/failed pull, not a real transcript


def _clean_vtt(vtt_text: str) -> str:
    """Strip WebVTT timestamps/cue markup, drop duplicate consecutive lines
    (auto-captions repeat the same line across overlapping cues)."""
    out: list[str] = []
    prev: str | None = None
    for line in vtt_text.splitlines():
        line = re.sub(r"<[^>]+>", "", line).strip()
        if not line or "-->" in line or line.startswith(("WEBVTT", "Kind:", "Language:")):
            continue
        if line != prev:
            out.append(line)
            prev = line
    return " ".join(out)


def fetch_transcript(url: str, *, lang: str = "en", work_dir: Path) -> str:
    """Real captions only — raises if yt-dlp is missing or the video has none,
    rather than silently falling back to a made-up transcript."""
    if shutil.which("yt-dlp") is None:
        raise RuntimeError(
            "yt-dlp is not installed. Install it (e.g. `brew install yt-dlp`) — "
            "this tool never fabricates a transcript when the real one is unavailable."
        )
    work_dir.mkdir(parents=True, exist_ok=True)
    out_stem = work_dir / "video"
    cmd = [
        "yt-dlp", "--write-auto-sub", "--skip-download",
        "--sub-lang", lang, "--sub-format", "vtt",
        "-o", f"{out_stem}.%(ext)s", url,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    vtt_path = work_dir / f"video.{lang}.vtt"
    if result.returncode != 0 or not vtt_path.is_file():
        raise RuntimeError(
            f"yt-dlp could not fetch captions for {url} (exit {result.returncode}). "
            f"stderr: {result.stderr[-500:]}"
        )
    return _clean_vtt(vtt_path.read_text(encoding="utf-8", errors="replace"))


def _manifest_for_transcript() -> dict:
    return {
        "schema_version": 1,
        "allowed_command_prefixes": [["python3"]],
        "checks": [
            {
                "id": "transcript_exists",
                "name": "Real transcript file exists",
                "type": "file_exists",
                "path": TRANSCRIPT_FILENAME,
            },
            {
                "id": "transcript_substantial",
                "name": "Transcript is real content, not a stub or placeholder",
                "type": "command_exit_zero",
                "command": [
                    "python3", "-c",
                    f"import sys; n = len(open('{TRANSCRIPT_FILENAME}').read().split()); "
                    f"sys.exit(0 if n >= {MIN_WORDS} else 1)",
                ],
            },
            {
                "id": "answer_file_exists",
                "name": "Answer file exists",
                "type": "file_exists",
                "path": "ANSWER.md",
            },
            {
                "id": "answer_mentions_evidence",
                "name": "Answer mentions evidence",
                "type": "file_contains",
                "path": "ANSWER.md",
                "text": "Evidence:",
            },
        ],
        "_instructions": [
            "Extend these checks with claims specific to what you did with the "
            "transcript (e.g. file_contains checks for real quoted phrases), "
            "so a false summary of the video fails verification.",
        ],
    }


def run_youtube_transcribe(url: str, *, output_dir: str | None = None,
                            lang: str = "en", overwrite: bool = False) -> dict:
    """Real, re-runnable pipeline: fetch real captions -> scaffold a real nkama
    run package -> write the transcript + a manifest that checks it's real."""
    prompt = (
        f"Real transcription of YouTube video {url}, fetched via yt-dlp's own "
        f"official/auto caption track (language={lang}), not an LLM guess."
    )
    package = create_run_package(
        prompt=prompt, output_dir=output_dir,
        title="Nkama YouTube Transcribe", overwrite=overwrite,
    )
    ai_output = Path(package["ai_output_dir"])
    transcript = fetch_transcript(url, lang=lang, work_dir=ai_output / "_yt_raw")
    (ai_output / TRANSCRIPT_FILENAME).write_text(transcript, encoding="utf-8")

    import json
    manifest_path = ai_output / "evidence_manifest.json"
    manifest_path.write_text(json.dumps(_manifest_for_transcript(), indent=2), encoding="utf-8")

    word_count = len(transcript.split())
    answer = (
        f"# Real transcript — {url}\n\n"
        f"## Answer\n\nFetched via yt-dlp's real caption track (not an LLM guess), "
        f"{word_count} words.\n\n"
        f"## Evidence:\n\n- `{TRANSCRIPT_FILENAME}` — real captions from the video itself\n\n"
        f"## Limitations:\n\n- Auto-generated captions can contain minor transcription "
        f"errors (proper nouns, homophones). This is YouTube's own ASR output, not "
        f"independently re-transcribed.\n"
    )
    (ai_output / "ANSWER.md").write_text(answer, encoding="utf-8")

    package["transcript_path"] = str(ai_output / TRANSCRIPT_FILENAME)
    package["word_count"] = word_count
    return package


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="nkama-youtube-transcribe",
        description="Fetch a YouTube video's real captions and wrap them in a nkama evidence run.",
    )
    p.add_argument("url", help="YouTube video URL")
    p.add_argument("--output", default=None, help="Run output directory")
    p.add_argument("--lang", default="en", help="Caption language (default: en)")
    p.add_argument("--overwrite", action="store_true")
    args = p.parse_args(argv)

    try:
        result = run_youtube_transcribe(
            args.url, output_dir=args.output, lang=args.lang, overwrite=args.overwrite,
        )
    except (RuntimeError, FileExistsError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    import json
    print(json.dumps(result, indent=2, default=str))
    print(f"\nverify with: uvx --from nkama-fact-benchmark nkama-evidence-layer "
          f"{Path(result['ai_output_dir']) / 'evidence_manifest.json'} --allow-commands")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
