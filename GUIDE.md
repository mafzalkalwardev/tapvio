# How to use Tapvio

Tapvio gives you a free link-in-bio page: one address that lists your website, profiles, shop and anything else you want people to find. Unlike most link-in-bio apps, your Tapvio page is a real web page that search engines can index, so it can appear when someone searches your name.

This guide covers creating your page, choosing a theme, editing it later, and getting it into Google.

## How Tapvio works

Tapvio has no database and no accounts. Each page is one small text file in a public GitHub repository:

1. Your details and links live in a file called `profiles/your-username.yml`.
2. When the file is added or changed, GitHub runs Tapvio's build script. It checks the file, turns it into a fast HTML page, makes a share image and a contact card, and updates the sitemap.
3. GitHub Pages publishes the result. Bing, Yandex and other IndexNow search engines are told about the new page automatically.

Because everything goes through GitHub, every change is reviewed before it goes live, and you can see the full history of your page.

## Create your page {#create}

You'll need a free [GitHub account](https://github.com/signup). That's the only sign-up.

1. Open the [builder](../create/).
2. Choose a **username**. It becomes your address, for example `tapvio.is-a.dev/ali-khan/`. Use 2 to 30 lowercase letters, numbers or hyphens.
3. Fill in your **name**, **what you do** and a **short bio**. The **About** box is optional, but a few sentences there help search engines understand your page.
4. Add a **photo**. Any image address that starts with `https://` works. If you have a GitHub account, click **Use my GitHub photo**.
5. Add your main **profiles** (LinkedIn, GitHub, Instagram, email). Then add **links** in sections such as "Work with me" or "Articles". Tick **Feature** to highlight your most important link.
6. Pick a **theme** and adjust the options. The preview on the right shows exactly what visitors will see.

Your draft is saved in your browser, so you can close the tab and come back.

## Publish it {#publish}

1. In the builder, click **Publish on GitHub**.
2. GitHub opens a new file with your page already filled in. If you're asked to fork the repository, click **Fork this repository**. This makes your own copy so you can suggest the change.
3. Click **Commit changes**, then **Propose changes**, then **Create pull request**.
4. An automatic check runs on your pull request. If it finds a problem, such as an address that doesn't start with `https://`, the error message says which line to fix.
5. A maintainer reviews and merges your pull request. About a minute later your page is live.

## Edit your page later {#edit}

Open the builder, fill it in again (or load your saved draft), and click **Publish on GitHub**. Because your username already exists, Tapvio copies your new file and opens your existing file on GitHub for editing. Select everything in the editor, paste, and propose the change.

You can also edit `profiles/your-username.yml` directly on GitHub.

## Themes {#themes}

Each theme has its own layout and fonts, not just different colours. You can try them all on the homepage.

| Theme | Best for | Light and dark |
| --- | --- | --- |
| Résumé | Freelancers and job seekers. Set like a CV, with section names in a left column. | Yes |
| Business card | Consultants and agencies. A printed card with a Save contact button. | No |
| Tiles | Creators with many links. A grid of tinted tiles, featured links are wider. | Yes |
| Studio | Designers and studios. Your name set very large, links as big lines of type. | No (dark) |
| Contents | Writers and academics. A book's table of contents with dotted leaders. | Yes |
| Terminal | Developers. An Ubuntu terminal, links listed like files. | No (dark) |
| Desktop 95 | Anyone who misses Windows 95. A window with bevelled buttons. | No |
| Bold | Shops and creators. Thick borders and hard shadows on yellow. | No |
| Cover | Photographers and artists. A full-width photo banner. | Yes |

### Options

| Option | What it does |
| --- | --- |
| Light or dark | Auto follows the visitor's device setting. Only some themes have both. |
| Accent colour | Replaces the theme's highlight colour with yours. |
| Font | Keeps the theme's font, or replaces it with one of ten others. |
| Photo shape | Circle, rounded or square. |
| Website icons | Shows each site's icon next to its link. Turn off for a plainer look. |
| Cover image | A banner photo, used by the Cover theme. |

## Features on every page {#features}

- **Save contact**: if you add an email (`mailto:`), phone (`tel:`) or WhatsApp (`wa.me`) link, visitors can add you to their phone contacts in one tap.
- **Share**: opens the phone's share menu, or copies your link on a computer.
- **Search**: pages with more than 12 links get a search box.
- **Share image**: a 1200 × 630 image with your photo and name, used when your link is posted on LinkedIn, X, WhatsApp or Slack.
- **Fast loading**: pages are plain HTML and CSS, with no app framework.

## Getting found on Google {#seo}

Every Tapvio page includes what search engines look for: a clear title and description, a canonical address, structured data (schema.org `ProfilePage` and `Person`, with a `sameAs` list linking every profile you own), a sitemap entry and a share image.

To help Google find and rank your page sooner:

1. **Write a real About paragraph.** Mention your name, what you do and where you're based, in plain sentences.
2. **Link to your Tapvio page from places Google already visits**: your GitHub profile README, your LinkedIn "Website" field, your Upwork, Fiverr or Dev.to profile, and your email signature.
3. **Use the same name everywhere.** The `sameAs` data works best when your profiles use the same name as your Tapvio page.
4. **Give it time.** New pages usually appear in Google within a few days to a few weeks.

Site owners can also add the site to [Google Search Console](https://search.google.com/search-console), submit `sitemap.xml` and request indexing for individual pages. The README explains how.

## Rules {#rules}

- One page per person or brand. Don't use someone else's name or brand.
- Only link to things you own or represent. No spam, scams, adult content or illegal content.
- Maintainers can decline or remove any page.

## Questions {#faq}

<details><summary>Is Tapvio really free?</summary>

Yes. There's no paid plan. Hosting is free on GitHub Pages, and the code is open source under the MIT license.
</details>

<details><summary>Do I need to know how to code?</summary>

No. The builder writes the file for you. You only need to click through GitHub's pull request screens once.
</details>

<details><summary>Can I use my own domain?</summary>

Pages live on the Tapvio domain. If you want your own domain, you can fork the repository and run your own copy of Tapvio. It's free, and the README explains how.
</details>

<details><summary>How do I delete my page?</summary>

Open a pull request that deletes `profiles/your-username.yml`, or open an issue on GitHub asking a maintainer to remove it.
</details>

<details><summary>Does Tapvio track visitors?</summary>

No. There are no analytics, cookies or ads. Website icons are loaded from DuckDuckGo's icon service, and fonts from Google Fonts.
</details>
