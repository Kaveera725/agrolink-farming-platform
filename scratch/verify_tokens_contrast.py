def lum(r, g, b):
    def channel(c):
        c = c / 255.0
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)

def ratio(hex1, hex2):
    r1, g1, b1 = int(hex1[1:3], 16), int(hex1[3:5], 16), int(hex1[5:7], 16)
    r2, g2, b2 = int(hex2[1:3], 16), int(hex2[3:5], 16), int(hex2[5:7], 16)
    l1, l2 = lum(r1, g1, b1), lum(r2, g2, b2)
    return (max(l1, l2) + 0.05) / (min(l1, l2) + 0.05)

tokens = [
    ('leaf-700 on white', '#1B4332', '#FFFFFF'),
    ('leaf-600 on white', '#2D6A4F', '#FFFFFF'),
    ('leaf-700 on leaf-100', '#1B4332', '#D8F3DC'),
    ('earth-800 on earth-100', '#5c2d18', '#FDF1E8'),
    ('sky-800 on sky-100', '#104269', '#EBF4FB'),
    ('gold dark text on gold-500', '#3B2A00', '#F4A226'),
    ('gold-900 on gold-100', '#633902', '#FFF8E7'),
    ('danger-700 on danger-100', '#7A271A', '#FEF3F2'),
    ('ink on white', '#1F2A24', '#FFFFFF'),
    ('ink on canvas', '#1F2A24', '#F7FAF5'),
    ('ink-secondary on white', '#3B4D41', '#FFFFFF'),
    ('ink-secondary on canvas', '#3B4D41', '#F7FAF5'),
    ('ink-muted on white', '#54685A', '#FFFFFF'),
    ('ink-muted on canvas', '#54685A', '#F7FAF5'),
]

for label, fg, bg in tokens:
    cr = ratio(fg, bg)
    status = 'PASS (AA)' if cr >= 4.5 else 'FAIL'
    print(f'{label:30} : {cr:.2f}:1  -> {status}')
