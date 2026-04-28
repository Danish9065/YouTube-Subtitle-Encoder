# YouTube Subtitle Encoder

Free local tool that converts subtitles from a YouTube video or playlist into PDF files.

It uses:

- `yt-dlp` to read YouTube video, playlist, and subtitle data.
- `reportlab` to create PDFs locally.
- No paid API keys.

## Install

```bash
python3 -m pip install -r requirements.txt
```

If macOS shows an SSL certificate error, run:

```bash
python3 -m pip install --upgrade certifi
```

## Easy UI

On Mac, double-click:

```text
Run YouTube Subtitle Encoder.command
```

Or run it from Terminal:

```bash
cd ~/Desktop/ytsubtitles
python3 ytsubtitles_gui.py
```

Paste your YouTube video or playlist URL, keep `Use automatic captions` checked, then click `Generate PDF`.

## Export one video

```bash
python3 youtube_subtitle_encoder.py "https://www.youtube.com/watch?v=VIDEO_ID" --auto --timestamps
```

PDFs are saved in the `subtitles/` folder by default.

## Export a playlist

```bash
python3 youtube_subtitle_encoder.py "https://www.youtube.com/playlist?list=PLAYLIST_ID" --auto --timestamps
```

This creates one PDF per video.

## Create one combined playlist PDF

```bash
python3 youtube_subtitle_encoder.py "https://www.youtube.com/playlist?list=PLAYLIST_ID" --auto --timestamps --combined playlist-subtitles.pdf
```

## Pick a language

```bash
python3 youtube_subtitle_encoder.py "YOUTUBE_URL" --lang hi --auto
```

Language codes are usually short codes like `en`, `hi`, `es`, `fr`, `de`, or regional variants like `en-US`.

## See available subtitle languages

```bash
python3 youtube_subtitle_encoder.py "https://www.youtube.com/watch?v=VIDEO_ID" --list-languages
```

## Useful options

```text
--auto                 Use automatic captions if manual subtitles are missing
--timestamps           Include timestamps in the PDF
--combined FILE.pdf    Make one PDF for a whole playlist
--limit 5              Only process the first 5 playlist videos
--output folder        Choose the output folder
--lang en              Choose subtitle language
```

## Notes

- YouTube videos must have subtitles or automatic captions available.
- Private, members-only, age-restricted, or region-blocked videos may fail unless `yt-dlp` can access them.
- Very large playlists can take time because each video must be checked for captions.
- The `ffmpeg not found` warning is okay for subtitles. It matters for video/audio downloads, not PDF subtitles.
- The JavaScript runtime warning usually does not stop subtitle extraction if captions are listed.
- If YouTube returns `HTTP Error 429: Too Many Requests`, wait 15-30 minutes and run again. The app skips PDFs that already exist, so it will continue from the remaining videos.
