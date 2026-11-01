# Daily Slip

## Printing from your Android phone (Bluetooth)

1. Open Daily Slip in **Chrome on Android** from an https address (a local file or a claude.ai preview won't have Bluetooth).
2. Turn the printer on. Open **Printer**, choose **Bluetooth**, press **Connect printer** and pick it from the list.
3. Press **Print**. Pocket printers (like the Gabba Goods GG-THPR3) switch the layout to 58 mm automatically.

Works with Bluetooth Low Energy printers that speak standard receipt commands (ESC/POS) or the common pocket-printer protocol. Chrome needs Location/Nearby devices permission to see the printer.

## Photo prints

Choose **Photo** under What to print, pick an image, then adjust brightness, contrast and dot style. Add a caption or the date if you like.

## Printing to an Ethernet receipt printer (PC helper)

A web page can't open a raw connection to a printer, so a small helper runs on your PC. It serves the Daily Slip page at http://localhost:8765, reads your Obsidian note, and sends the receipt to the printer on port 9100.

## Setup (Windows, about 5 minutes)

1. Install Python 3 from python.org or the Microsoft Store (if `py` isn't already there).
2. Put this folder anywhere and double-click `start-daily-slip.bat`. Your browser opens Daily Slip.
3. Find the printer's IP address: hold the feed button while powering on to print its self-test page, or check your router's device list. Give it a fixed IP in the router (DHCP reservation) so it doesn't change.
4. Open **Printer** in the left panel. Enter the IP (port 9100), your Obsidian vault folder, and press **Test connection**.
5. Pick what to print and press **Print**.

Settings are saved in `config.json` beside the helper.

## Weekly meal plan and shopping list

In **Meal plan** or **Shopping**, choose where the list comes from:

- **Obsidian note**: the helper reads the note from your vault (default `01 - Inbox/Weekly Shop.md`).
- **Upload .md**: pick or drop a file; no helper needed to read it.

Format (see `Weekly Shop.md`): a `## Meal plan` section with `- Mon: Dish | note` lines, and a `## Shopping list` section with `### Aisle` headings and `- [ ] item` lines. Ticked items (`[x]`) are left off the printout.

## Notes

- The helper only listens on your own PC (127.0.0.1) and ignores requests from other websites.
- Printing sends the preview as a 1-bit image, so what you see is what prints. If a print comes out too dark or too light, tell me and I'll adjust the threshold.
- If your printer's printable width is 512 dots instead of 576, tell me and I'll add a width setting.
