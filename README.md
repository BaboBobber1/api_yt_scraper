# API YT Scraper (Crypto YouTube Channel Harvester)

A single-page, local-only tool for discovering crypto-focused YouTube channels and enriching them with channel metadata, contact info, and outbound links. Everything runs in your browser—no server required.

## What it does

This app helps you:

- Search YouTube for channels based on crypto-related keywords.
- Deduplicate channels across searches.
- Enrich channel data (subscribers, language, email, Telegram, links).
- Filter and archive channels.
- Export enriched results to CSV.

The entire experience is contained in `index.html` and uses the YouTube Data API directly from the browser.

## How it works (high level)

1. **Search pass:** For each keyword, the app queries the YouTube Search API, collects channel IDs, and tracks crypto keyword hits per channel.
2. **Enrichment pass:** For the accepted channel IDs, the app fetches channel details to gather subscribers, language, and channel metadata. It also parses channel descriptions and links to extract email and Telegram handles/URLs.
3. **Filtering + export:** Use the built-in filters and archive tools to refine the list, then export to CSV.

## Requirements

- A modern browser (Chrome, Edge, Firefox, Safari).
- One or more **YouTube Data API v3 keys**.

## Getting started

1. Download or clone this repo.
2. Open `index.html` directly in your browser.
3. Paste your API keys (one per line).
4. Paste your keywords (one per line).
5. Pick a max results value, then click **Start Scan**.

> Tip: If you have multiple API keys, the app rotates through them when quota is exhausted.

## UI guide

### Inputs

- **API Keys**: One key per line.
- **Keywords**: One keyword per line (e.g. `bitcoin`, `crypto trading`).
- **Max results per keyword**: The cap for videos scanned per keyword (in multiples of 50).

### Status section

- **State**: Idle, Running, or any error state.
- **Current keyword**: The keyword currently being scanned.
- **Videos processed**: Total videos scanned so far.
- **Unique channels**: Channels collected so far.
- **API key**: Which key index is currently active.

### Results section

- **Archive current filter**: Moves visible channels to the archive.
- **Archive exported**: Moves the last-exported set to the archive.
- **Enrich Channels**: Fetches channel-level metadata and contact info.
- **Download CSV**: Exports the currently visible channels.

### Filters

- **Languages**: Multi-select grouped language filter with presets.
- **Subscribers range**: Min/Max subscriber filter.
- **Unique emails only**: Hide duplicate emails.
- **Telegram only**: Show only channels with Telegram handles or links.
- **Global search**: Text filter across channel data.

### Tabs

- **Active**: Channels in the main list.
- **Archived**: Channels previously archived.

## Data storage

The app stores your progress locally using **IndexedDB** (preferred) and legacy **LocalStorage** for compatibility. Data never leaves your browser unless you export it.

## CSV export format

The export includes:

```
channel_id,channel_url,channel_name,subscribers,language,email,telegram,crypto_hits,links
```

- **links** is a `|`-delimited list of outbound URLs detected on the channel.

## Notes & limits

- YouTube API quotas apply. The app automatically rotates through provided API keys when limits are hit.
- Enrichment is capped per run to avoid quota spikes.
- All processing happens client-side; there is no backend.

## Troubleshooting

- **No results**: Try different keywords or confirm your API key is valid.
- **Quota exhausted**: Add more keys or wait for quota reset.
- **Missing emails**: Not all channels list contact emails publicly.

## License

This project is provided as-is. If you intend to redistribute or use commercially, add an explicit license file.
