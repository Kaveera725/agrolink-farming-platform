import os
import re
import glob

# WCAG Luminance & Contrast Calculator
def srgb_to_linear(c):
    c = c / 255.0
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

def relative_luminance(rgb):
    r, g, b = rgb
    return 0.2126 * srgb_to_linear(r) + 0.7152 * srgb_to_linear(g) + 0.0722 * srgb_to_linear(b)

def contrast_ratio(rgb1, rgb2):
    l1 = relative_luminance(rgb1)
    l2 = relative_luminance(rgb2)
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)

# Common tailwind colors hex map
COLOR_MAP = {
    'white': (255, 255, 255),
    'black': (0, 0, 0),
    # Custom tokens
    'leaf': (45, 106, 79),         # #2D6A4F
    'leaf-light': (64, 145, 108),   # #40916C
    'leaf-dark': (27, 67, 50),      # #1B4332
    'leaf-pale': (216, 243, 220),   # #D8F3DC
    'earth': (139, 69, 19),         # #8B4513
    'earth-light': (160, 82, 45),   # #A0522D
    'earth-pale': (253, 241, 232),  # #FDF1E8
    'sky': (26, 101, 158),          # #1A659E
    'sky-pale': (235, 244, 251),    # #EBF4FB
    'gold': (217, 119, 6),          # #D97706
    'gold-light': (245, 158, 11),   # #F59E0B
    'gold-pale': (255, 248, 231),   # #FFF8E7
    # Tailwind Grays
    'gray-50': (249, 250, 251),
    'gray-100': (243, 244, 246),
    'gray-200': (229, 231, 235),
    'gray-300': (209, 213, 219),
    'gray-400': (156, 163, 175),
    'gray-500': (107, 114, 128),
    'gray-600': (75, 85, 99),
    'gray-700': (55, 65, 81),
    'gray-800': (31, 41, 55),
    'gray-900': (17, 24, 39),
    # Greens & Emeralds
    'green-50': (240, 253, 244),
    'green-100': (220, 252, 231),
    'green-200': (187, 247, 208),
    'green-300': (134, 239, 172),
    'green-400': (74, 222, 128),
    'green-500': (34, 197, 94),
    'green-600': (22, 163, 74),
    'green-700': (21, 128, 61),
    'green-800': (22, 101, 52),
    'green-900': (20, 83, 45),
    'emerald-50': (236, 253, 245),
    'emerald-100': (209, 250, 229),
    'emerald-200': (167, 243, 208),
    'emerald-300': (110, 231, 183),
    'emerald-400': (52, 211, 153),
    'emerald-500': (16, 185, 129),
    'emerald-600': (5, 150, 105),
    'emerald-700': (4, 120, 87),
    'emerald-800': (6, 95, 70),
    'emerald-900': (6, 78, 59),
    # Blues
    'blue-50': (239, 246, 255),
    'blue-100': (219, 234, 254),
    'blue-200': (191, 219, 254),
    'blue-500': (59, 130, 246),
    'blue-600': (37, 99, 235),
    'blue-700': (29, 78, 216),
    'blue-800': (30, 64, 175),
    'blue-900': (30, 58, 138),
    # Ambers & Yellows
    'yellow-50': (254, 252, 232),
    'yellow-100': (254, 249, 195),
    'yellow-500': (234, 179, 8),
    'yellow-600': (202, 138, 4),
    'yellow-700': (161, 98, 7),
    'yellow-800': (133, 77, 14),
    'amber-50': (255, 251, 235),
    'amber-100': (254, 243, 199),
    'amber-200': (253, 230, 138),
    'amber-500': (245, 158, 11),
    'amber-600': (217, 119, 6),
    'amber-700': (180, 83, 9),
    'amber-800': (146, 64, 14),
    'amber-900': (120, 53, 15),
    # Reds & Roses
    'red-50': (254, 242, 242),
    'red-100': (254, 226, 226),
    'red-200': (254, 202, 202),
    'red-500': (239, 68, 68),
    'red-600': (220, 38, 38),
    'red-700': (185, 28, 28),
    'red-800': (153, 27, 27),
    'red-900': (127, 29, 29),
    'rose-100': (255, 228, 230),
    'rose-900': (136, 19, 55),
    # Purples
    'purple-100': (243, 232, 255),
    'purple-700': (126, 34, 206),
    'purple-800': (107, 33, 168),
}

EMOJI_REGEX = re.compile(r'[\U00010000-\U0010ffff]|[\u2600-\u27bf]|[\u2300-\u23ff]|[\u2b50-\u2b55]|[\ufe0f]')

def audit_templates():
    template_files = sorted(glob.glob('templates/**/*.html', recursive=True))
    results = {}
    
    all_buttons = []
    all_colors = set()
    all_confirm_popups = []
    all_inline_styles = []
    all_emojis = []
    all_tap_targets_under_44 = []

    for fpath in template_files:
        rel_path = os.path.relpath(fpath, 'templates').replace('\\', '/')
        with open(fpath, 'r', encoding='utf-8') as f:
            content = f.read()

        # Check confirm() popups
        confirms = re.findall(r'confirm\([^)]+\)', content)
        if confirms:
            all_confirm_popups.append((rel_path, confirms))

        # Check inline styles
        inline_styles = re.findall(r'style=["\'][^"\']+["\']', content)
        if inline_styles:
            all_inline_styles.append((rel_path, inline_styles))

        # Check emojis
        emojis_found = EMOJI_REGEX.findall(content)
        if emojis_found:
            all_emojis.append((rel_path, list(set(emojis_found))))

        # Check buttons & links styled as buttons
        btn_matches = re.findall(r'<(?:button|a)[^>]*class=["\']([^"\']*)["\'][^>]*>(.*?)</(?:button|a)>', content, re.DOTALL)
        for cls, text in btn_matches:
            clean_text = re.sub(r'<[^>]+>', '', text).strip()
            clean_text = ' '.join(clean_text.split())[:30]
            if any(k in cls for k in ['btn-', 'bg-leaf', 'bg-gold', 'bg-yellow', 'bg-red', 'bg-green', 'bg-sky', 'px-', 'py-']):
                all_buttons.append({
                    'file': rel_path,
                    'classes': cls,
                    'text': clean_text
                })

        # Check tap targets under 44px
        # e.g., py-1, py-0.5, py-1.5, py-2, text-xs without min-h-[44px]
        small_targets = re.findall(r'<(?:button|a|input)[^>]*class=["\']([^"\']*(?:py-0\.5|py-1|py-1\.5|py-2|h-6|h-7|h-8|h-9)[^"\']*)["\']', content)
        for match in small_targets:
            if 'min-h-[44px]' not in match and 'min-h-[46px]' not in match and 'min-h-[48px]' not in match:
                all_tap_targets_under_44.append((rel_path, match))

        # Check color classes
        color_classes = re.findall(r'(?:bg|text|border)-([a-z0-9\-]+)', content)
        for c in color_classes:
            all_colors.add(c)

    return {
        'files': template_files,
        'buttons': all_buttons,
        'colors': all_colors,
        'confirms': all_confirm_popups,
        'inline_styles': all_inline_styles,
        'emojis': all_emojis,
        'small_targets': all_tap_targets_under_44
    }

if __name__ == '__main__':
    data = audit_templates()
    print(f"Audited {len(data['files'])} templates.")
    print(f"Found {len(data['buttons'])} button instances.")
    print(f"Found {len(data['confirms'])} files with confirm() popups.")
    print(f"Found {len(data['inline_styles'])} files with inline styles.")
    print(f"Found {len(data['emojis'])} files with emoji icons.")
    print(f"Found {len(data['small_targets'])} small tap target matches.")
