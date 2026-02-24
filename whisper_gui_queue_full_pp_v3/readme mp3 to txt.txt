Отлично — това е “старият/класически” whisper-cli синтаксис

От help-а се вижда, че работи с флагове като:

-m (model)

-f (file)

-otxt (output txt)

-of (output file base)

-l (language) и има auto

Затова коригирам Python скрипта да използва тези флагове (не --model/--file стил).

Python програма (точно за твоя whisper-cli.exe --help)

Създай файл: transcribe_chunks_whispercli.py

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import glob
import os
import subprocess
from pathlib import Path


def run(cmd: list[str]) -> None:
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(
            "Command failed:\n"
            f"  {' '.join(cmd)}\n\n"
            f"STDOUT:\n{p.stdout}\n\nSTDERR:\n{p.stderr}\n"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Batch transcribe part-*.mp3 chunks using whisper.cpp whisper-cli.exe.")
    parser.add_argument("--chunks_dir", required=True, help="Directory containing part-*.mp3")
    parser.add_argument("--whisper_cli", required=True, help="Full path to whisper-cli.exe")
    parser.add_argument("--model", required=True, help="Full path to ggml model (e.g. ggml-medium.bin)")
    parser.add_argument("--out_dir", default="transcripts", help="Directory for output .txt files")
    parser.add_argument("--merge_file", default="merged.txt", help="Merged transcript filename (saved in out_dir)")
    parser.add_argument("--language", default="auto", help="Language code, e.g. bg/en, or 'auto' (default: auto)")
    parser.add_argument("--threads", type=int, default=min(8, max(1, os.cpu_count() or 4)), help="Threads (default: min(8,cpu))")
    parser.add_argument("--no_timestamps", action="store_true", help="Do not print timestamps (adds -nt)")
    args = parser.parse_args()

    chunks_dir = Path(args.chunks_dir)
    whisper_cli = Path(args.whisper_cli)
    model = Path(args.model)
    out_dir = Path(args.out_dir)

    if not chunks_dir.exists():
        raise FileNotFoundError(f"chunks_dir not found: {chunks_dir}")
    if not whisper_cli.exists():
        raise FileNotFoundError(f"whisper_cli not found: {whisper_cli}")
    if not model.exists():
        raise FileNotFoundError(f"model not found: {model}")

    out_dir.mkdir(parents=True, exist_ok=True)

    mp3_files = sorted(Path(p) for p in glob.glob(str(chunks_dir / "part-*.mp3")))
    if not mp3_files:
        raise FileNotFoundError(f"No files matched: {chunks_dir / 'part-*.mp3'}")

    merged_parts: list[str] = []

    for idx, mp3 in enumerate(mp3_files, start=1):
        base = mp3.stem  # part-000
        out_base = out_dir / base  # whisper-cli will create <out_base>.txt
        out_txt = out_dir / f"{base}.txt"

        cmd = [
            str(whisper_cli),
            "-m", str(model),
            "-f", str(mp3),
            "-otxt",
            "-of", str(out_base),
            "-t", str(args.threads),
            "-l", str(args.language),
        ]
        if args.no_timestamps:
            cmd.append("-nt")

        print(f"[{idx}/{len(mp3_files)}] Transcribing: {mp3.name}")
        run(cmd)

        if not out_txt.exists():
            raise RuntimeError(f"Expected output not found: {out_txt}")

        text = out_txt.read_text(encoding="utf-8", errors="replace").strip()
        merged_parts.append(f"--- {base} ---\n{text}\n")

    merged_path = out_dir / args.merge_file
    merged_path.write_text("\n".join(merged_parts).strip() + "\n", encoding="utf-8")
    print("Done.")
    print(f"Per-chunk transcripts: {out_dir}")
    print(f"Merged transcript: {merged_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

Как да го пуснеш (с твоите реални пътища)

Имаш:

whisper-cli.exe:

D:\изтегляния download\whisper-bin-x64\Release\whisper-cli.exe

модел:

D:\Whisper Desctop audio to text trascribe\models bin\ggml-medium.bin

chunks:

ти каза, че са в mp3_chunks (ако е в текущата папка — ок)

Пример команда:

python .\transcribe_chunks_whispercli.py `
  --chunks_dir ".\mp3_chunks" `
  --whisper_cli "D:\изтегляния download\whisper-bin-x64\Release\whisper-cli.exe" `
  --model "D:\Whisper Desctop audio to text trascribe\models bin\ggml-medium.bin" `
  --out_dir ".\transcripts" `
  --language auto


Ако аудиото е на български и искаш по-малко грешки:

... --language bg

Малък performance tip

ggml-medium.bin е тежък. Ако ти е бавно:

ползвай ggml-small.bin или ggml-base.bin (ако имаш)

или намали --threads

Следващата логична стъпка: да го направим Copilot skill

Ако искаш, ще ти дам:

SKILL.md за mp3-transcriber

с инструкции:

split → transcribe → merge

и готови copy/paste команди за твоя Windows път

Кажи ми само къде точно се намира папката mp3_chunks (пълен път) и къде искаш да излизат transcripts.

пеместих cli тук "D:\Whisper Desctop audio to text trascribe\whisper-bin-x64\Release\ 

папката с mp3 е C:\Users\admin\Desktop\temp там да сложи транскрипта 
ОК — ето ти точната команда + скриптът е готов за твоите пътища
Пътища при теб

whisper-cli.exe:

D:\Whisper Desctop audio to text trascribe\whisper-bin-x64\Release\whisper-cli.exe

model:

D:\Whisper Desctop audio to text trascribe\models bin\ggml-medium.bin

mp3 chunks:

C:\Users\admin\Desktop\temp\mp3_chunks

изход (transcripts):

C:\Users\admin\Desktop\temp\transcripts

1) Създай файла transcribe_chunks_whispercli.py

Сложи го където искаш (най-лесно в C:\Users\admin\Desktop\temp\).

(Кодът е този от предния ми отговор: transcribe_chunks_whispercli.py)

2) Пусни го (готова команда 1:1)

От PowerShell:

cd "C:\Users\admin\Desktop\temp"

python .\transcribe_chunks_whispercli.py `
  --chunks_dir "C:\Users\admin\Desktop\temp\mp3_chunks" `
  --whisper_cli "D:\Whisper Desctop audio to text trascribe\whisper-bin-x64\Release\whisper-cli.exe" `
  --model "D:\Whisper Desctop audio to text trascribe\models bin\ggml-medium.bin" `
  --out_dir "C:\Users\admin\Desktop\temp\transcripts" `
  --merge_file "merged.txt" `
  --language bg `
  --no_timestamps


Ще получиш:

C:\Users\admin\Desktop\temp\transcripts\part-000.txt

...

part-005.txt

merged.txt

3) Ако искаш auto language (понякога по-добре при смесен език)

Смени --language bg с:

--language auto

4) Ако даде грешка “python not found”

Пусни:

py -V


и после използвай py вместо python:

py .\transcribe_chunks_whispercli.py ...

5) Ако искаш още по-лесно: “един ред” без скрипт

Може и директно да транскрибираш всички части, но ще е по-трудно да merge-неш чисто. Скриптът е по-добър.

Ако искаш, ще ти направя и втори режим в скрипта:

да взема *.mp3 (не само part-*.mp3)

да сортира по “part-число” правилно

и да добави “time offsets” (за да знаеш от коя минута е текстът).