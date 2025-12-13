from PIL import Image
import os

# Source icon path
source_icon = r"static\icons\icon-512x512.png"

# Sizes needed for PWA
sizes = [72, 96, 128, 144, 152, 192, 384, 512]

# Open the source image
img = Image.open(source_icon)

# Create resized versions
for size in sizes:
    # Skip 512 since we already have it
    if size == 512:
        continue
    
    # Resize with high-quality resampling
    resized = img.resize((size, size), Image.Resampling.LANCZOS)
    
    # Save the resized image
    output_path = f"static/icons/icon-{size}x{size}.png"
    resized.save(output_path, "PNG", optimize=True)
    print(f"Created {output_path}")

print("All icon sizes generated successfully!")
