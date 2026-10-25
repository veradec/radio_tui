# Telugu Radio TUI

A terminal UI for browsing and playing Telugu online radio stations from [OnlineRadioFM](https://onlineradiofm.in/language/telugu).

## Requirements

- Python 3.11+
- [mpv](https://mpv.io/) — playback
- [socat](https://sourceforge.net/projects/socat/) — mpv IPC

## Quick start

```bash
cd ~/code/radio_tui
chmod +x radio-tui
./radio-tui
```

The launcher creates a local `.venv` and installs dependencies on first run.

Or manually:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m radio_tui
```

## Keys

| Key | Action |
|-----|--------|
| `/` | Focus search |
| `Enter` | Play selected station |
| `n` / `p` | Next / previous station (and play) |
| `+` / `-` | Volume up / down |
| `m` | Mute |
| `s` | Stop |
| `f` | Toggle favorite |
| `y` | Show stream URL |
| `q` | Quit |

Favorites are saved to `~/.radio_tui_favorites.json`.

## Data

- `telugu-radio-stations.json` — station metadata and stream URLs
- `telugu-radio-stations.csv` — same data in CSV format

Source: https://onlineradiofm.in/language/telugu
