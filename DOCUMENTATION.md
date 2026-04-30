# Overwatch Weapon Charm Automation — Documentation

## What This Project Does

Automates favoriting (or unfavoriting) weapon charms for a hero in Overwatch. Open a hero's Weapon Charms cosmetics page, run the script, and it clicks through the charm list automatically.

The script is run once per hero. There is no automated hero navigation.

## How to Run

```
python weapon_charm_selection_automation.py
```

1. Run the script — the countdown starts immediately
2. Tab into Overwatch during the countdown
3. The cursor snaps to `START_POS` automatically when the countdown ends
4. Script scans for stars and clicks through the list
5. Press **S** to stop when done

## CLI Flags

| Flag | Behavior |
|------|----------|
| *(none)* | Click every unselected (dark) star |
| `--click-selected` | Click every selected (orange) star to deselect |
| `--click-all` | Click every row unconditionally |
| `--debug` | Print scan results and save `debug_scan_strip.png`. Does not click. |

## Hotkeys (during run)

| Key | Action |
|-----|--------|
| S | Stop the script |
| D | Snap cursor back to `START_POS` |

## Configuration

All tunable values are at the top of `weapon_charm_selection_automation.py`:

```python
KEY_PAUSE    = 0.075   # seconds after pressing down arrow before scanning
                       # 0.1 is safe, 0.05 is fast — too low = misses rows
CLICK_PAUSE  = 0.05    # seconds after clicking a star
COUNTDOWN    = 7       # seconds to tab into the game

SCAN_HALF_W  = 40      # pixels left/right of cursor X to scan
SCAN_HALF_H  = 20      # pixels above/below cursor Y (should cover one row)

MAX_DARK     = 80      # unselected star: R, G, and B must all be below this
ORANGE_MIN_R = 150     # selected star: R must be above this
ORANGE_MIN_G = 80      # selected star: G must be above this
ORANGE_MAX_B = 80      # selected star: B must be below this

START_POS    = (962, 1740)  # cursor position after countdown — must be on the star column
```

## How to Set START_POS

1. Set `START_POS = None`
2. Run with `--debug`
3. Tab into Overwatch, hover cursor over the star column before countdown ends
4. Script prints `Starting cursor position: (x, y)` — paste into `START_POS`

## How to Debug Star Detection

1. Run with `--debug`
2. Open `debug_scan_strip.png` to see exactly what region is being scanned
3. Each iteration prints `unselected: (x,y)  selected: (x,y)` — `None` means not detected
4. If stars are missed: raise `MAX_DARK`, adjust `ORANGE_*` thresholds, or fix `START_POS`

## Key Technical Notes

- **PIL ImageGrab does not work** — uses GDI, captures blank image for DirectX games. The script uses `mss` (DXGI) instead.
- **Down arrow does not move the Windows cursor** — it moves the game's internal selection only. The script scans a fixed region rather than reading the pixel under the cursor.
- **mss returns BGRA** — array channel order is `[B, G, R, A]`, not RGB.

## Dependencies

```
pip install pygetwindow mss numpy
```

## User Environment

- OS: Windows 11
- Resolution: 4K (3840×2160)
- HDR: Disabled
- Game: Overwatch, borderless/fullscreen DirectX
