import os
import yt_dlp
import sys
from pathlib import Path


def create_output_folder(output_path: str):
    """Create output folder if it doesn't exist."""
    os.makedirs(output_path, exist_ok=True)
    print(f"✓ Output folder ready: {output_path}\n")


def download_videos(urls: list, output_folder: str):
    """Download videos from YouTube in mp4 format."""
    os.makedirs(output_folder, exist_ok=True)

    ydl_opts = {
        # Prefer non-HLS MP4/DASH to avoid SABR/HLS fragment issues
        "format": "bestvideo[ext=mp4][protocol!=m3u8]+bestaudio[ext=m4a]/best[ext=mp4][protocol!=m3u8]/best",
        "outtmpl": os.path.join(output_folder, "%(title).200B.%(ext)s"),
        "quiet": False,
        "noprogress": False,
        "merge_output_format": "mp4",  # Ensure final output is mp4
        # Workaround for YouTube SABR streaming: use Android client to get direct URLs
        "extractor_args": {"youtube": {"player_client": ["android"]}},
        # Be resilient to transient errors
        "retries": 10,
        "fragment_retries": 10,
        "skip_unavailable_fragments": True,
    }

    print("=" * 60)
    print("DOWNLOADING VIDEOS FROM YOUTUBE")
    print("=" * 60)

    downloaded_files = []

    for url in urls:
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                print(f"\n➤ Downloading: {url}")
                info = ydl.extract_info(url, download=True)
                # Construct the full file path from the info
                title = info.get('title', 'Unknown')
                ext = info.get('ext', 'mp4')
                filename = os.path.join(output_folder, f"{title}.{ext}")
                
                # Verify the file exists
                if os.path.exists(filename):
                    downloaded_files.append(filename)
                    print(f"✓ Downloaded: {title}")
                else:
                    # Try to find the file with any extension
                    base_path = os.path.join(output_folder, title)
                    for file in os.listdir(output_folder):
                        if file.startswith(title):
                            full_path = os.path.join(output_folder, file)
                            downloaded_files.append(full_path)
                            print(f"✓ Downloaded: {title}")
                            break
        except Exception as e:
            print(f"✗ Error downloading {url}: {str(e)}")

    return downloaded_files


def main():
    """Main function to orchestrate the download process."""
    output_folder = "output"

    # Create output folder
    create_output_folder(output_folder)

    # Get user input for YouTube links
    print("=" * 60)
    print("YOUTUBE TO MP4 DOWNLOADER")
    print("=" * 60)
    print("\nEnter YouTube links separated by commas.")
    print("Example: https://www.youtube.com/watch?v=abc123, https://www.youtube.com/watch?v=def456\n")

    user_input = input("YouTube Links: ").strip()

    if not user_input:
        print("\n✗ No links provided. Exiting.")
        print("\nPress Enter to exit...")
        input()
        sys.exit(0)

    # Parse the URLs
    urls = [url.strip() for url in user_input.split(",")]
    urls = [url for url in urls if url]  # Remove empty strings

    if not urls:
        print("\n✗ No valid links found. Exiting.")
        print("\nPress Enter to exit...")
        input()
        sys.exit(0)

    print(f"\n✓ Found {len(urls)} link(s) to process")

    # Download videos
    video_files = download_videos(urls, output_folder)

    if video_files:
        print(f"\n✓ Successfully downloaded {len(video_files)} video(s)")
    else:
        print("\n✗ No videos were downloaded.")

    print("\n" + "=" * 60)
    print("PROCESS COMPLETED!")
    print(f"MP4 files saved to: {os.path.abspath(output_folder)}")
    print("=" * 60)
    print("\nPress Enter to exit...")
    input()


if __name__ == "__main__":
    main()
