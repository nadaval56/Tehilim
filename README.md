# תהילים — אתר לימודי

אתר סטטי בעברית סביב 150 מזמורי תהילים: דף לכל מזמור, ועדשות שמסתכלות על הספר כולו.
האפיון המלא נמצא ב-[`tehillim-project.md`](tehillim-project.md).

## כלל יסוד: שמות הקודש
אף שם קודש אינו נכתב במלואו, בשום מקום: לא באתר, לא בקבצי הנתונים, לא בקוד ולא בהודעות commit.
הזיהוי בקוד (`scripts/names.py`) בנוי מ-code points בלבד. הטקסט מספריא עובר המרה לכינוי בזיכרון,
לפני שהוא נשמר. `scripts/check_names.py` רץ ב-CI ומכשיל כל שם מלא ב-repo, ב-build ובהודעות ה-commit.

## מבנה
```
config/      kinuyim.json (צורות הכינוי), site.json
scripts/     fetch_psalms.py, fetch_sources.py   — שליפה מספריא (רשת)
             build_data.py                       — נתונים נגזרים (ללא רשת)
             build_site.py                       — בניית האתר ל-build/ (ללא רשת)
             check_names.py, names.py, hebrew.py, heading_vocab.py, a11y_snippets.py
data/        psalms/001–150.json, books.json, names_stats.json, doublets.json,
             chida.json, sources.json, annotations/chol_names.json
site/        templates/ (Jinja2), assets/ (CSS, JS, גופנים)
tests/       בדיקות יחידה וקבלה
```

## הרצה
```sh
pip install -r requirements.txt
python scripts/fetch_psalms.py      # רק כשרוצים לרענן מספריא
python scripts/fetch_sources.py
python scripts/build_data.py
python scripts/build_site.py        # → build/
python scripts/check_names.py --git-log
python -m unittest discover -s tests
```
הפריסה ל-GitHub Pages נעשית ב-`.github/workflows/deploy.yml` בכל push ל-`main`.
בהגדרות ה-repo, תחת Pages, יש לבחור Source: GitHub Actions.

## מה ממתין לאישור
- `data/annotations/chol_names.json`: מועמדים לשמות חול. כולם עדיין בכינוי ונספרים.
- `config/kinuyim.json`: צורות הכינוי המנוקדות.
- `data/doublets.json`: קטעים כפולים שנמצאו חישובית (`status: candidate`).
- `data/chida.json`: כלל הסידור של תהלים החיד"א.
- כותרות המזמורים (`heading.review: "auto"`).

## רישוי
נוסח המקרא: מקרא על פי המסורה (ספריא), CC-BY-SA. התלמוד: מהדורת ויקיטקסט (ספריא), CC-BY-SA.
הנתונים הנגזרים מוגשים ב-CC BY-SA 4.0. גופנים: SIL OFL 1.1. רכיבי הנגישות והפרטיות מבוססים על geniza-explorer (MIT).
