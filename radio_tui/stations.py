from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Station:
    name: str
    page_url: str
    stream_url: str | None
    stream_available: bool

    @property
    def playable(self) -> bool:
        return bool(self.stream_url)


def data_dir() -> Path:
    return Path(__file__).resolve().parent.parent


def load_stations(path: Path | None = None) -> list[Station]:
    json_path = path or data_dir() / "telugu-radio-stations.json"
    with json_path.open(encoding="utf-8") as handle:
        payload = json.load(handle)

    stations: list[Station] = []
    for item in payload["stations"]:
        stations.append(
            Station(
                name=item["name"],
                page_url=item["page_url"],
                stream_url=item.get("stream_url") or None,
                stream_available=bool(item.get("stream_available")),
            )
        )
    return stations


def export_csv(stations: list[Station], path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["name", "page_url", "stream_url", "stream_available"],
        )
        writer.writeheader()
        for station in stations:
            writer.writerow(
                {
                    "name": station.name,
                    "page_url": station.page_url,
                    "stream_url": station.stream_url or "",
                    "stream_available": station.stream_available,
                }
            )
