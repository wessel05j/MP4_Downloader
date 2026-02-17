from __future__ import annotations

import argparse
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple
from urllib.parse import parse_qs, urlparse

import yt_dlp
from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, TextColumn
from rich.prompt import Confirm
from rich.table import Table

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
SYSTEM_DIR = BASE_DIR / "system"

DEFAULT_BROWSERS = ("edge", "chrome", "firefox", "brave", "opera", "vivaldi")
VIDEO_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{11}$")
VALID_VIDEO_EXTENSIONS = {".mp4", ".mkv", ".webm", ".mov"}
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)


class _SilentYDLLogger:
    def debug(self, _: str) -> None:
        return None

    def warning(self, _: str) -> None:
        return None

    def error(self, _: str) -> None:
        return None


@dataclass
class CookieSource:
    mode: str
    value: Optional[Any]
    description: str


@dataclass
class DownloadResult:
    url: str
    success: bool
    title: str
    output_file: Optional[Path]
    strategy: str
    error: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download YouTube links to the output folder in the highest available quality."
    )
    parser.add_argument(
        "urls",
        nargs="*",
        help="Optional YouTube links or video IDs. If omitted, interactive input is used.",
    )
    parser.add_argument(
        "--links-file",
        type=Path,
        help="Optional text file containing YouTube links.",
    )
    parser.add_argument(
        "--no-confirm",
        action="store_true",
        help="Start downloads without the interactive confirmation prompt.",
    )
    return parser.parse_args()


def ensure_runtime_folders() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    SYSTEM_DIR.mkdir(parents=True, exist_ok=True)


def normalize_video_url(raw_url: str) -> str:
    value = (raw_url or "").strip().strip('"').strip("'").strip(",")
    if not value:
        return ""

    if VIDEO_ID_PATTERN.fullmatch(value):
        return f"https://www.youtube.com/watch?v={value}"

    if value.startswith("youtube.com/") or value.startswith("youtu.be/") or value.startswith("www.youtube.com/"):
        value = f"https://{value}"

    try:
        parsed = urlparse(value)
    except Exception:
        return ""

    netloc = parsed.netloc.lower()
    path = parsed.path or ""

    if "youtu.be" in netloc:
        candidate = path.strip("/").split("/")[0]
        if VIDEO_ID_PATTERN.fullmatch(candidate):
            return f"https://www.youtube.com/watch?v={candidate}"
        return ""

    if "youtube.com" in netloc:
        if path == "/watch":
            query = parse_qs(parsed.query)
            candidate = (query.get("v") or [None])[0]
            if candidate and VIDEO_ID_PATTERN.fullmatch(candidate):
                return f"https://www.youtube.com/watch?v={candidate}"
            return ""

        parts = [part for part in path.split("/") if part]
        if len(parts) >= 2 and parts[0] in {"shorts", "embed", "live"}:
            candidate = parts[1]
            if VIDEO_ID_PATTERN.fullmatch(candidate):
                return f"https://www.youtube.com/watch?v={candidate}"
            return ""

    return ""


def extract_urls(raw_text: str) -> List[str]:
    candidates: List[str] = []
    for piece in re.split(r"[\s,]+", raw_text or ""):
        cleaned = piece.strip().strip('"').strip("'").strip("<>").strip("[](){}")
        if not cleaned:
            continue
        normalized = normalize_video_url(cleaned)
        if normalized:
            candidates.append(normalized)

    seen: set[str] = set()
    deduped: List[str] = []
    for url in candidates:
        if url in seen:
            continue
        seen.add(url)
        deduped.append(url)
    return deduped


def collect_raw_input(console: Console, args: argparse.Namespace) -> str:
    chunks: List[str] = []
    if args.links_file:
        if not args.links_file.exists():
            raise FileNotFoundError(f"Links file does not exist: {args.links_file}")
        chunks.append(args.links_file.read_text(encoding="utf-8"))
    if args.urls:
        chunks.append(" ".join(args.urls))
    if chunks:
        return "\n".join(chunks)

    console.print(
        Panel.fit(
            "Paste one or more YouTube links.\n"
            "You can paste multiple lines or comma-separated links.\n"
            "Press Enter on an empty line to start.",
            title="Input",
        )
    )

    lines: List[str] = []
    while True:
        line = console.input("[bold cyan]link[/bold cyan]> ").strip()
        if not line:
            break
        lines.append(line)
    return "\n".join(lines)


def _to_int(value: Any) -> int:
    try:
        return int(value)
    except Exception:
        return 0


def _to_float(value: Any) -> float:
    try:
        return float(value)
    except Exception:
        return 0.0


def _stream_sort_key(fmt: Dict[str, Any]) -> Tuple[int, float, float, int]:
    return (
        _to_int(fmt.get("height")),
        _to_float(fmt.get("fps")),
        _to_float(fmt.get("tbr") or fmt.get("vbr")),
        _to_int(fmt.get("filesize") or fmt.get("filesize_approx")),
    )


def choose_download_format(extracted_info: Dict[str, Any]) -> Tuple[str, str]:
    formats = extracted_info.get("formats") or []
    if not isinstance(formats, list):
        return "bestvideo*+bestaudio/bestvideo+bestaudio/best", "generic-best"

    video_only: List[Dict[str, Any]] = []
    progressive: List[Dict[str, Any]] = []

    for fmt in formats:
        if not isinstance(fmt, dict):
            continue
        if not fmt.get("format_id"):
            continue
        if fmt.get("has_drm"):
            continue

        vcodec = fmt.get("vcodec")
        acodec = fmt.get("acodec")
        has_video = vcodec not in (None, "none")
        has_audio = acodec not in (None, "none")

        if has_video and not has_audio:
            video_only.append(fmt)
        elif has_video and has_audio:
            progressive.append(fmt)

    if video_only:
        video_only.sort(key=_stream_sort_key, reverse=True)
        best = video_only[0]
        fmt_id = str(best["format_id"])
        height = _to_int(best.get("height"))
        return (
            f"{fmt_id}+bestaudio[acodec!=none]/{fmt_id}+bestaudio/{fmt_id}/best",
            f"video-only {height}p",
        )

    if progressive:
        progressive.sort(key=_stream_sort_key, reverse=True)
        best = progressive[0]
        fmt_id = str(best["format_id"])
        height = _to_int(best.get("height"))
        return fmt_id, f"progressive {height}p"

    return "bestvideo*+bestaudio/bestvideo+bestaudio/best", "generic-best"


def find_cookie_file() -> Optional[Path]:
    for candidate in (
        BASE_DIR / "cookies.txt",
        SYSTEM_DIR / "cookies.txt",
        BASE_DIR / "resources" / "cookies.txt",
    ):
        if candidate.exists() and candidate.stat().st_size > 0:
            return candidate
    return None


def browser_cookie_source_is_valid(browser: str) -> bool:
    test_opts: Dict[str, Any] = {
        "quiet": True,
        "skip_download": True,
        "extract_flat": "in_playlist",
        "playlist_items": "1",
        "cookiesfrombrowser": (browser,),
        "ignoreerrors": True,
        "no_warnings": True,
        "ignoreconfig": True,
        "logger": _SilentYDLLogger(),
    }
    try:
        with yt_dlp.YoutubeDL(test_opts) as ydl:
            result = ydl.extract_info("https://www.youtube.com/@YouTube/videos", download=False)
        if result and (result.get("entries") or result.get("id")):
            return True
    except Exception:
        return False
    return False


def detect_cookie_source() -> CookieSource:
    cookie_file = find_cookie_file()
    if cookie_file:
        return CookieSource(
            mode="file",
            value=str(cookie_file),
            description=f"cookie file: {cookie_file}",
        )

    for browser in DEFAULT_BROWSERS:
        if browser_cookie_source_is_valid(browser):
            return CookieSource(
                mode="browser",
                value=(browser,),
                description=f"browser cookies: {browser}",
            )

    return CookieSource(mode="none", value=None, description="no cookies detected")


def apply_cookie_source(ydl_opts: Dict[str, Any], cookie_source: CookieSource, use_cookies: bool) -> None:
    ydl_opts.pop("cookiefile", None)
    ydl_opts.pop("cookiesfrombrowser", None)
    if not use_cookies:
        return

    if cookie_source.mode == "file" and cookie_source.value:
        ydl_opts["cookiefile"] = str(cookie_source.value)
    elif cookie_source.mode == "browser" and cookie_source.value:
        ydl_opts["cookiesfrombrowser"] = cookie_source.value


def download_strategies() -> List[Dict[str, Any]]:
    return [
        {
            "name": "cookies-desktop-clients",
            "use_cookies": True,
            "extractor_args": {"youtube": {"player_client": ["tv_downgraded", "web", "web_safari"]}},
        },
        {
            "name": "cookies-mobile-clients",
            "use_cookies": True,
            "extractor_args": {"youtube": {"player_client": ["ios_downgraded", "android_vr", "web"]}},
        },
        {
            "name": "no-cookies-mobile",
            "use_cookies": False,
            "extractor_args": {"youtube": {"player_client": ["ios_downgraded", "android_vr"]}},
        },
        {
            "name": "no-cookies-default",
            "use_cookies": False,
            "extractor_args": {"youtube": {"player_client": ["android", "web"]}},
        },
    ]


def base_download_options() -> Dict[str, Any]:
    return {
        "merge_output_format": "mp4",
        "outtmpl": str(OUTPUT_DIR / "%(title).200B.%(ext)s"),
        "quiet": True,
        "noprogress": True,
        "noplaylist": True,
        "socket_timeout": 60,
        "retries": 15,
        "fragment_retries": 15,
        "skip_unavailable_fragments": True,
        "ignoreerrors": False,
        "allow_unplayable_formats": False,
        "ignoreconfig": True,
        "http_headers": {
            "User-Agent": USER_AGENT,
            "Accept-Language": "en-us,en;q=0.5",
        },
        "postprocessors": [{"key": "FFmpegVideoConvertor", "preferedformat": "mp4"}],
        "logger": _SilentYDLLogger(),
    }


def snapshot_output_folder() -> Dict[str, int]:
    snapshot: Dict[str, int] = {}
    for path in OUTPUT_DIR.glob("*"):
        if path.is_file():
            snapshot[str(path.resolve())] = path.stat().st_size
    return snapshot


def find_new_video_files(before: Dict[str, int]) -> List[Path]:
    created: List[Path] = []
    for path in OUTPUT_DIR.glob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in VALID_VIDEO_EXTENSIONS:
            continue
        if path.suffix.lower() in {".part", ".ytdl"}:
            continue

        resolved = str(path.resolve())
        size = path.stat().st_size
        if resolved not in before or before[resolved] != size:
            created.append(path)
    created.sort(key=lambda item: item.stat().st_mtime, reverse=True)
    return created


def resolve_output_from_info(info: Any) -> Optional[Path]:
    if not isinstance(info, dict):
        return None

    raw_candidates: List[Path] = []
    for key in ("filepath", "_filename"):
        value = info.get(key)
        if isinstance(value, str) and value.strip():
            raw_candidates.append(Path(value))

    requested = info.get("requested_downloads")
    if isinstance(requested, list):
        for entry in requested:
            if not isinstance(entry, dict):
                continue
            value = entry.get("filepath")
            if isinstance(value, str) and value.strip():
                raw_candidates.append(Path(value))

    checked: List[Path] = []
    for candidate in raw_candidates:
        checked.append(candidate)
        if candidate.suffix.lower() != ".mp4":
            checked.append(candidate.with_suffix(".mp4"))
        checked.append(OUTPUT_DIR / candidate.name)

    for candidate in checked:
        if candidate.exists() and candidate.is_file() and candidate.suffix.lower() in VALID_VIDEO_EXTENSIONS:
            return candidate
    return None


def probe_format(url: str, ydl_opts: Dict[str, Any]) -> Tuple[str, str]:
    probe_opts = dict(ydl_opts)
    probe_opts.update(
        {
            "skip_download": True,
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
        }
    )
    with yt_dlp.YoutubeDL(probe_opts) as ydl:
        info = ydl.extract_info(url, download=False)
    if not isinstance(info, dict):
        return "bestvideo*+bestaudio/bestvideo+bestaudio/best", "generic-best"
    return choose_download_format(info)


def summarize_exception(exc: Exception) -> str:
    text = str(exc).strip()
    if not text:
        return exc.__class__.__name__
    first_line = text.splitlines()[0]
    if len(first_line) > 180:
        return f"{first_line[:177]}..."
    return first_line


def format_bytes(value: Any) -> str:
    size = _to_float(value)
    if size <= 0:
        return "0 B"
    units = ("B", "KB", "MB", "GB", "TB")
    unit_index = 0
    while size >= 1024 and unit_index < len(units) - 1:
        size /= 1024.0
        unit_index += 1
    if unit_index == 0:
        return f"{int(size)} {units[unit_index]}"
    return f"{size:.1f} {units[unit_index]}"


def format_eta(seconds: Any) -> str:
    eta = _to_int(seconds)
    if eta <= 0:
        return "-"
    hours, remainder = divmod(eta, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours > 0:
        return f"{hours:d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def create_progress_hook(progress: Progress, task_id: int, strategy_name: str) -> Callable[[Dict[str, Any]], None]:
    def hook(data: Dict[str, Any]) -> None:
        status = data.get("status")
        if status == "downloading":
            downloaded = _to_float(data.get("downloaded_bytes"))
            total = _to_float(data.get("total_bytes") or data.get("total_bytes_estimate"))
            speed_text = f"{format_bytes(data.get('speed'))}/s" if data.get("speed") else "-"
            eta_text = format_eta(data.get("eta"))

            if total > 0:
                percent = min(100.0, (downloaded / total) * 100.0)
                progress.update(
                    task_id,
                    total=total,
                    completed=min(downloaded, total),
                    description=f"[cyan]Downloading ({strategy_name})[/cyan]",
                    percent=f"{percent:5.1f}%",
                    speed=speed_text,
                    eta=eta_text,
                )
            else:
                progress.update(
                    task_id,
                    total=None,
                    completed=0,
                    description=f"[cyan]Downloading ({strategy_name}) {format_bytes(downloaded)}[/cyan]",
                    percent="  ?  %",
                    speed=speed_text,
                    eta=eta_text,
                )
        elif status == "finished":
            progress.update(
                task_id,
                description=f"[yellow]Download complete, merging ({strategy_name})...[/yellow]",
                percent="100.0%",
                speed="-",
                eta="-",
            )

    return hook


def download_video(url: str, cookie_source: CookieSource, progress: Progress, task_id: int) -> DownloadResult:
    before = snapshot_output_folder()
    last_error = "unknown download error"

    for strategy in download_strategies():
        progress.update(
            task_id,
            total=100,
            completed=0,
            description=f"[cyan]Preparing strategy: {strategy['name']}[/cyan]",
            percent="  0.0%",
            speed="-",
            eta="-",
        )

        ydl_opts = dict(base_download_options())
        extractor_args = strategy.get("extractor_args")
        if extractor_args:
            ydl_opts["extractor_args"] = extractor_args

        apply_cookie_source(ydl_opts, cookie_source, use_cookies=bool(strategy.get("use_cookies", True)))

        try:
            selected_format, format_strategy = probe_format(url, ydl_opts)
            ydl_opts["format"] = selected_format
        except Exception as exc:
            selected_format = "bestvideo*+bestaudio/bestvideo+bestaudio/best"
            format_strategy = "generic-best"
            last_error = f"format probe failed: {summarize_exception(exc)}"
            ydl_opts["format"] = selected_format

        strategy_name = f"{strategy['name']} | {format_strategy}"
        ydl_opts["progress_hooks"] = [create_progress_hook(progress, task_id, strategy_name)]
        progress.update(
            task_id,
            description=f"[cyan]Starting download ({strategy_name})[/cyan]",
            percent="  0.0%",
            speed="-",
            eta="-",
            total=100,
            completed=0,
        )

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
        except Exception as exc:
            last_error = summarize_exception(exc)
            progress.update(
                task_id,
                description=f"[yellow]Retrying with next strategy after error: {last_error}[/yellow]",
                percent="  0.0%",
                speed="-",
                eta="-",
                total=100,
                completed=0,
            )
            continue

        new_files = find_new_video_files(before)
        output_file = new_files[0] if new_files else resolve_output_from_info(info)
        if output_file is None:
            last_error = "yt-dlp finished but no output file was created"
            continue

        if output_file.stat().st_size < 10_000:
            last_error = f"downloaded file was too small: {output_file.name}"
            output_file.unlink(missing_ok=True)
            continue

        title = output_file.stem
        if isinstance(info, dict):
            title = str(info.get("title") or title)
        progress.update(
            task_id,
            total=100,
            completed=100,
            description=f"[green]Finished: {output_file.name}[/green]",
            percent="100.0%",
            speed="-",
            eta="-",
        )
        return DownloadResult(
            url=url,
            success=True,
            title=title,
            output_file=output_file,
            strategy=strategy_name,
            error="",
        )

    return DownloadResult(
        url=url,
        success=False,
        title="",
        output_file=None,
        strategy="all strategies failed",
        error=last_error,
    )


def render_runtime_table(cookie_source: CookieSource, ffmpeg_found: bool) -> Table:
    table = Table(title="Runtime")
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="white")
    table.add_row("Output folder", str(OUTPUT_DIR.resolve()))
    table.add_row("Cookie mode", cookie_source.description)
    table.add_row("ffmpeg in PATH", "yes" if ffmpeg_found else "no (required for reliable mp4 merging)")
    return table


def render_queue_table(urls: Sequence[str]) -> Table:
    table = Table(title="Download Queue")
    table.add_column("#", style="cyan", justify="right")
    table.add_column("YouTube URL", style="white")
    for index, url in enumerate(urls, start=1):
        table.add_row(str(index), url)
    return table


def render_results_table(results: Sequence[DownloadResult]) -> Table:
    table = Table(title="Results")
    table.add_column("#", style="cyan", justify="right")
    table.add_column("Status")
    table.add_column("Title")
    table.add_column("File")
    table.add_column("Details")

    for index, result in enumerate(results, start=1):
        status = "[green]OK[/green]" if result.success else "[red]FAILED[/red]"
        file_name = result.output_file.name if result.output_file else "-"
        details = result.strategy if result.success else result.error
        table.add_row(str(index), status, result.title or "-", file_name, details)
    return table


def run() -> int:
    args = parse_args()
    console = Console()
    ensure_runtime_folders()

    console.print(
        Panel.fit(
            "MP4 Downloader\n"
            "Automatic cookie detection + highest quality fallback downloader.",
            title="YouTube to MP4",
        )
    )

    ffmpeg_found = shutil.which("ffmpeg") is not None
    with console.status("[bold cyan]Detecting cookie source...[/bold cyan]"):
        cookie_source = detect_cookie_source()
    console.print(render_runtime_table(cookie_source, ffmpeg_found))

    try:
        raw_input = collect_raw_input(console, args)
    except FileNotFoundError as exc:
        console.print(f"[red]{exc}[/red]")
        return 1

    urls = extract_urls(raw_input)
    if not urls:
        console.print("[red]No valid YouTube video links were found.[/red]")
        return 1

    console.print(render_queue_table(urls))
    if not args.no_confirm and not Confirm.ask("Start download now?", default=True):
        console.print("Canceled.")
        return 0

    results: List[DownloadResult] = []
    total = len(urls)
    for index, url in enumerate(urls, start=1):
        console.print(f"[bold]Video {index}/{total}[/bold] {url}")
        with Progress(
            TextColumn("{task.description}"),
            BarColumn(bar_width=40),
            TextColumn("[bold]{task.fields[percent]}[/bold]"),
            TextColumn("speed: {task.fields[speed]}"),
            TextColumn("eta: {task.fields[eta]}"),
            console=console,
            expand=True,
        ) as progress:
            task_id = progress.add_task(
                "[cyan]Preparing...[/cyan]",
                total=100,
                completed=0,
                percent="  0.0%",
                speed="-",
                eta="-",
            )
            result = download_video(url, cookie_source, progress, task_id)
        results.append(result)
        if result.success and result.output_file:
            console.print(f"[green]OK[/green] {result.title} -> {result.output_file.name}")
        else:
            console.print(f"[red]FAILED[/red] {url} -> {result.error}")

    success_count = sum(1 for result in results if result.success)
    failed_count = total - success_count

    console.print(render_results_table(results))
    console.print(f"Completed. Success: {success_count} | Failed: {failed_count}")
    console.print(f"Output folder: {OUTPUT_DIR.resolve()}")

    if success_count == 0:
        return 1
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
        raise SystemExit(130)
