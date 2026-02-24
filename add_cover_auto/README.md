Автоматично добавя JPG корица към PDF с минимално рязане.

Използва `img2pdf` и `pypdf`. Решава дали да запълни страницата (възможно рязане) или да вмъкне без рязане на базата на оценка на crop fraction.

Примери за използване (от командния ред):

- `python add_cover_auto.py cover.jpg input.pdf output.pdf --crop-threshold 0.02`

Описание на аргументите: `cover`, `input_pdf`, `output_pdf`, `--crop-threshold`.