"""
YouTube crypto channel harvester.

Usage: python harvest_crypto_channels.py

Dependencies:
    pip install requests
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import requests

CONFIG_PATH = Path("config.json")


class ConfigError(Exception):
    """Custom exception for configuration related errors."""


def load_config(config_path: Path = CONFIG_PATH) -> Dict:
    """Load and validate configuration from JSON file."""
    if not config_path.exists():
        raise ConfigError(f"Configuration file not found: {config_path}")
    try:
        with config_path.open("r", encoding="utf-8") as f:
            config = json.load(f)
    except json.JSONDecodeError as exc:
        raise ConfigError(f"Invalid JSON in configuration file: {exc}") from exc

    required_keys = ["api_keys", "keywords", "max_results_per_keyword", "state_file", "output_file"]
    missing = [k for k in required_keys if k not in config]
    if missing:
        raise ConfigError(f"Missing required config keys: {', '.join(missing)}")

    if not isinstance(config.get("api_keys"), list) or not config["api_keys"]:
        raise ConfigError("config['api_keys'] must be a non-empty list")
    if not isinstance(config.get("keywords"), list) or not config["keywords"]:
        raise ConfigError("config['keywords'] must be a non-empty list")
    if not isinstance(config.get("max_results_per_keyword"), int) or config["max_results_per_keyword"] <= 0:
        raise ConfigError("config['max_results_per_keyword'] must be a positive integer")

    return config


def load_state(state_path: Path) -> Dict:
    """Load pagination state from disk, returning an empty dict on first run."""
    if not state_path.exists():
        return {}
    try:
        with state_path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as exc:
        print(f"Error reading state file {state_path}: {exc}", file=sys.stderr)
        return {}


def save_state(state: Dict, state_path: Path) -> None:
    """Persist current state to disk."""
    tmp_path = state_path.with_suffix(".tmp")
    with tmp_path.open("w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, sort_keys=True)
    tmp_path.replace(state_path)


def load_known_channels(output_path: Path) -> Set[str]:
    """Load existing channels from output file into a set for deduplication."""
    if not output_path.exists():
        return set()
    channels: Set[str] = set()
    with output_path.open("r", encoding="utf-8") as f:
        for line in f:
            url = line.strip()
            if url:
                channels.add(url)
    return channels


def save_known_channels(channels: Set[str], output_path: Path) -> None:
    """Write deduplicated channel URLs to output file."""
    tmp_path = output_path.with_suffix(".tmp")
    with tmp_path.open("w", encoding="utf-8") as f:
        for url in sorted(channels):
            f.write(url + "\n")
    tmp_path.replace(output_path)


def get_next_api_key(keys: List[str], exhausted: Set[int], current_index: int) -> Optional[Tuple[int, str]]:
    """Return the next available API key index and value, or None if all exhausted."""
    total = len(keys)
    for offset in range(1, total + 1):
        idx = (current_index + offset) % total
        if idx not in exhausted:
            return idx, keys[idx]
    return None


def handle_quota_error(response_json: Dict) -> bool:
    """Determine whether the API response indicates quota exhaustion."""
    if not response_json:
        return False
    error = response_json.get("error", {})
    errors = error.get("errors", [])
    reasons = {item.get("reason") for item in errors if isinstance(item, dict)}
    if "quotaExceeded" in reasons or "dailyLimitExceeded" in reasons:
        return True
    return False


def request_with_retries(url: str, params: Dict, retries: int = 3, delay: float = 1.5) -> requests.Response:
    """Perform an HTTP GET request with retry logic for network errors."""
    attempt = 0
    while True:
        attempt += 1
        try:
            resp = requests.get(url, params=params, timeout=10)
            return resp
        except requests.RequestException as exc:
            if attempt >= retries:
                raise
            print(f"Network error ({exc}), retrying in {delay} seconds...", file=sys.stderr)
            time.sleep(delay)


def search_videos_for_keyword(
    keyword: str,
    api_key: str,
    page_token: Optional[str],
) -> Tuple[Optional[Dict], Optional[requests.Response]]:
    """Call the YouTube search API for a keyword and optional page token."""
    base_url = "https://www.googleapis.com/youtube/v3/search"
    params = {
        "part": "snippet",
        "type": "video",
        "q": keyword,
        "maxResults": 50,
        "key": api_key,
    }
    if page_token:
        params["pageToken"] = page_token

    response = request_with_retries(base_url, params=params)
    if response.status_code != 200:
        return None, response
    try:
        data = response.json()
    except json.JSONDecodeError:
        print("Failed to parse JSON from API response", file=sys.stderr)
        return None, response
    return data, response


def process_keyword(
    keyword: str,
    config: Dict,
    state: Dict,
    known_channels: Set[str],
    keys: List[str],
) -> Tuple[Dict, Set[str]]:
    """Fetch videos for a keyword, updating state and known channel URLs."""
    state.setdefault(keyword, {"last_page_token": None, "fetched_count": 0, "completed": False})
    kw_state = state[keyword]
    if kw_state.get("completed"):
        print(f"Keyword '{keyword}' already completed. Skipping.")
        return state, known_channels

    current_key_index = 0
    exhausted_keys: Set[int] = set()
    api_key = keys[current_key_index]

    max_results = config["max_results_per_keyword"]
    state_path = Path(config["state_file"])
    output_path = Path(config["output_file"])

    while not kw_state.get("completed"):
        print(f"Using API key index {current_key_index} for keyword '{keyword}' with page token {kw_state.get('last_page_token')!r}.")
        data, response = search_videos_for_keyword(keyword, api_key, kw_state.get("last_page_token"))

        if data is None:
            if response is not None and response.status_code == 403:
                try:
                    error_json = response.json()
                except json.JSONDecodeError:
                    error_json = {}
                if handle_quota_error(error_json):
                    exhausted_keys.add(current_key_index)
                    next_key_info = get_next_api_key(keys, exhausted_keys, current_key_index)
                    if next_key_info is None:
                        print("All API keys are exhausted. Exiting.")
                        save_state(state, state_path)
                        save_known_channels(known_channels, output_path)
                        sys.exit(0)
                    current_key_index, api_key = next_key_info
                    print(f"Quota exhausted. Switching to API key index {current_key_index}.")
                    continue
            status_code = response.status_code if response is not None else "unknown"
            print(f"API request failed with status {status_code}. Stopping keyword '{keyword}'.", file=sys.stderr)
            save_state(state, state_path)
            save_known_channels(known_channels, output_path)
            return state, known_channels

        items = data.get("items", [])
        for item in items:
            snippet = item.get("snippet", {})
            channel_id = snippet.get("channelId")
            if channel_id:
                url = f"https://www.youtube.com/channel/{channel_id}"
                if url not in known_channels:
                    known_channels.add(url)

        fetched = len(items)
        kw_state["fetched_count"] = kw_state.get("fetched_count", 0) + fetched
        kw_state["last_page_token"] = data.get("nextPageToken")

        save_state(state, state_path)
        save_known_channels(known_channels, output_path)

        print(
            f"Keyword '{keyword}': fetched {kw_state['fetched_count']} items so far. "
            f"Unique channels: {len(known_channels)}."
        )

        if kw_state["fetched_count"] >= max_results or not kw_state["last_page_token"]:
            kw_state["completed"] = True
            save_state(state, state_path)
            print(f"Keyword '{keyword}' completed with {kw_state['fetched_count']} items.")
            break

        # Small delay to be gentle with API.
        time.sleep(0.5)

    return state, known_channels


def main() -> None:
    try:
        config = load_config()
    except ConfigError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        sys.exit(1)

    state_path = Path(config["state_file"])
    output_path = Path(config["output_file"])

    state = load_state(state_path)
    known_channels = load_known_channels(output_path)

    print(f"Loaded {len(known_channels)} known channels.")

    api_keys: List[str] = config["api_keys"]
    for keyword in config["keywords"]:
        state, known_channels = process_keyword(keyword, config, state, known_channels, api_keys)

    print("Harvesting completed for all keywords.")


if __name__ == "__main__":
    main()
