#!/usr/bin/env python3
"""
Tehillim site — the accessibility/privacy markup that every page carries.

Adapted from geniza-explorer (same author, MIT).

Both generators need the exact same two blocks: build.py for index.html and
fragment.html, prerender.py for the ~36K document pages and the static index.
Keeping them here means the snippet is written once, and a change to the
accessibility menu cannot drift between the home page and a document page.

The snippets are plain strings and are *not* run through str.format(), so the
braces in the inline JavaScript stay single. Callers interpolate them into
their own templates through a named placeholder.

    head(root)   goes in <head>, after the site stylesheet
    foot(root)   goes immediately before </body>

`root` is the relative path back to the site root ("" at the top level,
"../" under d/), the same value the templates already use for assets.
"""


def head(root: str = "", version: str = "") -> str:
    """Stylesheet plus the pre-paint restore of the visitor's own settings.

    The inline script has to run before the first paint. Applying the saved
    preferences from a11y.js instead — after the body has parsed — makes a
    visitor who chose high contrast watch the page load in the normal palette
    and then flip, on every single page view.

    It reads the privacy decision first: someone who declined local storage
    gets nothing read back, not even their display preferences.
    """
    v = f"?v={version}" if version else ""
    return f"""  <link rel="stylesheet" href="{root}assets/a11y.css{v}">
  <script>
    try {{
      var _p = localStorage.getItem('privacy:v1');
      if (!_p || JSON.parse(_p).local !== false) {{
        var _r = document.documentElement, _a = localStorage.getItem('a11y:v1');
        if (_a) {{
          _a = JSON.parse(_a);
          if (_a.fs) _r.setAttribute('data-fs', _a.fs);
          if (_a.mode) _r.classList.add('a11y-' + _a.mode);
          ['links', 'readable', 'spacing', 'still', 'cursor', 'focus']
            .forEach(function (k) {{ if (_a[k]) _r.classList.add('a11y-' + k); }});
        }}
        var _t = localStorage.getItem('tehillim:prefs');
        if (_t) {{
          _t = JSON.parse(_t);
          if (_t.theme === 'light' || _t.theme === 'dark') _r.setAttribute('data-theme', _t.theme);
          if (_t.names) _r.classList.add('show-names');
        }}
      }}
    }} catch (e) {{ /* מצב פרטי, או אחסון חסום — הדף פשוט נטען כרגיל */ }}
  </script>"""


def foot(root: str = "", version: str = "") -> str:
    """The two components. privacy.js first, always.

    a11y.js asks PRIVACY whether it may write to localStorage before it saves
    anything; if privacy.js has not defined it yet, that question silently
    answers "yes" and the visitor's "no local storage" choice is ignored.

    The document URLs are passed explicitly rather than derived from the path
    depth, so they stay correct under d/ and inside any future subdirectory.
    """
    v = f"?v={version}" if version else ""
    return f"""  <script>
    window.PRIVACY_CONFIG = {{ appPrefixes: ['a11y:', 'tehillim:'], privacyUrl: '{root}privacy/' }};
    window.A11Y_CONFIG = {{ privacyUrl: '{root}privacy/', accessibilityUrl: '{root}accessibility/' }};
  </script>
  <script src="{root}assets/privacy.js{v}"></script>
  <script src="{root}assets/a11y.js{v}"></script>"""
