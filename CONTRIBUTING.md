# Contributing to Tapvio

Issues and pull requests are welcome. You can add your own page, or change the generator, the themes and the docs.

## Adding your page

1. Easiest: use the visual builder at https://mafzalkalwardev.github.io/tapvio/create/ and click **Publish on GitHub**.
   Or fork the repo and copy `profiles/_template.yml` to `profiles/<username>.yml`.
2. Fill in your details. You can run `python build.py --check` locally to validate.
3. Open a pull request titled `Add <username>`.

### Guidelines

- One profile per person or brand. Your username must not impersonate someone else.
- Only real links you own or represent. No spam, phishing, adult, gambling or illegal content.
- Don't add `verified: true` yourself. Maintainers set it.
- An avatar can be any `https://` image (for example `https://github.com/<you>.png`) or a square JPG/PNG under 200 KB committed to `avatars/<username>.jpg`.
- To edit your page later, open another PR that changes your file.

Maintainers may decline or remove any profile.

## Changing the code

CI runs on Python 3.12. Use that version locally.

```bash
pip install -r requirements.txt
python build.py --check
TAPVIO_SITE_URL=http://localhost:8000 python build.py --no-og
python -m http.server -d dist 8000
```

Open http://localhost:8000/. `--no-og` skips share-image rendering. `TAPVIO_SITE_URL` points the generated links at your local server.

| Change | Where to look |
| --- | --- |
| Validation, HTML, share images, vCards, sitemap | `build.py` |
| Page markup | `templates/` |
| Theme CSS | `static/profile/themes/<name>.css` (register it in `THEMES` in `build.py`; see the README) |
| Homepage, builder and guide styles | `static/site.css` |
| The published guide | `GUIDE.md` (rendered at `/guide/`) |
| IndexNow ping after deploy | `scripts/indexnow.py` |
| Site name, URL, repo, verification tokens | `config.yml` |

For a code change, describe what you changed and how you checked it. The checklist in the pull request template is for new profile pages; leave it blank when it does not apply.

GitHub Actions runs `python build.py --check` and a full build on every pull request. A maintainer merges it.

## Code of Conduct

This project follows [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
