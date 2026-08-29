# OpenFlipbook source mirror

The files in this directory are copied from OpenFlipbook commit `b3e5044` and
used directly by QianScope's `/play` world surface.

Upstream: <https://github.com/eren23/openflipbook>

The mirror includes the upstream world/scene types, numeric geometry and click
routing, map projection/layout, breadcrumb and spatial-path navigation, branch
beacons, enterable markers, two-image morphing, click feedback, entity overlay,
and the interactive `WorldMap` page atlas. Only import paths, QianScope Agent
types, balanced cobalt/coral presentation classes, and product-facing Chinese
copy are adapted.

`frontend/components/openflipbook-play-world.tsx` is QianScope's Guiyang page
orchestrator. It follows the upstream `/play` page graph and image-is-interface
sequence while connecting QianScope locations, floors, Agents, search, persona
panels, and simulation tools. Guiyang node geometry and image-page data live in
`frontend/lib/openflipbook-world.ts`.

The source layout mirrors upstream `apps/web/{config,components/PlayPage,hooks,lib}`
so future upstream updates can be reviewed as ordinary file diffs.

License: MIT. See `frontend/THIRD_PARTY_NOTICES.md`.
