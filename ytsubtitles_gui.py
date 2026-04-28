#!/usr/bin/env python3
"""
Simple desktop UI for YouTube Subtitle Encoder.
"""

from __future__ import annotations

import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from youtube_subtitle_encoder import (
    fetch_video_captions,
    resolve_video_jobs,
    safe_filename,
    write_combined_pdf,
    write_pdf,
)


class SubtitleEncoderApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("YouTube Subtitle Encoder")
        self.geometry("760x560")
        self.minsize(680, 500)

        self.messages: queue.Queue[tuple[str, str]] = queue.Queue()
        self.worker: threading.Thread | None = None

        self.url_var = tk.StringVar()
        self.lang_var = tk.StringVar(value="en")
        self.output_var = tk.StringVar(value=str(Path.cwd() / "subtitles"))
        self.auto_var = tk.BooleanVar(value=True)
        self.timestamps_var = tk.BooleanVar(value=True)
        self.combined_var = tk.BooleanVar(value=False)
        self.combined_name_var = tk.StringVar(value="playlist-subtitles.pdf")
        self.limit_var = tk.StringVar()

        self._build_ui()
        self.after(120, self._drain_messages)

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        root = ttk.Frame(self, padding=18)
        root.grid(row=0, column=0, sticky="nsew")
        root.columnconfigure(1, weight=1)
        root.rowconfigure(8, weight=1)

        title = ttk.Label(root, text="YouTube Subtitle Encoder", font=("Helvetica", 20, "bold"))
        title.grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 14))

        ttk.Label(root, text="YouTube video or playlist URL").grid(row=1, column=0, sticky="w", pady=6)
        ttk.Entry(root, textvariable=self.url_var).grid(row=1, column=1, columnspan=2, sticky="ew", pady=6)

        ttk.Label(root, text="Language code").grid(row=2, column=0, sticky="w", pady=6)
        lang_row = ttk.Frame(root)
        lang_row.grid(row=2, column=1, columnspan=2, sticky="ew", pady=6)
        lang_row.columnconfigure(0, weight=0)
        lang_row.columnconfigure(1, weight=1)
        ttk.Combobox(
            lang_row,
            textvariable=self.lang_var,
            values=("en", "en-orig", "hi", "ur", "es", "fr", "de", "ar", "pt", "zh-Hans"),
            width=14,
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(lang_row, text="Use en for English, hi for Hindi, or en-orig for original English captions.").grid(
            row=0,
            column=1,
            sticky="w",
            padx=(12, 0),
        )

        ttk.Label(root, text="Output folder").grid(row=3, column=0, sticky="w", pady=6)
        ttk.Entry(root, textvariable=self.output_var).grid(row=3, column=1, sticky="ew", pady=6)
        ttk.Button(root, text="Choose", command=self._choose_output).grid(row=3, column=2, sticky="ew", padx=(8, 0))

        options = ttk.Frame(root)
        options.grid(row=4, column=0, columnspan=3, sticky="ew", pady=(10, 4))
        ttk.Checkbutton(options, text="Use automatic captions", variable=self.auto_var).grid(row=0, column=0, sticky="w")
        ttk.Checkbutton(options, text="Include timestamps", variable=self.timestamps_var).grid(
            row=0,
            column=1,
            sticky="w",
            padx=(22, 0),
        )
        ttk.Checkbutton(options, text="One combined playlist PDF", variable=self.combined_var).grid(
            row=0,
            column=2,
            sticky="w",
            padx=(22, 0),
        )

        ttk.Label(root, text="Combined PDF name").grid(row=5, column=0, sticky="w", pady=6)
        ttk.Entry(root, textvariable=self.combined_name_var).grid(row=5, column=1, sticky="ew", pady=6)

        ttk.Label(root, text="Playlist limit").grid(row=6, column=0, sticky="w", pady=6)
        limit_row = ttk.Frame(root)
        limit_row.grid(row=6, column=1, columnspan=2, sticky="ew", pady=6)
        ttk.Entry(limit_row, textvariable=self.limit_var, width=12).grid(row=0, column=0, sticky="w")
        ttk.Label(limit_row, text="Leave empty for all videos.").grid(row=0, column=1, sticky="w", padx=(12, 0))

        actions = ttk.Frame(root)
        actions.grid(row=7, column=0, columnspan=3, sticky="ew", pady=(12, 10))
        actions.columnconfigure(0, weight=1)
        self.generate_button = ttk.Button(actions, text="Generate PDF", command=self._start_generate)
        self.generate_button.grid(row=0, column=0, sticky="ew")

        log_frame = ttk.LabelFrame(root, text="Status")
        log_frame.grid(row=8, column=0, columnspan=3, sticky="nsew")
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        self.log = tk.Text(log_frame, height=12, wrap="word", state="disabled")
        self.log.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(log_frame, orient="vertical", command=self.log.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.log.configure(yscrollcommand=scroll.set)

        self._log("Paste a YouTube URL, choose options, then click Generate PDF.")

    def _choose_output(self) -> None:
        folder = filedialog.askdirectory(initialdir=self.output_var.get() or str(Path.cwd()))
        if folder:
            self.output_var.set(folder)

    def _start_generate(self) -> None:
        if self.worker and self.worker.is_alive():
            return

        url = self.url_var.get().strip()
        if not url:
            messagebox.showerror("Missing URL", "Paste a YouTube video or playlist URL first.")
            return

        try:
            limit = int(self.limit_var.get()) if self.limit_var.get().strip() else None
            if limit is not None and limit < 1:
                raise ValueError
        except ValueError:
            messagebox.showerror("Invalid limit", "Playlist limit must be a whole number, or blank.")
            return

        config = {
            "url": url,
            "language": self.lang_var.get().strip() or "en",
            "output": Path(self.output_var.get()).expanduser(),
            "allow_auto": self.auto_var.get(),
            "timestamps": self.timestamps_var.get(),
            "combined": self.combined_var.get(),
            "combined_name": self.combined_name_var.get().strip() or "playlist-subtitles.pdf",
            "limit": limit,
        }

        self.generate_button.configure(state="disabled")
        self._log("")
        self._log("Starting...")
        self.worker = threading.Thread(target=self._generate_worker, args=(config,), daemon=True)
        self.worker.start()

    def _generate_worker(self, config: dict) -> None:
        try:
            output_dir = config["output"].resolve()
            output_dir.mkdir(parents=True, exist_ok=True)
            self.messages.put(("log", f"Output folder: {output_dir}"))

            jobs = resolve_video_jobs(config["url"], config["limit"])
            self.messages.put(("log", f"Found {len(jobs)} video(s)."))

            rendered = []
            for index, video in enumerate(jobs, start=1):
                if not config["combined"]:
                    expected_path = output_dir / f"{safe_filename(video.title, video.video_id)}.{config['language']}.pdf"
                    if expected_path.exists():
                        self.messages.put(("log", f"[{index}/{len(jobs)}] Skipping existing PDF: {expected_path.name}"))
                        continue

                self.messages.put(("log", f"[{index}/{len(jobs)}] Reading subtitles: {video.title}"))
                title, captions, auto_caption = fetch_video_captions(
                    video,
                    config["language"],
                    config["allow_auto"],
                )
                rendered.append((video, title, captions, auto_caption))

                if not config["combined"]:
                    output_path = output_dir / f"{safe_filename(title, video.video_id)}.{config['language']}.pdf"
                    write_pdf(
                        output_path,
                        title,
                        video.url,
                        captions,
                        config["language"],
                        config["timestamps"],
                        auto_caption,
                    )
                    self.messages.put(("log", f"Saved: {output_path}"))

            if config["combined"]:
                combined_name = config["combined_name"]
                if not combined_name.lower().endswith(".pdf"):
                    combined_name += ".pdf"
                output_path = output_dir / combined_name
                write_combined_pdf(output_path, rendered, config["language"], config["timestamps"])
                self.messages.put(("log", f"Saved combined PDF: {output_path}"))

            self.messages.put(("done", "Finished. Your PDF file is ready."))
        except Exception as exc:
            self.messages.put(("error", str(exc)))

    def _drain_messages(self) -> None:
        try:
            while True:
                kind, text = self.messages.get_nowait()
                if kind == "log":
                    self._log(text)
                elif kind == "done":
                    self._log(text)
                    self.generate_button.configure(state="normal")
                    messagebox.showinfo("Done", text)
                elif kind == "error":
                    self._log(f"Error: {text}")
                    self.generate_button.configure(state="normal")
                    messagebox.showerror("Error", text)
        except queue.Empty:
            pass
        self.after(120, self._drain_messages)

    def _log(self, text: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", text + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")


def main() -> None:
    app = SubtitleEncoderApp()
    app.mainloop()


if __name__ == "__main__":
    main()
