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
    pdf_file = "Вторият Прастарец Изречения.pdf"
    txt_file = "Вторият Прастарец Изречения.txt"

    if not Path(pdf_file).exists():
        print("PDF файлът не съществува!")
    else:
        pdf_to_txt(pdf_file, txt_file)