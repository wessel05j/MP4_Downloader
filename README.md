# YouTube to MP4 Downloader

A simple Python application that downloads videos from YouTube in high-quality MP4 format.

## Features

- ✓ Download multiple YouTube videos at once
- ✓ Download videos in best available MP4 quality
- ✓ Automatic output folder creation
- ✓ Easy-to-use command-line interface
- ✓ Windows batch launcher included

## Requirements

Before using this tool, ensure you have the following installed:

1. **Python 3.7+** - Download from [python.org](https://www.python.org/)

### Quick Setup

The `launch.bat` file automatically handles Python package installation! It will:
- Create a virtual environment (venv) if it doesn't exist
- Install all required packages from `requirements.txt`
- Run the MP4 downloader

### Manual Setup (Optional)

If you prefer to set up manually without using the batch file:

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment (Windows)
venv\Scripts\activate.bat

# Install required packages
pip install -r requirements.txt

# Run the application
python MP4.py
```

## Usage

### Option 1: Using the Batch Launcher (Recommended)
Double-click `launch.bat` to start the application.

### Option 2: Using Command Prompt/PowerShell
Navigate to the folder and run:
```bash
python MP4.py
```

### Instructions

1. When prompted, enter one or more YouTube links separated by commas
2. Example:
   ```
   https://www.youtube.com/watch?v=dQw4w9WgXcQ, https://www.youtube.com/watch?v=jNQXAC9IVRw
   ```
3. Press Enter to start the download process
4. The MP4 files will be saved in the `output` folder
5. Press Enter again to exit the application

## File Structure

```
MP4_Downloader/
├── MP4.py                 # Main Python script
├── launch.bat            # Windows batch launcher (handles venv setup)
├── requirements.txt      # Python package dependencies
├── README.md             # This file
├── venv/                 # Virtual environment (created automatically)
└── output/               # Output folder (created automatically)
```

## Output Quality

The application uses the following settings for best quality:

- **Video Download**: Best available MP4 format with highest resolution and quality
- **Format**: MP4 (H.264 video with AAC audio when available)

## Troubleshooting

### yt-dlp not found
- Run `pip install yt-dlp` to install the required package
- Make sure you've run the `launch.bat` file at least once

### Video download fails
- Check that you have a stable internet connection
- Verify the YouTube URL is correct and the video is available
- Some videos may be restricted by geographic location or copyright
- Try a different video URL to ensure the tool is working correctly
 - If you see messages like:
    - `Some web client https formats have been skipped as they are missing a url. YouTube is forcing SABR streaming for this client.`
    - `fragment not found; Skipping fragment ...`
    This is due to YouTube's SABR streaming for certain web clients. The downloader is configured to use the Android player client and avoid HLS formats, which resolves this. If issues persist, update `yt-dlp` and retry.

### Insufficient disk space
- Ensure you have enough disk space for video downloads
- Check the output folder and clear old files if needed

## Notes

- The output folder is created automatically if it doesn't exist
- MP4 files are saved with the original video title
- Videos are downloaded in the best available MP4 quality
- Be mindful of copyright and only download content you have the right to download

## License

This tool is for personal use and educational purposes only. Users are responsible for respecting copyright and intellectual property rights.
