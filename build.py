#!/usr/bin/env python3
"""Tapvio: static link-in-bio site generator.

Reads config.yml + profiles/*.yml and writes a fully static, SEO-ready site to dist/.
Usage:
    python build.py            # build site into dist/
    python build.py --check    # validate profiles only (used on pull requests)
    python build.py --no-og    # skip Open Graph image rendering (faster local builds)
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path
from urllib.parse import quote, urlparse

import yaml
from jinja2 import Environment, FileSystemLoader, select_autoescape

ROOT = Path(__file__).resolve().parent
PROFILES, TEMPLATES, STATIC = ROOT / "profiles", ROOT / "templates", ROOT / "static"
AVATARS, FONTS, CACHE, DIST = ROOT / "avatars", ROOT / "fonts", ROOT / ".cache", ROOT / "dist"
THEME_CSS = STATIC / "profile" / "themes"
GF = "https://fonts.googleapis.com/css2?display=swap&family="

# Each theme: label, one-line description, Google Fonts query, whether it has a dark mode,
# and the colours used for its share image (bg, text, accent).
THEMES = {
    "resume":    {"label": "Résumé", "desc": "Set like a well-made CV. Section names in a left column.",
                  "font": "Hanken+Grotesk:wght@400;500;600;700", "modes": True, "og": ("#ffffff", "#141a2a", "#2240c4")},
    "card":      {"label": "Business card", "desc": "A printed contact card on a desk, with Save contact.",
                  "font": "Libre+Franklin:wght@400;500;600;700", "modes": False, "og": ("#34463d", "#f9f7f1", "#f9f7f1")},
    "tiles":     {"label": "Tiles", "desc": "A grid of tinted tiles. Featured links get a wide tile.",
                  "font": "Figtree:wght@400;600;700;800", "modes": True, "og": ("#eceef2", "#151820", "#1f6feb")},
    "studio":    {"label": "Studio", "desc": "Your name set huge, links as large lines of type.",
                  "font": "Bricolage+Grotesque:opsz,wdth,wght@12..96,75..100,400..700", "modes": False, "og": ("#000000", "#f1f1ef", "#f1f1ef")},
    "contents":  {"label": "Contents", "desc": "A book's table of contents, with dotted leaders.",
                  "font": "Newsreader:ital,opsz,wght@0,6..72,400..600;1,6..72,400", "modes": True, "og": ("#fffefb", "#1c1b19", "#8c1c2b")},
    "terminal":  {"label": "Terminal", "desc": "An Ubuntu terminal session. Links listed like files.",
                  "font": "Ubuntu+Mono:wght@400;700", "modes": False, "og": ("#300a24", "#ffffff", "#8ae234")},
    "desktop95": {"label": "Desktop 95", "desc": "A Windows 95 window with bevelled buttons.",
                  "font": None, "modes": False, "og": ("#008080", "#ffffff", "#c0c0c0")},
    "bold":      {"label": "Bold", "desc": "Thick borders and hard shadows on yellow.",
                  "font": "Archivo:wdth,wght@62..125,400..900", "modes": False, "og": ("#ffd23f", "#000000", "#ff8fd6")},
    "cover":     {"label": "Cover", "desc": "A full-width photo banner with a large serif name.",
                  "font": "Instrument+Sans:wght@400..700&family=Instrument+Serif", "modes": True, "og": ("#ffffff", "#16171a", "#14532d")},
}
DEFAULT_THEME = "resume"
# Themes from the first version map to their closest new equivalent.
THEME_ALIASES = {"aurora": "studio", "midnight": "studio", "light": "resume", "glass": "tiles", "neon": "terminal",
                 "ocean": "cover", "forest": "card", "sunset": "bold", "rose": "tiles", "sand": "contents", "minimal": "resume"}
# Optional font override: key -> (Google Fonts query or None, CSS stack)
FONTS_OVERRIDE = {
    "hanken-grotesk": ("Hanken+Grotesk:wght@400;500;600;700", '"Hanken Grotesk",system-ui,sans-serif'),
    "figtree": ("Figtree:wght@400;600;700;800", '"Figtree",system-ui,sans-serif'),
    "libre-franklin": ("Libre+Franklin:wght@400;500;600;700", '"Libre Franklin",system-ui,sans-serif'),
    "bricolage-grotesque": ("Bricolage+Grotesque:opsz,wdth,wght@12..96,75..100,400..700", '"Bricolage Grotesque",system-ui,sans-serif'),
    "instrument-sans": ("Instrument+Sans:wght@400..700", '"Instrument Sans",system-ui,sans-serif'),
    "ibm-plex-sans": ("IBM+Plex+Sans:wght@400;500;600;700", '"IBM Plex Sans",system-ui,sans-serif'),
    "newsreader": ("Newsreader:ital,opsz,wght@0,6..72,400..600;1,6..72,400", '"Newsreader",Georgia,serif'),
    "source-serif": ("Source+Serif+4:ital,opsz,wght@0,8..60,400..700;1,8..60,400", '"Source Serif 4",Georgia,serif'),
    "ubuntu-mono": ("Ubuntu+Mono:wght@400;700", '"Ubuntu Mono",ui-monospace,monospace'),
    "system": (None, 'system-ui,-apple-system,"Segoe UI",Roboto,sans-serif'),
}
OPTIONS = {"mode": ["auto", "light", "dark"], "avatar": ["circle", "rounded", "square"], "icons": ["on", "off"]}
RETIRED_STYLE_KEYS = {"buttons", "layout", "effect", "animation", "gradient", "background_image"}
HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
USERNAME_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,28}[a-z0-9])$")
RESERVED = {
    "admin", "api", "app", "assets", "static", "avatars", "about", "help", "login", "create", "guide",
    "signup", "register", "settings", "sitemap", "robots", "index", "404", "www", "themes", "preview",
    "mail", "blog", "docs", "terms", "privacy", "contact", "support", "new", "join", "feed", "demo",
}
ALLOWED_SCHEMES = {"https", "http", "mailto", "tel"}
LIMITS = {"bio": 200, "about": 1200, "name": 80, "headline": 100, "title": 120,
          "description": 160, "socials": 12, "sections": 15, "links": 200}
WARNINGS: list[str] = []


class ProfileError(Exception):
    pass


# ---------------------------------------------------------------- validation
def _url(url, where: str) -> str:
    if not isinstance(url, str) or not url.strip():
        raise ProfileError(f"{where}: url is required")
    url = url.strip()
    parsed = urlparse(url)
    if parsed.scheme.lower() not in ALLOWED_SCHEMES:
        raise ProfileError(f"{where}: url must start with https://, mailto: or tel: (got {url!r})")
    if parsed.scheme in {"http", "https"} and not parsed.netloc:
        raise ProfileError(f"{where}: invalid url {url!r}")
    return url


def _text(value, key: str, where: str) -> str:
    value = "" if value is None else str(value).strip()
    if len(value) > LIMITS[key]:
        raise ProfileError(f"{where}: {key} is longer than {LIMITS[key]} characters")
    return value


def _image(value, where: str, field: str) -> str:
    value = str(value or "").strip()
    if value.startswith("avatars/"):
        if not (ROOT / value).is_file():
            raise ProfileError(f"{where}: {field} file {value} not found")
    elif value and urlparse(value).scheme != "https":
        raise ProfileError(f"{where}: {field} must be an https URL or avatars/<file>")
    if any(c in value for c in "\"'<>\\ "):
        raise ProfileError(f"{where}: {field} contains invalid characters")
    return value


def parse_style(data: dict, where: str) -> dict:
    style = data.get("style") or {}
    if not isinstance(style, dict):
        raise ProfileError(f"{where}: style must be a mapping")
    if data.get("theme") and "theme" not in style:
        style["theme"] = data["theme"]
    retired = sorted(RETIRED_STYLE_KEYS & set(style))
    if retired:
        WARNINGS.append(f"{where}: style option(s) {', '.join(retired)} are no longer used and were ignored")
    theme = str(style.get("theme") or "").strip()
    if theme in THEME_ALIASES:
        WARNINGS.append(f"{where}: theme {theme!r} was retired; using {THEME_ALIASES[theme]!r}")
        theme = THEME_ALIASES[theme]
    if theme and theme not in THEMES:
        raise ProfileError(f"{where}: style.theme must be one of {list(THEMES)} (got {theme!r})")
    s = {"theme": theme}
    for key, allowed in OPTIONS.items():
        val = str(style.get(key) or allowed[0]).strip()
        if val in ("true", "True"):
            val = "on"
        if val in ("false", "False"):
            val = "off"
        if val not in allowed:
            raise ProfileError(f"{where}: style.{key} must be one of {allowed} (got {val!r})")
        s[key] = val
    font = str(style.get("font") or "default").strip()
    if font in ("inter", "poppins", "space-grotesk", "outfit", "playfair", "jetbrains-mono", "nunito"):
        WARNINGS.append(f"{where}: font {font!r} was retired; using the theme's own font")
        font = "default"
    if font != "default" and font not in FONTS_OVERRIDE:
        raise ProfileError(f"{where}: style.font must be 'default' or one of {list(FONTS_OVERRIDE)}")
    s["font"] = font
    accent = str(style.get("accent") or "").strip()
    if accent and not HEX_RE.match(accent):
        raise ProfileError(f"{where}: style.accent must be a hex colour like #2240c4")
    s["accent"] = accent
    return s


def load_profile(path: Path, demo: bool = False) -> dict:
    where = path.name
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise ProfileError(f"{where}: invalid YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise ProfileError(f"{where}: file must contain a YAML mapping")

    username = str(data.get("username", "")).strip()
    if not USERNAME_RE.match(username):
        raise ProfileError(f"{where}: username must be 2-30 chars of a-z, 0-9 and '-'")
    if not demo:
        if username in RESERVED:
            raise ProfileError(f"{where}: username {username!r} is reserved")
        if path.stem != username:
            raise ProfileError(f"{where}: file name must be {username}.yml")

    p = {
        "username": username,
        "name": _text(data.get("name"), "name", where),
        "headline": _text(data.get("headline"), "headline", where),
        "bio": _text(data.get("bio"), "bio", where),
        "about": _text(data.get("about"), "about", where),
        "location": _text(data.get("location"), "headline", where),
        "job_title": _text(data.get("job_title"), "headline", where),
        "verified": bool(data.get("verified", False)) and not demo,
        "keywords": [str(k).strip() for k in (data.get("keywords") or []) if str(k).strip()][:15],
        "style": parse_style(data, where),
        "avatar": _image(data.get("avatar"), where, "avatar"),
        "cover": _image(data.get("cover"), where, "cover"),
    }
    if not p["name"]:
        raise ProfileError(f"{where}: name is required")

    wf = data.get("works_for") or {}
    p["works_for"] = None
    if isinstance(wf, dict) and wf.get("name"):
        p["works_for"] = {"name": _text(wf["name"], "name", where),
                          "url": _url(wf["url"], f"{where} works_for") if wf.get("url") else ""}

    socials = data.get("socials") or []
    if len(socials) > LIMITS["socials"]:
        raise ProfileError(f"{where}: at most {LIMITS['socials']} socials")
    p["socials"] = [{"label": _text(s.get("label"), "title", f"{where} socials") or "Link",
                     "url": _url(s.get("url"), f"{where} socials")} for s in socials]

    sections = data.get("sections") or []
    if len(sections) > LIMITS["sections"]:
        raise ProfileError(f"{where}: at most {LIMITS['sections']} sections")
    p["sections"], total = [], 0
    for i, sec in enumerate(sections, 1):
        links = []
        for j, ln in enumerate(sec.get("links") or [], 1):
            w = f"{where} section {i} link {j}"
            title = _text(ln.get("title"), "title", w)
            if not title:
                raise ProfileError(f"{w}: title is required")
            links.append({"title": title, "url": _url(ln.get("url"), w),
                          "description": _text(ln.get("description"), "description", w),
                          "featured": bool(ln.get("featured", False))})
        total += len(links)
        p["sections"].append({"title": _text(sec.get("title"), "title", where), "links": links})
    if total > LIMITS["links"]:
        raise ProfileError(f"{where}: at most {LIMITS['links']} links")
    p["link_count"] = total + len(p["socials"])
    return p


def load_all() -> list[dict]:
    profiles, errors = [], []
    for path in sorted(PROFILES.glob("*.yml")):
        if path.name.startswith("_"):
            continue
        try:
            profiles.append(load_profile(path))
        except ProfileError as exc:
            errors.append(str(exc))
    if errors:
        print("Profile validation failed:\n  - " + "\n  - ".join(errors), file=sys.stderr)
        sys.exit(1)
    return profiles


# ---------------------------------------------------------------- helpers
def last_modified(path: Path) -> str:
    try:
        out = subprocess.run(["git", "log", "-1", "--format=%cs", "--", str(path)],
                             cwd=ROOT, capture_output=True, text=True, check=False).stdout.strip()
        if out:
            return out
    except OSError:
        pass
    return dt.date.today().isoformat()


def domain_of(url: str) -> str:
    return urlparse(url).netloc.lower().removeprefix("www.")


def link_rel(url: str, verified: bool) -> str:
    if not url.startswith("http"):
        return ""
    return "noopener me" if verified else "noopener me ugc nofollow"


def contrast_text(hex_color: str) -> str:
    r, g, b = (int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5))
    lum = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4  # noqa: E731
    return "#000000" if 0.2126 * lum(r) + 0.7152 * lum(g) + 0.0722 * lum(b) > 0.35 else "#ffffff"


def theme_font_url(theme: str) -> str:
    q = THEMES[theme]["font"]
    return GF + q if q else ""


def resolve_style(style: dict, cfg: dict) -> dict:
    theme = style["theme"] or cfg.get("default_theme") or DEFAULT_THEME
    theme = THEME_ALIASES.get(theme, theme)
    mode = style["mode"] if THEMES[theme]["modes"] else "light"
    css_vars, font_url = [], theme_font_url(theme)
    if style["accent"]:
        css_vars += [f"--accent:{style['accent']}", f"--accent-ink:{contrast_text(style['accent'])}"]
    if style["font"] != "default":
        q, stack = FONTS_OVERRIDE[style["font"]]
        css_vars += [f"--font-body:{stack}", f"--font-display:{stack}"]
        if q:
            font_url = GF + q
    return {**style, "theme": theme, "mode": mode, "css": ";".join(css_vars), "font_url": font_url}


def profile_css(theme: str) -> str:
    base = (STATIC / "profile" / "base.css").read_text(encoding="utf-8")
    return base + "\n" + (THEME_CSS / f"{theme}.css").read_text(encoding="utf-8")


def vcard(p: dict, page_url: str) -> str:
    emails, phones = [], []
    for item in p["socials"] + [l for s in p["sections"] for l in s["links"]]:
        u = item["url"]
        if u.startswith("mailto:"):
            emails.append(u[7:].split("?")[0])
        elif u.startswith("tel:"):
            phones.append(u[4:])
        elif domain_of(u) == "wa.me":
            num = urlparse(u).path.strip("/")
            if num.isdigit():
                phones.append("+" + num)
    if not emails and not phones:
        return ""
    esc = lambda s: s.replace("\\", "\\\\").replace(",", "\\,").replace(";", "\\;").replace("\n", " ")  # noqa: E731
    parts = p["name"].split()
    lines = ["BEGIN:VCARD", "VERSION:3.0", f"FN:{esc(p['name'])}",
             f"N:{esc(parts[-1] if len(parts) > 1 else p['name'])};{esc(' '.join(parts[:-1]))};;;"]
    if p["job_title"] or p["headline"]:
        lines.append(f"TITLE:{esc(p['job_title'] or p['headline'])}")
    if p["works_for"]:
        lines.append(f"ORG:{esc(p['works_for']['name'])}")
    lines += [f"EMAIL;TYPE=INTERNET:{e}" for e in dict.fromkeys(emails)]
    lines += [f"TEL;TYPE=CELL:{t}" for t in dict.fromkeys(phones)]
    if p["location"]:
        lines.append(f"ADR;TYPE=WORK:;;;{esc(p['location'])};;;")
    lines.append(f"URL:{page_url}")
    if p["avatar_url"].startswith("https://"):
        lines.append(f"PHOTO;VALUE=URI:{p['avatar_url']}")
    lines.append("END:VCARD")
    return "\r\n".join(lines) + "\r\n"


def json_ld(p: dict, cfg: dict, page_url: str, avatar_url: str, modified: str, og: str) -> str:
    same_as = [l["url"] for l in p["socials"] if l["url"].startswith("http")]
    same_as += [l["url"] for s in p["sections"] for l in s["links"] if l["url"].startswith("http")]
    person = {"@type": "Person", "@id": f"{page_url}#person", "name": p["name"], "url": page_url,
              "sameAs": list(dict.fromkeys(same_as))[:60]}
    if p["bio"]:
        person["description"] = p["bio"]
    if avatar_url:
        person["image"] = avatar_url
    if p["job_title"] or p["headline"]:
        person["jobTitle"] = p["job_title"] or p["headline"]
    if p["location"]:
        person["address"] = {"@type": "PostalAddress", "addressLocality": p["location"]}
    if p["works_for"]:
        person["worksFor"] = {"@type": "Organization", "name": p["works_for"]["name"],
                              **({"url": p["works_for"]["url"]} if p["works_for"]["url"] else {})}
    if p["keywords"]:
        person["knowsAbout"] = p["keywords"]
    page = {"@type": "ProfilePage", "@id": page_url, "url": page_url,
            "name": f"{p['name']} | {cfg['site_name']}", "dateModified": modified,
            "mainEntity": {"@id": f"{page_url}#person"},
            "isPartOf": {"@type": "WebSite", "name": cfg["site_name"], "url": cfg["site_url"] + "/"}}
    if og:
        page["primaryImageOfPage"] = og
    graph = {"@context": "https://schema.org", "@graph": [
        page, person,
        {"@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": cfg["site_name"], "item": cfg["site_url"] + "/"},
            {"@type": "ListItem", "position": 2, "name": p["name"], "item": page_url}]}]}
    return json.dumps(graph, ensure_ascii=False, indent=2).replace("</", "<\\/")


# ---------------------------------------------------------------- Open Graph images
def _fetch_image(url: str):
    from PIL import Image
    try:
        if url.startswith("/") or url.startswith(str(ROOT)):
            return Image.open(url).convert("RGB")
        CACHE.mkdir(exist_ok=True)
        cached = CACHE / (hashlib.sha1(url.encode()).hexdigest() + ".img")
        if not cached.exists():
            req = urllib.request.Request(url, headers={"User-Agent": "Tapvio-build/1.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                cached.write_bytes(resp.read(5_000_000))
        return Image.open(io.BytesIO(cached.read_bytes())).convert("RGB")
    except Exception as exc:  # network blocked, 404, not an image...
        print(f"  ! image not loaded for share image ({exc.__class__.__name__}): {url}")
        return None


def render_og(p: dict, theme: str, accent: str, avatar_src: str, out: Path, site: str) -> bool:
    """1200x630 share image in the profile's theme colours: avatar, name, headline, address."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        return False
    bg, fg, t_accent = THEMES[theme]["og"]
    accent = accent or t_accent
    W, H, M = 1200, 630, 80
    img = Image.new("RGB", (W, H), bg)
    draw = ImageDraw.Draw(img)

    def font(bold: bool, size: int):
        try:
            return ImageFont.truetype(str(FONTS / ("Inter-Bold.otf" if bold else "Inter-Regular.otf")), size)
        except OSError:
            return ImageFont.load_default(size)

    size = 168
    avatar = _fetch_image(avatar_src) if avatar_src else None
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size - 1, size - 1), fill=255)
    if avatar:
        w, h = avatar.size
        side = min(w, h)
        avatar = avatar.crop(((w - side) // 2, (h - side) // 2, (w + side) // 2, (h + side) // 2))
        img.paste(avatar.resize((size, size), Image.LANCZOS), (M, M), mask)
    else:
        tile = Image.new("RGB", (size, size), accent)
        ImageDraw.Draw(tile).text((size / 2, size / 2), p["name"][:1].upper(), font=font(True, 84),
                                  fill=contrast_text(accent), anchor="mm")
        img.paste(tile, (M, M), mask)

    maxw = W - 2 * M

    def wrap(s: str, f, lines: int):
        words, out_lines, cur = s.split(), [], ""
        for w in words:
            trial = (cur + " " + w).strip()
            if draw.textlength(trial, font=f) <= maxw:
                cur = trial
            else:
                out_lines.append(cur)
                cur = w
        out_lines.append(cur)
        if len(out_lines) > lines:
            out_lines = out_lines[:lines]
            out_lines[-1] = out_lines[-1].rstrip(".,") + "…"
        return out_lines

    name_f, sub_f = font(True, 76), font(False, 36)
    y = M + size + 40
    for line in wrap(p["name"], name_f, 1):
        draw.text((M, y), line, font=name_f, fill=fg)
        y += 92
    sub = p["headline"] or p["bio"]
    for line in wrap(sub, sub_f, 2) if sub else []:
        draw.text((M, y), line, font=sub_f, fill=fg)
        y += 48
    label = f"{site}/{p['username']}"
    for sz in range(30, 15, -2):
        small_f = font(True, sz)
        if draw.textlength(label, font=small_f) <= maxw - 260:
            break
    draw.text((M, H - M + 6), label, font=small_f, fill=fg, anchor="ls")
    draw.rectangle((M, H - M + 22, M + 64, H - M + 28), fill=accent if accent.lower() != bg.lower() else fg)
    mark = FONTS.parent / "static" / "brand" / "tapvio-mark-256.png"
    if mark.exists():
        m = Image.open(mark).convert("RGBA").resize((64, 64), Image.LANCZOS)
        img.paste(m, (W - M - 64, H - M - 52), m)
    img.save(out, "PNG", optimize=True)
    return True


def render_guide() -> dict:
    """GUIDE.md is the single source for the /guide/ page."""
    import markdown
    md = markdown.Markdown(extensions=["tables", "attr_list", "md_in_html", "toc"])
    html = md.convert((ROOT / "GUIDE.md").read_text(encoding="utf-8"))
    html = html.replace('href="../create/"', 'href="../create/"')
    toc = [{"id": t["id"], "name": t["name"]} for top in md.toc_tokens for t in top.get("children", [])]
    return {"guide_html": html, "guide_toc": toc}


# ---------------------------------------------------------------- build
def build(cfg: dict, profiles: list[dict], og_images: bool = True) -> None:
    site_url = cfg["site_url"] = cfg["site_url"].rstrip("/")
    cfg["repo_url"] = f"https://github.com/{cfg['repo']}"
    host_path = site_url.split("://", 1)[-1]
    env = Environment(loader=FileSystemLoader(TEMPLATES), autoescape=select_autoescape(["html", "xml"]),
                      trim_blocks=True, lstrip_blocks=True)
    env.filters["domain"] = domain_of
    today = dt.date.today().isoformat()
    theme_fonts = json.dumps({k: theme_font_url(k) for k in THEMES})

    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir()
    if AVATARS.is_dir():
        shutil.copytree(AVATARS, DIST / "avatars")
    for f in STATIC.iterdir():
        if f.is_file() and f.suffix in {".svg", ".png", ".ico", ".webmanifest"}:
            shutil.copy(f, DIST / f.name)
    if (STATIC / "brand").is_dir():
        shutil.copytree(STATIC / "brand", DIST / "assets" / "brand")
    (DIST / "assets" / "themes").mkdir(parents=True, exist_ok=True)
    for t in THEMES:
        shutil.copy(THEME_CSS / f"{t}.css", DIST / "assets" / "themes" / f"{t}.css")
    shutil.copy(STATIC / "profile" / "base.css", DIST / "assets" / "profile-base.css")
    site_css = (STATIC / "site.css").read_text(encoding="utf-8")

    logo = (STATIC / "brand" / "tapvio-logo.svg").read_text(encoding="utf-8")
    logo = logo.replace('role="img" aria-label="Tapvio"', 'aria-hidden="true" focusable="false"', 1)
    common = {"cfg": cfg, "year": dt.date.today().year, "themes": THEMES, "theme_fonts": theme_fonts, "logo_svg": logo}
    sitemap = [{"loc": f"{site_url}/{p}", "lastmod": today, "images": []} for p in ("", "create/", "guide/")]

    def render_profile(p: dict, out: Path, page_url: str, noindex: bool = False):
        avatar_url = f"{site_url}/{p['avatar']}" if p["avatar"].startswith("avatars/") else p["avatar"]
        p["cover_url"] = f"{site_url}/{p['cover']}" if p["cover"].startswith("avatars/") else p["cover"]
        p["avatar_url"], p["page_url"] = avatar_url, page_url
        p["modified"] = p.get("modified") or today
        style = resolve_style(p["style"], cfg)
        for s in p["sections"]:
            for l in s["links"]:
                l["rel"] = link_rel(l["url"], p["verified"])
        for s in p["socials"]:
            s["rel"] = link_rel(s["url"], p["verified"])
        out.mkdir(parents=True, exist_ok=True)
        card = vcard(p, page_url)
        if card:
            (out / "contact.vcf").write_text(card, encoding="utf-8")
        p["vcard"] = bool(card)
        og_url = ""
        avatar_local = str(ROOT / p["avatar"]) if p["avatar"].startswith("avatars/") else p["avatar"]
        if og_images and not noindex and render_og(p, style["theme"], style["accent"], avatar_local, out / "og.png", host_path):
            og_url = page_url + "og.png"
        p["og_url"] = og_url
        title = p["name"] + (f", {p['headline']}" if p["headline"] else "") + f" | {cfg['site_name']}"
        description = p["bio"] or p["about"][:155] or f"All links for {p['name']} in one place."
        (out / "index.html").write_text(env.get_template("profile.html").render(
            **common, p=p, s=style, t=THEMES[style["theme"]], css=profile_css(style["theme"]),
            page_url=page_url, avatar_url=avatar_url, title=title, description=description,
            modified=p["modified"], og_image=og_url or avatar_url, noindex=noindex,
            json_ld="" if noindex else json_ld(p, cfg, page_url, avatar_url, p["modified"], og_url)), encoding="utf-8")
        return style

    for p in profiles:
        p["modified"] = last_modified(PROFILES / f"{p['username']}.yml")
        page_url = f"{site_url}/{p['username']}/"
        render_profile(p, DIST / p["username"], page_url)
        sitemap.append({"loc": page_url, "lastmod": p["modified"],
                        "images": [i for i in (p["og_url"], p["avatar_url"]) if i.startswith("http")]})

    demo_path = PROFILES / "_demo.yml"
    demo = None
    if demo_path.exists():
        demo = load_profile(demo_path, demo=True)
        render_profile(demo, DIST / "demo", f"{site_url}/demo/", noindex=True)

    ordered = sorted(profiles, key=lambda x: x["name"].lower())
    builder_data = {
        "themes": {k: {"label": v["label"], "desc": v["desc"], "modes": v["modes"], "font": theme_font_url(k),
                       "og": v["og"]} for k, v in THEMES.items()},
        "fonts": {k: {"url": GF + q if q else "", "stack": st} for k, (q, st) in FONTS_OVERRIDE.items()},
        "options": OPTIONS, "reserved": sorted(RESERVED), "taken": [p["username"] for p in profiles],
        "repo": cfg["repo"], "branch": cfg.get("branch", "main"), "site_url": site_url, "limits": LIMITS,
    }
    builder_json = json.dumps(builder_data).replace("</", "<\\/")
    pages = {
        "index.html": ("index.html", {"profiles": ordered, "page_url": site_url + "/"}),
        "404.html": ("404.html", {"page_url": site_url + "/404.html"}),
        "create/index.html": ("create.html", {"page_url": site_url + "/create/", "builder": builder_json}),
        "guide/index.html": ("guide.html", {"page_url": site_url + "/guide/", **render_guide()}),
        "preview/index.html": ("preview.html", {"page_url": site_url + "/preview/", "builder": builder_json,
                                                "base_css": (STATIC / "profile" / "base.css").read_text(encoding="utf-8")}),
    }
    for target, (tpl, ctx) in pages.items():
        (DIST / target).parent.mkdir(parents=True, exist_ok=True)
        (DIST / target).write_text(env.get_template(tpl).render(**common, css=site_css, **ctx), encoding="utf-8")

    (DIST / "sitemap.xml").write_text(env.get_template("sitemap.xml").render(urls=sitemap), encoding="utf-8")
    (DIST / "feed.xml").write_text(env.get_template("feed.xml").render(
        cfg=cfg, updated=max([p["modified"] for p in profiles] + ["2026-01-01"]),
        profiles=sorted(profiles, key=lambda x: x["modified"], reverse=True)[:50]), encoding="utf-8")
    (DIST / "llms.txt").write_text(env.get_template("llms.txt").render(cfg=cfg, profiles=ordered), encoding="utf-8")
    (DIST / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\nDisallow: /preview/\nDisallow: /demo/\n\nSitemap: {site_url}/sitemap.xml\n", encoding="utf-8")
    if cfg.get("indexnow_key"):
        (DIST / f"{cfg['indexnow_key']}.txt").write_text(cfg["indexnow_key"])
    (DIST / ".nojekyll").write_text("")
    if cfg.get("custom_domain"):
        (DIST / "CNAME").write_text(cfg["custom_domain"].strip() + "\n")
    (DIST / "urls.txt").write_text("\n".join(u["loc"] for u in sitemap) + "\n")
    for w in dict.fromkeys(WARNINGS):
        print("  warning:", w)
    print(f"Built {len(profiles)} profile(s){' + demo' if demo else ''} into {DIST.relative_to(ROOT)}/")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="validate profiles without building")
    ap.add_argument("--no-og", action="store_true", help="skip Open Graph image generation")
    args = ap.parse_args()
    cfg = yaml.safe_load((ROOT / "config.yml").read_text(encoding="utf-8"))
    if os.environ.get("TAPVIO_SITE_URL"):  # local preview: python build.py with TAPVIO_SITE_URL=http://localhost:8000
        cfg["site_url"] = os.environ["TAPVIO_SITE_URL"]
    profiles = load_all()
    if (PROFILES / "_demo.yml").exists():
        try:
            load_profile(PROFILES / "_demo.yml", demo=True)
        except ProfileError as exc:
            print(f"Demo profile invalid: {exc}", file=sys.stderr)
            sys.exit(1)
    if args.check:
        for w in dict.fromkeys(WARNINGS):
            print("  warning:", w)
        print(f"All {len(profiles)} profile(s) are valid.")
        return
    build(cfg, profiles, og_images=not args.no_og)


if __name__ == "__main__":
    main()
