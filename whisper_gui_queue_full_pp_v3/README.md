# Whisper GUI (whisper-cli)

Интерфейс и помощни скриптове за пакетно транскрибиране на аудио чрез `whisper-cli.exe`.

Съдържание на папката:

- `WhisperGUI.exe` — изпълним GUI (Windows)
- `whisper_gui_queue_full_pp_v3.py` — изходен Python скрипт за GUI
- `readme mp3 to txt.txt` — оригинални инструкции (конвертирани тук)

## Описание

Тук има инструкции за използване на `whisper-cli.exe` за транскрибиране на mp3 части (part-*.mp3). Скриптът предлага:

- пакетна обработка на частите
- запис на отделни `.txt` файлове за всяка част
- сливане в един `merged.txt`

## Бързо ръководство и примерен скрипт

По-долу е примерен скрипт `transcribe_chunks_whispercli.py` (готов за Windows):

```python
# Пример: transcribe_chunks_whispercli.py
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

# (Останалата част от скрипта е налична в оригиналния `readme mp3 to txt.txt`.)
```

## Примери за команди (Windows PowerShell)

С вашите пътища (пример):

```powershell
cd "C:\Users\admin\Desktop\temp"
python .\transcribe_chunks_whispercli.py `
	--chunks_dir "C:\Users\admin\Desktop\temp\mp3_chunks" `
	--whisper_cli "D:\\изтегляния download\\whisper-bin-x64\\Release\\whisper-cli.exe" `
	--model "D:\\Whisper Desctop audio to text trascribe\\models bin\\ggml-medium.bin" `
	--out_dir "C:\Users\admin\Desktop\temp\transcripts" `
	--merge_file "merged.txt" `
	--language bg `
	--no_timestamps
```

## Пътеки (пример за вас)

- `whisper-cli.exe`: `D:\\Whisper Desctop audio to text trascribe\\whisper-bin-x64\\Release\\whisper-cli.exe`
- Модел: `D:\\Whisper Desctop audio to text trascribe\\models bin\\ggml-medium.bin`
- mp3 chunks: `C:\\Users\\admin\\Desktop\\temp\\mp3_chunks`
- изход (transcripts): `C:\\Users\\admin\\Desktop\\temp\\transcripts`

## Забележки и оптимизации

- Можете да използвате `--language auto` за автоматично разпознаване.
- За по-бърза обработка използвайте по-малък модел (`ggml-small.bin` или `ggml-base.bin`) или намалете `--threads`.

---

Ако искаш, мога да добавя пълен `transcribe_chunks_whispercli.py` файл в тази папка и да настроя примерните пътища.