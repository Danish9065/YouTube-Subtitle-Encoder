# YouTube Subtitle Encoder

A free local desktop tool that converts subtitles from YouTube videos or playlists into PDF transcripts.

It works without any paid API. The app uses `yt-dlp` to read YouTube subtitle data and `reportlab` to generate PDF files locally on your computer.

## Features

- Convert subtitles from a YouTube video into a PDF.
- Convert subtitles from a YouTube playlist into separate PDFs.
- Create one combined PDF for a full playlist.
- Use manual subtitles when available.
- Use automatic captions when manual subtitles are missing.
- Include timestamps in the generated PDF.
- Simple GUI for non-terminal users.
- Free and local, with no paid API keys.

## Tech Stack

- Python
- yt-dlp
- ReportLab
- Tkinter

## Requirements

- Python 3.10 or newer
- Internet connection
- YouTube videos with subtitles or automatic captions available

## Installation

First download or clone this repository.

```bash
git clone https://github.com/Danish9065/YouTube-Subtitle-Encoder.git
cd YouTube-Subtitle-Encoder
```

Install dependencies:

```bash
python3 -m pip install -r requirements.txt
```

On Windows, if `python3` does not work, use:

```bash
python -m pip install -r requirements.txt
```

## Run the GUI

### macOS

Double-click:

```text
Run YouTube Subtitle Encoder.command
```

Or run from Terminal:

```bash
python3 ytsubtitles_gui.py
```

### Windows

Open Command Prompt or PowerShell inside the project folder and run:

```bash
python ytsubtitles_gui.py
```

### Linux

Open Terminal inside the project folder and run:

```bash
python3 ytsubtitles_gui.py
```

If Tkinter is missing on Linux, install it with your package manager:

```bash
sudo apt install python3-tk
```

## How to Use the GUI

1. Paste a YouTube video or playlist URL.
2. Choose a language code, for example `en`, `hi`, `es`, or `en-orig`.
3. Keep `Use automatic captions` enabled if the video has no manual subtitles.
4. Enable `Include timestamps` if you want timestamps in the PDF.
5. Enable `One combined playlist PDF` if you want one PDF for the full playlist.
6. Choose an output folder.
7. Click `Generate PDF`.

Generated files are saved in the selected output folder. By default, the app saves PDFs in:

```text
subtitles/
```

## Command Line Usage

Export subtitles from one video:

```bash
python3 youtube_subtitle_encoder.py "https://www.youtube.com/watch?v=VIDEO_ID" --auto --timestamps
```

Export subtitles from a playlist:

```bash
python3 youtube_subtitle_encoder.py "https://www.youtube.com/playlist?list=PLAYLIST_ID" --auto --timestamps
```

Create one combined PDF for a playlist:

```bash
python3 youtube_subtitle_encoder.py "https://www.youtube.com/playlist?list=PLAYLIST_ID" --auto --timestamps --combined playlist-subtitles.pdf
```

Use a specific language:

```bash
python3 youtube_subtitle_encoder.py "YOUTUBE_URL" --lang hi --auto
```

List available subtitle languages:

```bash
python3 youtube_subtitle_encoder.py "YOUTUBE_URL" --list-languages
```

On Windows, replace `python3` with `python` if needed.

## Useful Options

```text
--auto                 Use automatic captions if manual subtitles are missing
--timestamps           Include timestamps in the PDF
--combined FILE.pdf    Make one PDF for a whole playlist
--limit 5              Only process the first 5 playlist videos
--output folder        Choose the output folder
--lang en              Choose subtitle language
```

## Troubleshooting

If you see an SSL certificate error on macOS, run:

```bash
python3 -m pip install --upgrade certifi
```

If YouTube returns `HTTP Error 429: Too Many Requests`, wait 15-30 minutes and run the app again. Already-created PDFs are skipped, so the app can continue from the remaining videos.

If you see `ffmpeg not found`, you can ignore it for subtitle PDF generation. `ffmpeg` is mainly needed for video or audio downloading.

If the video shows `Manual subtitles: none`, enable automatic captions. Many YouTube videos only provide auto-generated captions.

Private, members-only, age-restricted, or region-blocked videos may fail unless `yt-dlp` can access them.

## License

This project is free to use and modify.
