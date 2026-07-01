#!/usr/bin/env python3
"""
weapon_charm_selection_automation.py

All-hero weapon charm favoriter. Navigates through every hero in the hero grid,
opens each hero's Weapon Charms page, clicks un-favorited stars, then moves on.

HOW TO USE:
    1. Open Overwatch to the hero selection grid (Weapon Charms cosmetics section).
    2. Make sure your cursor is positioned on the star column (used to compute bbox).
    3. Run this script — the countdown starts immediately.
    4. Tab into Overwatch before the countdown ends.

USAGE:
    python weapon_charm_selection_automation.py [row] [col] [--debug] [--click-all] [--click-selected]

    row, col   Optional 1-indexed starting position. Overrides saved progress.
               Example: python weapon_charm_selection_automation.py 1 2

STOP: Press S or move the mouse to the top-left corner.

EMAIL NOTIFICATIONS:
    The script sends an email to moseleywalton@gmail.com when it finishes or when
    the Weapon Charms button fails to appear MAX_CONSECUTIVE_FAILURES times in a row
    (default 3), which indicates a disconnect or other unrecoverable error.

    Set these environment variables to enable email (one-time setup):
        setx OW_SMTP_USER "youraddress@gmail.com"
        setx OW_SMTP_PASS "your_gmail_app_password"

    Generate an App Password at: myaccount.google.com/apppasswords

REQUIREMENTS:
    pip install pygetwindow mss numpy opencv-python
"""

import sys
import argparse
import ctypes
import smtplib
import time
import json
import os
from email.mime.text import MIMEText
import numpy as np
import cv2
import pygetwindow as gw
import mss

# ── Windows API setup ──────────────────────────────────────────────────────────

user32 = ctypes.windll.user32

class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

VK_DOWN              = 0x28
VK_LEFT              = 0x25
VK_RIGHT             = 0x27
VK_SPACE             = 0x20
VK_ESCAPE            = 0x1B
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
    user32.keybd_event(VK_DOWN,   0, 0,               0)
    user32.keybd_event(VK_DOWN,   0, KEYEVENTF_KEYUP, 0)

def press_left():
    user32.keybd_event(VK_LEFT,   0, 0,               0)
    user32.keybd_event(VK_LEFT,   0, KEYEVENTF_KEYUP, 0)

def press_right():
    user32.keybd_event(VK_RIGHT,  0, 0,               0)
    user32.keybd_event(VK_RIGHT,  0, KEYEVENTF_KEYUP, 0)

def press_space():
    user32.keybd_event(VK_SPACE,  0, 0,               0)
    user32.keybd_event(VK_SPACE,  0, KEYEVENTF_KEYUP, 0)

def press_escape():
    user32.keybd_event(VK_ESCAPE, 0, 0,               0)
    user32.keybd_event(VK_ESCAPE, 0, KEYEVENTF_KEYUP, 0)

# ── Configuration — charm selection ───────────────────────────────────────────

KEY_PAUSE    = 0.18          # seconds after pressing down before scanning — must exceed
                             # the menu scroll animation, or the scan catches the star
                             # mid-glide and clicks the gap. 0.075 was too fast; 0.30 was
                             # reliable. Raise toward 0.30 if it starts missing rows.
CLICK_PAUSE  = 0.075         # seconds after clicking a star
COUNTDOWN    = 7             # seconds to tab into the game

SCAN_HALF_W  = 20            # pixels left/right of cursor X to scan (tight on the star)
SCAN_HALF_H  = 12            # pixels above/below cursor Y to scan (just the star glyph)

# Dark pixel thresholds — unselected stars are near-black.
# Raise MAX_DARK if stars are missed; lower it if non-stars are clicked.
MAX_DARK     = 80            # R, G, and B must all be below this to count as a dark star

# Minimum number of matching pixels required to count as a real star (not stray
# background). A star glyph fills many pixels; dark gaps between stars or dark
# edges near a selected star are only a handful. Run --debug to see live counts
# and set these between the "star present" count and the "no star" count.
MIN_DARK_PIXELS   = 15       # dark pixels needed to click an un-favorited star
MIN_ORANGE_PIXELS = 15       # orange pixels needed to click a selected star

# Orange pixel thresholds — selected stars are orange.
# Tune if --click-selected misses or mis-clicks stars.
ORANGE_MIN_R = 150           # R must be above this
ORANGE_MIN_G = 80            # G must be above this
ORANGE_MAX_B = 80            # B must be below this

# Pre-set cursor position (x, y) to snap to at the start of each hero's charm page.
# Set to None to use wherever the cursor already is.
# Run once with START_POS = None and --debug to find the right position.
START_POS    = (962, 1740)

# Flags — set via command line, not here:
#   --debug           print scan results each iteration, save strip image, no clicking
#   --click-all       click every row without checking star color
#   --click-selected  click already-selected (orange) stars to deselect them

# ── Configuration — hero grid navigation ──────────────────────────────────────

# Number of heroes in each row. Add or remove entries for more/fewer rows.
# Even rows (0, 2, …) are navigated left→right; odd rows (1, 3, …) right→left.
HEROES_PER_ROW          = [26, 26]

# Hero to start on. 0-indexed: row 0 is the top row, col 0 is the leftmost hero.
START_ROW               = 0
START_COL               = 0

# How long to run charm selection on each hero before moving to the next.
CHARM_SELECTION_SECONDS = 60

HERO_NAV_PAUSE          = 0.15   # pause between hero-navigation key presses
MENU_LOAD_PAUSE         = 1.5    # pause after opening hero popup / weapon charms page
ESCAPE_PAUSE            = 0.5    # pause after each Escape press

# Template image used to locate the Weapon Charms menu item after the popup opens.
# Crop a tight screenshot of the Weapon Charms button and save it as this filename.
WEAPON_CHARM_TEMPLATE   = "weapon_charms_template.png"
MATCH_THRESHOLD         = 0.8    # 0–1 confidence; lower if it fails to find, raise if it false-matches

PROGRESS_FILE           = "progress.json"

# ── Configuration — email notifications ───────────────────────────────────────

RECIPIENT_EMAIL       = "moseleywalton@gmail.com"
# Set OW_SMTP_USER (sender Gmail) and OW_SMTP_PASS (Gmail App Password) as env vars.
SMTP_USER             = os.environ.get("OW_SMTP_USER", "")
SMTP_PASS             = os.environ.get("OW_SMTP_PASS", "")

# How many consecutive "Weapon Charms button not found" failures before treating it as a
# disconnect / unrecoverable error, sending an email, and exiting.
MAX_CONSECUTIVE_FAILURES = 3

# ── Progress persistence ───────────────────────────────────────────────────────

def load_progress():
    """Return (row, col) from the progress file, or None if it doesn't exist."""
    if not os.path.exists(PROGRESS_FILE):
        return None
    with open(PROGRESS_FILE) as f:
        data = json.load(f)
    return data["row"], data["col"]

def save_progress(row, col):
    with open(PROGRESS_FILE, "w") as f:
        json.dump({"row": row, "col": col}, f)

def reset_progress():
    if os.path.exists(PROGRESS_FILE):
        os.remove(PROGRESS_FILE)

# ── Email ──────────────────────────────────────────────────────────────────────

def send_email(subject, body):
    """Send a notification email. Skips silently if credentials are not configured."""
    if not SMTP_USER or not SMTP_PASS:
        print(f"  (Email skipped — set OW_SMTP_USER and OW_SMTP_PASS env vars to enable)")
        return
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"]    = SMTP_USER
    msg["To"]      = RECIPIENT_EMAIL
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_USER, RECIPIENT_EMAIL, msg.as_string())
        print(f"  Email sent to {RECIPIENT_EMAIL}: {subject}")
    except Exception as e:
        print(f"  WARNING: Failed to send email: {e}")


# ── Helpers ────────────────────────────────────────────────────────────────────

_sct = mss.MSS()

def _scan(bbox, mask):
    """Given a boolean pixel mask, return (count, centroid) in screen coords.

    centroid is the (x, y) center of mass of the matching pixels — i.e. the
    middle of the star — so clicks land on the star itself rather than at a
    fixed point that may sit in the gap beside it. Returns (0, None) if empty.
    """
    ys, xs = np.where(mask)
    count = len(xs)
    if count == 0:
        return 0, None
    cx = bbox[0] + int(round(xs.mean()))
    cy = bbox[1] + int(round(ys.mean()))
    return count, (cx, cy)


def find_dark_star(bbox):
    """Return (count, centroid) of dark (un-favorited) star pixels in the region."""
    region = {"left": bbox[0], "top": bbox[1],
              "width": bbox[2] - bbox[0], "height": bbox[3] - bbox[1]}
    arr = np.array(_sct.grab(region))
    # mss returns BGRA — index 2=R, 1=G, 0=B
    dark = (arr[:, :, 2] < MAX_DARK) & \
           (arr[:, :, 1] < MAX_DARK) & \
           (arr[:, :, 0] < MAX_DARK)
    return _scan(bbox, dark)


def find_orange_star(bbox):
    """Return (count, centroid) of orange (selected) star pixels in the region."""
    region = {"left": bbox[0], "top": bbox[1],
              "width": bbox[2] - bbox[0], "height": bbox[3] - bbox[1]}
    arr = np.array(_sct.grab(region))
    # mss BGRA: index 2=R, 1=G, 0=B
    orange = (arr[:, :, 2] > ORANGE_MIN_R) & \
             (arr[:, :, 1] > ORANGE_MIN_G) & \
             (arr[:, :, 0] < ORANGE_MAX_B)
    return _scan(bbox, orange)


def find_on_screen(template_path):
    """
    Search the full screen for template_path using OpenCV template matching.
    Returns the screen (x, y) center of the best match if confidence >= MATCH_THRESHOLD,
    or None if not found.
    """
    template = cv2.imread(template_path, cv2.IMREAD_COLOR)
    if template is None:
        print(f"  ERROR: template image not found: {template_path}")
        return None

    monitor = _sct.monitors[1]
    raw = _sct.grab(monitor)
    # mss returns BGRA; drop alpha to get BGR for OpenCV
    screen = np.array(raw)[:, :, :3]

    result = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(result)

    if max_val < MATCH_THRESHOLD:
        print(f"  WARNING: Weapon Charms button not found (confidence {max_val:.2f} < {MATCH_THRESHOLD})")
        return None

    th, tw = template.shape[:2]
    cx = max_loc[0] + tw // 2
    cy = max_loc[1] + th // 2
    return cx, cy


def build_hero_list():
    """Return (row, col) tuples in snake-pattern navigation order."""
    heroes = []
    for row_idx, count in enumerate(HEROES_PER_ROW):
        if row_idx % 2 == 0:
            heroes.extend((row_idx, col) for col in range(count))
        else:
            heroes.extend((row_idx, col) for col in range(count - 1, -1, -1))
    return heroes


def run_charm_selection(bbox, duration_seconds, click_all, click_selected, debug, label=""):
    """
    Run charm selection for up to duration_seconds seconds.
    Returns (total_clicked, stopped_by_user).
    """
    end_time = time.time() + duration_seconds
    total = 0
    first_iter = True

    while time.time() < end_time:
        remaining = max(0, int(end_time - time.time()))
        print(f"\r{label}  {remaining} seconds...", end="", flush=True)
        if user32.GetAsyncKeyState(VK_S) & 0x8000:
            return total, True

        if user32.GetAsyncKeyState(VK_D) & 0x8000 and START_POS is not None:
            set_cursor_pos(*START_POS)
            time.sleep(0.05)
        x, y = cursor_pos()
        if x < 5 and y < 5:
            return total, True

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
            dark_count, dark_pos     = find_dark_star(bbox)
            orange_count, orange_pos = find_orange_star(bbox)
            print(f"  dark px: {dark_count} @ {dark_pos} (>= {MIN_DARK_PIXELS} clicks)  "
                  f"orange px: {orange_count} @ {orange_pos} (>= {MIN_ORANGE_PIXELS} clicks)")
        elif click_selected:
            # Click the center of the detected star. Its screen position is stable
            # (the list scrolls under a fixed reticle), so aiming at the centroid
            # lands on the star without drifting.
            count, pos = find_orange_star(bbox)
            if count >= MIN_ORANGE_PIXELS and pos:
                set_cursor_pos(*pos)
                left_click()
                total += 1
                time.sleep(CLICK_PAUSE)
        else:
            count, pos = find_dark_star(bbox)
            if count >= MIN_DARK_PIXELS and pos:
                set_cursor_pos(*pos)
                left_click()
                total += 1
                time.sleep(CLICK_PAUSE)

        press_down()
        time.sleep(KEY_PAUSE)  # let the scroll animation settle before the next scan

    return total, False

# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="All-Hero Weapon Charm Selection Automation")
    parser.add_argument("--debug",          action="store_true", help="Print scan info and save strip image. Does not click.")
    parser.add_argument("--click-all",      action="store_true", help="Click every row without checking star color.")
    parser.add_argument("--click-selected", action="store_true", help="Click already-selected (orange) stars to deselect them.")
    parser.add_argument("row",              type=int, nargs="?",    default=None, help="Starting row (1-indexed).")
    parser.add_argument("col",              type=int, nargs="?",    default=None, help="Starting column (1-indexed).")
    args = parser.parse_args()
    debug          = args.debug
    click_all      = args.click_all
    click_selected = args.click_selected

    # Resolve starting hero: CLI args > saved progress > config defaults
    saved_progress = load_progress()
    if args.row is not None and args.col is not None:
        resume_row, resume_col = args.row - 1, args.col - 1
    elif saved_progress is not None:
        resume_row, resume_col = saved_progress
    else:
        resume_row, resume_col = START_ROW, START_COL

    heroes = build_hero_list()
    try:
        start_idx = heroes.index((resume_row, resume_col))
    except ValueError:
        sys.exit(f"ERROR: (row={resume_row + 1}, col={resume_col + 1}) not found in hero grid.")
    total_heroes = len(heroes)

    print("All-Hero Weapon Charm Selection Automation")
    print("==========================================")
    print()
    print(f"Tab into Overwatch, then select a Weapon Charm from the menu.")
    print(f"Starting at row: {resume_row + 1}, col: {resume_col + 1}")
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


    wins = gw.getWindowsWithTitle("Overwatch")
    if not wins:
        sys.exit("ERROR: Overwatch window not found.")
    wins[0].activate()
    time.sleep(0.3)


    grand_total          = 0
    consecutive_failures = 0

    for i in range(start_idx, len(heroes)):
        curr_row, curr_col = heroes[i]
        label = f"Hero {i + 1}/{total_heroes}  (row={curr_row + 1}, col={curr_col + 1})"
        save_progress(curr_row, curr_col)

        # On a fresh start the first hero is already on the weapon charms page — skip navigation.
        # On resume, or for any hero after the first, navigate into the weapon charms page.
        if i != start_idx:
            press_space()
            time.sleep(MENU_LOAD_PAUSE)
            charm_pos = find_on_screen(WEAPON_CHARM_TEMPLATE)
            if charm_pos is None:
                consecutive_failures += 1
                if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                    send_email(
                        "Overwatch Charm Automation — Stopped (repeated failures)",
                        f"The Weapon Charms button could not be found {consecutive_failures} times in a row.\n\n"
                        f"Last hero: {i + 1}/{total_heroes} (row={curr_row + 1}, col={curr_col + 1}).\n"
                        f"Progress saved. Run the script again to resume."
                    )
                    print(f"  Weapon Charms button not found {consecutive_failures} times in a row. Exiting.")
                    sys.exit(1)
                print("  Skipping hero — could not locate Weapon Charms button.")
                press_escape()
                time.sleep(ESCAPE_PAUSE)
                continue
            consecutive_failures = 0
            set_cursor_pos(*charm_pos)
            time.sleep(0.05)
            left_click()
            time.sleep(MENU_LOAD_PAUSE)

        # Snap cursor to star column
        if START_POS is not None:
            set_cursor_pos(*START_POS)
            time.sleep(0.05)

        # Run charm selection for this hero
        total, stopped = run_charm_selection(bbox, CHARM_SELECTION_SECONDS,
                                             click_all, click_selected, debug, label)
        grand_total += total
        print(f"\r{label}  done. ({total} charm(s) favorited)")

        if stopped:
            print("Stopped by user.")
            sys.exit(0)

        # Return to hero grid
        press_escape()
        time.sleep(ESCAPE_PAUSE)
        press_escape()
        time.sleep(ESCAPE_PAUSE)

        # Navigate to next hero
        if i + 1 < len(heroes):
            next_row, _ = heroes[i + 1]
            if next_row == curr_row:
                # Same row — advance one hero in the current direction
                if curr_row % 2 == 0:
                    press_right()
                else:
                    press_left()
            else:
                # End of row — move down to the next row
                press_down()
            time.sleep(ESCAPE_PAUSE)

    reset_progress()
    print(f"\nAll done. {grand_total} total charm(s) favorited.")
    send_email(
        "Overwatch Charm Automation — Complete",
        f"All {total_heroes} heroes processed! {grand_total} total charm(s) favorited."
    )


if __name__ == "__main__":
    main()
