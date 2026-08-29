# Third-party notices

## OpenFlipbook

`frontend/vendor/openflipbook/` contains source files copied directly from
OpenFlipbook commit `b3e5044`. The Guiyang scene adapter imports and executes
those files for image-as-interface navigation, click ripple, descent-video
playback, crosshair, markers and entity overlays. Only import paths,
product-facing Chinese copy and the pre-generated clip adapter were adapted.

MIT License

Copyright (c) 2026 Eren Akbulut

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

## LTX-Video generated media

The 28 MP4 files under
`frontend/public/openflipbook/guiyang/transitions/` were generated locally with
Lightricks `ltxv-2b-0.9.8-distilled`. Model weights and inference code are not
redistributed by this repository. Generation provenance and settings are
documented in `docs/OPENFLIPBOOK_SCENE_TRANSITIONS.md`.

Model and license: <https://huggingface.co/Lightricks/LTX-Video>
