from pdfminer.high_level import extract_pages
from pdfminer.layout import LTTextContainer
from pathlib import Path
import re

def extract_text_by_page(pdf_path):
    """
    Генератор: връща (page_number, text) за всяка страница
    """
    for page_number, page_layout in enumerate(extract_pages(pdf_path), start=1):
        page_text = []
        for element in page_layout:
            if isinstance(element, LTTextContainer):
                page_text.append(element.get_text())
        yield page_number, "".join(page_text)

def search_in_pdf(pdf_path, keywords=None, regex=None):
    """
    Търси ключови думи или regex в PDF файл
    """
    results = []

    for page_number, text in extract_text_by_page(pdf_path):
        if keywords:
            for kw in keywords:
                if kw.lower() in text.lower():
                    results.append({
                        "page": page_number,
                        "keyword": kw,
                        "context": get_context(text, kw)
                    })

        if regex:
            for match in re.finditer(regex, text, re.IGNORECASE):
                results.append({
                    "page": page_number,
                    "pattern": match.group(),
                    "context": get_context(text, match.group())
                })

    return results

def get_context(text, match, window=80):
    """
    Връща текстов контекст около намереното
    """
    index = text.lower().find(match.lower())
    if index == -1:
        return ""

    start = max(0, index - window)
    end = min(len(text), index + len(match) + window)
    return text[start:end].replace("\n", " ").strip()

if __name__ == "__main__":
    pdf_directory = Path("D:/изтегляния download/Книги 2025 г")
    pdf_files = list(pdf_directory.glob("*.pdf"))

    # Update keywords for the search
    keywords = ["бездна", "пустота", "Абсолют"]
    regex_pattern = None  # Add regex if needed

    for pdf_file in pdf_files:
        print(f"\nAnalyzing: {pdf_file.name}")
        results = search_in_pdf(
            pdf_file,
            keywords=keywords,
            regex=regex_pattern
        )

        for r in results:
            print(f"\n📄 Страница {r['page']}")
            print(f"🔎 Намерено: {r.get('keyword') or r.get('pattern')}")
            print(f"🧠 Контекст: {r['context']}")