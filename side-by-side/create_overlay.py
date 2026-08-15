from PIL import Image, ImageDraw, ImageFont
import os

# Create a 1280x360 label overlay with transparent background
img = Image.new('RGBA', (1280, 360), (0, 0, 0, 0))
draw = ImageDraw.Draw(img)

# Use a large built-in font
try:
    font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 28)
except:
    font = ImageFont.load_default()

# Busquets label - left side
draw.rounded_rectangle([(10, 10), (320, 55)], radius=8, fill=(0, 0, 0, 160))
draw.text((20, 15), "Sergio Busquets", fill=(255, 255, 255), font=font)

# Rodri label - right side
draw.rounded_rectangle([(650, 10), (950, 55)], radius=8, fill=(0, 0, 0, 160))
draw.text((660, 15), "Rodri Hernandez", fill=(255, 255, 255), font=font)

# Divider line
for x in range(639, 642):
    for y in range(360):
        draw.point((x, y), fill=(255, 255, 255, 60))

# Barcelona badge text for Busquets
try:
    font_small = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 16)
except:
    font_small = ImageFont.load_default()
draw.text((20, 58), "FC Barcelona", fill=(200, 200, 200, 180), font=font_small)
draw.text((660, 58), "Manchester City", fill=(200, 200, 200, 180), font=font_small)

img.save("/Users/danbadea/Documents/Projects/Personal/football/side-by-side/labels_overlay.png")
print("Overlay created")
