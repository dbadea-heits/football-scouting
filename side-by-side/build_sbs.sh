#!/bin/bash
set -e

cd /Users/danbadea/Documents/Projects/Personal/football/side-by-side

BUSDUR=$(ffprobe -v error -show_entries format=duration -of csv=p=0 busquets_shee2rLaoq4.webm | cut -d. -f1)
RODDUR=$(ffprobe -v error -show_entries format=duration -of csv=p=0 rodri_e9c3wuptql0.webm | cut -d. -f1)
echo "Busquets: ${BUSDUR}s, Rodri: ${RODDUR}s"

# ~30 seconds final = 12 segments of ~2.5 seconds each
SEGMENTS=12
SEG_DUR=2.5
TOTAL=$(echo "$SEGMENTS * $SEG_DUR" | bc)
echo "Target: ${TOTAL}s video with ${SEGMENTS} segments"

# Calculate step sizes
BSTEP=$(echo "scale=0; $BUSDUR / $SEGMENTS" | bc)
ROSTEP=$(echo "scale=0; $RODDUR / $SEGMENTS" | bc)
echo "Step: Busquets=${BSTEP}s, Rodri=${ROSTEP}s"

mkdir -p clips
rm -f clips/*.mp4

for i in $(seq 0 $((SEGMENTS - 1))); do
  BSTART=$((i * BSTEP))
  RSTART=$((i * ROSTEP))
  PAD=$(printf "%02d" $i)
  
  ffmpeg -y -ss ${BSTART} -i busquets_shee2rLaoq4.webm -t ${SEG_DUR} \
    -vf "scale=640:360:force_original_aspect_ratio=increase,crop=640:360" \
    -c:v libx264 -preset fast -crf 22 -an \
    "clips/b_${PAD}.mp4" -hide_banner -loglevel error
  
  ffmpeg -y -ss ${RSTART} -i rodri_e9c3wuptql0.webm -t ${SEG_DUR} \
    -vf "scale=640:360:force_original_aspect_ratio=increase,crop=640:360" \
    -c:v libx264 -preset fast -crf 22 -an \
    "clips/r_${PAD}.mp4" -hide_banner -loglevel error
  
  # Stack side by side
  ffmpeg -y -i "clips/b_${PAD}.mp4" -i "clips/r_${PAD}.mp4" \
    -filter_complex "[0:v][1:v]hstack=inputs=2[v]" \
    -map "[v]" -c:v libx264 -preset fast -crf 22 \
    "clips/sbs_${PAD}.mp4" -hide_banner -loglevel error
  
  echo "Segment $PAD done: Busquets @${BSTART}s + Rodri @${RSTART}s"
done

# Create concat file
> concat_list.txt
for f in clips/sbs_*.mp4; do echo "file '$PWD/$f'" >> concat_list.txt; done

ffmpeg -y -f concat -safe 0 -i concat_list.txt \
  -c:v libx264 -preset fast -crf 22 -pix_fmt yuv420p \
  -movflags +faststart \
  "busquets_rodri_comparison.mp4" -hide_banner -loglevel error

echo "Done! Final video: $(du -h busquets_rodri_comparison.mp4 | cut -f1)"
