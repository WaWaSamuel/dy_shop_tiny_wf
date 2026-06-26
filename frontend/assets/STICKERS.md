## Sticker Asset Catalog

This folder is now organized by visual content instead of numeric ids.

### Structure

- `wallpapers/`
  - Full-page background wallpaper assets.
- `stickers/food/`
  - Bakery, food, dining, snack, mascot-with-food stickers.
- `stickers/letters/`
  - Alphabet character stickers.
- `stickers/pennants/`
  - Flag, pennant, badge-banner style character stickers.
- `stickers/window/`
  - Window-frame, snow-dome, pop-up frame stickers.
- `stickers/work/`
  - Clipboard, apron, officer, work/task themed stickers.
- `stickers/group/`
  - Duo, trio, crowd, group-badge stickers.
- `stickers/reaction/`
  - Expression, speech, motion, pause/retry, emotional reaction stickers.
- `stickers/cards/`
  - Card, panel, frame, collage, tag, poster-like stickers.

### UI Usage Convention

- Navigation: prefer `work/`, `cards/`, `pennants/`
- Metrics / dashboard: prefer `work/`, `group/`, `cards/`
- Actions: prefer `reaction/`, `work/`, `cards/`
- Status: prefer expressive `reaction/` or clear `food/` single-character badges
- Decorative fillers: prefer `pennants/`, `group/`

### Naming Rule

`<category>/<content>_<index>.png`

Examples:

- `stickers/work/hachiware_clipboard_blue_091.png`
- `stickers/pennants/pennant_hachiware_blue_044.png`
- `stickers/cards/collage_blue_109.png`
