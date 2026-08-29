# OpenFlipbook source mirror

The files in this directory are copied from OpenFlipbook commit `b3e5044` and
used directly by the Guiyang social-world image canvas.

Upstream: <https://github.com/eren23/openflipbook>

Import paths and product-facing Chinese copy are adapted. The descent video
adapter is extracted from the upstream `/play` page's first/last-frame clip
flow so QianScope can play pre-generated clips without waiting for inference.
The source layout otherwise mirrors the upstream
`apps/web/{components/PlayPage,hooks,lib}` layout so future upstream updates
can be reviewed as normal file diffs.

License: MIT. See `frontend/THIRD_PARTY_NOTICES.md`.
