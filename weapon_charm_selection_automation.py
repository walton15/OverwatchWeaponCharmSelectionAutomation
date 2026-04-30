#!/usr/bin/env python3
"""
weapon_charm_selection_automation.py

Single-hero weapon charm favoriter. Scans a narrow vertical strip at the star
column and clicks any un-favorited (dark) star found. Presses the down arrow
to advance the game's selection after each check.

HOW TO USE:
    1. Open a hero's Weapon Charms page.
    2. Run this script — the countdown starts immediately.
    3. Tab into Overwatch and position your cursor over the star column
       (anywhere on the column, not necessarily on a star) before the countdown ends.

STOP: Press S or move the mouse to the top-left corner.

REQUIREMENTS:
    pip install pygetwindow mss numpy
"""

import sys
import argparse
import ctypes
import time
import numpy as np
import pygetwindow as gw
import mss

# ── Windows API setup ──────────────────────────────────────────────────────────

user32 = ctypes.windll.user32

class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

VK_DOWN              = 0x28
VK_S                 = 0x53
VK_D                 = 0x44
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP   = 0x0004
KEYEVENTF_KEYUP      = 0x0002

def cursor_pos():
    pt = POINT()
    user32.GetCursorPos(ctypes.byref(pt))
    return pt.x, pt.y

def set_cursor_pos(x, y):
    user32.SetCursorPos(x, y)

def left_click():
    user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    user32.mouse_event(MOUSEEVENTF_LEFTUP,   0, 0, 0, 0)

def press_down():
    user32.keybd_event(VK_DOWN, 0, 0,               0)
    user32.keybd_event(VK_DOWN, 0, KEYEVENTF_KEYUP, 0)

# ── Configuration ──────────────────────────────────────────────────────────────

KEY_PAUSE    = 0.075         # seconds after pressing down before scanning (lower once working)
CLICK_PAUSE  = 0.075        # seconds after clicking
COUNTDOWN    = 7           # seconds to tab into the game

SCAN_HALF_W  = 40          # pixels left/right of cursor X to scan
SCAN_HALF_H  = 20          # pixels above/below cursor Y to scan (just one row height)

# Dark pixel thresholds — unselected stars are near-black.
# Raise MAX_DARK if stars are missed; lower it if non-stars are clicked.
MAX_DARK     = 80          # R, G, and B must all be below this to count as a dark star

# Orange pixel thresholds — selected stars are orange.
# Tune if --click-selected misses or mis-clicks stars.
ORANGE_MIN_R = 150         # R must be above this
ORANGE_MIN_G = 80          # G must be above this
ORANGE_MAX_B = 80          # B must be below this

# Pre-set cursor position (x, y) to snap to after the countdown.
# Set to None to use wherever the cursor already is.
# Run once with START_POS = None and DEBUG = True to find the right position.
START_POS    = (962, 1740)       # e.g. (1843, 612)

# Flags — set via command line, not here:
#   --debug           print scan results each iteration, save strip image, no clicking
#   --click-all       click every row without checking star color
#   --click-selected  click already-selected (orange) stars to deselect them

# ── Helpers ────────────────────────────────────────────────────────────────────

_sct = mss.MSS()

def find_dark_star(bbox):
    """
    Grab a strip of the screen and return the screen (x, y) of the first
    dark (un-favorited) star pixel found, or None if none found.
    """
    region = {"left": bbox[0], "top": bbox[1],
              "width": bbox[2] - bbox[0], "height": bbox[3] - bbox[1]}
    raw = _sct.grab(region)
    # mss returns BGRA — index 2=R, 1=G, 0=B
    arr = np.array(raw)

    dark = (arr[:, :, 2] < MAX_DARK) & \
           (arr[:, :, 1] < MAX_DARK) & \
           (arr[:, :, 0] < MAX_DARK)

    ys, xs = np.where(dark)
    if len(ys) == 0:
        return None

    # Return the topmost dark pixel translated back to screen coordinates.
    return bbox[0] + int(xs[0]), bbox[1] + int(ys[0])


def find_orange_star(bbox):
    """Return screen (x, y) of the first orange (selected) star pixel, or None."""
    region = {"left": bbox[0], "top": bbox[1],
              "width": bbox[2] - bbox[0], "height": bbox[3] - bbox[1]}
    arr = np.array(_sct.grab(region))
    # mss BGRA: index 2=R, 1=G, 0=B
    orange = (arr[:, :, 2] > ORANGE_MIN_R) & \
             (arr[:, :, 1] > ORANGE_MIN_G) & \
             (arr[:, :, 0] < ORANGE_MAX_B)
    ys, xs = np.where(orange)
    if len(ys) == 0:
        return None
    return bbox[0] + int(xs[0]), bbox[1] + int(ys[0])

# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Weapon Charm Selection Automation")
    parser.add_argument("--debug",          action="store_true", help="Print scan info and save strip image. Does not click.")
    parser.add_argument("--click-all",      action="store_true", help="Click every row without checking star color.")
    parser.add_argument("--click-selected", action="store_true", help="Click already-selected (orange) stars to deselect them.")
    args = parser.parse_args()
    debug          = args.debug
    click_all      = args.click_all
    click_selected = args.click_selected

    print("Weapon Charm Selection Automation")
    print("==================================")
    print()
    print("Tab into the game and position your cursor over the star column.")
    print(f"Starting in {COUNTDOWN} seconds ...")
    for i in range(COUNTDOWN, 0, -1):
        print(f"  {i}...")
        time.sleep(1)

    if START_POS is not None:
        set_cursor_pos(*START_POS)
        time.sleep(0.05)

    cx, cy = cursor_pos()
    if debug:
        print(f"Starting cursor position: ({cx}, {cy})  ← paste into START_POS to reuse")
    bbox = (
        max(0, cx - SCAN_HALF_W),
        max(0, cy - SCAN_HALF_H),
        cx + SCAN_HALF_W,
        min(cy + SCAN_HALF_H, 2160),
    )
    print(f"Scanning strip: x={cx}±{SCAN_HALF_W}, y={cy}±{SCAN_HALF_H}")

    wins = gw.getWindowsWithTitle("Overwatch")
    if not wins:
        sys.exit("ERROR: Overwatch window not found.")
    wins[0].activate()
    time.sleep(0.3)

    total = 0
    first_iter = True

    while True:
        # S key or top-left corner = stop
        if user32.GetAsyncKeyState(VK_S) & 0x8000:
            break

        # D key = reset cursor to starting position
        if user32.GetAsyncKeyState(VK_D) & 0x8000 and START_POS is not None:
            set_cursor_pos(*START_POS)
            time.sleep(0.05)
        x, y = cursor_pos()
        if x < 5 and y < 5:
            break

        if debug and first_iter:
            region = {"left": bbox[0], "top": bbox[1],
                      "width": bbox[2] - bbox[0], "height": bbox[3] - bbox[1]}
            shot = _sct.grab(region)
            mss.tools.to_png(shot.rgb, shot.size, output="debug_scan_strip.png")
            print("  Saved debug_scan_strip.png — open it to see exactly what is being scanned.")
            first_iter = False

        if click_all:
            left_click()
            total += 1
        elif debug:
            dark_pos  = find_dark_star(bbox)
            orange_pos = find_orange_star(bbox)
            print(f"  unselected: {dark_pos}  selected: {orange_pos}")
        elif click_selected:
            star_pos = find_orange_star(bbox)
            if star_pos:
                set_cursor_pos(*star_pos)
                left_click()
                total += 1
                time.sleep(CLICK_PAUSE)
        else:
            star_pos = find_dark_star(bbox)
            if star_pos:
                set_cursor_pos(*star_pos)
                left_click()
                total += 1
                time.sleep(CLICK_PAUSE)

        press_down()
        time.sleep(KEY_PAUSE)

    print(f"Done. Favorited {total} charm(s).")


if __name__ == "__main__":
    main()
