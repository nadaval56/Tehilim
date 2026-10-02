#!/usr/bin/env python3
"""
מחשבון ניגודיות WCAG.

ניגודיות היא הכשל הנפוץ ביותר בביקורת נגישות, והיא בלתי ניתנת
לאומדן בעין: גוון אפור שנראה "בסדר" על רקע בהיר יכול לתת 2.9:1
במקום 4.5:1 הנדרשים. תמיד לחשב.

  python3 contrast.py "#5A6470" "#E4E6DE"          # זוג בודד
  python3 contrast.py --matrix fg.txt bg.txt        # כל הזוגות
  python3 contrast.py --css assets/css/style.css    # שולף משתני צבע ובונה מטריצה

ספים (WCAG 2.x):
  4.5:1  טקסט רגיל, רמה AA          ← ברירת המחדל שנבדקת
  3.0:1  טקסט גדול (18.66px+ מודגש, או 24px+), וגם רכיבי ממשק וגבולות (1.4.11)
  7.0:1  טקסט רגיל, רמה AAA
"""
import re, sys, itertools

def lum(h):
    h = h.lstrip('#')
    if len(h) == 3:
        h = ''.join(c * 2 for c in h)
    r, g, b = (int(h[i:i+2], 16) / 255 for i in (0, 2, 4))
    f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = f(r), f(g), f(b)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b

def ratio(a, b):
    la, lb = lum(a), lum(b)
    if la < lb:
        la, lb = lb, la
    return (la + 0.05) / (lb + 0.05)

def grade(r):
    if r >= 7:   return 'AAA'
    if r >= 4.5: return 'AA'
    if r >= 3:   return 'AA-large / UI'
    return 'נכשל'

def suggest(fg, bg, target=4.5):
    """מחשיך או מבהיר את הטקסט בצעדים קטנים עד שהיחס עובר את הסף,
       ומשמר את הגוון — כדי שהתיקון לא יהרוס את זהות העיצוב."""
    h = fg.lstrip('#')
    if len(h) == 3:
        h = ''.join(c * 2 for c in h)
    r, g, b = (int(h[i:i+2], 16) for i in (0, 2, 4))
    darker = lum(bg) > 0.3
    for _ in range(255):
        if ratio('#%02X%02X%02X' % (r, g, b), bg) >= target:
            break
        step = -3 if darker else 3
        r, g, b = (max(0, min(255, v + step)) for v in (r, g, b))
    return '#%02X%02X%02X' % (r, g, b)

def report(pairs, target=4.5):
    bad = 0
    for fg, bg, label in pairs:
        r = ratio(fg, bg)
        ok = r >= target
        bad += 0 if ok else 1
        line = f'{"ok " if ok else "BAD"} {r:5.2f}  {grade(r):14} {fg} על {bg}'
        if label:
            line += f'   {label}'
        if not ok:
            line += f'\n      הצעה: {suggest(fg, bg, target)} (נותן {ratio(suggest(fg,bg,target), bg):.2f})'
        print(line)
    return bad

def hexes(path):
    txt = open(path, encoding='utf-8').read()
    out = {}
    for m in re.finditer(r'(--[\w-]+)\s*:\s*(#[0-9A-Fa-f]{3,6})\b', txt):
        out[m.group(1)] = m.group(2)
    if not out:
        for m in re.finditer(r'#[0-9A-Fa-f]{6}\b', txt):
            out[m.group(0)] = m.group(0)
    return out

def main():
    a = sys.argv[1:]
    if not a:
        print(__doc__); return 0
    target = 4.5
    if '--target' in a:
        i = a.index('--target'); target = float(a[i+1]); del a[i:i+2]

    if a[0] == '--css':
        colors = hexes(a[1])
        if not colors:
            print('לא נמצאו צבעים.'); return 1
        print(f'{len(colors)} צבעים ב-{a[1]}:')
        for k, v in colors.items():
            print(f'   {k:22} {v}')
        print('\nמטריצה (כל צבע כטקסט על כל צבע כרקע; מוצגים רק הזוגות שנכשלים):\n')
        pairs = [(f, b, f'{kf} על {kb}') for kf, f in colors.items() for kb, b in colors.items()
                 if f.lower() != b.lower() and ratio(f, b) < target]
        if not pairs:
            print('  כל הזוגות עוברים — אבל שים לב: לא כל זוג באמת מופיע יחד בעיצוב.')
        else:
            report(pairs, target)
        print('\nהמטריצה מציפה מועמדים; ההכרעה היא אילו זוגות באמת מופיעים יחד באתר.')
        return 0

    if a[0] == '--matrix':
        fg = [l.strip() for l in open(a[1]) if l.strip()]
        bg = [l.strip() for l in open(a[2]) if l.strip()]
        return 1 if report([(f, b, '') for f, b in itertools.product(fg, bg)], target) else 0

    pairs = [(a[i], a[i+1], '') for i in range(0, len(a) - 1, 2)]
    return 1 if report(pairs, target) else 0

if __name__ == '__main__':
    sys.exit(main())
