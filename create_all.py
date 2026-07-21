import os
import csv
import ast
import re
import difflib
import io
import badgepy
import cairosvg
import xml.etree.ElementTree as ET
from PIL import Image, ImageDraw, ImageFont

import argparse

# --- CONFIGURATION & PATHS ---
# FACTION = "deadsouls"
# FACTION = "abhorrers"
# FACTION = "necromancers"
# CSV_PATH = f"{FACTION}.csv"
VIDEO_NAME = "Matchup1_Basic_Abhorrers_Deadsouls"
FACTIONS = ["abhorrers", "deadsouls", "necromancers"]
OUTPUT_DIR = "output_cards"
GUIDES_FILE = "guides.txt"
HOMEDIR = os.path.expanduser("~")

# State variables overridden during execution 
TIME = None
HP = None
ABILITY = None
SIDE = None
CONDITIONS = []

# --- BADGE CONFIGURATION ---
BADGE_SCALE = 1.25  # Tweak this multiplier to scale the badge up/down crisply
BADGE_SPACING = 12  # Vertical pixel spacing between multiple badges

# Add or modify conditions here. You can use CSS color names (e.g., 'red') or hex codes ('#d32f2f').
CONDITION_COLORS = {
    "Strength": {"left": "red", "right": "grey"},
    "Weak": {"left": "grey", "right": "red"},
    "Vitality": {"left": "green", "right": "pink"},
    "Vulnerability": {"left": "pink", "right": "green"},
    "Speed": {"left": "yellow", "right": "brown"},
    "Slow": {"left": "#987654", "right": "yellow"},
    "Miracle": {"left": "white", "right": "white"},
    "Smite": {"left": "yellow", "right": "blue"},
    "Doom": {"left": "#91ffef", "right": "#91ffef"},
    "Winch": {"left": "#987654", "right": "#C0C0C0"},
    "Curseproof": {"left": "black", "right": "white"},
    "Grace": {"left": "purple", "right": "white"},
}
# Fallback colors if a condition isn't found in the dictionary above
DEFAULT_BADGE_COLORS = {"left": "#333333", "right": "#d32f2f"}

# --- FONT FAMILY CONFIGURATION ---
FONT_REGULAR = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_ITALIC = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf"
FONT_BOLD_ITALIC = "/usr/share/fonts/truetype/dejavu/DejaVuSans-BoldOblique.ttf"
FONT_MALEGHAST = f"{HOMEDIR}/.local/share/fonts/maleghast.ttf"

ICON_PATHS = {
    'HP': f'{HOMEDIR}/Documents/books/MAGNAGOTHICA/card design/hearts.png',
    'DEF': f'{HOMEDIR}/Documents/books/MAGNAGOTHICA/card design/shield.png',
    'ARM': f'{HOMEDIR}/Documents/books/MAGNAGOTHICA/card design/trench-body-armor.png',
    'MV': f'{HOMEDIR}/Documents/books/MAGNAGOTHICA/card design/barefoot.png'
}

UNIT_IMG_DIR = f"{HOMEDIR}/Documents/books/MAGNAGOTHICA/all_units/sources/"
NECROMANCER_DIR = f"{HOMEDIR}/Documents/books/MAGNAGOTHICA/all_units/Necromancers"
CANVAS_SIZE = (400, 1080)

os.makedirs(OUTPUT_DIR, exist_ok=True)


# Create the parser
parser = argparse.ArgumentParser(
    description="Process raid/deployment guide files."
)

# Add the --matchup argument
parser.add_argument(
    "--matchup",
    type=str,
    default=None,
    help="Specify the matchup string (e.g., 'boss_1' or 'pvp_season_2')",
)

# Parse the arguments from the command line
args = parser.parse_args()

def parse_rgb(rgb_str):
    """Fallback color handling if extraction fails"""
    rgbregex = re.search(r'\{outlineColor:rgba\(([0-9]{1,3}),\s*([0-9]{1,3}),\s*([0-9]{1,3}),\s*1\)\}', rgb_str)
    if rgbregex:
        return (int(rgbregex.group(1)), int(rgbregex.group(2)), int(rgbregex.group(3)))
    return (255, 255, 255) # Default white

def get_light_tint(rgb, factor=0.75):
    """Mixes the background color with white to create a legible text panel tone."""
    r, g, b = rgb
    new_r = int(r + (255 - r) * factor)
    new_g = int(g + (255 - g) * factor)
    new_b = int(b + (255 - b) * factor)
    return (new_r, new_g, new_b)

def clean_html_and_markdown(text):
    """Strips HTML list elements and normalizes paragraph delimiters."""
    if not text:
        return ""
    if '•' in text: 
        text = text.replace("/\n",'')
        text = text.replace("\n   • ",' - ')
        text = text.replace("\n    ",' ')
    text = re.sub(re.compile('</li>'), ' • ', text)
    text = re.sub(re.compile('<.*?>'), '', text)
    paragraphs = [p.strip() for p in text.split('/') if p.strip()]
    return "\n\n".join(paragraphs)

def find_fuzzy_image(target_name, directory):
    """Looks for a direct match or uses fuzzy string matching to find the file."""
    if FACTION == "necromancers":
        directory = NECROMANCER_DIR
        target_name = target_name.replace("Leaders/", "")
    if not target_name or not os.path.exists(directory):
        return None
        
    direct_path = os.path.join(directory, target_name)
    if os.path.exists(direct_path):
        return direct_path
        
    try:
        available_files = os.listdir(directory)
    except Exception:
        return None
        
    if not available_files:
        return None

    if FACTION == "necromancers":
        matches = difflib.get_close_matches(f"{target_name}", available_files, n=1, cutoff=0.3)
    else:
        matches = difflib.get_close_matches(f"{FACTION}_{target_name}", available_files, n=1, cutoff=0.3)
    if matches:
        # print(f"Fuzzy Match: '{target_name}' mapped to disk asset -> '{matches[0]}'")
        return os.path.join(directory, matches[0])
        
    return None

def split_individual_abilities(raw_abilities_text):
    """
    Splits the composite abilities field into clean individual blocks
    using the lookahead markdown **Header:** pattern.
    """
    if not raw_abilities_text:
        return []
    soul_costs = []
    if re.search(r'\([1-6] SOUL\)', raw_abilities_text):
        ability_names_findall = re.findall(r'\*\*([^*:\n]+) (\([1-6] SOUL\))(?:(?:\*\* ?:)|(?:: ?\*\*))', raw_abilities_text)
        ability_names = [an[0] for an in ability_names_findall]
        soul_costs = [an[1] for an in ability_names_findall]
        blocks = re.split(r'\*\*([^*:\n]+) (\([1-6] SOUL\))(?:(?:\*\* ?:)|(?:: ?\*\*))', raw_abilities_text)
    else:        
        ability_names = re.findall(r'\*\*([^*:\n]+)(?:(?:\*\* ?:)|(?:: ?\*\*))', raw_abilities_text)
        blocks = re.split(r'\*\*([^*:\n]+)(?:(?:\*\* ?:)|(?:: ?\*\*))', raw_abilities_text)
    refined_abilities = []
    
    for block in blocks:
        b_str = block.strip()
        if not b_str:
            continue
        lines = [line.strip() for line in b_str.split('/') if line.strip() and line.strip() != '/' and line.strip() not in ability_names and line.strip() not in soul_costs]
        if lines:
            refined_abilities.append("\n\n".join(lines))
    if len(ability_names) != len(refined_abilities):
        raise Exception(f"Abilities count mismatch. Names: {ability_names} {len(ability_names)}, Texts: {refined_abilities} {len(refined_abilities)}")
    for i in range(len(ability_names)):
        refined_abilities[i] = f"**{ability_names[i]}**\n\n{refined_abilities[i]}"
            
    return (refined_abilities, ability_names, soul_costs)

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

def draw_rich_paragraph(draw, text, position, max_width, font_size, fill="black", force_font_style=None, dry_run=False):
    """Draws multi-styled wrapped text and handles automatic word wrapping."""
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
                if not dry_run:
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
            if not dry_run:
                for cl_word, cl_style in current_line_chunks:
                    draw.text((x, y), cl_word, font=fonts[cl_style], fill=fill)
                    c_box = draw.textbbox((0, 0), cl_word, font=fonts[cl_style])
                    x += (c_box[2] - c_box[0])
            x = x_start
            y += line_height

    return y

def adjust_svg_text_color(svg_str, c_name, c_amt, left_bg, right_bg):
    """Intercepts the SVG string from pybadges and forces text to black if the panel is white."""
    try:
        white_colors = ["white", "#ffffff", "#fff", "#91ffef", "pink"]
        left_needs_black = left_bg.lower() in white_colors
        right_needs_black = right_bg.lower() in white_colors
        
        # Fast exit if we don't need to change anything
        if not (left_needs_black or right_needs_black):
            return svg_str

        # Register standard SVG namespace so ElementTree doesn't output generic tags
        ET.register_namespace('', 'http://www.w3.org/2000/svg')
        root = ET.fromstring(svg_str)
        
        # Iterate over elements ignoring namespace prefixes for robustness
        for elem in root.iter():
            if elem.tag.endswith('text'):
                # Check for Left Panel match
                if elem.text == c_name and left_needs_black:
                    # Strip any pybadges drop-shadow attributes for clear readability
                    if 'fill' in elem.attrib:
                        del elem.attrib['fill']
                    if 'fill-opacity' in elem.attrib:
                        del elem.attrib['fill-opacity']
                    elem.set('fill', '#000000') # Force black text
                
                # Check for Right Panel match
                elif elem.text == str(c_amt) and right_needs_black:
                    if 'fill' in elem.attrib:
                        del elem.attrib['fill']
                    if 'fill-opacity' in elem.attrib:
                        del elem.attrib['fill-opacity']
                    elem.set('fill', '#000000') # Force black text
                    
        return ET.tostring(root, encoding='unicode')
    except Exception as e:
        print(f"SVG color adjustment failed: {e}")
        return svg_str


def create_unit_card(row, focus_ability=None, ability_suffix_name=None, soul_cost=None):
    """
    Renders full cards. If focus_ability is passed, it preserves all art and 
    stats but swaps the text block for just that upscaled ability.
    """
    bg_color = parse_rgb(row.get('card_background style', ''))
    card = Image.new("RGB", CANVAS_SIZE, color=bg_color)
    draw = ImageDraw.Draw(card)
    
    # Composite the Unit Artwork
    unit_img_name = row.get('card_background', '')
    resolved_img_path = find_fuzzy_image(unit_img_name, UNIT_IMG_DIR)
    
    if resolved_img_path:
        with Image.open(resolved_img_path) as usr_img:
            usr_img = usr_img.convert("RGBA")
            
            bbox = usr_img.getbbox()
            if bbox:
                usr_img = usr_img.crop(bbox)
                
            target_width = 360
            scale_ratio = target_width / float(usr_img.width)
            target_height = int(float(usr_img.height) * scale_ratio)
            
            if target_height > 500:
                usr_img.thumbnail((360, 500), Image.Resampling.LANCZOS)
            else:
                usr_img = usr_img.resize((target_width, target_height), Image.Resampling.LANCZOS)
                
            img_x = (CANVAS_SIZE[0] - usr_img.width) // 2
            img_y = 120 
            card.paste(usr_img, (img_x, img_y), usr_img)

            # --- BADGES INTEGRATION ---
            if CONDITIONS:
                badge_start_y = img_y + 20
                for cond in CONDITIONS:
                    c_name = cond.get("condition", "").capitalize()
                    c_amt = cond.get("amount", "")
                    
                    # Fetch color from dict or fallback to default
                    colors = CONDITION_COLORS.get(c_name, DEFAULT_BADGE_COLORS)
                    b_left_color = colors.get("left", DEFAULT_BADGE_COLORS["left"])
                    b_right_color = colors.get("right", DEFAULT_BADGE_COLORS["right"])
                    
                    # Generate the standard SVG string from badgepy
                    svg_str = badgepy.badge(
                        left_text=c_name, 
                        right_text=c_amt,
                        left_color=b_left_color,
                        right_color=b_right_color
                    )
                    
                    # Intercept the SVG to override text colors if the background is white
                    svg_str = adjust_svg_text_color(svg_str, c_name, c_amt, b_left_color, b_right_color)
                    
                    # Scale using cairosvg natively to preserve 100% crisp vector edges!
                    png_data = cairosvg.svg2png(bytestring=svg_str.encode('utf-8'), scale=BADGE_SCALE)
                    badge_img = Image.open(io.BytesIO(png_data)).convert("RGBA")
                    
                    # Calculate horizontal placement based on the unit's 'side'
                    if SIDE == "Left":
                        # Position right border of the unit art
                        badge_x = img_x + usr_img.width - (badge_img.width // 2)
                    elif SIDE == "Right":
                        # Position left border of the unit art
                        badge_x = img_x - (badge_img.width // 2)
                    else:
                        badge_x = img_x - (badge_img.width // 2)
                    
                    # Keep the badge inside the canvas bounds visually
                    badge_x = max(10, min(badge_x, CANVAS_SIZE[0] - badge_img.width - 10))
                    
                    # Paste with transparency support
                    card.paste(badge_img, (badge_x, badge_start_y), badge_img)
                    badge_start_y += badge_img.height + BADGE_SPACING
            # --------------------------
            
    else:
        print(f"Warning: Could not match image resource for asset target: '{unit_img_name}'")

    # Paste Stat Icons & Overlay Values
    stat_layouts = {
        'HP':  {'icon_pos': (10, 0),   'size': (140, 140), 'text_pos': (80, 30),  'val': f"/{row.get('HP','')}"},
        'DEF': {'icon_pos': (200, 10),  'size': (120, 115), 'text_pos': (235, 40), 'val': f"{row.get('DEF','')}"},
        'ARM': {'icon_pos': (290, 10),  'size': (120, 120), 'text_pos': (338, 35), 'val': row.get('ARM','')},
        'MV':  {'icon_pos': (140, 15),  'size': (100, 105), 'text_pos': (158, 50), 'val': row.get('MV','')}
    }
    if HP is None:
        stat_layouts['HP'] = {'icon_pos': (10, 0),   'size': (140, 140), 'text_pos': (55, 20),  'val': f"{row.get('HP','')}"}
    
    for stat, layout in stat_layouts.items():
        path = ICON_PATHS[stat]
        if os.path.exists(path):
            with Image.open(path) as icon:
                icon = icon.convert("RGBA")
                icon = icon.resize(layout['size'], Image.Resampling.LANCZOS)
                card.paste(icon, layout['icon_pos'], icon)
        
        font_stat = ImageFont.truetype(FONT_BOLD, 36)
        text_pos = layout['text_pos']
        if stat == "ARM":
            if layout['val'] == "":
                layout['val'] = "-"
            if layout['val'] == "M":
                text_pos = (333, 35)
            if layout['val'] == "-":
                text_pos = (343, 35)
        if stat == "HP":
            font_stat = ImageFont.truetype(FONT_BOLD, 50)
            if int(row.get('HP','')) > 9:
                font_stat = ImageFont.truetype(FONT_BOLD, 35)
                text_pos = (75, 25)
            if HP is None:
                font_stat = ImageFont.truetype(FONT_BOLD, 80)
                if int(row.get('HP','')) > 9:
                    font_stat = ImageFont.truetype(FONT_BOLD, 60)
                    text_pos = (40, 25)

        draw.text(text_pos, layout['val'], font=font_stat, fill="black")
        if stat == "HP" and HP is not None:
            if int(row.get('HP','')) > 9:
                if int(HP) > 9:
                    draw.text((25, 25), HP, font=font_stat, fill="black")
                else:
                    draw.text((35, 25), HP, font=font_stat, fill="black")

            else:
                draw.text((40, 30), HP, font=font_stat, fill="black")

    # --- TEXT BOX GEOMETRY ENGINE ---
    text_start_y = 650
    margin_x = 24
    max_text_width = CANVAS_SIZE[0] - (margin_x * 2)
    
    name_text = clean_html_and_markdown(row.get('Name', 'UNKNOWN'))
    
    # Toggle logic depending on whether this execution is a single ability focus view
    if focus_ability:
        joined_traits = "" # Clear traits from focus views
        abilities_payload = clean_html_and_markdown(focus_ability)
        
        # Upscale font size engine loop for single ability display
        act_font_size = 24
        while act_font_size > 14:
            calc_y = text_start_y
            calc_y = draw_rich_paragraph(draw, name_text.upper(), (margin_x, calc_y), max_text_width, font_size=32, force_font_style='name', dry_run=True)
            calc_y = draw_rich_paragraph(draw, abilities_payload, (margin_x, calc_y), max_text_width, font_size=act_font_size, dry_run=True)
            if (calc_y - text_start_y) <= (CANVAS_SIZE[1] - text_start_y - 40):
                break
            act_font_size -= 1
    else:
        type_and_traits = []
        if row.get('Type'): type_and_traits.append(row.get('Type'))
        if row.get('Traits'): type_and_traits.append(clean_html_and_markdown(row.get('Traits')))
        joined_traits = " • ".join(type_and_traits).strip(" • ") if type_and_traits else ""
        
        abilities_payload = clean_html_and_markdown(row.get('ACT Abilities'))
        act_font_size = 15
        if len(abilities_payload + joined_traits) > 600:
            act_font_size = 14

    # Phase 1: Dry run calculation for layout box panel geometry
    calc_y = text_start_y
    calc_y = draw_rich_paragraph(draw, name_text.upper(), (margin_x, calc_y), max_text_width, font_size=32, force_font_style='name', dry_run=True)
    if joined_traits:
        calc_y = draw_rich_paragraph(draw, f"*{joined_traits}*", (margin_x, calc_y), max_text_width, font_size=16, dry_run=True) + 10
    if abilities_payload:
        calc_y = draw_rich_paragraph(draw, abilities_payload, (margin_x, calc_y), max_text_width, font_size=act_font_size, dry_run=True)
    
    total_text_height = calc_y - text_start_y
    padding = 20
    
    # Phase 2: Create a blended semi-transparent panel box layer
    overlay = Image.new("RGBA", CANVAS_SIZE, (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    
    panel_color = get_light_tint(bg_color, factor=0.82)
    panel_box = [
        margin_x - 10, 
        text_start_y - 10, 
        CANVAS_SIZE[0] - margin_x + 10, 
        text_start_y + total_text_height + padding
    ]
    
    overlay_draw.rectangle(panel_box, fill=(panel_color[0], panel_color[1], panel_color[2], 230))
    card = Image.alpha_composite(card.convert("RGBA"), overlay).convert("RGB")
    draw = ImageDraw.Draw(card)

    # Phase 3: Final rich text engine canvas render pass
    current_y = text_start_y
    current_y = draw_rich_paragraph(draw, name_text.upper(), (margin_x, current_y), max_text_width, font_size=32, force_font_style='name')
    if joined_traits:
        current_y = draw_rich_paragraph(draw, f"*{joined_traits}*", (margin_x, current_y), max_text_width, font_size=16, fill="#333333")
        current_y += 10
    if abilities_payload:
        current_y = draw_rich_paragraph(draw, abilities_payload, (margin_x, current_y), max_text_width, font_size=act_font_size)

    # Filename serialization engine logic
    clean_name = re.sub(r'\s+', '', row.get('Name', 'unit'))
    sanitized_filename = "".join([c for c in clean_name if c.isalnum()]).strip().capitalize()
    
    final_output_dir = OUTPUT_DIR
    if ability_suffix_name:
        output_filename = f"{TIME}_{FACTION}_{sanitized_filename}_{ability_suffix_name}.png"
        final_output_dir = f"{OUTPUT_DIR}/{VIDEO_NAME}"
        os.makedirs(final_output_dir, exist_ok=True)
    elif TIME:
        output_filename = f"{TIME}_{FACTION}_{sanitized_filename}.png"
        final_output_dir = f"{OUTPUT_DIR}/{VIDEO_NAME}"
        os.makedirs(final_output_dir, exist_ok=True)
    else:
        output_filename = f"{FACTION}_{sanitized_filename}.png"
    card.save(os.path.join(final_output_dir, output_filename), "PNG")
    print(f"Generated Sheet: {output_filename}")

def main_run():
    if not os.path.exists(CSV_PATH):
        raise Exception(f"File not found: {CSV_PATH}")
    found_match = False
    with open(CSV_PATH, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f, delimiter='\t')
        for row in reader:
            clean_unit_name = re.sub(r'\s+', '', row.get('Name', 'unit'))
            if not TIME:
                create_unit_card(row)
            elif clean_unit_name.capitalize() == re.sub(r'\s+', '', ABILITY).capitalize():
                create_unit_card(row)
                return True
            # Split and execute separate ability focus variants
            raw_abilities = row.get('ACT Abilities', '')
            individual_abilities, ability_names, _ = split_individual_abilities(raw_abilities)
            sanitized_unit_base = "".join([c for c in clean_unit_name if c.isalnum()]).strip().capitalize()           
            for idx, single_ability in enumerate(individual_abilities):
                ability_title = ability_names[idx]
                clean_ability = re.sub(r'\s+', '_', ability_title)                
                # Generate the full asset card focused exclusively on this layout string
                if TIME and ABILITY == ability_title.capitalize():
                    create_unit_card(row, focus_ability=single_ability, ability_suffix_name=clean_ability)
                    return True
            bg_color = parse_rgb(row.get('card_background style', ''))
            if FACTION == "necromancers":
                soul_abilities = row.get('SOUL Abilities', '')
                individual_abilities, ability_names, soul_costs = split_individual_abilities(soul_abilities)
                for idx, single_ability in enumerate(individual_abilities):
                    ability_title = ability_names[idx]
                    soul_cost = soul_costs[idx]
                    clean_ability = re.sub(r'\s+', '_', ability_title)                
                    # Generate the full asset card focused exclusively on this layout string
                    if TIME and ABILITY == ability_title.capitalize():
                        create_unit_card(row, focus_ability=f"{soul_cost}\n{single_ability}", ability_suffix_name=f"{clean_ability}")
                        return True

                ACTS_CSV_PATH = f"{FACTION}_ACTs.csv"
                if not os.path.exists(ACTS_CSV_PATH):
                    raise Exception(f"File not found: {ACTS_CSV_PATH}")                
                with open(ACTS_CSV_PATH, mode='r', encoding='utf-8') as acts_f:
                    acts_reader = csv.DictReader(acts_f, delimiter='\t')
                    for act_upgrades_row in acts_reader:
                        act_bg_color = parse_rgb(act_upgrades_row.get('card_background style', ''))
                        if bg_color != act_bg_color:
                            continue
                        raw_acts = act_upgrades_row.get('ACT Upgrades', '')
                        individual_acts, act_names, _ = split_individual_abilities(raw_acts)                                        
                        for idx, single_act in enumerate(individual_acts):
                            act_title = act_names[idx]
                            clean_act = re.sub(r'\s+', '_', act_title)                        
                            # Generate the full asset card focused exclusively on this layout string
                            if TIME and ABILITY == act_title.capitalize():
                                create_unit_card(row, focus_ability=single_act, ability_suffix_name=clean_act)
                                return True
                SOUL_CSV_PATH = f"{FACTION}_SOULs.csv"
                if not os.path.exists(SOUL_CSV_PATH):
                    raise Exception(f"File not found: {SOUL_CSV_PATH}")
                with open(SOUL_CSV_PATH, mode='r', encoding='utf-8') as souls_f:
                    souls_reader = csv.DictReader(souls_f, delimiter='\t')
                    for soul_upgrades_row in souls_reader:
                        soul_bg_color = parse_rgb(soul_upgrades_row.get('card_background style', ''))
                        if bg_color != soul_bg_color:
                            continue
                        raw_souls = soul_upgrades_row.get('SOUL Upgrades', '')
                        individual_souls, soul_names, soul_costs = split_individual_abilities(raw_souls)                                        
                        for idx, single_soul in enumerate(individual_souls):
                            soul_title = soul_names[idx]
                            soul_cost = soul_costs[idx]
                            clean_soul = re.sub(r'\s+', '_', soul_title)                        
                            # Generate the full asset card focused exclusively on this layout string
                            # if ABILITY == "Twist sinews":
                            #     print([ABILITY,soul_title.capitalize()])
                            if TIME and ABILITY == soul_title.capitalize():
                                create_unit_card(row, focus_ability=f"{soul_cost}\n{single_soul}", ability_suffix_name=f"{clean_soul}")
                                return True
            if not TIME:
                print("---")
    return False


def fix_timestamp(timestamp_str: str) -> str:
    """Prepends '00:' to timestamps missing the hour mark and pads single-digit minutes."""
    parts = timestamp_str.split(":")
    if len(parts) == 2:
        return f"00:{parts[0].zfill(2)}:{parts[1]}"
    if len(parts) == 3:
        return f"{parts[0].zfill(2)}:{parts[1]}:{parts[2]}"
    return timestamp_str


if __name__ == "__main__":
    if not args.matchup:
        for FACTION in FACTIONS:
            TIME = None
            HP = None
            SIDE = None
            CONDITIONS = []
            CSV_PATH = f"{FACTION}.csv"
            ABILITY = None
            main_run()
        exit(0)
    if args.matchup and not os.path.exists(args.matchup):
        raise Exception(f"File not found: {args.matchup}")

    guides = []

    with open(args.matchup, "r", encoding="utf-8") as file:
        for line in file:
            cleaned_line = line.strip()

            # Skip empty lines and lines starting with 'Deployments'
            if not cleaned_line or cleaned_line.startswith("Deployments") or cleaned_line.startswith("Dupl"):
                continue

            # Split the line by the ' - ' delimiter
            # Example: "Left - 7:55 - smite_4" -> ['Left', '7:55', 'smite_4']
            parts = [part.strip() for part in cleaned_line.split(" - ")]
            # Ensure the line has exactly the 3 expected parts before parsing
            if len(parts) == 3:
                side, raw_time, comment = parts
                conditions_parsed = []
                comment_parts = comment.split('_')
                if len(comment_parts) > 3:
                    raise Exception(f"Bad format in guide line: {cleaned_line}")
                if len(comment_parts) == 2:
                    action,hp = comment_parts
                    if not hp.isdigit():
                        raise Exception(f"Bad format in guide line: {cleaned_line}")
                elif len(comment_parts) == 3:
                    action,hp,all_conditions = comment_parts
                    conditions = all_conditions.split('+')
                    conditions_parsed = []
                    for c in conditions:
                        cregex = re.search(r'([A-Za-z ]+)([0-9]?)',c)
                        
                        if not cregex:
                            raise Exception(f"Bad condition format in guide comment: {comment}")
                        c_replacements = {
                            "Doomed": "Doom",
                            "Weakness": "Weak",
                        }
                        cname = c_replacements[cregex.group(1).capitalize()] if cregex.group(1).capitalize() in c_replacements else cregex.group(1).capitalize()
                        # print(cname)
                        conditions_parsed.append({
                            "condition": cname,
                            "amount": cregex.group(2) if cregex.group(2) else "1",
                        })
                conditions_parsed.sort(key=lambda x: x["condition"])
                # For when I forget the proper name
                line_data = {
                    "side": side,
                    "timestamp": fix_timestamp(raw_time),
                    "action": action.capitalize(),
                    "hp": hp,
                    "conditions": conditions_parsed,
                }
                guides.append(line_data)

    for guide in guides:
        TIME = guide["timestamp"]  
        HP = guide["hp"]
        ABILITY = guide["action"]
        SIDE = guide["side"]
        CONDITIONS = guide["conditions"]
        VIDEO_NAME = args.matchup
        found_match = False
        for FACTION in FACTIONS:
            CSV_PATH = f"{FACTION}.csv"            
            if main_run():
                found_match = True
        if not found_match:
            print(f"=== Could not match ability/unit: {ABILITY}")
