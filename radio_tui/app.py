from __future__ import annotations

import json
from pathlib import Path

from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import (
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    Static,
    Switch,
)

from radio_tui.player import MpvPlayer
from radio_tui.stations import Station, load_stations


class NowPlayingPanel(Static):
    DEFAULT_CSS = """
    NowPlayingPanel {
        height: 8;
        border: round $accent;
        padding: 1 2;
        background: $surface;
    }

    NowPlayingPanel .title {
        text-style: bold;
        color: $accent;
    }

    NowPlayingPanel .offline {
        color: $error;
    }
    """

    station = reactive("")
    track = reactive("")
    volume = reactive(50)
    muted = reactive(False)
    offline = reactive(False)

    def render(self) -> str:
        station = self.station or "Nothing playing"
        track = self.track or "Select a station and press Enter"
        volume = f"{self.volume}%"
        if self.muted:
            volume += " (muted)"
        status = "offline" if self.offline else "live"
        lines = [
            "[b accent]Now Playing[/]",
            f"[bold]{station}[/]",
            f"[dim]{track}[/]" if not self.offline else f"[error]{track}[/]",
            f"Volume: {volume}  ·  {status}",
        ]
        return "\n".join(lines)


class RadioApp(App):
    TITLE = "Telugu Radio"
    SUB_TITLE = "OnlineRadioFM"
    CSS = """
    Screen {
        layout: vertical;
    }

    #main {
        height: 1fr;
    }

    #sidebar {
        width: 34;
        border-right: solid $primary;
        padding: 0 1;
    }

    #sidebar Label {
        margin: 1 0 0 0;
        text-style: bold;
    }

    #search {
        margin: 1 0;
    }

    #playable-only {
        margin: 0 0 1 0;
    }

    #station-table {
        height: 1fr;
    }

    #details {
        padding: 1 2;
        height: 1fr;
    }

    #details-title {
        text-style: bold;
        margin-bottom: 1;
    }

    #details-body {
        color: $text-muted;
    }

    .stat-block {
        margin-top: 1;
        padding: 1;
        border: round $primary-lighten-2;
        background: $panel;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("enter", "play_selected", "Play"),
        Binding("space", "play_selected", "Play", show=False),
        Binding("n", "next_station", "Next"),
        Binding("p", "prev_station", "Prev"),
        Binding("/", "focus_search", "Search"),
        Binding("+", "volume_up", "Vol +"),
        Binding("=", "volume_up", "Vol +", show=False),
        Binding("-", "volume_down", "Vol -"),
        Binding("m", "toggle_mute", "Mute"),
        Binding("s", "stop", "Stop"),
        Binding("f", "toggle_favorite", "Favorite"),
        Binding("y", "copy_stream", "Copy URL"),
    ]

    favorites_path = Path.home() / ".radio_tui_favorites.json"
    selected_index = reactive(0)
    filter_text = reactive("")
    playable_only = reactive(True)

    def __init__(self) -> None:
        super().__init__()
        self.all_stations = load_stations()
        self.filtered_stations: list[Station] = []
        self.player = MpvPlayer()
        self.favorites: set[str] = self._load_favorites()

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="main"):
            with Vertical(id="sidebar"):
                yield Label("Search")
                yield Input(placeholder="Filter stations...", id="search")
                with Horizontal(id="playable-only"):
                    yield Switch(value=True, id="playable-switch")
                    yield Label("Playable only")
                yield DataTable(id="station-table", zebra_stripes=True, cursor_type="row")
            with Vertical(id="details"):
                yield NowPlayingPanel(id="now-playing")
                yield Static("Select a station", id="details-title")
                yield Static("", id="details-body")
                yield Static("", id="details-stats", classes="stat-block")
        yield Footer()

    def on_mount(self) -> None:
        if not self.player.available:
            self.notify(
                "mpv and socat are required for playback.",
                severity="error",
                timeout=8,
            )
        table = self.query_one("#station-table", DataTable)
        table.add_columns("Station", "Live")
        self.refresh_table()
        table.focus()
        self.set_interval(1, self.refresh_now_playing)

    def _load_favorites(self) -> set[str]:
        if not self.favorites_path.exists():
            return set()
        try:
            data = json.loads(self.favorites_path.read_text(encoding="utf-8"))
            return set(data)
        except (json.JSONDecodeError, TypeError):
            return set()

    def _save_favorites(self) -> None:
        self.favorites_path.write_text(
            json.dumps(sorted(self.favorites), indent=2),
            encoding="utf-8",
        )

    def _apply_filter(self) -> None:
        query = self.filter_text.casefold().strip()
        stations = self.all_stations
        if self.playable_only:
            stations = [station for station in stations if station.playable]
        if query:
            stations = [
                station
                for station in stations
                if query in station.name.casefold()
            ]
        self.filtered_stations = stations

    def refresh_table(self) -> None:
        self._apply_filter()
        table = self.query_one("#station-table", DataTable)
        table.clear()
        for station in self.filtered_stations:
            fav = "★ " if station.name in self.favorites else ""
            live = "●" if station.playable else "○"
            table.add_row(f"{fav}{station.name}", live)
        if self.filtered_stations:
            self.selected_index = min(self.selected_index, len(self.filtered_stations) - 1)
            table.move_cursor(row=self.selected_index)
            self.update_details()
        else:
            self.query_one("#details-title", Static).update("No stations match")
            self.query_one("#details-body", Static).update("")
            self.query_one("#details-stats", Static).update("")

    def selected_station(self) -> Station | None:
        if not self.filtered_stations:
            return None
        index = max(0, min(self.selected_index, len(self.filtered_stations) - 1))
        return self.filtered_stations[index]

    def update_details(self) -> None:
        station = self.selected_station()
        if not station:
            return
        favorite = "Yes" if station.name in self.favorites else "No"
        stream = station.stream_url or "Not available online"
        body = (
            f"Page: {station.page_url}\n"
            f"Stream: {stream}\n"
            f"Favorite: {favorite}"
        )
        playable = sum(1 for item in self.all_stations if item.playable)
        stats = (
            f"{len(self.all_stations)} stations total  ·  "
            f"{playable} playable  ·  "
            f"{len(self.favorites)} favorites"
        )
        self.query_one("#details-title", Static).update(station.name)
        self.query_one("#details-body", Static).update(body)
        self.query_one("#details-stats", Static).update(stats)

    def refresh_now_playing(self) -> None:
        panel = self.query_one("#now-playing", NowPlayingPanel)
        state = self.player.snapshot()
        panel.station = state.station_name
        panel.track = state.media_title
        panel.volume = state.volume
        panel.muted = state.muted
        panel.offline = state.offline

    @on(Input.Changed, "#search")
    def on_search_changed(self, event: Input.Changed) -> None:
        self.filter_text = event.value
        self.selected_index = 0
        self.refresh_table()

    @on(Switch.Changed, "#playable-switch")
    def on_playable_changed(self, event: Switch.Changed) -> None:
        self.playable_only = event.value
        self.selected_index = 0
        self.refresh_table()

    @on(DataTable.RowHighlighted)
    def on_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        if event.cursor_row is not None:
            self.selected_index = event.cursor_row
            self.update_details()

    @on(DataTable.RowSelected)
    def on_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.cursor_row is not None:
            self.selected_index = event.cursor_row
            self.update_details()
        self.action_play_selected()

    def action_focus_search(self) -> None:
        self.query_one("#search", Input).focus()

    def action_play_selected(self) -> None:
        station = self.selected_station()
        if not station:
            return
        if not station.playable or not station.stream_url:
            self.notify(f"No stream for {station.name}", severity="warning")
            return
        self.player.play(station.name, station.stream_url)
        self.notify(f"Playing {station.name}")

    def action_stop(self) -> None:
        self.player.stop()
        self.notify("Stopped")

    def action_next_station(self) -> None:
        if not self.filtered_stations:
            return
        self.selected_index = (self.selected_index + 1) % len(self.filtered_stations)
        table = self.query_one("#station-table", DataTable)
        table.move_cursor(row=self.selected_index)
        self.action_play_selected()

    def action_prev_station(self) -> None:
        if not self.filtered_stations:
            return
        self.selected_index = (self.selected_index - 1) % len(self.filtered_stations)
        table = self.query_one("#station-table", DataTable)
        table.move_cursor(row=self.selected_index)
        self.action_play_selected()

    def action_volume_up(self) -> None:
        self.player.adjust_volume(5)
        self.refresh_now_playing()

    def action_volume_down(self) -> None:
        self.player.adjust_volume(-5)
        self.refresh_now_playing()

    def action_toggle_mute(self) -> None:
        self.player.toggle_mute()
        self.refresh_now_playing()

    def action_toggle_favorite(self) -> None:
        station = self.selected_station()
        if not station:
            return
        if station.name in self.favorites:
            self.favorites.remove(station.name)
            self.notify(f"Removed {station.name} from favorites")
        else:
            self.favorites.add(station.name)
            self.notify(f"Added {station.name} to favorites")
        self._save_favorites()
        self.refresh_table()

    def action_copy_stream(self) -> None:
        import shutil
        import subprocess

        station = self.selected_station()
        if not station or not station.stream_url:
            self.notify("No stream URL to copy", severity="warning")
            return
        url = station.stream_url
        for copy_cmd in (["wl-copy"], ["xclip", "-selection", "clipboard"]):
            if shutil.which(copy_cmd[0]):
                subprocess.run(copy_cmd, input=url.encode(), check=False)
                self.notify("Stream URL copied")
                return
        self.notify(url, title="Stream URL", timeout=10)

    def on_unmount(self) -> None:
        self.player.stop()


def main() -> None:
    RadioApp().run()


if __name__ == "__main__":
    main()
