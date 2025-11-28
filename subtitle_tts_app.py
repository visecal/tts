"""Desktop helper app for generating TTS clips from SRT files."""

import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import requests


DEFAULT_API_BASE = "http://localhost:5050"
SUPPORTED_FORMATS = ["mp3", "wav", "opus", "aac", "flac"]


def fetch_models(api_base: str):
    response = requests.get(f"{api_base}/v1/models", timeout=10)
    response.raise_for_status()
    payload = response.json()
    return [model["id"] for model in payload.get("models", [])]


def fetch_voices(api_base: str):
    response = requests.get(f"{api_base}/v1/audio/voices", timeout=10)
    response.raise_for_status()
    payload = response.json()
    return [voice["id"] if isinstance(voice, dict) else voice for voice in payload.get("voices", [])]


class SubtitleTTSApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Subtitle TTS Builder")
        self.geometry("520x440")

        self.api_base = tk.StringVar(value=DEFAULT_API_BASE)
        self.srt_path = tk.StringVar()
        self.output_dir = tk.StringVar(value=os.getcwd())
        self.voice = tk.StringVar()
        self.model = tk.StringVar()
        self.response_format = tk.StringVar(value=SUPPORTED_FORMATS[0])
        self.speed = tk.DoubleVar(value=1.0)
        self.max_workers = tk.IntVar(value=4)

        self.status_text = tk.StringVar(value="Ready")

        self._build_ui()
        threading.Thread(target=self._populate_options, daemon=True).start()

    def _build_ui(self):
        padding = {"padx": 10, "pady": 5, "sticky": "ew"}
        self.columnconfigure(1, weight=1)

        ttk.Label(self, text="API base URL").grid(row=0, column=0, **padding)
        ttk.Entry(self, textvariable=self.api_base).grid(row=0, column=1, columnspan=2, **padding)

        ttk.Label(self, text="SRT file").grid(row=1, column=0, **padding)
        ttk.Entry(self, textvariable=self.srt_path).grid(row=1, column=1, **padding)
        ttk.Button(self, text="Browse", command=self._pick_srt).grid(row=1, column=2, **padding)

        ttk.Label(self, text="Output folder").grid(row=2, column=0, **padding)
        ttk.Entry(self, textvariable=self.output_dir).grid(row=2, column=1, **padding)
        ttk.Button(self, text="Select", command=self._pick_output_dir).grid(row=2, column=2, **padding)

        ttk.Label(self, text="Model").grid(row=3, column=0, **padding)
        self.model_select = ttk.Combobox(self, textvariable=self.model, state="readonly")
        self.model_select.grid(row=3, column=1, columnspan=2, **padding)

        ttk.Label(self, text="Voice").grid(row=4, column=0, **padding)
        self.voice_select = ttk.Combobox(self, textvariable=self.voice, state="readonly")
        self.voice_select.grid(row=4, column=1, columnspan=2, **padding)

        ttk.Label(self, text="Format").grid(row=5, column=0, **padding)
        ttk.Combobox(
            self, textvariable=self.response_format, values=SUPPORTED_FORMATS, state="readonly"
        ).grid(row=5, column=1, columnspan=2, **padding)

        ttk.Label(self, text="Speed").grid(row=6, column=0, **padding)
        ttk.Scale(self, from_=0.5, to=1.5, variable=self.speed, orient=tk.HORIZONTAL).grid(
            row=6, column=1, columnspan=2, **padding
        )

        ttk.Label(self, text="Max workers").grid(row=7, column=0, **padding)
        ttk.Spinbox(self, from_=1, to=16, textvariable=self.max_workers, width=8).grid(
            row=7, column=1, **padding
        )

        ttk.Button(self, text="Generate", command=self._start_generation).grid(
            row=8, column=0, columnspan=3, pady=15
        )

        ttk.Label(self, textvariable=self.status_text, foreground="#444").grid(
            row=9, column=0, columnspan=3, **padding
        )

    def _pick_srt(self):
        path = filedialog.askopenfilename(filetypes=[("SubRip subtitles", "*.srt"), ("All files", "*.*")])
        if path:
            self.srt_path.set(path)

    def _pick_output_dir(self):
        path = filedialog.askdirectory()
        if path:
            self.output_dir.set(path)

    def _populate_options(self):
        try:
            models = fetch_models(self.api_base.get())
            voices = fetch_voices(self.api_base.get())
        except Exception as exc:
            self.status_text.set(f"Failed to load options: {exc}")
            return

        if models:
            self.model_select.configure(values=models)
            self.model.set(models[0])
        if voices:
            self.voice_select.configure(values=voices)
            self.voice.set(voices[0])

    def _start_generation(self):
        if not self.srt_path.get():
            messagebox.showerror("Missing file", "Please select an SRT file to process.")
            return

        if not os.path.exists(self.srt_path.get()):
            messagebox.showerror("File not found", "The selected SRT file does not exist.")
            return

        self.status_text.set("Generating audio clips...")
        threading.Thread(target=self._generate, daemon=True).start()

    def _generate(self):
        api_base = self.api_base.get().rstrip('/')
        endpoint = f"{api_base}/v1/subtitles/tts"

        try:
            with open(self.srt_path.get(), 'rb') as handle:
                response = requests.post(
                    endpoint,
                    files={'file': handle},
                    data={
                        'voice': self.voice.get(),
                        'response_format': self.response_format.get(),
                        'speed': str(self.speed.get()),
                        'max_workers': str(self.max_workers.get()),
                    },
                    timeout=120,
                )

            response.raise_for_status()

            output_path = os.path.join(self.output_dir.get(), 'subtitle_audio.zip')
            with open(output_path, 'wb') as outfile:
                outfile.write(response.content)

            self.status_text.set(f"Saved audio bundle to {output_path}")
        except Exception as exc:
            self.status_text.set(f"Generation failed: {exc}")
            messagebox.showerror("Error", str(exc))


if __name__ == "__main__":
    app = SubtitleTTSApp()
    app.mainloop()

