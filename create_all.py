import os
import csv
import ast
import re
import difflib
from PIL import Image, ImageDraw, ImageFont

# --- CONFIGURATION & PATHS ---
FACTION = "carcass"
CSV_PATH = f"{FACTION}.csv"
OUTPUT_DIR = "output_cards"

# --- FONT FAMILY CONFIGURATION ---
FONT_REGULAR = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_ITALIC = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf"
FONT_BOLD_ITALIC = "/usr/share/fonts/truetype/dejavu/DejaVuSans-BoldOblique.ttf"
FONT_MALEGHAST = "/home/db0/.local/share/fonts/maleghast.ttf"

ICON_PATHS = {
    'HP': '/home/db0/Documents/books/MAGNAGOTHICA/card design/hearts.png',
    'DEF': '/home/db0/Documents/books/MAGNAGOTHICA/card design/shield.png',
    'ARM': '/home/db0/Documents/books/MAGNAGOTHICA/card design/trench-body-armor.png',
    'MV': '/home/db0/Documents/books/MAGNAGOTHICA/card design/barefoot.png'
}

UNIT_IMG_DIR = "/home/db0/Documents/books/MAGNAGOTHICA/all_units/sources/"
CANVAS_SIZE = (400, 1080)

os.makedirs(OUTPUT_DIR, exist_ok=True)

def parse_rgb(rgb_str):
    """Fallback color handling if extraction fails"""
    rgbregex = re.search(r'\{outlineColor:rgba\(([0-9]{1,3}), ([0-9]{1,3}), ([0-9]{1,3}), 1\)\}',rgb_str)
    print(rgbregex)
    if rgbregex:
        return (int(rgbregex.group(1)),int(rgbregex.group(2)),int(rgbregex.group(3)))
    return (255, 255, 255) # Default white

def clean_html_and_markdown(text):
    """Strips HTML list elements and normalizes paragraph delimiters."""
    if not text:
        return ""
    text = re.sub(re.compile('<.*?>'), '', text)
    paragraphs = [p.strip() for p in text.split('/') if p.strip()]
    return "\n\n".join(paragraphs)

def find_fuzzy_image(target_name, directory):
    """
    Looks for an exact filename match. If not found, uses fuzzy logic 
    to locate the closest matching filename in the source directory.
    """
    if not target_name or not os.path.exists(directory):
        return None
        
    # Check for direct match first
    direct_path = os.path.join(directory, target_name)
    if os.path.exists(direct_path):
        return direct_path
        
    # Read files present on disk
    try:
        available_files = os.listdir(directory)
    except Exception:
        return None
        
    if not available_files:
        return None

    # Find the single closest string match
    matches = difflib.get_close_matches(f"{FACTION}_{target_name}", available_files, n=1, cutoff=0.3)
    if matches:
        print(f"Fuzzy Match: '{target_name}' mapped to disk asset -> '{matches[0]}'")
        return os.path.join(directory, matches[0])
        
    return None

def parse_markdown_line(text):
    """Parses **bold** and *italic* tags into structured token chunks."""
    pattern = r'(\*\*\*.*?\*\*\*|\*\*.*?\*\*|\*.*?\*)'
    tokens = re.split(pattern, text)
    
    parsed_chunks = []
    for token in tokens:
        if not token:
            continue
        if token.startswith('***') and token.endswith('***'):
            parsed_chunks.append((token[3:-3], 'bold_italic'))
        elif token.startswith('**') and token.endswith('**'):
            parsed_chunks.append((token[2:-2], 'bold'))
        elif token.startswith('*') and token.endswith('*'):
            parsed_chunks.append((token[1:-1], 'italic'))
        else:
            parsed_chunks.append((token, 'regular'))
    return parsed_chunks

def draw_rich_paragraph(draw, text, position, max_width, font_size, fill="black", force_font_style=None):
    """
    Draws multi-styled wrapped text and handles automatic word wrapping.
    If force_font_style is set (e.g., 'name'), overrides standard font styles.
    """
    x_start, y = position
    x = x_start
    
    fonts = {
        'name': ImageFont.truetype(FONT_MALEGHAST, font_size),
        'regular': ImageFont.truetype(FONT_REGULAR, font_size),
        'bold': ImageFont.truetype(FONT_BOLD, font_size),
        'italic': ImageFont.truetype(FONT_ITALIC, font_size),
        'bold_italic': ImageFont.truetype(FONT_BOLD_ITALIC, font_size)
    }
    
    sample_font = fonts[force_font_style] if force_font_style else fonts['regular']
    sample_box = draw.textbbox((0, 0), "Hg", font=sample_font)
    line_height = int((sample_box[3] - sample_box[1]) * 1.25)
    
    lines = text.split('\n')
    
    for line in lines:
        if not line.strip():
            y += line_height
            continue
            
        chunks = parse_markdown_line(line)
        words_with_styles = []
        
        for text_chunk, style in chunks:
            # If a specific global style override is passed, enforce it over markdown styles
            chosen_style = force_font_style if force_font_style else style
            words = text_chunk.split(' ')
            for i, word in enumerate(words):
                space = " " if i < len(words) - 1 else ""
                words_with_styles.append((word + space, chosen_style))
        
        current_line_chunks = []
        current_line_width = 0
        
        for word, style in words_with_styles:
            box = draw.textbbox((0, 0), word, font=fonts[style])
            word_width = box[2] - box[0]
            
            if x + current_line_width + word_width > x_start + max_width:
                for cl_word, cl_style in current_line_chunks:
                    draw.text((x, y), cl_word, font=fonts[cl_style], fill=fill)
                    c_box = draw.textbbox((0, 0), cl_word, font=fonts[cl_style])
                    x += (c_box[2] - c_box[0])
                x = x_start
                y += line_height
                current_line_chunks = [(word, style)]
                current_line_width = word_width
            else:
                current_line_chunks.append((word, style))
                current_line_width += word_width
                
        if current_line_chunks:
            for cl_word, cl_style in current_line_chunks:
                draw.text((x, y), cl_word, font=fonts[cl_style], fill=fill)
                c_box = draw.textbbox((0, 0), cl_word, font=fonts[cl_style])
                x += (c_box[2] - c_box[0])
            x = x_start
            y += line_height

    return y

def create_unit_card(row):
    bg_color = parse_rgb(row.get('card_background style', ''))
    card = Image.new("RGB", CANVAS_SIZE, color=bg_color)
    draw = ImageDraw.Draw(card)
    
    # Composite the Unit Artwork (Fuzzy Match Execution)
    unit_img_name = row.get('card_background', '')
    resolved_img_path = find_fuzzy_image(unit_img_name, UNIT_IMG_DIR)
    
    if resolved_img_path:
        with Image.open(resolved_img_path) as usr_img:
            usr_img = usr_img.convert("RGBA")
            usr_img.thumbnail((360, 500), Image.Resampling.LANCZOS)
            img_x = (CANVAS_SIZE[0] - usr_img.width) // 2
            img_y = 120 
            card.paste(usr_img, (img_x, img_y), usr_img)
    else:
        print(f"Warning: Could not match image resource for asset target: '{unit_img_name}'")

    # Paste Stat Icons & Overlay Values
    stat_layouts = {
        'HP':  {'icon_pos': (10, 10),   'size': (120, 120), 'text_pos': (70, 40),  'val': f"/{row.get('HP','')}"},
        'DEF': {'icon_pos': (200, 10),  'size': (120, 120), 'text_pos': (235, 40), 'val': f"{row.get('DEF','')}"},
        'ARM': {'icon_pos': (310, 10),  'size': (120, 120), 'text_pos': (360, 35), 'val': row.get('ARM','')},
        'MV':  {'icon_pos': (120, 10),  'size': (120, 120), 'text_pos': (140, 80), 'val': row.get('MV','')}
    }
    
    for stat, layout in stat_layouts.items():
        path = ICON_PATHS[stat]
        if os.path.exists(path):
            with Image.open(path) as icon:
                icon = icon.convert("RGBA")
                icon = icon.resize(layout['size'], Image.Resampling.LANCZOS)
                card.paste(icon, layout['icon_pos'], icon)
        
        font_stat = ImageFont.truetype(FONT_BOLD, 36)
        draw.text(layout['text_pos'], layout['val'], font=font_stat, fill="black")

    # Render Text Content Engine
    current_y = 650
    margin_x = 24
    max_text_width = CANVAS_SIZE[0] - (margin_x * 2)
    
    # 1. Cleaned Title Header Text (Rendered exclusively using FONT_MALEGHAST)
    name_text = clean_html_and_markdown(row.get('Name', 'UNKNOWN'))
    current_y = draw_rich_paragraph(
        draw, name_text.upper(), (margin_x, current_y), 
        max_text_width, font_size=32, force_font_style='name'
    )
    
    # 2. Subtitle / Classification Info
    type_and_traits = []
    if row.get('Type'): type_and_traits.append(row.get('Type'))
    if row.get('Traits'): type_and_traits.append(clean_html_and_markdown(row.get('Traits')))
    
    if type_and_traits:
        joined_traits = " • ".join(type_and_traits)
        current_y = draw_rich_paragraph(draw, f"*{joined_traits}*", (margin_x, current_y), max_text_width, font_size=16, fill="#333333")
        current_y += 10

    # 3. Process Abilities Block safely
    if row.get('ACT Abilities'):
        abilities_payload = clean_html_and_markdown(row.get('ACT Abilities'))
        current_y = draw_rich_paragraph(draw, abilities_payload, (margin_x, current_y), max_text_width, font_size=15)

    # Clean internal text spacing specifically for saving legible final files
    clean_name = re.sub(r'\s+', '', row.get('Name', 'unit'))
    sanitized_filename = "".join([c for c in clean_name if c.isalnum()]).strip().capitalize()
    output_filename = f"{FACTION}_{sanitized_filename}.png"
    
    card.save(os.path.join(OUTPUT_DIR, output_filename), "PNG")
    print(f"Generated Layout File: {output_filename}\n---")

if __name__ == "__main__":
    if os.path.exists(CSV_PATH):
        with open(CSV_PATH, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f, delimiter='\t')
            for row in reader:
                copies = int(row.get('Copies', 1) if row.get('Copies') else 1)
                for _ in range(copies):
                    create_unit_card(row)