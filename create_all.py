import os
import csv
import ast
from PIL import Image, ImageDraw, ImageFont

# --- CONFIGURATION & PATHS ---
CSV_PATH = "units.csv"  # Path to your tab-separated file
OUTPUT_DIR = "output_cards"
FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" # Change to your preferred font path

# Icon Paths
ICON_PATHS = {
    'HP': '/home/db0/Documents/books/MAGNAGOTHICA/card design/heart.png',     # Placeholders
    'DEF': '/home/db0/Documents/books/MAGNAGOTHICA/card design/shield.png',    # Provided path
    'ARM': '/home/db0/Documents/books/MAGNAGOTHICA/card design/armor.png',     # Placeholders
    'MV': '/home/db0/Documents/books/MAGNAGOTHICA/card design/boot.png'        # Placeholders
}

UNIT_IMG_DIR = "/home/db0/Documents/books/MAGNAGOTHICA/all_units/sources/"
CANVAS_SIZE = (400, 1080)

os.makedirs(OUTPUT_DIR, exist_ok=True)

def parse_rgb(rgb_str):
    """Parses a string like '(255, 204, 51)' or '255,204,51' into an RGB tuple."""
    try:
        cleaned = rgb_str.strip()
        if not cleaned.startswith('('):
            cleaned = f"({cleaned})"
        return ast.literal_eval(cleaned)
    except Exception:
        return (240, 190, 60) # Fallback gold/yellow background

def draw_wrapped_text_with_auto_shrink(draw, text, position, max_width, max_font_size=32, font_path=FONT_PATH, fill="black"):
    """
    Draws text at a position, automatically reducing font size if it exceeds max_width.
    Splits text by words if it needs simple wrapping.
    """
    current_size = max_font_size
    x, y = position
    
    while current_size > 10:
        font = ImageFont.truetype(font_path, current_size)
        # Check text width
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        
        if text_width <= max_width:
            draw.text((x, y), text, font=font, fill=fill)
            return y + (bbox[4] if len(bbox) > 4 else (bbox[3] - bbox[1])) + 5 # Return next y position
        current_size -= 2
        
    # Ultimate fallback if it still doesn't fit: draw it wrapped or truncated
    font = ImageFont.truetype(font_path, 12)
    draw.text((x, y), text, font=font, fill=fill)
    return y + 20

def create_unit_card(row):
    # 1. Initialize Background Canvas
    bg_color = parse_rgb(row.get('card_background style', '(255, 204, 51)'))
    card = Image.new("RGB", CANVAS_SIZE, color=bg_color)
    draw = ImageDraw.Draw(card)
    
    # 2. Composite the Unit Artwork
    unit_img_name = row.get('card_background', '')
    if unit_img_name:
        full_unit_path = os.path.join(UNIT_IMG_DIR, unit_img_name)
        if os.path.exists(full_unit_path):
            with Image.open(full_unit_path) as usr_img:
                # Convert to RGBA to preserve transparency if applicable
                usr_img = usr_img.convert("RGBA")
                # Scale image contextually to fit the upper portion of the card
                usr_img.thumbnail((360, 500), Image.Resampling.LANCZOS)
                # Paste it centered horizontally, slightly down from top
                img_x = (CANVAS_SIZE[0] - usr_img.width) // 2
                img_y = 120 
                card.paste(usr_img, (img_x, img_y), usr_img)
        else:
            print(f"Warning: Artwork file not found at {full_unit_path}")

    # 3. Paste Stat Icons & Overlay Values
    # Define Layout coordinates for stats based on the reference layout
    stat_layouts = {
        'HP':  {'icon_pos': (10, 10),   'size': (120, 120), 'text_pos': (75, 40),  'val': f"/{row.get('HP','')}"},
        'DEF': {'icon_pos': (200, 15),  'size': (80, 90),   'text_pos': (215, 25), 'val': f"{row.get('DEF','')}+"},
        'ARM': {'icon_pos': (310, 15),  'size': (75, 95),   'text_pos': (330, 25), 'val': row.get('ARM','')},
        'MV':  {'icon_pos': (10, 480),  'size': (120, 120), 'text_pos': (45, 540), 'val': row.get('MV','')}
    }
    
    for stat, layout in stat_layouts.items():
        path = ICON_PATHS[stat]
        if os.path.exists(path):
            with Image.open(path) as icon:
                icon = icon.convert("RGBA")
                icon = icon.resize(layout['size'], Image.Resampling.LANCZOS)
                card.paste(icon, layout['icon_pos'], icon)
        
        # Draw Stat text overlay
        font_stat = ImageFont.truetype(FONT_PATH, 36)
        draw.text(layout['text_pos'], layout['val'], font=font_stat, fill="black")

    # 4. Text Bounding Box Region (Lower part of the card)
    current_y = 650
    margin_x = 20
    max_text_width = CANVAS_SIZE[0] - (margin_x * 2)
    
    # Draw Name
    current_y = draw_wrapped_text_with_auto_shrink(
        draw, row.get('Name', 'UNKNOWN').upper(), (margin_x, current_y), 
        max_text_width, max_font_size=38
    )
    
    # Draw Nickname / Subtitle
    if row.get('Nickname'):
        current_y = draw_wrapped_text_with_auto_shrink(
            draw, row.get('Nickname', ''), (margin_x, current_y), 
            max_text_width, max_font_size=22, fill="#222222"
        )
        
    # Draw Type & Traits
    traits_text = f"{row.get('Type', '')} - {row.get('Traits', '')}"
    current_y = draw_wrapped_text_with_auto_shrink(
        draw, traits_text, (margin_x, current_y + 10), 
        max_text_width, max_font_size=18, fill="#333333"
    )
    
    # Draw Core Abilities / Rules Text
    if row.get('Abilities'):
        current_y += 15
        abilities = row.get('Abilities', '').split('|') # Splits by vertical bar if multiple abilities exist
        for ability in abilities:
            current_y = draw_wrapped_text_with_auto_shrink(
                draw, ability.strip(), (margin_x, current_y), 
                max_text_width, max_font_size=18
            )

    # 5. Save the generated card image
    sanitized_name = "".join([c for c in row.get('Name', 'unit') if c.isalpha() or c.isdigit() or c==' ']).rstrip()
    output_filename = f"{sanitized_name.replace(' ', '_')}.png"
    card.save(os.path.join(OUTPUT_DIR, output_filename), "PNG")
    print(f"Successfully generated: {output_filename}")

# --- MAIN RUNNER ---
if __name__ == "__main__":
    if not os.path.exists(CSV_PATH):
        print(f"Error: Could not find data file at {CSV_PATH}. Please create it first.")
    else:
        with open(CSV_PATH, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f, delimiter='\t')
            for row in reader:
                # Read structural "Copies" configuration
                copies = int(row.get('Copies', 1) if row.get('Copies') else 1)
                for _ in range(copies):
                    create_unit_card(row)