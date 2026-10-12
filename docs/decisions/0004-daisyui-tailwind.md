# 0004 - Tailwind CSS and DaisyUI for the interface

Status: Accepted

## Context
The interface used one block of hand-written CSS in `base.html`. It was hard to
extend and had no shared components. The project must stay self-hosted, so no
CDN link and no Node.js in the runtime image.

## Decision
- Use Tailwind CSS 4 with the DaisyUI 5 plugin. DaisyUI 5 needs Tailwind 4 and the CSS-first `@plugin` setup.
- Build the CSS in a `css` stage of the `Dockerfile`. The stage uses the Tailwind standalone CLI (v4.3.3). It needs no Node.js.
- Fetch the CLI and `daisyui.js` (v5.7.47) at build time from their GitHub releases. Both downloads are pinned by SHA-256.
- Keep the source in `app/frontend/app.css`. The build writes `app/static/css/app.css`. That file is gitignored and is not committed.
- The runtime stage copies the built file, then `collectstatic` publishes it. WhiteNoise serves it.
- Use two DaisyUI themes: `light` and `dark`. The browser setting `prefers-color-scheme` picks one.

## Consequences
- The page makes no outside requests. The image builds without Node.js.
- The first build needs network access to GitHub. Later builds use the Docker cache.
- To change a version, edit the URL and checksum in the `Dockerfile`.
- The dev and test image does not build CSS. Tests do not need it.
- A local run outside Docker has no `app.css` until you build it. Run the `css` stage or the `tailwindcss` CLI by hand.
- DaisyUI adds about 440 KB of CSS (about 52 KB compressed). Tailwind removes unused utility classes, but DaisyUI components stay.
