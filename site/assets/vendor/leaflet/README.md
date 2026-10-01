# Leaflet 1.9.4 — עותק מקומי

הקבצים כאן הם `dist/` של חבילת npm `leaflet@1.9.4` (רישיון BSD-2-Clause,
ראו `LICENSE`).

## למה מקומי ולא מ-CDN

עד עכשיו העמוד הראשי טען את `leaflet.js` ואת `leaflet.css` מ-`unpkg.com`.
תג `<script>` ל-CDN מוסר את כתובת ה-IP של כל מבקר לצד שלישי בטעינת הדף —
בדיוק מה שמדיניות הפרטיות מבטיחה שלא קורה. אותו שיקול שבגללו הגופנים כבר
מוגשים מהאתר עצמו ולא מ-Google Fonts.

## השינוי היחיד מול המקור

ארבע הצהרות `font-size` ב-`leaflet.css` הומרו מ-`px` ל-`rem` בבסיס 16:

| שורה | לפני | אחרי |
|------|------|-------|
| `.leaflet-container` | `12px` | `0.75rem` |
| `.leaflet-control-zoom-in/out` | `22px` | `1.375rem` |
| `.leaflet-popup-content` | `13px` | `0.8125rem` |
| `.leaflet-tooltip` | `13px` | `0.8125rem` |

ההמרה מדויקת ואינה משנה את הגודל בברירת המחדל. בלעדיה כפתורי הזום ושורת
הייחוס של המפה היו נשארים קפואים בזמן שכל שאר האתר גדל, מפני שפקד גודל
הטקסט פועל בשינוי `font-size` של אלמנט השורש ו-`px` מתעלם ממנו.

## עדכון גרסה

```
npm pack leaflet@<version>
tar xzf leaflet-<version>.tgz
cp package/dist/leaflet.js package/dist/leaflet.css package/LICENSE assets/vendor/leaflet/
cp -r package/dist/images assets/vendor/leaflet/
```

ואז להחיל מחדש את המרת ה-`px` שלמעלה, ולהריץ את ביקורת הנגישות.
