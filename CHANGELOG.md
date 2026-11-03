# Changelog

All notable changes to Tapvio are listed here. Versions follow [Semantic Versioning](https://semver.org/).

## [1.0.0] - 2026-11-03

The first public release of Tapvio: free, open-source link-in-bio pages that search engines can index.

### Themes
- Nine themes, each with its own typography and layout: **Résumé**, **Business card**, **Tiles**, **Studio**, **Contents**, **Terminal**, **Desktop 95**, **Bold** and **Cover**.
- Light, dark and automatic modes for Résumé, Tiles, Contents and Cover.
- Options for accent colour, ten font choices, cover image, photo shape and website icons.

### Pages
- **Save contact** button: a vCard is generated from email, phone and WhatsApp links.
- A share image (1200 × 630) for every page, in the theme's colours.
- Share button, link search on pages with more than 12 links, keyboard navigation and reduced-motion support.
- About 5–8 KB per page, compressed.

### SEO
- Static HTML with a canonical URL, title and description on every page.
- JSON-LD structured data: `ProfilePage`, `Person` with `sameAs`, `BreadcrumbList`, `WebSite`, `SoftwareApplication` and `HowTo`.
- `sitemap.xml` with image entries, `robots.txt`, an Atom feed and `llms.txt`.
- IndexNow ping after every deploy, so Bing and other search engines are notified.

### Site
- New homepage with a live theme preview, comparison table and directory.
- Visual builder with a live phone preview that publishes through a GitHub pull request.
- User guide at `/guide/`, generated from `GUIDE.md`.
- New logo, icon, favicon and social preview image.

### Developers
- Profile validation in CI with clear error messages on pull requests.
- `TAPVIO_SITE_URL` override for local previews.
- Themes from the first preview (`aurora`, `midnight` and others) map to their closest new theme automatically.

## [0.2.0] - 2026-11-03
### Changed
- Renamed the project from Linkora to Tapvio.
- Documented the free `tapvio.is-a.dev` custom domain.

## [0.1.0] - 2026-11-03
### Added
- First preview: static link-in-bio generator with a profile builder, SEO markup and GitHub Pages deployment.

[1.0.0]: https://github.com/mafzalkalwardev/tapvio/releases/tag/v1.0.0
[0.2.0]: https://github.com/mafzalkalwardev/tapvio/compare/7aa88c0...bf75115
[0.1.0]: https://github.com/mafzalkalwardev/tapvio/commit/7aa88c0
