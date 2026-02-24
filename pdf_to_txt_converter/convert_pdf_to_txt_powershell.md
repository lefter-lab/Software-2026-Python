# Конвертиране на PDF към TXT чрез PowerShell

Този файл описва как да конвертирате PDF файл в TXT файл с помощта на PowerShell и Python.

## Предварителни стъпки
1. **Инсталирайте Python**
   - Уверете се, че Python е инсталиран на вашата система.
   - Можете да го изтеглите от [официалния сайт на Python](https://www.python.org/).

2. **Инсталирайте библиотеката pdfminer.six**
   - Отворете PowerShell и изпълнете следната команда:
     ```powershell
     pip install pdfminer.six
     ```

3. **Създайте Python скрипт за конвертиране**
   - Създайте файл с име `pdf_to_txt_converter.py` и добавете следния код:
     ```python
     from pdfminer.high_level import extract_text
     from pathlib import Path

     def pdf_to_txt(pdf_path, txt_path):
         """
         Конвертира PDF файл в TXT с UTF-8 кодировка (поддържа кирилица)
         """
         text = extract_text(pdf_path)

         with open(txt_path, "w", encoding="utf-8") as f:
             f.write(text)

         print(f"Файлът е конвертиран успешно: {txt_path}")

     if __name__ == "__main__":
         pdf_file = "input.pdf"
         txt_file = "output.txt"

         if not Path(pdf_file).exists():
             print("PDF файлът не съществува!")
         else:
             pdf_to_txt(pdf_file, txt_file)
     ```

## Стъпки за конвертиране
1. **Навигирайте до директорията с вашия PDF файл**
   - Използвайте командата `cd`, за да отидете до папката, където се намира вашият PDF файл.
     ```powershell
     cd "D:\изтегляния download\Книги 2025 г"
     ```

2. **Стартирайте Python скрипта**
   - Изпълнете следната команда, като замените `Вторият Прастарец Изречения.pdf` с името на вашия PDF файл:
     ```powershell
     python pdf_to_txt_converter.py
     ```

3. **Резултат**
   - TXT файлът ще бъде създаден в същата директория с името `Вторият Прастарец Изречения.txt` (или друго име, зададено в скрипта).

## Забележки
- Уверете се, че PDF файлът съдържа текст (а не изображения). За сканирани PDF файлове ще е необходим OCR софтуер.
- Ако срещнете грешки, уверете се, че всички зависимости са инсталирани правилно.