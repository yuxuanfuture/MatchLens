# Third-party notices

MatchLens uses or can optionally install third-party components. This file is a
navigation aid, not a replacement for the upstream license texts.

## Fonts and icons

- Fraunces and Nunito Sans are distributed under the SIL Open Font License. The
  corresponding license files are in `dist/assets/`.
- Phosphor Icons is distributed under its upstream license. A copy is stored at
  `dist/assets/LICENSE-Phosphor.txt`.

## Optional vision dependencies and weights

- Python package versions are enumerated in `requirements-vision.lock` and
  `requirements-vision-windows.lock`; every package remains subject to its
  upstream license.
- The primary football detector and its AGPL-3.0 model-card reference are listed
  in `config/vision-model.json`.
- The optional pitch and ball detector weights are downloaded from the Roboflow
  Sports example sources listed in `config/vision-model.json`. They are not
  distributed in this repository. Review and accept the upstream terms before
  downloading or using them.

The `models/` directory and platform-specific virtual environments are excluded
from Git. `scripts/setup_vision.py` and `scripts/setup_vision_windows.py` download
and verify optional components by checksum.

## Sound recordings

The public source repository does not distribute the finished soundtrack or the
source recordings. The cue plan and attribution links are preserved in
`data/stream-04-audio.json` and `dist/audio/credits.html`.

The local handoff soundtrack was assembled from Mixkit material and Freesound
recordings under the licenses identified in those files. Anyone rebuilding or
redistributing audio must obtain the source recordings lawfully and comply with
the applicable licenses, including attribution requirements.

## Project data and branding

The bundled clubs, players, events, tracking samples, and scores are fictional
synthetic data. The repository does not include Premier League match footage,
official club crests, or an official competition data feed.
