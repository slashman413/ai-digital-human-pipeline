#!/usr/bin/env python3
"""Transcribe audio to an SRT subtitle file using openai-whisper.

If whisper is unavailable, or the audio is missing/empty, it writes a minimal
valid 1-cue SRT placeholder so FFmpeg (and the rest of the pipeline) won't fail.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def format_timestamp(seconds: float) -> str:
    """Format seconds as an SRT timestamp: HH:MM:SS,mmm."""
    if seconds < 0:
        seconds = 0.0
    millis = int(round(seconds * 1000.0))
    hours, millis = divmod(millis, 3600 * 1000)
    minutes, millis = divmod(millis, 60 * 1000)
    secs, millis = divmod(millis, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def segments_to_srt(segments) -> str:
    """Render whisper segments into standard SRT text.

    Collapses consecutive duplicate cue texts into a single cue. Whisper
    (especially the tiny model) is prone to repetition loops where the same
    line is emitted over and over; merging identical back-to-back cues keeps
    that repetition off screen instead of flashing the same subtitle.
    """
    cues = []
    for seg in segments:
        text = str(seg.get("text", "")).strip()
        if not text:
            continue
        start = float(seg.get("start", 0.0))
        end = float(seg.get("end", 0.0))
        if cues and cues[-1]["text"] == text:
            # Same text as the previous cue -> extend its end, don't repeat it.
            cues[-1]["end"] = max(cues[-1]["end"], end)
            continue
        cues.append({"start": start, "end": end, "text": text})

    lines = []
    for i, cue in enumerate(cues, start=1):
        lines.append(str(i))
        lines.append(f"{format_timestamp(cue['start'])} --> {format_timestamp(cue['end'])}")
        lines.append(cue["text"])
        lines.append("")  # blank line separates cues
    return "\n".join(lines).strip() + "\n"


def placeholder_srt() -> str:
    """A minimal valid single-cue SRT so FFmpeg has something to burn in."""
    return (
        "1\n"
        "00:00:00,000 --> 00:00:02,000\n"
        "\n"
    )


def write_srt(output: str, content: str) -> None:
    out_dir = os.path.dirname(os.path.abspath(output))
    os.makedirs(out_dir, exist_ok=True)
    with open(output, "w", encoding="utf-8") as f:
        f.write(content)


def main() -> None:
    parser = argparse.ArgumentParser(description="Transcribe audio to SRT via whisper.")
    parser.add_argument("--audio", required=True, help="Input audio file (mp3).")
    parser.add_argument("--model", required=True, help="Whisper model name, e.g. tiny.")
    parser.add_argument("--output", required=True, help="Output .srt path.")
    parser.add_argument("--language", default=None,
                        help="Force transcription language (e.g. zh, en). Default: auto-detect.")
    args = parser.parse_args()

    # Guard: missing or empty audio -> placeholder SRT.
    if not os.path.exists(args.audio) or os.path.getsize(args.audio) == 0:
        print("[warn] audio is missing or empty; writing placeholder SRT.")
        write_srt(args.output, placeholder_srt())
        return

    try:
        import whisper  # imported lazily so a missing package is handled gracefully

        model = whisper.load_model(args.model)
        # Anti-repetition decoding options. condition_on_previous_text=False is
        # the key one: it stops Whisper feeding its own prior output back in,
        # which is what makes the tiny model loop the same phrase forever.
        # compression_ratio_threshold + temperature fallback re-decode any
        # segment whose output looks repetitive/degenerate.
        result = model.transcribe(
            args.audio,
            language=args.language,
            task="transcribe",
            condition_on_previous_text=False,
            compression_ratio_threshold=2.4,
            logprob_threshold=-1.0,
            no_speech_threshold=0.6,
            temperature=(0.0, 0.2, 0.4, 0.6, 0.8, 1.0),
        )
        segments = result.get("segments") or []
        if not segments:
            print("[warn] whisper returned no segments; writing placeholder SRT.")
            write_srt(args.output, placeholder_srt())
            return
        write_srt(args.output, segments_to_srt(segments))
        print(f"[ok] wrote {len(segments)} subtitle cues to {args.output}")
    except ImportError:
        print("[warn] openai-whisper is not installed; writing placeholder SRT.")
        write_srt(args.output, placeholder_srt())
    except Exception as exc:  # model download failure, decode error, etc.
        print(f"[warn] whisper transcription failed ({exc}); writing placeholder SRT.")
        write_srt(args.output, placeholder_srt())


if __name__ == "__main__":
    main()
