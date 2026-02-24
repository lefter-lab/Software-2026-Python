from __future__ import annotations

import queue
import os
import re
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# =========================
# MINIMAL PORTABLE CHANGES
# =========================
def get_default_ffprobe() -> str:
    """
    Priority:
    1) If running from a PyInstaller bundle, use _MEIPASS/ffmpeg/ffprobe.exe
    2) Otherwise rely on PATH ("ffprobe")
    """
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        cand = Path(meipass) / "ffmpeg" / "ffprobe.exe"
        if cand.exists():
            return str(cand)
    return "ffprobe"


FFPROBE_PATH = get_default_ffprobe()
# =========================

SUPPORTED_AUDIO_EXTS = {".wav", ".mp3", ".ogg", ".flac", ".m4a", ".aac"}
MAX_QUEUE = 300

# Optional drag & drop
HAS_DND = False
try:
    from tkinterdnd2 import DND_FILES, TkinterDnD  # type: ignore
    HAS_DND = True
except Exception:
    HAS_DND = False
    TkinterDnD = None
    DND_FILES = None

PROG_RE = re.compile(
    r"whisper_print_progress_callback:\s*progress\s*=\s*([0-9]+(?:\.[0-9]+)?)%?",
    re.IGNORECASE
)


def fmt_interval(seconds: float) -> str:
    seconds = max(0.0, float(seconds))
    s = int(seconds)
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h:d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def get_default_whisper_cli() -> str:
    """Return a sensible default path for whisper-cli.exe.

    Priority:
    1. If running from a PyInstaller bundle, use the bundled binary in _MEIPASS/whisper/whisper-cli.exe
       (also supports legacy _MEIPASS/whisper-cli.exe)
    2. Use the workspace whisper-cli at ./whisper-bin-x64/Release/whisper-cli.exe if present.
    3. Use the user's D: path shown in the README if present.
    4. Otherwise return empty string so the UI prompts the user.
    """
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        # NEW: bundled folder layout for onefile
        cand = Path(meipass) / "whisper" / "whisper-cli.exe"
        if cand.exists():
            return str(cand)
        # legacy fallback
        cand2 = Path(meipass) / "whisper-cli.exe"
        if cand2.exists():
            return str(cand2)

    ws_cand = Path.cwd() / "whisper-bin-x64" / "Release" / "whisper-cli.exe"
    if ws_cand.exists():
        return str(ws_cand)

    d_cand = Path(r"D:\Whisper Desctop audio to text trascribe\models bin\whisper-cli.exe")
    if d_cand.exists():
        return str(d_cand)

    return ""


def get_nearby_model() -> str:
    """Search for a .bin model next to the EXE (when frozen) or in the script folder.

    Returns the first .bin found or empty string if none.
    """
    if getattr(sys, 'frozen', False):
        base_dir = Path(sys.executable).parent
    else:
        base_dir = Path(__file__).parent

    models = list(base_dir.glob("*.bin"))
    if models:
        return str(models[0])
    return ""


def run_capture(cmd: List[str]) -> tuple[int, str, str]:
    p = subprocess.run(cmd, capture_output=True, text=True)
    return p.returncode, (p.stdout or "").strip(), (p.stderr or "").strip()


def get_duration_seconds(audio_path: Path) -> float:
    cmd = [
        FFPROBE_PATH, "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(audio_path),
    ]
    rc, out, err = run_capture(cmd)
    if rc != 0:
        raise RuntimeError(f"ffprobe failed for {audio_path.name}: {err or out}")
    return max(0.0, float(out))


def normalize_dnd_paths(raw: str) -> list[str]:
    raw = raw.strip()
    if not raw:
        return []
    out: list[str] = []
    token = ""
    in_brace = False
    for ch in raw:
        if ch == "{":
            in_brace = True
            token = ""
        elif ch == "}":
            in_brace = False
            if token:
                out.append(token)
                token = ""
        elif ch.isspace() and not in_brace:
            if token:
                out.append(token)
                token = ""
        else:
            token += ch
    if token:
        out.append(token)
    return out


def derive_merged_basename(files: list[Path]) -> str:
    if not files:
        return "merged"
    stems = [f.stem for f in files]
    if len(stems) == 1:
        base = stems[0]
    else:
        base = stems[0]
        for s in stems[1:]:
            i = 0
            lim = min(len(base), len(s))
            while i < lim and base[i] == s[i]:
                i += 1
            base = base[:i]
            if not base:
                break

    base = base.rstrip("._- ")
    base = re.sub(r"([._-]?\d+)+$", "", base).rstrip("._- ")
    return base if base else "merged"


@dataclass
class JobSettings:
    whisper_cli: Path
    model: Path
    out_dir: Path
    language: str
    threads: int
    beam_size: int
    best_of: int
    no_fallback: bool
    no_timestamps: bool
    flash_attn: bool
    vad: bool
    compute_mode: str
    real_progress: bool


class WhisperGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Whisper GUI Queue (whisper-cli.exe)")
        self.root.geometry("1040x780")
        self.root.minsize(900, 650)

        self.cancel_event = threading.Event()
        self.worker_thread: Optional[threading.Thread] = None
        self.ui_queue: "queue.Queue[tuple[str, object]]" = queue.Queue()

        self.files: list[Path] = []

        # Vars
        self.var_whisper_cli = tk.StringVar(value=get_default_whisper_cli())
        # auto-fill model if a .bin is next to the EXE/script
        self.var_model = tk.StringVar(value=get_nearby_model())
        self.var_out_dir = tk.StringVar(value=str(Path.cwd() / "transcripts"))

        self.var_language = tk.StringVar(value="bg")
        self.var_threads = tk.StringVar(value="8")
        self.var_bs = tk.StringVar(value="1")
        self.var_bo = tk.StringVar(value="1")

        self.var_nf = tk.BooleanVar(value=True)
        self.var_nt = tk.BooleanVar(value=True)
        self.var_fa = tk.BooleanVar(value=False)
        self.var_vad = tk.BooleanVar(value=False)

        self.var_compute = tk.StringVar(value="Auto (default)")
        self.var_realpp = tk.BooleanVar(value=True)

        self.total_progress = tk.DoubleVar(value=0.0)
        self.file_progress = tk.DoubleVar(value=0.0)

        self.var_total_label = tk.StringVar(
            value="Total Progress: 0% | 00:00/00:00 | 0.00x [00:00<00:00, 0.00s/s] time to finish all task 00:00"
        )
        self.var_file_label = tk.StringVar(value="File: -")

        # UI handles (used for DnD)
        self.lst: Optional[tk.Listbox] = None
        self.ent_model: Optional[ttk.Entry] = None
        self.txt: Optional[tk.Text] = None
        self.btn_cancel: Optional[ttk.Button] = None
        self.lbl_status: Optional[ttk.Label] = None

        self._build_ui()
        self._poll_ui_queue()

    # ---------------- UI (GRID + PANEDWINDOW) ----------------
    def _build_ui(self) -> None:
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)

        main = ttk.Frame(self.root, padding=10)
        main.grid(row=0, column=0, sticky="nsew")
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(2, weight=1)

        cfg = ttk.LabelFrame(main, text="Configuration", padding=10)
        cfg.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        cfg.grid_columnconfigure(1, weight=1)

        ttk.Label(cfg, text="whisper-cli.exe:").grid(row=0, column=0, sticky="w")
        ttk.Entry(cfg, textvariable=self.var_whisper_cli).grid(row=0, column=1, sticky="ew", padx=6)
        ttk.Button(cfg, text="Browse", command=self.pick_whisper_cli).grid(row=0, column=2, padx=4)

        ttk.Label(cfg, text="Model (.bin):").grid(row=1, column=0, sticky="w")
        self.ent_model = ttk.Entry(cfg, textvariable=self.var_model)
        self.ent_model.grid(row=1, column=1, sticky="ew", padx=6)
        ttk.Button(cfg, text="Browse", command=self.pick_model).grid(row=1, column=2, padx=4)

        ttk.Label(cfg, text="Output dir:").grid(row=2, column=0, sticky="w")
        ttk.Entry(cfg, textvariable=self.var_out_dir).grid(row=2, column=1, sticky="ew", padx=6)
        ttk.Button(cfg, text="Browse", command=self.pick_out_dir).grid(row=2, column=2, padx=4)

        params1 = ttk.Frame(cfg)
        params1.grid(row=3, column=0, columnspan=3, sticky="ew", pady=(8, 2))

        ttk.Label(params1, text="Language (-l):").grid(row=0, column=0, sticky="w")
        ttk.Combobox(
            params1, textvariable=self.var_language,
            values=["bg", "en", "ru", "auto"], width=6, state="readonly"
        ).grid(row=0, column=1, padx=(6, 14))

        ttk.Label(params1, text="Threads (-t):").grid(row=0, column=2, sticky="w")
        ttk.Combobox(
            params1, textvariable=self.var_threads,
            values=["4", "6", "8", "10", "12"], width=6, state="readonly"
        ).grid(row=0, column=3, padx=(6, 14))

        ttk.Label(params1, text="Beam (-bs):").grid(row=0, column=4, sticky="w")
        ttk.Combobox(
            params1, textvariable=self.var_bs,
            values=["1", "2", "3", "4", "5"], width=4, state="readonly"
        ).grid(row=0, column=5, padx=(6, 14))

        ttk.Label(params1, text="Best-of (-bo):").grid(row=0, column=6, sticky="w")
        ttk.Combobox(
            params1, textvariable=self.var_bo,
            values=["1", "2", "3", "4", "5"], width=4, state="readonly"
        ).grid(row=0, column=7, padx=(6, 14))

        ttk.Checkbutton(params1, text="No fallback (-nf)", variable=self.var_nf).grid(row=0, column=8, padx=(4, 10))
        ttk.Checkbutton(params1, text="No timestamps (-nt)", variable=self.var_nt).grid(row=0, column=9, padx=(4, 10))
        ttk.Checkbutton(params1, text="Flash attn (-fa)", variable=self.var_fa).grid(row=0, column=10, padx=(4, 10))
        ttk.Checkbutton(params1, text="VAD (--vad)", variable=self.var_vad).grid(row=0, column=11, padx=(4, 10))

        params2 = ttk.Frame(cfg)
        params2.grid(row=4, column=0, columnspan=3, sticky="ew", pady=(6, 2))

        ttk.Label(params2, text="Compute mode:").grid(row=0, column=0, sticky="w")
        ttk.Combobox(
            params2,
            textvariable=self.var_compute,
            values=[
                "Auto (default)",
                "CPU only (-ng)",
                "OpenVINO CPU (encode) (-oved CPU)",
                "OpenVINO GPU (encode) (-oved GPU)",
            ],
            width=34,
            state="readonly",
        ).grid(row=0, column=1, padx=(6, 14))

        ttk.Checkbutton(params2, text="Real ETA via -pp", variable=self.var_realpp).grid(row=0, column=2, padx=(4, 10))

        ctl = ttk.Frame(main)
        ctl.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        ttk.Button(ctl, text="Start", command=self.start).pack(side="left", padx=4)
        self.btn_cancel = ttk.Button(ctl, text="Cancel", command=self.cancel, state="disabled")
        self.btn_cancel.pack(side="left", padx=4)
        self.lbl_status = ttk.Label(ctl, text="Idle")
        self.lbl_status.pack(side="right")

        paned = ttk.Panedwindow(main, orient="vertical")
        paned.grid(row=2, column=0, sticky="nsew")

        top = ttk.Frame(paned)
        top.grid_columnconfigure(0, weight=1)
        top.grid_rowconfigure(0, weight=3)
        top.grid_rowconfigure(1, weight=1)

        bottom = ttk.Frame(paned)
        bottom.grid_columnconfigure(0, weight=1)
        bottom.grid_rowconfigure(0, weight=1)

        paned.add(top, weight=4)
        paned.add(bottom, weight=1)

        qf = ttk.LabelFrame(top, text=f"Queue (max {MAX_QUEUE} files)", padding=10)
        qf.grid(row=0, column=0, sticky="nsew", pady=(0, 10))
        qf.grid_rowconfigure(1, weight=1)
        qf.grid_columnconfigure(0, weight=1)

        qtop = ttk.Frame(qf)
        qtop.grid(row=0, column=0, sticky="ew")
        ttk.Button(qtop, text="Add files", command=self.add_files).pack(side="left", padx=4)
        ttk.Button(qtop, text="Add folder", command=self.add_folder).pack(side="left", padx=4)
        ttk.Button(qtop, text="Remove selected", command=self.remove_selected).pack(side="left", padx=4)
        ttk.Button(qtop, text="Clear", command=self.clear_queue).pack(side="left", padx=4)
        ttk.Label(qtop, text="(DnD: pip install tkinterdnd2)").pack(side="right")

        lst_frame = ttk.Frame(qf)
        lst_frame.grid(row=1, column=0, sticky="nsew", pady=(8, 0))
        lst_frame.grid_rowconfigure(0, weight=1)
        lst_frame.grid_columnconfigure(0, weight=1)

        self.lst = tk.Listbox(lst_frame, selectmode="extended")
        self.lst.grid(row=0, column=0, sticky="nsew")
        sb = ttk.Scrollbar(lst_frame, orient="vertical", command=self.lst.yview)
        sb.grid(row=0, column=1, sticky="ns")
        self.lst.configure(yscrollcommand=sb.set)

        prog = ttk.LabelFrame(top, text="Progress", padding=10)
        prog.grid(row=1, column=0, sticky="ew")
        prog.grid_columnconfigure(0, weight=1)

        ttk.Label(prog, textvariable=self.var_total_label).grid(row=0, column=0, sticky="w")
        ttk.Progressbar(prog, variable=self.total_progress, maximum=100.0).grid(row=1, column=0, sticky="ew", pady=(4, 10))

        ttk.Label(prog, textvariable=self.var_file_label).grid(row=2, column=0, sticky="w")
        ttk.Progressbar(prog, variable=self.file_progress, maximum=100.0).grid(row=3, column=0, sticky="ew", pady=(4, 0))

        logf = ttk.LabelFrame(bottom, text="Log", padding=10)
        logf.grid(row=0, column=0, sticky="nsew")
        logf.grid_rowconfigure(0, weight=1)
        logf.grid_columnconfigure(0, weight=1)

        self.txt = tk.Text(logf, wrap="word")
        self.txt.grid(row=0, column=0, sticky="nsew")
        logsb = ttk.Scrollbar(logf, orient="vertical", command=self.txt.yview)
        logsb.grid(row=0, column=1, sticky="ns")
        self.txt.configure(yscrollcommand=logsb.set)

        if HAS_DND and self.lst is not None and self.ent_model is not None:
            try:
                self.lst.drop_target_register(DND_FILES)  # type: ignore
                self.lst.dnd_bind("<<Drop>>", self._on_drop_files)  # type: ignore
                self.ent_model.drop_target_register(DND_FILES)  # type: ignore
                self.ent_model.dnd_bind("<<Drop>>", self._on_drop_model)  # type: ignore
            except Exception:
                pass

    def _on_drop_files(self, event) -> None:
        for p in normalize_dnd_paths(getattr(event, "data", "")):
            self._add_paths([p])

    def _on_drop_model(self, event) -> None:
        paths = normalize_dnd_paths(getattr(event, "data", ""))
        if paths:
            p = Path(paths[0])
            if p.is_file():
                self.var_model.set(str(p))
                self.log(f"Model set via drop: {p}")

    def pick_whisper_cli(self) -> None:
        p = filedialog.askopenfilename(title="Select whisper-cli.exe", filetypes=[("Executable", "*.exe"), ("All files", "*.*")])
        if p:
            self.var_whisper_cli.set(p)

    def pick_model(self) -> None:
        p = filedialog.askopenfilename(title="Select model .bin", filetypes=[("Whisper model", "*.bin"), ("All files", "*.*")])
        if p:
            self.var_model.set(p)

    def pick_out_dir(self) -> None:
        p = filedialog.askdirectory(title="Select output directory")
        if p:
            self.var_out_dir.set(p)

    def add_files(self) -> None:
        paths = filedialog.askopenfilenames(
            title="Select audio files",
            filetypes=[("Audio", "*.wav *.mp3 *.ogg *.flac *.m4a *.aac"), ("All files", "*.*")]
        )
        if paths:
            self._add_paths(list(paths))

    def add_folder(self) -> None:
        folder = filedialog.askdirectory(title="Select folder with audio files")
        if not folder:
            return
        p = Path(folder)
        files: list[str] = []
        for ext in sorted(SUPPORTED_AUDIO_EXTS):
            files.extend([str(x) for x in p.glob(f"*{ext}")])
        self._add_paths(files)

    def _add_paths(self, paths: list[str]) -> None:
        added = 0
        for s in paths:
            if len(self.files) >= MAX_QUEUE:
                break
            p = Path(s)
            if p.is_dir():
                continue
            if p.suffix.lower() not in SUPPORTED_AUDIO_EXTS:
                continue
            if p not in self.files:
                self.files.append(p)
                if self.lst is not None:
                    self.lst.insert("end", str(p))
                added += 1
        if added:
            self.log(f"Added {added} file(s). Queue size: {len(self.files)}")

    def remove_selected(self) -> None:
        if self.lst is None:
            return
        sel = list(self.lst.curselection())
        if not sel:
            return
        for i in reversed(sel):
            try:
                self.files.pop(i)
                self.lst.delete(i)
            except Exception:
                pass
        self.log(f"Removed {len(sel)} file(s). Queue size: {len(self.files)}")

    def clear_queue(self) -> None:
        self.files.clear()
        if self.lst is not None:
            self.lst.delete(0, "end")
        self.log("Queue cleared.")

    def log(self, msg: str) -> None:
        if self.txt is None:
            return
        ts = time.strftime("%H:%M:%S")
        self.txt.insert("end", f"[{ts}] {msg}\n")
        self.txt.see("end")

    def _validate(self) -> Optional[JobSettings]:
        whisper_cli = Path(self.var_whisper_cli.get().strip())
        model = Path(self.var_model.get().strip())
        out_dir = Path(self.var_out_dir.get().strip())

        if not whisper_cli.exists():
            messagebox.showerror("Missing whisper-cli.exe", "Select a valid whisper-cli.exe path.")
            return None
        if not model.exists():
            messagebox.showerror("Missing model", "Select a valid model .bin file.")
            return None
        if not self.files:
            messagebox.showerror("Empty queue", "Add at least one audio file.")
            return None

        out_dir.mkdir(parents=True, exist_ok=True)

        try:
            threads = int(self.var_threads.get())
            bs = int(self.var_bs.get())
            bo = int(self.var_bo.get())
        except ValueError:
            messagebox.showerror("Invalid numbers", "Threads/bs/bo must be numbers.")
            return None

        return JobSettings(
            whisper_cli=whisper_cli,
            model=model,
            out_dir=out_dir,
            language=self.var_language.get().strip() or "bg",
            threads=threads,
            beam_size=bs,
            best_of=bo,
            no_fallback=bool(self.var_nf.get()),
            no_timestamps=bool(self.var_nt.get()),
            flash_attn=bool(self.var_fa.get()),
            vad=bool(self.var_vad.get()),
            compute_mode=self.var_compute.get(),
            real_progress=bool(self.var_realpp.get()),
        )

    def start(self) -> None:
        if self.worker_thread and self.worker_thread.is_alive():
            return
        settings = self._validate()
        if not settings:
            return

        if self.btn_cancel is not None:
            self.btn_cancel.config(state="normal")
        if self.lbl_status is not None:
            self.lbl_status.config(text="Running...")
        self.cancel_event.clear()

        self.total_progress.set(0.0)
        self.file_progress.set(0.0)

        self.worker_thread = threading.Thread(target=self._worker, args=(settings, list(self.files)), daemon=True)
        self.worker_thread.start()

    def cancel(self) -> None:
        if self.worker_thread and self.worker_thread.is_alive():
            self.cancel_event.set()
            self.log("Cancel requested...")
            if self.btn_cancel is not None:
                self.btn_cancel.config(state="disabled")

    def _worker(self, settings: JobSettings, files: list[Path]) -> None:
        try:
            durations = [get_duration_seconds(f) for f in files]
            total_audio = float(sum(durations)) or 0.0

            merged_base = derive_merged_basename(files)
            merged_path = settings.out_dir / f"{merged_base}_merged.txt"
            merged_parts: list[str] = []

            total_start = time.time()
            total_done_audio = 0.0
            speed_est = 0.20

            for idx, (audio, dur) in enumerate(zip(files, durations), start=1):
                if self.cancel_event.is_set():
                    break

                base = audio.stem
                out_txt = settings.out_dir / f"{base}.txt"
                file_start = time.time()

                self.ui_queue.put(("file_start", (idx, len(files), audio.name, dur)))

                cmd = [
                    str(settings.whisper_cli),
                    "-m", str(settings.model),
                    "-f", str(audio),
                    "-otxt",
                    "-of", str(settings.out_dir / base),
                    "-t", str(settings.threads),
                    "-l", str(settings.language),
                    "-bs", str(settings.beam_size),
                    "-bo", str(settings.best_of),
                ]

                mode = settings.compute_mode
                if mode.startswith("CPU only"):
                    cmd.append("-ng")
                elif "OpenVINO CPU" in mode:
                    cmd += ["-oved", "CPU"]
                elif "OpenVINO GPU" in mode:
                    cmd += ["-oved", "GPU"]

                if settings.no_timestamps:
                    cmd.append("-nt")
                if settings.no_fallback:
                    cmd.append("-nf")
                if settings.flash_attn:
                    cmd.append("-fa")
                if settings.vad:
                    cmd.append("--vad")

                if settings.real_progress:
                    cmd.append("-pp")
                    popen_kwargs = dict(stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                        text=True, bufsize=1, universal_newlines=True)
                else:
                    cmd.append("-np")
                    popen_kwargs = dict(stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

                # Prevent a black console window when launching whisper-cli on Windows
                if sys.platform.startswith("win"):
                    try:
                        si = subprocess.STARTUPINFO()
                        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                        popen_kwargs["startupinfo"] = si
                        popen_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
                    except Exception:
                        pass

                proc = subprocess.Popen(cmd, **popen_kwargs)

                buf = ""
                last_pct: Optional[float] = None
                last_done_file = 0.0

                while proc.poll() is None:
                    if self.cancel_event.is_set():
                        try:
                            proc.terminate()
                        except Exception:
                            pass
                        break

                    now = time.time()
                    file_elapsed = now - file_start
                    total_elapsed = now - total_start

                    if settings.real_progress and proc.stdout is not None:
                        try:
                            ch = proc.stdout.read(1)
                        except Exception:
                            ch = ""
                        if ch:
                            buf += ch
                            parts = re.split(r"[\r\n]+", buf)
                            buf = parts[-1]
                            for part in parts[:-1]:
                                m = PROG_RE.search(part)
                                if not m:
                                    continue
                                raw = float(m.group(1))
                                pct = (raw / 100.0) if raw > 100.0 else raw
                                pct = max(0.0, min(100.0, pct))
                                last_pct = pct

                    if dur > 0 and last_pct is not None:
                        done_file = dur * (last_pct / 100.0)
                    else:
                        done_file = min(dur, file_elapsed * speed_est)

                    if done_file > last_done_file:
                        last_done_file = done_file
                        total_done_est = total_done_audio + done_file
                        self.ui_queue.put(("progress", (total_audio, total_done_est, total_elapsed,
                                                       dur, done_file, file_elapsed, idx, len(files), audio.name)))
                    time.sleep(0.2)

                if self.cancel_event.is_set():
                    break

                total_done_audio += dur

                file_wall = max(0.001, time.time() - file_start)
                if dur > 0:
                    speed_now = dur / file_wall
                    speed_est = speed_est * 0.70 + speed_now * 0.30

                if out_txt.exists():
                    text = out_txt.read_text(encoding="utf-8", errors="replace").strip()
                else:
                    text = "[NO OUTPUT TXT FOUND]"
                merged_parts.append(f"--- {base} ---\n{text}\n")

                self.ui_queue.put(("file_done", (idx, len(files), audio.name)))

            merged_path.write_text("\n".join(merged_parts).strip() + "\n", encoding="utf-8")
            self.ui_queue.put(("log", f"Merged transcript: {merged_path}"))
            self.ui_queue.put(("done", None))

        except Exception as e:
            self.ui_queue.put(("error", str(e)))

    def _poll_ui_queue(self) -> None:
        try:
            while True:
                kind, payload = self.ui_queue.get_nowait()

                if kind == "log":
                    self.log(str(payload))

                elif kind == "error":
                    self.log(f"ERROR: {payload}")
                    messagebox.showerror("Error", str(payload))
                    self._finish()

                elif kind == "file_start":
                    idx, total, name, dur = payload  # type: ignore
                    self.file_progress.set(0.0)
                    self.var_file_label.set(
                        f"File {idx}/{total} ({name}): 0% | 00:00/{fmt_interval(dur)} | 0.00x [00:00<00:00] time to finish current task 00:00"
                    )

                elif kind == "file_done":
                    self.file_progress.set(100.0)

                elif kind == "progress":
                    total_audio, total_done_est, total_elapsed, f_total, f_done, f_elapsed, idx, nfiles, name = payload  # type: ignore
                    self._update_total(total_audio, total_done_est, total_elapsed)
                    self._update_file(f_total, f_done, f_elapsed, idx, nfiles, name)

                elif kind == "done":
                    self.log("Stopped." if self.cancel_event.is_set() else "All done.")
                    self._finish()

        except queue.Empty:
            pass

        self.root.after(100, self._poll_ui_queue)

    def _update_total(self, total_audio: float, done_audio: float, elapsed_wall: float) -> None:
        pct = 0.0 if total_audio <= 0 else min(100.0, (done_audio / total_audio) * 100.0)
        self.total_progress.set(pct)

        x = (done_audio / elapsed_wall) if elapsed_wall > 0 else 0.0
        remaining_audio = max(0.0, total_audio - done_audio)
        remaining_wall = (remaining_audio / x) if x > 0 else 0.0
        rate_s_per_s = (elapsed_wall / done_audio) if done_audio > 0 else 0.0
        total_finish = elapsed_wall + remaining_wall

        self.var_total_label.set(
            f"Total Progress: {pct:3.0f}% | {fmt_interval(done_audio)}/{fmt_interval(total_audio)} | {x:0.2f}x "
            f"[{fmt_interval(elapsed_wall)}<{fmt_interval(remaining_wall)}, {rate_s_per_s:0.2f}s/s] "
            f"time to finish all task {fmt_interval(total_finish)}"
        )

    def _update_file(self, total_audio: float, done_audio: float, elapsed_wall: float,
                     idx: int, nfiles: int, name: str) -> None:
        pct = 0.0 if total_audio <= 0 else min(100.0, (done_audio / total_audio) * 100.0)
        self.file_progress.set(pct)

        x = (done_audio / elapsed_wall) if elapsed_wall > 0 else 0.0
        remaining_audio = max(0.0, total_audio - done_audio)
        remaining_wall = (remaining_audio / x) if x > 0 else 0.0
        file_finish = elapsed_wall + remaining_wall

        self.var_file_label.set(
            f"File {idx}/{nfiles} ({name}): {pct:3.0f}% | {fmt_interval(done_audio)}/{fmt_interval(total_audio)} | {x:0.2f}x "
            f"[{fmt_interval(elapsed_wall)}<{fmt_interval(remaining_wall)}] "
            f"time to finish current task {fmt_interval(file_finish)}"
        )

    def _finish(self) -> None:
        if self.btn_cancel is not None:
            self.btn_cancel.config(state="disabled")
        if self.lbl_status is not None:
            self.lbl_status.config(text="Idle")


def main() -> None:
    # If running from a PyInstaller onefile bundle, help Tcl/Tk find tkdnd
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        try:
            os.environ["TCLLIBPATH"] = str(Path(meipass) / "tkinterdnd2")
        except Exception:
            pass

    if HAS_DND and TkinterDnD is not None:
        root = TkinterDnD.Tk()
    else:
        root = tk.Tk()
    WhisperGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()