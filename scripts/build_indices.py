#!/usr/bin/env python3
"""Fetch and merge M3U/JSON sources into pre-processed channel indices.

Outputs one JSON file per source type under the `channels/` directory.
Each file is a `{"version": int, "generated_at": str, "channels": [...]}` structure.

The Android client fetches these from GitHub Pages instead of hitting
the original (often slow/unreliable) M3U hosts directly.
"""

import hashlib
import json
import os
import re
import sys
import time
import urllib.request
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.dirname(SCRIPT_DIR)
OUTPUT_DIR = os.path.join(REPO_DIR, "channels")
HEALTH_DIR = os.path.join(REPO_DIR, "health")

VERSION = 1
REQUEST_TIMEOUT = 45
USER_AGENT = "StreamVerse-DataBuild/1.0"


def log(msg: str):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def fetch(url: str, timeout: int = REQUEST_TIMEOUT) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def stable_id(seed: str) -> str:
    return str(hashlib.sha256(seed.encode()).hexdigest()[:12])


def parse_m3u(content: str, source_key: str = "") -> list[dict]:
    channels = []
    lines = content.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("#EXTINF:"):
            info = line
            i += 1
            if i < len(lines):
                url = lines[i].strip()
                if not url or url.startswith("#"):
                    continue
                name = ""
                logo = None
                category = None
                country = None
                language = None
                quality = None
                tvg_id = None
                headers = {}

                m = re.search(r'tvg-id="([^"]*)"', info)
                if m:
                    tvg_id = m.group(1)
                m = re.search(r'tvg-logo="([^"]*)"', info)
                if m:
                    logo = m.group(1) or None
                m = re.search(r'group-title="([^"]*)"', info)
                if m:
                    category = m.group(1) or None
                m = re.search(r'tvg-country="([^"]*)"', info)
                if m:
                    country = m.group(1) or None
                m = re.search(r'tvg-language="([^"]*)"', info)
                if m:
                    language = m.group(1) or None
                m = re.search(r'tvg-quality="([^"]*)"', info)
                if m:
                    quality = m.group(1) or None

                name = info.rsplit(",", 1)[-1].strip() if "," in info else ""
                if not name:
                    name = tvg_id or ""

                ch_id = stable_id(f"{source_key}|{url}|{name}")
                channels.append(
                    {
                        "id": ch_id,
                        "name": name,
                        "streamUrl": url,
                        "logoUrl": logo,
                        "category": category,
                        "country": country,
                        "language": language,
                        "quality": quality,
                        "source": source_key,
                        "headers": headers,
                        "drmKeyId": None,
                        "drmKey": None,
                    }
                )
        i += 1
    return channels


def fetch_channels(source_key: str, urls: list[str]) -> list[dict]:
    all_channels = []
    seen_ids = set()
    for url in urls:
        try:
            log(f"  fetching {source_key}: {url}")
            body = fetch(url)
            chs = parse_m3u(body, source_key)
            for ch in chs:
                if ch["id"] not in seen_ids:
                    seen_ids.add(ch["id"])
                    all_channels.append(ch)
            log(f"    -> {len(chs)} channels ({len(all_channels)} unique so far)")
        except Exception as e:
            log(f"  FAILED {source_key}: {url} -> {e}")
    return all_channels


def write_index(source_key: str, channels: list[dict]):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    path = os.path.join(OUTPUT_DIR, f"{source_key}_index.json")
    doc = {
        "version": VERSION,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "count": len(channels),
        "channels": channels,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    log(f"  written {path} ({len(channels)} channels, {os.path.getsize(path) / 1024:.0f} KB)")


def write_dead_channels(dead: list[str]):
    os.makedirs(HEALTH_DIR, exist_ok=True)
    path = os.path.join(HEALTH_DIR, "dead_channels.json")
    doc = {
        "version": VERSION,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "count": len(dead),
        "names": dead,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    log(f"  written {path} ({len(dead)} dead channels)")


def build_premium_index():
    log("=== Building PREMIUM index ===")
    urls = [
        "https://iptv-org.github.io/iptv/categories/movies.m3u",
        "https://iptv-org.github.io/iptv/categories/sports.m3u",
        "https://iptv-org.github.io/iptv/categories/series.m3u",
        "https://iptv-org.github.io/iptv/categories/documentary.m3u",
        "https://raw.githubusercontent.com/amazeyourself/tamil-local-iptv/main/channels.m3u",
        "https://raw.githubusercontent.com/Shariar-Ahamed/online-tv-streaming-platform/main/other_channel_file/IP-TV.m3u",
        "https://raw.githubusercontent.com/Shariar-Ahamed/online-tv-streaming-platform/main/other_channel_file/07-fgd.m3u",
        "https://raw.githubusercontent.com/Shariar-Ahamed/online-tv-streaming-platform/main/other_channel_file/06-Skym3u%20sports.m3u",
        "https://raw.githubusercontent.com/Shariar-Ahamed/online-tv-streaming-platform/main/other_channel_file/08-Fifa%20world%20cup.m3u",
        "https://raw.githubusercontent.com/Shariar-Ahamed/online-tv-streaming-platform/main/other_channel_file/4-Update-New.m3u",
        "https://raw.githubusercontent.com/Shariar-Ahamed/online-tv-streaming-platform/main/other_channel_file/5.m3u",
        "https://raw.githubusercontent.com/Shariar-Ahamed/online-tv-streaming-platform/main/other_channel_file/iptv-playlist.m3u",
        "https://raw.githubusercontent.com/Shariar-Ahamed/online-tv-streaming-platform/main/other_channel_file/4.m3u",
        "https://raw.githubusercontent.com/Shariar-Ahamed/online-tv-streaming-platform/main/other_channel_file/new-bd-channels.m3u",
        "https://raw.githubusercontent.com/Romaxa55/world_ip_tv/master/output/index.m3u",
        "https://raw.githubusercontent.com/Zaman-Topu/Ip-tv-Collection/main/FINAL_IPTV_GEO.m3u",
        "https://raw.githubusercontent.com/tniint/M3U_Organizer/main/usTV_local_edit.m3u",
        "https://raw.githubusercontent.com/tniint/M3U_Organizer/main/us_cleaned_matched.m3u",
        "https://raw.githubusercontent.com/tniint/M3U_Organizer/main/us_cleaned.m3u",
        "https://raw.githubusercontent.com/tniint/M3U_Organizer/main/us_organized_final.m3u",
        "https://raw.githubusercontent.com/tniint/M3U_Organizer/main/us_organized_with_local.m3u",
        "https://raw.githubusercontent.com/tniint/M3U_Organizer/main/us_organized_local_top.m3u",
        "https://raw.githubusercontent.com/Zaman-Topu/Ip-tv-Collection/main/custom_playlist.m3u",
        "https://raw.githubusercontent.com/dhasap/dhanytv/main/dhanytv-ott.m3u",
        "https://raw.githubusercontent.com/Zaman-Topu/Ip-tv-Collection/main/FINAL_IPTV_ACTIVE.m3u",
        "https://raw.githubusercontent.com/Zaman-Topu/Ip-tv-Collection/main/FINAL_IPTV_COMPLETE.m3u",
        "https://raw.githubusercontent.com/Zaman-Topu/Ip-tv-Collection/main/FINAL_MOVIES_COMPLETE.m3u",
    ]
    channels = fetch_channels("premium", urls)
    write_index("premium", channels)
    return channels


def build_iptv_index():
    log("=== Building IPTV index ===")
    urls = [
        "https://iptv-org.github.io/iptv/index.m3u",
        "https://iptv-org.github.io/iptv/countries/ng.m3u",
        "https://iptv-org.github.io/iptv/countries/gh.m3u",
        "https://iptv-org.github.io/iptv/countries/za.m3u",
        "https://iptv-org.github.io/iptv/countries/ke.m3u",
        "https://iptv-org.github.io/iptv/countries/eg.m3u",
        "https://iptv-org.github.io/iptv/countries/tz.m3u",
        "https://iptv-org.github.io/iptv/countries/et.m3u",
        "https://iptv-org.github.io/iptv/countries/ug.m3u",
        "https://iptv-org.github.io/iptv/regions/afr.m3u",
    ]
    channels = fetch_channels("iptv", urls)
    write_index("iptv", channels)
    return channels


def build_fasttv_index():
    log("=== Building FASTTV index ===")
    country_codes = [
        "ng", "gh", "za", "ke", "et", "tz", "ug", "ci", "cm", "sn",
        "rw", "ma", "eg", "ao", "dz",
        "uk", "us", "in", "ph", "mx", "br", "tr", "ar", "de", "fr",
        "es", "it", "ru",
    ]
    urls = [
        f"https://raw.githubusercontent.com/iptv-org/iptv/master/streams/{cc}.m3u"
        for cc in country_codes
    ]
    channels = fetch_channels("fasttv", urls)
    write_index("fasttv", channels)
    return channels


def build_freelive_index():
    log("=== Building FREE LIVE index ===")
    urls = [
        "https://raw.githubusercontent.com/BuddyChewChew/app-m3u-generator/refs/heads/main/playlists/plutotv_all.m3u",
        "https://raw.githubusercontent.com/BuddyChewChew/app-m3u-generator/refs/heads/main/playlists/plex_all.m3u",
        "https://raw.githubusercontent.com/BuddyChewChew/app-m3u-generator/refs/heads/main/playlists/roku_all.m3u",
        "https://raw.githubusercontent.com/BuddyChewChew/app-m3u-generator/refs/heads/main/playlists/tubi_all.m3u",
        "https://raw.githubusercontent.com/BuddyChewChew/app-m3u-generator/refs/heads/main/playlists/xumo_all.m3u",
        "https://raw.githubusercontent.com/BuddyChewChew/app-m3u-generator/refs/heads/main/playlists/samsung_all.m3u",
        "https://raw.githubusercontent.com/BuddyChewChew/app-m3u-generator/refs/heads/main/playlists/vizio_all.m3u",
        "https://raw.githubusercontent.com/BuddyChewChew/app-m3u-generator/refs/heads/main/playlists/stirr_all.m3u",
        "https://raw.githubusercontent.com/BuddyChewChew/app-m3u-generator/refs/heads/main/playlists/haystack_all.m3u",
        "https://raw.githubusercontent.com/BuddyChewChew/app-m3u-generator/refs/heads/main/playlists/localnow_all.m3u",
        "https://raw.githubusercontent.com/BuddyChewChew/app-m3u-generator/refs/heads/main/playlists/klowdtv_all.m3u",
    ]
    channels = fetch_channels("freelive", urls)
    write_index("freelive", channels)
    return channels


def build_freetv_index():
    log("=== Building FREE-TV index ===")
    urls = [
        "https://raw.githubusercontent.com/Free-TV/IPTV/master/playlist.m3u8",
        "https://raw.githubusercontent.com/Free-TV/IPTV/master/playlist.m3u",
    ]
    channels = fetch_channels("freetv", urls)
    write_index("freetv", channels)
    return channels


def main():
    log("StreamVerse Data Index Builder starting")
    log(f"Output directory: {OUTPUT_DIR}")

    premium = build_premium_index()
    iptv = build_iptv_index()
    fasttv = build_fasttv_index()
    freelive = build_freelive_index()
    freetv = build_freetv_index()

    total = len(premium) + len(iptv) + len(fasttv) + len(freelive) + len(freetv)
    log(f"\n=== DONE: {total} total channels indexed ===")
    log(f"  premium:  {len(premium)}")
    log(f"  iptv:     {len(iptv)}")
    log(f"  fasttv:   {len(fasttv)}")
    log(f"  freelive: {len(freelive)}")
    log(f"  freetv:   {len(freetv)}")

    write_dead_channels([])

    log("All indices written successfully.")


if __name__ == "__main__":
    main()
