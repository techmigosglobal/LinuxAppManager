# VIN-LinuxManager website

This is a dependency-free static landing page. It can be served directly from
the `website/` directory by GitHub Pages, Cloudflare Pages, Netlify, or any
static web host.

## Local preview

```bash
python3 -m http.server 4173 --directory website
```

Open <http://127.0.0.1:4173> and test the responsive navigation, copy button,
keyboard focus order, and reduced-motion behavior.

## Before public deployment

- Keep the public support address at
  `Vin-Linux-App-Manager@techmigos.com` and the project site at
  `https://techmigos.com`.
- Add the final custom domain, canonical URL, Open Graph image, `robots.txt`,
  and `sitemap.xml` once the domain is chosen.
- Replace “Submission next” store cards with real Flatpak/Snap links after the first
  store submissions are accepted.
- Keep the website’s download links pointed at the exact release assets and
  publish their checksums, detached signatures, public key, and fingerprint.
