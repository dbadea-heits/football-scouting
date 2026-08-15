from PIL import Image, ImageDraw, ImageFont

img = Image.new('RGBA', (1280, 360), (0, 0, 0, 0))
draw = ImageDraw.Draw(img)

font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 24)
font_sm = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 14)

# Center divider line
for y in range(360):
    draw.point((639, y), fill=(255, 255, 255, 60))
    draw.point((640, y), fill=(255, 255, 255, 60))

# LEFT: Busquets
draw.rounded_rectangle([(10, 8), (310, 44)], radius=6, fill=(0, 0, 0, 160))
draw.text((20, 12), "Sergio Busquets", fill=(255, 255, 255), font=font)
draw.text((20, 46), "Barcelona", fill=(165, 42, 42, 180), font=font_sm)

# RIGHT: Rodri
draw.rounded_rectangle([(650, 8), (950, 44)], radius=6, fill=(0, 0, 0, 160))
draw.text((660, 12), "Rodri Hernandez", fill=(255, 255, 255), font=font)
draw.text((660, 46), "Manchester City", fill=(0, 150, 255, 180), font=font_sm)

img.save("/Users/danbadea/Documents/Projects/Personal/football/side-by-side/labels_v2.png")
print("Clean overlay created")
