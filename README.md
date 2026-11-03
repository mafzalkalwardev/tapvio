# Tapvio

**A free, open-source link-in-bio platform that search engines can actually index.**
It's an alternative to Linktree with animated themes, deep customization and serious SEO. Each page is static HTML on GitHub Pages: no server, no database, no ads, no tracking, and $0 to run.

**Live:** https://mafzalkalwardev.github.io/tapvio/ · **Create your page:** https://mafzalkalwardev.github.io/tapvio/create/

---

## Features

**Design**
- **12 themes:** aurora, midnight, light, glass, neon, ocean, forest, sunset, rose, sand, minimal, terminal
- **Animated backgrounds:** aurora blobs, moving grid, floating particles, waves, or none
- **Entrance animations:** rise, fade, pop, slide, with staggered link reveal, hover lift and light-sweep effects, a glowing featured link and a rotating avatar ring
- **8 fonts:** Inter, Poppins, Space Grotesk, Outfit, Playfair Display, JetBrains Mono, Nunito, system
- **6 button styles:** rounded, pill, square, outline, glass, brutal (neo-brutalist)
- Custom accent colour, gradient or image backgrounds, list or 2-column grid layout, and circle, rounded or square avatars
- Built-in link search, a share button, and full support for `prefers-reduced-motion` and keyboard navigation

**SEO & indexing**
- Server-rendered HTML with **no `noindex`** (Linktree pages can ship `noindex, nofollow`)
- A unique title, meta description and canonical URL for each page
- **JSON-LD:** `ProfilePage` + `Person` (with `sameAs` linking every profile you own, `worksFor` and `knowsAbout`) + `BreadcrumbList`
- **Auto-generated 1200×630 share image** (Open Graph / Twitter large card) for every profile
- `sitemap.xml` with image entries and real git-based `lastmod` dates, plus `robots.txt`, an Atom `feed.xml` and `llms.txt`
- **IndexNow auto-ping** after every deploy, so Bing, Yandex, Seznam, Naver and Yep learn about new or changed pages within minutes
- A homepage directory with `ItemList` schema that links to every profile, so crawlers find new pages
- Do-follow links for verified profiles; `ugc nofollow` for everyone else (anti-spam)

## Create your page (no coding)

1. Open the **[visual builder](https://mafzalkalwardev.github.io/tapvio/create/)**. Fill in your details, pick a theme and watch the live preview.
2. Click **Publish on GitHub**. GitHub opens with your file pre-filled. Click **Commit changes → Propose changes → Create pull request**.
3. After a maintainer merges it, your page is live at `https://mafzalkalwardev.github.io/tapvio/<username>/`.

Prefer YAML? Copy `profiles/_template.yml` to `profiles/<username>.yml` and open a PR. See [CONTRIBUTING.md](CONTRIBUTING.md).

## Run locally

```bash
pip install -r requirements.txt
python build.py --check          # validate all profiles
python build.py                  # build into dist/  (add --no-og to skip share images)
python -m http.server -d dist 8000
```

## Deploy your own copy

1. Fork or clone this repo, then go to **Settings → Pages → Source → GitHub Actions**.
2. Edit `config.yml`: `site_url`, `repo` and `owner_*`.
3. Push to `main`. The workflow validates, builds, deploys and pings IndexNow.

## Free custom domain: `tapvio.is-a.dev`

[is-a.dev](https://is-a.dev) gives free subdomains to developer projects through a GitHub pull request.

1. Make sure the site is live on GitHub Pages first, because the is-a.dev reviewers check it.
2. Open a pull request to [is-a-dev/register](https://github.com/is-a-dev/register) that adds `domains/tapvio.json`:
   ```json
   {
     "owner": { "username": "mafzalkalwardev" },
     "records": { "CNAME": "mafzalkalwardev.github.io" }
   }
   ```
   In the PR description, say it's an open-source, free link-in-bio generator and link this repo and the live site.
3. After it's merged, go to **Settings → Pages → Custom domain**, enter `tapvio.is-a.dev`, save, and tick **Enforce HTTPS**.
4. In `config.yml`, set `site_url: "https://tapvio.is-a.dev"` and `custom_domain: "tapvio.is-a.dev"`, then push. Canonical URLs, the sitemap and share images all switch to the new domain, and the old github.io address redirects to it automatically.

**Any other domain:** set `site_url` and `custom_domain` to it. At your DNS provider, add `CNAME <sub> → <user>.github.io` (or GitHub's A records for an apex domain), then enter the domain under Settings → Pages.

## Getting indexed by Google

Google has no instant-ping API for normal pages, so do this once:

1. **[Google Search Console](https://search.google.com/search-console)** → Add property → **URL prefix** → `https://mafzalkalwardev.github.io/tapvio/`
2. Choose **HTML tag** verification, copy the `content="…"` value into `config.yml` → `google_site_verification`, push, then click Verify.
3. **Sitemaps** → submit `sitemap.xml`.
4. **URL Inspection** → paste your profile URL → **Request indexing**.
5. **[Bing Webmaster Tools](https://www.bing.com/webmasters)** → Import from Google Search Console (one click). IndexNow keeps Bing updated from then on.
6. Link to your page from places Google already crawls: your GitHub profile README, your portfolio, the LinkedIn "Website" field, your Dev.to / Medium / Hashnode bios, and your Upwork profile. Backlinks are the fastest way to get a new page discovered.

## Project layout

```
config.yml              site name, URL, repo, verification tokens, IndexNow key
profiles/*.yml          one file per user (files starting with _ are ignored)
avatars/                optional local avatar images
templates/              Jinja2: profile, directory, builder (create), 404, sitemap, feed, llms.txt
static/                 CSS (inlined into pages) + favicon
fonts/                  Inter (OFL), used to render share images
build.py                validator + static site generator + OG image renderer
scripts/indexnow.py     IndexNow ping (run by CI after deploy)
.github/workflows/      validate PRs; build, deploy and ping on main
```

## Moderation

Maintainers review every pull request before it goes live. Set `verified: true` only for trusted people, because it gives their links do-follow status. To remove a page, delete its file.

## License

MIT © INDUS Web Agency. The Inter font is © Rasmus Andersson, SIL OFL 1.1.
