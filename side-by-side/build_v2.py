#!/Users/danbadea/Documents/Projects/Personal/football/side-by-side/.venv/bin/python3
"""
Build a side-by-side comparison of Busquets vs Rodri using ffmpeg.
Picks 14 segments (~2s each) from multiple video sources for variety.
"""
import subprocess, os, json, math

BASE = "/Users/danbadea/Documents/Projects/Personal/football/side-by-side"
os.chdir(BASE)

# Video sources
busquets_sources = [
    {"file": "busquets_shee2rLaoq4.webm", "dur": 310},
    {"file": "busquets_skills_Cl8DfBfxhf4.mkv", "dur": 446},
]
rodri_sources = [
    {"file": "rodri_e9c3wuptql0.webm", "dur": 507},
    {"file": "rodri_cdm_Lpz4PUPJ5kM.webm", "dur": 497},
]

SEGMENTS = 14
SEG_DUR = 2.0  # ~28 seconds total, close to 30

# Interleave sources: alternate between the two sources for variety
def pick_times(sources, n_segments):
    times = []
    total_dur = sum(s["dur"] for s in sources)
    seg_per_source = math.ceil(n_segments / len(sources))
    for si, src in enumerate(sources):
        step = max(1, src["dur"] // seg_per_source)
        for i in range(seg_per_source):
            t = i * step
            if t + SEG_DUR < src["dur"] and len(times) < n_segments:
                times.append({"file": src["file"], "start": t, "source_idx": si})
    return times[:n_segments]

b_times = pick_times(busquets_sources, SEGMENTS)
r_times = pick_times(rodri_sources, SEGMENTS)

os.makedirs("clips2", exist_ok=True)
for d in ["clips2"]:
    for f in os.listdir(d):
        os.remove(os.path.join(d, f))

def extract_clip(src_file, start, dur, out_name):
    """Extract a trimmed, scaled clip."""
    cmd = [
        "ffmpeg", "-y", "-ss", str(start), "-i", src_file, "-t", str(dur),
        "-vf", "scale=640:360:force_original_aspect_ratio=increase,crop=640:360",
        "-c:v", "libx264", "-preset", "fast", "-crf", "22", "-an",
        out_name, "-hide_banner", "-loglevel", "error"
    ]
    subprocess.run(cmd, check=True)

print(f"Extracting {SEGMENTS} segments per player...")
for i in range(SEGMENTS):
    pad = f"{i:02d}"
    b = b_times[i]
    r = r_times[i]
    
    extract_clip(b["file"], b["start"], SEG_DUR, f"clips2/b_{pad}.mp4")
    extract_clip(r["file"], r["start"], SEG_DUR, f"clips2/r_{pad}.mp4")
    
    # Stack side by side
    cmd = [
        "ffmpeg", "-y", "-i", f"clips2/b_{pad}.mp4", "-i", f"clips2/r_{pad}.mp4",
        "-filter_complex", "[0:v][1:v]hstack=inputs=2[v]",
        "-map", "[v]", "-c:v", "libx264", "-preset", "fast", "-crf", "22",
        f"clips2/sbs_{pad}.mp4", "-hide_banner", "-loglevel", "error"
    ]
    subprocess.run(cmd, check=True)
    print(f"  Segment {pad}: B@{b['start']}s (src{b['source_idx']}) + R@{r['start']}s (src{r['source_idx']})")

# Create concat file
with open("concat2.txt", "w") as f:
    for i in range(SEGMENTS):
        f.write(f"file '{BASE}/clips2/sbs_{i:02d}.mp4'\n")

# Concatenate
cmd = [
    "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", "concat2.txt",
    "-c:v", "libx264", "-preset", "fast", "-crf", "22", "-pix_fmt", "yuv420p",
    "-movflags", "+faststart",
    "busquets_rodri_raw.mp4", "-hide_banner", "-loglevel", "error"
]
subprocess.run(cmd, check=True)

# Add label overlay
cmd = [
    "ffmpeg", "-y", "-i", "busquets_rodri_raw.mp4", "-i", "labels_overlay.png",
    "-filter_complex", "[0:v][1:v]overlay=0:0",
    "-c:v", "libx264", "-preset", "fast", "-crf", "22", "-pix_fmt", "yuv420p",
    "-movflags", "+faststart",
    "busquets_rodri_comparison_v2.mp4", "-hide_banner", "-loglevel", "error"
]
subprocess.run(cmd, check=True)

final_size = os.path.getsize("busquets_rodri_comparison_v2.mp4")
final_dur = float(subprocess.check_output(
    ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", "busquets_rodri_comparison_v2.mp4"]
).decode().strip())

print(f"\nDONE! Final video: {final_size/1024/1024:.1f}MB, {final_dur:.1f}s")
print(f"Path: {BASE}/busquets_rodri_comparison_v2.mp4")
