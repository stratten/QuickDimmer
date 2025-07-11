#!/usr/bin/env python3
"""
Generate basic icons for MonitorDimmer app
Creates simple monitor/screen icons with dimming theme
"""

from PIL import Image, ImageDraw
import os

def create_monitor_icon(size=256, bg_color=(240, 240, 240), monitor_color=(60, 60, 60)):
    """Create a simple monitor icon"""
    img = Image.new('RGBA', (size, size), (255, 255, 255, 0))  # Transparent background
    draw = ImageDraw.Draw(img)
    
    # Calculate dimensions
    margin = size // 8
    screen_width = size - (margin * 2)
    screen_height = int(screen_width * 0.6)  # 16:10 aspect ratio
    
    # Screen position (centered)
    screen_x = margin
    screen_y = (size - screen_height - margin) // 2
    
    # Draw monitor screen (main rectangle)
    screen_rect = [screen_x, screen_y, screen_x + screen_width, screen_y + screen_height]
    draw.rectangle(screen_rect, fill=monitor_color, outline=(40, 40, 40), width=3)
    
    # Draw screen bezel (inner lighter area)
    bezel_margin = size // 20
    bezel_rect = [
        screen_x + bezel_margin,
        screen_y + bezel_margin,
        screen_x + screen_width - bezel_margin,
        screen_y + screen_height - bezel_margin
    ]
    draw.rectangle(bezel_rect, fill=bg_color, outline=(100, 100, 100), width=2)
    
    # Draw monitor stand (base)
    stand_width = screen_width // 3
    stand_height = size // 12
    stand_x = screen_x + (screen_width - stand_width) // 2
    stand_y = screen_y + screen_height + size // 20
    
    # Stand neck
    neck_width = size // 20
    neck_height = size // 15
    neck_x = screen_x + (screen_width - neck_width) // 2
    neck_y = screen_y + screen_height
    
    draw.rectangle([neck_x, neck_y, neck_x + neck_width, neck_y + neck_height], 
                   fill=monitor_color)
    
    # Stand base
    draw.rectangle([stand_x, stand_y, stand_x + stand_width, stand_y + stand_height], 
                   fill=monitor_color)
    
    # Add a dimming effect (gradient overlay)
    overlay = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    
    # Create a subtle dimming effect on half the screen
    dim_rect = [
        bezel_rect[0],
        bezel_rect[1],
        bezel_rect[2] // 2 + bezel_rect[0] // 2,
        bezel_rect[3]
    ]
    overlay_draw.rectangle(dim_rect, fill=(0, 0, 0, 80))  # Semi-transparent black
    
    # Composite the overlay
    img = Image.alpha_composite(img, overlay)
    
    return img

def create_tray_icon(size=32):
    """Create a smaller tray icon version"""
    img = Image.new('RGBA', (size, size), (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)
    
    # Simple monitor shape for tray
    margin = 2
    width = size - (margin * 2)
    height = int(width * 0.6)
    
    x = margin
    y = (size - height) // 2
    
    # Monitor outline
    draw.rectangle([x, y, x + width, y + height], 
                   fill=(60, 60, 60), outline=(40, 40, 40), width=1)
    
    # Screen area
    inner_margin = 2
    draw.rectangle([x + inner_margin, y + inner_margin, 
                   x + width - inner_margin, y + height - inner_margin], 
                   fill=(200, 200, 200))
    
    # Dimming effect (left half darker)
    draw.rectangle([x + inner_margin, y + inner_margin, 
                   x + width // 2, y + height - inner_margin], 
                   fill=(100, 100, 100))
    
    return img

def main():
    # Create assets directory if it doesn't exist
    assets_dir = "frontend/assets"
    os.makedirs(assets_dir, exist_ok=True)
    
    print("Generating MonitorDimmer icons...")
    
    # Generate main icon (256x256)
    main_icon = create_monitor_icon(256)
    main_icon.save(f"{assets_dir}/icon.png")
    print(f"✓ Created {assets_dir}/icon.png (256x256)")
    
    # Generate tray icon (32x32)
    tray_icon = create_tray_icon(32)
    tray_icon.save(f"{assets_dir}/tray-icon.png")
    print(f"✓ Created {assets_dir}/tray-icon.png (32x32)")
    
    # Generate additional sizes for better scaling
    for size in [16, 24, 48, 128]:
        resized = main_icon.resize((size, size), Image.Resampling.LANCZOS)
        resized.save(f"{assets_dir}/icon-{size}.png")
        print(f"✓ Created {assets_dir}/icon-{size}.png ({size}x{size})")
    
    print("\nAll icons generated successfully!")
    print("Icons feature a simple monitor with dimming effect theme.")

if __name__ == "__main__":
    # Check if Pillow is available
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        print("Error: Pillow (PIL) is required to generate icons.")
        print("Install it with: pip install Pillow")
        exit(1)
    
    main() 