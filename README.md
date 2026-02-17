# MP4 Downloader

A YouTube-to-MP4 downloader with automatic cookie setup, high-quality format selection, and a cleaner terminal interface.

## What this version does

- Downloads all pasted YouTube video links in one run.
- Chooses the highest quality stream available (video+audio) with fallback strategies.
- Converts/merges to MP4 output.
- Detects cookies automatically:
  - `cookies.txt` (project root)
  - `system/cookies.txt`
  - browser cookies (`edge`, `chrome`, `firefox`, `brave`, `opera`, `vivaldi`)
- Uses a one-command bootstrap flow via `run.bat` or `run.ps1`.

## Requirements

- Python 3.10+
- ffmpeg in PATH (strongly recommended for reliable MP4 merging)

## Quick Start (Windows)

### Option 1: Double-click launcher

1. Open this folder.
2. Double-click `run.bat`.

### Option 2: PowerShell launcher

```powershell
.\run.ps1
```

If execution policy blocks scripts, run:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\run.ps1
```

## What the launchers do automatically

On first run, they will:

1. Create `venv` if missing.
2. Activate the virtual environment.
3. Install/update dependencies from `requirements.txt` through `setup_env.py`.
4. Start `MP4.py`.

## Usage

When the app starts:

1. Paste YouTube links (one per line, space-separated, or comma-separated).
2. Press Enter on an empty line.
3. Confirm the queue and start download.
4. Files are saved to `output/`.

## Optional CLI usage

```powershell
python MP4.py "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
```

```powershell
python MP4.py --links-file .\my_links.txt --no-confirm
```

## Automatic cookie setup

No manual yt-dlp cookie flags are required.

At startup, MP4 Downloader checks cookie sources in this order:

1. `cookies.txt`
2. `system/cookies.txt`
3. browser cookies (`cookiesfrombrowser`)

If no cookies are available, downloads still run, but some restricted/private videos may fail.

## Output location

- Video output: `output/`
- Setup cache: `system/setup_state.json`

## Troubleshooting

### Download fails on many links

- Update dependencies by rerunning `run.bat`.
- Make sure yt-dlp is current.
- Retry with browser closed if cookie decryption fails.

### MP4 merging fails

- Install ffmpeg and ensure `ffmpeg` is in PATH.

### No links detected

- Paste full YouTube video URLs or valid 11-char video IDs.

## Legal note

Use this tool only for content you have rights to download.
