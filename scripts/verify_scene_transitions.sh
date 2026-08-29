#!/usr/bin/env bash

set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
transition_dir="$repo_root/frontend/public/openflipbook/guiyang/transitions"
mapping_file="$repo_root/frontend/lib/openflipbook-guiyang.ts"

if ! command -v ffprobe >/dev/null 2>&1; then
  echo "ffprobe is required" >&2
  exit 1
fi

files=("$transition_dir"/*.mp4)
if [[ ! -f "${files[0]}" || "${#files[@]}" -ne 28 ]]; then
  echo "expected 28 transition videos, found ${#files[@]}" >&2
  exit 1
fi

references="$(rg -o '[a-z0-9-]+\.mp4' "$mapping_file" | sort -u)"
reference_count="$(printf '%s\n' "$references" | sed '/^$/d' | wc -l | tr -d ' ')"
if [[ "$reference_count" -ne 28 ]]; then
  echo "expected 28 unique video references, found $reference_count" >&2
  exit 1
fi

while IFS= read -r filename; do
  [[ -z "$filename" ]] && continue
  if [[ ! -f "$transition_dir/$filename" ]]; then
    echo "missing referenced video: $filename" >&2
    exit 1
  fi
done <<< "$references"

for file in "${files[@]}"; do
  codec="$(ffprobe -v error -select_streams v:0 -show_entries stream=codec_name -of default=nw=1:nk=1 "$file")"
  dimensions="$(ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of csv=p=0:s=x "$file")"
  pixel_format="$(ffprobe -v error -select_streams v:0 -show_entries stream=pix_fmt -of default=nw=1:nk=1 "$file")"
  frame_rate="$(ffprobe -v error -select_streams v:0 -show_entries stream=r_frame_rate -of default=nw=1:nk=1 "$file")"
  frame_count="$(ffprobe -v error -select_streams v:0 -show_entries stream=nb_frames -of default=nw=1:nk=1 "$file")"
  if [[ "$codec" != "h264" || "$dimensions" != "1024x576" || "$pixel_format" != "yuv420p" || "$frame_rate" != "24/1" || "$frame_count" != "49" ]]; then
    echo "invalid video: $(basename "$file")" >&2
    exit 1
  fi
done

if command -v shasum >/dev/null 2>&1; then
  unique_count="$(shasum -a 256 "${files[@]}" | awk '{print $1}' | sort -u | wc -l | tr -d ' ')"
else
  unique_count="$(sha256sum "${files[@]}" | awk '{print $1}' | sort -u | wc -l | tr -d ' ')"
fi

if [[ "$unique_count" -ne 28 ]]; then
  echo "expected 28 unique videos, found $unique_count" >&2
  exit 1
fi

echo "28 transition videos verified: H.264, 1024x576, 24 fps, 49 frames, all unique"

