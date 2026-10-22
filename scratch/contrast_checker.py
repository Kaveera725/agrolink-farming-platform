import os
import sys
import re
sys.path.insert(0, os.path.dirname(__file__))
from audit_extractor import COLOR_MAP, contrast_ratio, audit_templates

# Common text + bg pairings used in Tailwind across the templates
TEST_PAIRS = [
    ("text-gray-400 on white", "gray-400", "white", "Secondary text / placeholders"),
    ("text-gray-500 on white", "gray-500", "white", "Secondary labels / subtitles"),
    ("text-gray-600 on white", "gray-600", "white", "Body descriptions"),
    ("text-gray-700 on white", "gray-700", "white", "Labels and card headings"),
    ("text-gray-800 on white", "gray-800", "white", "Primary headings"),
    ("text-gray-900 on white", "gray-900", "white", "Main display titles"),
    ("text-leaf on white", "leaf", "white", "Brand green text"),
    ("text-leaf-light on white", "leaf-light", "white", "Light leaf accent text"),
    ("text-leaf-dark on white", "leaf-dark", "white", "Dark green headings"),
    ("text-earth on white", "earth", "white", "Farmer persona badge text"),
    ("text-earth-light on white", "earth-light", "white", "Earth subtitles"),
    ("text-sky on white", "sky", "white", "Buyer persona links / titles"),
    ("text-gold on white", "gold", "white", "Price highlights on white"),
    ("text-yellow-500 on white", "yellow-500", "white", "Legacy yellow accents"),
    ("text-red-500 on white", "red-500", "white", "Error hints / delete links"),
    ("text-white on bg-leaf", "white", "leaf", "Primary button text"),
    ("text-white on bg-leaf-light", "white", "leaf-light", "Button hover state"),
    ("text-white on bg-leaf-dark", "white", "leaf-dark", "Hero button text / footer"),
    ("text-gray-900 on bg-gold", "gray-900", "gold", "CTA button text on gold"),
    ("text-white on bg-gold", "white", "gold", "White text on gold button"),
    ("text-white on bg-yellow-500", "white", "yellow-500", "Legacy search button text"),
    ("text-white on bg-red-600", "white", "red-600", "Danger button text"),
    ("text-white on bg-blue-600", "white", "blue-600", "Call farmer button text"),
    ("text-white on bg-emerald-600", "white", "emerald-600", "WhatsApp button text"),
    ("text-leaf-dark on bg-leaf-pale", "leaf-dark", "leaf-pale", "Active badge text"),
    ("text-leaf on bg-leaf-pale", "leaf", "leaf-pale", "Secondary button hover"),
    ("text-earth on bg-earth-pale", "earth", "earth-pale", "Farmer role chip"),
    ("text-sky on bg-sky-pale", "sky", "sky-pale", "Buyer role chip"),
    ("text-amber-900 on bg-amber-100", "amber-900", "amber-100", "Warning banner / deal badge"),
    ("text-yellow-800 on bg-yellow-50", "yellow-800", "yellow-50", "Advisory note text"),
    ("text-emerald-900 on bg-emerald-100", "emerald-900", "emerald-100", "Growing crop status badge"),
    ("text-rose-900 on bg-rose-100", "rose-900", "rose-100", "High margin warning badge"),
    ("text-purple-800 on bg-purple-100", "purple-800", "purple-100", "Admin role badge"),
    ("text-green-200 on bg-leaf-dark", "green-200", "leaf-dark", "Hero/footer subtitle text"),
    ("text-green-100 on bg-leaf", "green-100", "leaf", "Hero header microcopy"),
]

def analyze_contrasts():
    print("=== WCAG 2.1 CONTRAST ANALYSIS ===")
    failures = []
    passes = []
    for label, fg_name, bg_name, usage in TEST_PAIRS:
        fg_rgb = COLOR_MAP.get(fg_name)
        bg_rgb = COLOR_MAP.get(bg_name)
        if not fg_rgb or not bg_rgb:
            continue
        ratio = contrast_ratio(fg_rgb, bg_rgb)
        is_normal_pass = ratio >= 4.5
        is_large_pass = ratio >= 3.0
        
        status = "PASS (AAA)" if ratio >= 7.0 else ("PASS (AA)" if is_normal_pass else ("PASS (Large text / UI only)" if is_large_pass else "FAIL (WCAG AA)"))
        entry = {
            'label': label,
            'fg': fg_name,
            'bg': bg_name,
            'ratio': ratio,
            'status': status,
            'usage': usage,
            'is_fail': not is_normal_pass
        }
        if not is_normal_pass:
            failures.append(entry)
        else:
            passes.append(entry)
        print(f"{label:<32} Ratio: {ratio:5.2f}:1  ->  {status} ({usage})")
    
    return passes, failures

def analyze_buttons(buttons):
    print("\n=== BUTTON INVENTORY ANALYSIS ===")
    styles = {}
    for b in buttons:
        cls = b['classes']
        # Extract padding, bg, text, rounded, height
        py = re.search(r'py-([0-9\.]+)', cls)
        px = re.search(r'px-([0-9\.]+)', cls)
        text_sz = re.search(r'text-([a-z]+)', cls)
        bg = re.search(r'bg-([a-z0-9\-]+)', cls)
        rounded = re.search(r'rounded-([a-z0-9]+)', cls)
        min_h = re.search(r'min-h-\[([0-9]+px)\]', cls)

        style_key = (
            f"px-{px.group(1)}" if px else "no-px",
            f"py-{py.group(1)}" if py else "no-py",
            text_sz.group(0) if text_sz else "text-base",
            bg.group(0) if bg else "no-bg",
            rounded.group(0) if rounded else "rounded-none",
            min_h.group(1) if min_h else "<44px (implicit)"
        )
        if style_key not in styles:
            styles[style_key] = []
        styles[style_key].append(b)

    print(f"Total distinct button style signatures found: {len(styles)}")
    for style, instances in sorted(styles.items(), key=lambda x: len(x[1]), reverse=True):
        print(f"- Style {style}: {len(instances)} instances (e.g. '{instances[0]['text']}' in {instances[0]['file']})")
    return styles

if __name__ == '__main__':
    passes, failures = analyze_contrasts()
    data = audit_templates()
    styles = analyze_buttons(data['buttons'])
    print(f"\nTotal Contrast Failures for normal text: {len(failures)}")
