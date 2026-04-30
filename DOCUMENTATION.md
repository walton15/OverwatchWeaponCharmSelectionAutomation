# Overwatch Weapon Charm Automation — Documentation

## What This Project Does

Automates favoriting (or unfavoriting) weapon charms for every hero in Overwatch. The script navigates through the full hero grid automatically — opening each hero's Weapon Charms page, clicking through the charm list, then moving to the next hero.

Progress is saved after each hero. If you stop the script mid-run, it resumes from where it left off on the next run.

## How to Run

```
python weapon_charm_selection_automation.py
```

1. Open Overwatch to the hero grid (Weapon Charms cosmetics section)
2. Navigate to the starting hero and open their Weapon Charms page
3. Run the script — the countdown starts immediately
4. Tab into Overwatch during the countdown with your cursor over the star column
5. The script runs through all heroes automatically
6. Press **S** to stop at any time — progress is saved

## CLI Flags

| Flag | Behavior |
|------|----------|
| *(none)* | Click every unselected (dark) star |
| `--click-selected` | Click every selected (orange) star to deselect |
| `--click-all` | Click every row unconditionally |
| `--debug` | Print scan results and save `debug_scan_strip.png`. Does not click. |
| `--row ROW` | Override starting row (1-indexed). Must be used with `--col`. |
| `--col COL` | Override starting column (1-indexed). Must be used with `--row`. |

## Hotkeys (during run)

| Key | Action |
|-----|--------|
| S | Stop the script (progress is saved) |
| D | Snap cursor back to `START_POS` |

## Progress / Resume

- Progress is saved to `progress.json` before each hero is processed
- On next run the script automatically resumes from the saved hero
- When all heroes complete, `progress.json` is deleted and the next run starts fresh
- Use `--row`/`--col` to override the saved position and start from a specific hero

## Configuration

All tunable values are at the top of `weapon_charm_selection_automation.py`:

```python
# Charm selection
KEY_PAUSE    = 0.075   # seconds after pressing down arrow before scanning
CLICK_PAUSE  = 0.075   # seconds after clicking a star
COUNTDOWN    = 7       # seconds to tab into the game

SCAN_HALF_W  = 40      # pixels left/right of cursor X to scan
SCAN_HALF_H  = 20      # pixels above/below cursor Y (should cover one row)

MAX_DARK     = 80      # unselected star: R, G, and B must all be below this
ORANGE_MIN_R = 150     # selected star: R must be above this
ORANGE_MIN_G = 80      # selected star: G must be above this
ORANGE_MAX_B = 80      # selected star: B must be below this

START_POS    = (962, 1740)  # cursor position after countdown — must be on the star column

# Hero grid navigation
HEROES_PER_ROW          = [30, 21]   # heroes in each row; add/remove entries for more rows
START_ROW               = 0          # default starting row (0-indexed internally)
START_COL               = 0          # default starting column (0-indexed internally)
CHARM_SELECTION_SECONDS = 60         # seconds to spend on each hero's charm page

HERO_NAV_PAUSE          = 0.15       # pause between hero-navigation key presses
MENU_LOAD_PAUSE         = 1.5        # pause after opening hero popup / weapon charms page
ESCAPE_PAUSE            = 0.5        # pause after each Escape press

WEAPON_CHARM_TEMPLATE   = "weapon_charms_template.png"
MATCH_THRESHOLD         = 0.8        # template match confidence threshold (0–1)
```

## How to Set START_POS

1. Set `START_POS = None`
2. Run with `--debug`
3. Tab into Overwatch, hover cursor over the star column before countdown ends
4. Script prints `Starting cursor position: (x, y)` — paste into `START_POS`

## How to Set Up the Weapon Charms Template

The script uses image recognition to click the Weapon Charms button in the hero cosmetics popup.

1. Open any hero's cosmetics popup in Overwatch
2. Take a screenshot and crop tightly around the Weapon Charms button/text
3. Save the crop as `weapon_charms_template.png` in the project folder
4. If the button isn't being found, lower `MATCH_THRESHOLD` (try `0.7`)
5. If it's clicking the wrong thing, raise it toward `0.9`

## How to Debug Star Detection

1. Run with `--debug`
2. Open `debug_scan_strip.png` to see exactly what region is being scanned
3. Each iteration prints `unselected: (x,y)  selected: (x,y)` — `None` means not detected
4. If stars are missed: raise `MAX_DARK`, adjust `ORANGE_*` thresholds, or fix `START_POS`

## Hero Grid Navigation

Heroes are traversed in a snake pattern:
- Even rows (1, 3, …): left → right
- Odd rows (2, 4, …): right → left (the script entered from the right end)

Between rows the script presses Down once, which lands at the correct end of the next row.

To enter a hero's Weapon Charms page: Space opens the cosmetics popup, then the script uses OpenCV template matching to locate and click the Weapon Charms button.

To return to the hero grid: Escape × 2.

## Key Technical Notes

- **PIL ImageGrab does not work** — uses GDI, captures blank image for DirectX games. The script uses `mss` (DXGI) instead.
- **Down arrow does not move the Windows cursor** — it moves the game's internal selection only. The script scans a fixed region rather than reading the pixel under the cursor.
- **mss returns BGRA** — array channel order is `[B, G, R, A]`, not RGB. OpenCV uses BGR, so the alpha channel is dropped before matching.

## Dependencies

```
pip install pygetwindow mss numpy opencv-python
```

## User Environment

- OS: Windows 11
- Resolution: 4K (3840×2160)
- HDR: Disabled
- Game: Overwatch, borderless/fullscreen DirectX
