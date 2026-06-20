#!/usr/bin/env python3
"""Run local Wav2Lip lip-sync on a self-hosted Windows GPU runner.

If WAV2LIP_DIR / checkpoint / inference.py are not configured, warn and copy the
input video to the output as a pass-through so the pipeline still yields an artifact.
"""
import argparse
import os
import shutil
import subprocess
import sys


def passthrough(video: str, output: str, why: str):
    """Copy input video to output and exit 0."""
    print(f"[warn] {why}; copying input video as pass-through.", file=sys.stderr)
    if os.path.isfile(video):
        shutil.copyfile(video, output)
        print(f"[ok] pass-through artifact -> {output}")
    else:
        print(f"[warn] input video missing too: {video}; no artifact produced.", file=sys.stderr)
    sys.exit(0)


def main():
    parser = argparse.ArgumentParser(description="Wav2Lip lip-sync processing.")
    parser.add_argument("--video", required=True, help="path to face/source video")
    parser.add_argument("--audio", required=True, help="path to driving audio")
    parser.add_argument("--output", required=True, help="path to write result video")
    args = parser.parse_args()

    # Ensure output directory exists (Windows-safe absolute path).
    out_dir = os.path.dirname(os.path.abspath(args.output))
    os.makedirs(out_dir, exist_ok=True)

    wav2lip_dir = os.environ.get("WAV2LIP_DIR")
    if not wav2lip_dir:
        passthrough(args.video, args.output, "WAV2LIP_DIR not set (self-hosted GPU not configured)")

    checkpoint = os.path.join(wav2lip_dir, "checkpoints", "wav2lip_gan.pth")
    inference = os.path.join(wav2lip_dir, "inference.py")

    if not os.path.isfile(checkpoint):
        passthrough(args.video, args.output, f"checkpoint not found: {checkpoint}")
    if not os.path.isfile(inference):
        passthrough(args.video, args.output, f"inference.py not found: {inference}")
    if not os.path.isfile(args.audio):
        passthrough(args.video, args.output, f"audio not found: {args.audio}")

    # Invoke Wav2Lip inference via subprocess using the same Python interpreter.
    cmd = [
        sys.executable,
        inference,
        "--checkpoint_path", checkpoint,
        "--face", os.path.abspath(args.video),
        "--audio", os.path.abspath(args.audio),
        "--outfile", os.path.abspath(args.output),
    ]
    print(f"[info] running Wav2Lip: {' '.join(cmd)}")
    try:
        # Run from the Wav2Lip dir so its relative imports/assets resolve.
        subprocess.run(cmd, cwd=wav2lip_dir, check=True)
    except Exception as exc:
        passthrough(args.video, args.output, f"Wav2Lip inference failed ({exc})")

    if not (os.path.isfile(args.output) and os.path.getsize(args.output) > 0):
        passthrough(args.video, args.output, "Wav2Lip produced no output")

    print(f"[ok] Wav2Lip output -> {args.output}")


if __name__ == "__main__":
    main()
