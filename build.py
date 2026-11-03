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
import re
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

import yaml
from jinja2 import Environment, FileSystemLoader, select_autoescape

ROOT = Path(__file__).resolve().parent
PROFILES, TEMPLATES, STATIC = ROOT / "profiles", ROOT / "templates", ROOT / "static"
AVATARS, FONTS, CACHE, DIST = ROOT / "avatars", ROOT / "fonts", ROOT / ".cache", ROOT / "dist"

# theme -> (background, glow1, glow2, glow3, text, accent, default animated effect)
THEMES = {
    "aurora":   ("#080a1a", "#6d5dfc", "#00c2ff", "#ff4fd8", "#f2f3ff", "#8b7cff", "aurora"),
    "midnight": ("#0f1222", "#3446c9", "#5b2bbd", "#1b6fc9", "#eef0ff", "#7c8cff", "particles"),
    "light":    ("#f4f5fb", "#c7cdff", "#ffd6f1", "#c8f1ff", "#14172b", "#4353e8", "aurora"),
    "glass":    ("#1b1036", "#ff6ec4", "#7873f5", "#3cd3ff", "#ffffff", "#ffffff", "aurora"),
    "neon":     ("#05010d", "#ff2fd6", "#00f0ff", "#7a2bff", "#f6edff", "#ff2fd6", "grid"),
    "ocean":    ("#041b26", "#0090b3", "#00c9a7", "#0b4f9c", "#e8fbff", "#3fd1e6", "waves"),
    "forest":   ("#0b170f", "#2f8f4e", "#9bc53d", "#16695a", "#eefaf1", "#5fd68a", "particles"),
    "sunset":   ("#1f0d18", "#ff5f6d", "#ffc371", "#b0306a", "#fff1f6", "#ff8a5c", "waves"),
    "rose":     ("#fff5f7", "#ffc2d1", "#ffe0c2", "#e7c6ff", "#3a0f1e", "#e8436f", "aurora"),
    "sand":     ("#f6f0e6", "#f0d3a8", "#e8b98a", "#d9cbb0", "#2d2418", "#b5652b", "waves"),
    "minimal":  ("#ffffff", "#eeeeee", "#f5f5f5", "#e8e8e8", "#111111", "#111111", "none"),
    "terminal": ("#030a04", "#0f5a1d", "#1f8a35", "#0a3a14", "#b8ffb8", "#39ff6a", "grid"),
}
# font key -> (Google Fonts family query or None, CSS font stack)
FONT_STACKS = {
    "inter": ("Inter:wght@400;600;800", '"Inter",system-ui,sans-serif'),
    "poppins": ("Poppins:wght@400;600;800", '"Poppins",system-ui,sans-serif'),
    "space-grotesk": ("Space+Grotesk:wght@400;600;700", '"Space Grotesk",system-ui,sans-serif'),
    "outfit": ("Outfit:wght@400;600;800", '"Outfit",system-ui,sans-serif'),
    "playfair": ("Playfair+Display:wght@400;600;800", '"Playfair Display",Georgia,serif'),
    "jetbrains-mono": ("JetBrains+Mono:wght@400;600;800", '"JetBrains Mono",ui-monospace,monospace'),
    "nunito": ("Nunito:wght@400;600;800", '"Nunito",system-ui,sans-serif'),
    "system": (None, 'system-ui,-apple-system,"Segoe UI",Roboto,sans-serif'),
}
OPTIONS = {
    "buttons": ["rounded", "pill", "square", "outline", "glass", "brutal"],
    "layout": ["list", "grid"],
    "avatar": ["circle", "rounded", "square"],
    "effect": ["auto", "aurora", "grid", "particles", "waves", "none"],
    "animation": ["rise", "fade", "pop", "slide", "none"],
}
HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
USERNAME_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,28}[a-z0-9])$")
RESERVED = {
    "admin", "api", "app", "assets", "static", "avatars", "about", "help", "login", "create",
    "signup", "register", "settings", "sitemap", "robots", "index", "404", "www", "themes",
    "mail", "blog", "docs", "terms", "privacy", "contact", "support", "new", "join", "feed",
}
ALLOWED_SCHEMES = {"https", "http", "mailto", "tel"}
LIMITS = {"bio": 200, "about": 1200, "name": 80, "headline": 100, "title": 120,
          "description": 160, "socials": 12, "sections": 15, "links": 200}


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


def _choice(style: dict, key: str, allowed, default, where: str):
    val = style.get(key) or default
    if val not in allowed:
        raise ProfileError(f"{where}: style.{key} must be one of {list(allowed)} (got {val!r})")
    return val


def parse_style(data: dict, where: str) -> dict:
    style = data.get("style") or {}
    if not isinstance(style, dict):
        raise ProfileError(f"{where}: style must be a mapping")
    if data.get("theme") and "theme" not in style:  # backwards compatible top-level theme
        style["theme"] = data["theme"]
    s = {
        "theme": _choice(style, "theme", THEMES, "", where) if style.get("theme") else "",
        "font": _choice(style, "font", FONT_STACKS, "inter", where),
        **{k: _choice(style, k, v, v[0], where) for k, v in OPTIONS.items()},
    }
    accent = str(style.get("accent") or "").strip()
    if accent and not HEX_RE.match(accent):
        raise ProfileError(f"{where}: style.accent must be a hex colour like #ff5c8a")
    s["accent"] = accent
    grad = style.get("gradient") or []
    if grad and (not isinstance(grad, list) or not 2 <= len(grad) <= 4
                 or not all(HEX_RE.match(str(c)) for c in grad)):
        raise ProfileError(f"{where}: style.gradient must be a list of 2-4 hex colours")
    s["gradient"] = [str(c) for c in grad]
    bgi = str(style.get("background_image") or "").strip()
    if bgi and urlparse(bgi).scheme != "https":
        raise ProfileError(f"{where}: style.background_image must be an https URL")
    if any(c in bgi for c in "\"'()\\ ;"):
        raise ProfileError(f"{where}: style.background_image contains invalid characters")
    s["background_image"] = bgi
    return s


def load_profile(path: Path) -> dict:
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
        "verified": bool(data.get("verified", False)),
        "keywords": [str(k).strip() for k in (data.get("keywords") or []) if str(k).strip()][:15],
        "style": parse_style(data, where),
    }
    if not p["name"]:
        raise ProfileError(f"{where}: name is required")

    wf = data.get("works_for") or {}
    p["works_for"] = None
    if isinstance(wf, dict) and wf.get("name"):
        p["works_for"] = {"name": _text(wf["name"], "name", where),
                          "url": _url(wf["url"], f"{where} works_for") if wf.get("url") else ""}

    avatar = str(data.get("avatar") or "").strip()
    if avatar.startswith("avatars/"):
        if not (ROOT / avatar).is_file():
            raise ProfileError(f"{where}: avatar file {avatar} not found")
    elif avatar and urlparse(avatar).scheme != "https":
        raise ProfileError(f"{where}: avatar must be an https URL or avatars/<file>")
    p["avatar"] = avatar

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
    return "#0b0b14" if 0.2126 * lum(r) + 0.7152 * lum(g) + 0.0722 * lum(b) > 0.4 else "#ffffff"


def resolve_style(style: dict, cfg: dict) -> dict:
    theme = style["theme"] or cfg.get("default_theme", "aurora")
    effect = THEMES[theme][6] if style["effect"] == "auto" else style["effect"]
    css_vars = []
    if style["accent"]:
        css_vars += [f"--accent:{style['accent']}", f"--accent-text:{contrast_text(style['accent'])}"]
    if style["gradient"]:
        css_vars.append(f"--page-bg:linear-gradient(160deg,{','.join(style['gradient'])})")
    if style["background_image"]:
        css_vars.append(f"--bg-img:url({style['background_image']})")
    gfont, stack = FONT_STACKS[style["font"]]
    if not (theme == "terminal" and style["font"] == "inter"):
        css_vars.append(f"--font:{stack}")
    elif theme == "terminal":
        gfont = FONT_STACKS["jetbrains-mono"][0]
    return {**style, "theme": theme, "effect": effect, "css": ";".join(css_vars),
            "font_url": f"https://fonts.googleapis.com/css2?family={gfont}&display=swap" if gfont else ""}


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
    CACHE.mkdir(exist_ok=True)
    cached = CACHE / (hashlib.sha1(url.encode()).hexdigest() + ".img")
    try:
        if not cached.exists():
            req = urllib.request.Request(url, headers={"User-Agent": "Tapvio-build/1.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                cached.write_bytes(resp.read(5_000_000))
        return Image.open(io.BytesIO(cached.read_bytes())).convert("RGB")
    except Exception as exc:  # network blocked, 404, not an image...
        print(f"  ! avatar not loaded for OG image ({exc.__class__.__name__}): {url}")
        return None


def render_og(p: dict, theme: str, accent: str, avatar_src: str, out: Path, site: str) -> bool:
    try:
        from PIL import Image, ImageDraw, ImageFilter, ImageFont
    except ImportError:
        return False
    bg, c1, c2, c3, text, t_accent, _ = THEMES[theme]
    accent = accent or t_accent
    W, H = 1200, 630
    img = Image.new("RGB", (W, H), bg)
    glow = Image.new("RGB", (W, H), bg)
    d = ImageDraw.Draw(glow)
    d.ellipse((-200, -260, 560, 420), fill=c1)
    d.ellipse((760, 140, 1400, 820), fill=c2)
    d.ellipse((300, 420, 900, 980), fill=c3)
    img = Image.blend(img, glow.filter(ImageFilter.GaussianBlur(140)), 0.55)
    draw = ImageDraw.Draw(img)

    def font(bold: bool, size: int):
        f = FONTS / ("Inter-Bold.otf" if bold else "Inter-Regular.otf")
        try:
            return ImageFont.truetype(str(f), size)
        except OSError:
            return ImageFont.load_default(size)

    # avatar
    size, ax, ay = 300, 90, (H - 300) // 2
    ring = Image.new("L", (size + 16, size + 16), 0)
    ImageDraw.Draw(ring).ellipse((0, 0, size + 15, size + 15), fill=255)
    img.paste(Image.new("RGB", ring.size, accent), (ax - 8, ay - 8), ring)
    avatar = _fetch_image(avatar_src) if avatar_src else None
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size - 1, size - 1), fill=255)
    if avatar:
        w, h = avatar.size
        side = min(w, h)
        avatar = avatar.crop(((w - side) // 2, (h - side) // 2, (w + side) // 2, (h + side) // 2))
        img.paste(avatar.resize((size, size), Image.LANCZOS), (ax, ay), mask)
    else:
        tile = Image.new("RGB", (size, size), bg)
        td = ImageDraw.Draw(tile)
        td.text((size / 2, size / 2), p["name"][:1].upper(), font=font(True, 150), fill=text, anchor="mm")
        img.paste(tile, (ax, ay), mask)

    # text block with simple word wrap
    x, maxw = ax + size + 70, W - (ax + size + 70) - 70

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

    name_f, sub_f, small_f = font(True, 66), font(False, 34), font(True, 28)
    name_lines = wrap(p["name"], name_f, 2)
    sub_lines = wrap(p["headline"] or p["bio"], sub_f, 3) if (p["headline"] or p["bio"]) else []
    block = len(name_lines) * 78 + (24 + len(sub_lines) * 46 if sub_lines else 0)
    y = (H - block) // 2 - 20
    for line in name_lines:
        draw.text((x, y), line, font=name_f, fill=text)
        y += 78
    y += 24
    for line in sub_lines:
        draw.text((x, y), line, font=sub_f, fill=text)
        y += 46
    label = f"{site}/{p['username']}"
    for sz in range(28, 15, -2):  # shrink long URLs until they fit
        small_f = font(True, sz)
        if draw.textlength(label, font=small_f) + 34 <= W - x - 40:
            break
    draw.rounded_rectangle((x - 2, H - 112, x + draw.textlength(label, font=small_f) + 34, H - 62),
                           radius=25, fill=accent)
    draw.text((x + 16, H - 87), label, font=small_f, fill=contrast_text(accent), anchor="lm")
    img.save(out, "PNG", optimize=True)
    return True


# ---------------------------------------------------------------- build
def build(cfg: dict, profiles: list[dict], og_images: bool = True) -> None:
    site_url = cfg["site_url"] = cfg["site_url"].rstrip("/")
    cfg["repo_url"] = f"https://github.com/{cfg['repo']}"
    host_path = site_url.split("://", 1)[-1]
    env = Environment(loader=FileSystemLoader(TEMPLATES), autoescape=select_autoescape(["html", "xml"]),
                      trim_blocks=True, lstrip_blocks=True)
    env.filters["domain"] = domain_of
    css = (STATIC / "style.css").read_text(encoding="utf-8")
    today = dt.date.today().isoformat()

    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir()
    if AVATARS.is_dir():
        shutil.copytree(AVATARS, DIST / "avatars")
    for f in STATIC.iterdir():
        if f.name != "style.css":
            shutil.copy(f, DIST / f.name)

    common = {"cfg": cfg, "css": css, "year": dt.date.today().year}
    sitemap = [{"loc": site_url + "/", "lastmod": today, "images": []},
               {"loc": site_url + "/create/", "lastmod": today, "images": []}]

    for p in profiles:
        page_url = f"{site_url}/{p['username']}/"
        avatar_url = f"{site_url}/{p['avatar']}" if p["avatar"].startswith("avatars/") else p["avatar"]
        modified = last_modified(PROFILES / f"{p['username']}.yml")
        style = resolve_style(p["style"], cfg)
        for s in p["sections"]:
            for l in s["links"]:
                l["rel"] = link_rel(l["url"], p["verified"])
        for s in p["socials"]:
            s["rel"] = link_rel(s["url"], p["verified"])
        out = DIST / p["username"]
        out.mkdir()
        avatar_local = str(ROOT / p["avatar"]) if p["avatar"].startswith("avatars/") else p["avatar"]
        og_url = ""
        if og_images and render_og(p, style["theme"], style["accent"], avatar_local, out / "og.png", host_path):
            og_url = page_url + "og.png"
        p["og_url"], p["modified"], p["page_url"], p["avatar_url"] = og_url, modified, page_url, avatar_url

        title = p["name"] + (f" - {p['headline']}" if p["headline"] else "") + f" | {cfg['site_name']}"
        description = p["bio"] or p["about"][:155] or f"All links for {p['name']} in one place."
        (out / "index.html").write_text(env.get_template("profile.html").render(
            **common, p=p, s=style, page_url=page_url, avatar_url=avatar_url, title=title,
            description=description, modified=modified, og_image=og_url or avatar_url,
            json_ld=json_ld(p, cfg, page_url, avatar_url, modified, og_url)), encoding="utf-8")
        sitemap.append({"loc": page_url, "lastmod": modified,
                        "images": [i for i in (og_url, avatar_url) if i.startswith("http")]})

    home_style = resolve_style({**parse_style({}, "config"), "theme": cfg.get("default_theme", "aurora")}, cfg)
    # The builder nests a live preview inside the page, so the outer page must not set
    # layout/button/avatar/effect attributes that would leak into the preview.
    builder_style = {**home_style, "effect": "none", "buttons": "", "layout": "", "avatar": "", "animation": "fade",
                     "css": "--page-bg:radial-gradient(1200px 700px at 20% -10%,#1d1846,transparent),radial-gradient(900px 600px at 100% 0%,#0b2a44,transparent),#080a1a"}
    ordered = sorted(profiles, key=lambda x: x["name"].lower())
    builder_data = {
        "themes": {k: {"bg": v[0], "c1": v[1], "c2": v[2], "accent": v[5], "text": v[4], "effect": v[6]}
                   for k, v in THEMES.items()},
        "fonts": {k: {"url": f"https://fonts.googleapis.com/css2?family={g}&display=swap" if g else "",
                      "stack": st} for k, (g, st) in FONT_STACKS.items()},
        "options": OPTIONS, "reserved": sorted(RESERVED), "taken": [p["username"] for p in profiles],
        "repo": cfg["repo"], "branch": cfg.get("branch", "main"), "site_url": site_url,
        "limits": LIMITS,
    }
    pages = {
        "index.html": ("index.html", {"profiles": ordered, "page_url": site_url + "/", "themes": THEMES}),
        "404.html": ("404.html", {}),
        "create/index.html": ("create.html", {"page_url": site_url + "/create/", "s": builder_style,
                                              "builder": json.dumps(builder_data).replace("</", "<\\/")}),
    }
    for target, (tpl, ctx) in pages.items():
        (DIST / target).parent.mkdir(parents=True, exist_ok=True)
        (DIST / target).write_text(env.get_template(tpl).render(**{**common, "s": home_style, **ctx}), encoding="utf-8")

    (DIST / "sitemap.xml").write_text(env.get_template("sitemap.xml").render(urls=sitemap), encoding="utf-8")
    (DIST / "feed.xml").write_text(env.get_template("feed.xml").render(
        cfg=cfg, updated=max([p["modified"] for p in profiles] + ["2026-01-01"]),
        profiles=sorted(profiles, key=lambda x: x["modified"], reverse=True)[:50]), encoding="utf-8")
    (DIST / "llms.txt").write_text(env.get_template("llms.txt").render(cfg=cfg, profiles=ordered), encoding="utf-8")
    (DIST / "robots.txt").write_text(f"User-agent: *\nAllow: /\n\nSitemap: {site_url}/sitemap.xml\n", encoding="utf-8")
    if cfg.get("indexnow_key"):
        (DIST / f"{cfg['indexnow_key']}.txt").write_text(cfg["indexnow_key"])
    (DIST / ".nojekyll").write_text("")
    if cfg.get("custom_domain"):
        (DIST / "CNAME").write_text(cfg["custom_domain"].strip() + "\n")
    (DIST / "urls.txt").write_text("\n".join(u["loc"] for u in sitemap) + "\n")  # used by IndexNow ping
    print(f"Built {len(profiles)} profile(s) into {DIST.relative_to(ROOT)}/")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="validate profiles without building")
    ap.add_argument("--no-og", action="store_true", help="skip Open Graph image generation")
    args = ap.parse_args()
    cfg = yaml.safe_load((ROOT / "config.yml").read_text(encoding="utf-8"))
    profiles = load_all()
    if args.check:
        print(f"All {len(profiles)} profile(s) are valid.")
        return
    build(cfg, profiles, og_images=not args.no_og)


if __name__ == "__main__":
    main()
