# ARMADA website

Live at https://armada.stamih.com. UI and publication approved on October 3, 2026.

This is a buildless static page. Preview locally with
`python -m http.server 8768 --bind 127.0.0.1 --directory website` from the repository root.

Deploy only `index.html`, `style.css`, and `assets/` to the website document root.
The other files describe the design and are not public website assets. Keep FTP credentials
outside this repository and use certificate-verified explicit FTPS. Preserve existing remote
files and back up anything replaced; upload the entry page after its dependencies.

The initial deployment verified every upload by SHA-256 and checked the public HTTPS assets
and installer URL. The hosting provider appends its own `wsimg.com/traffic-assets/js/tccl.min.js`
monitoring script to HTML responses; it is not part of this source. Other public assets match
the uploaded files byte for byte.

When adopting a new app release, update the version and installer/release links in `index.html`
together. Brand artwork is supplied by the project owner; font licenses ship in `assets/fonts/`.
