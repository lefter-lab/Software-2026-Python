Добавя JPG корица към PDF, като съвпада с размера на първата страница на PDF.

Поддържа режими `fill` (може да изреже част от изображението) и `into` (не реже, може да остави граници). Използва `img2pdf` и `pypdf`.

Пример: `python add_cover_match_pdf.py cover.jpg input.pdf output.pdf --mode fill`.