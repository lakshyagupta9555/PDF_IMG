# PDF & Image Tools (Django)

A simple Django project with a dark-themed UI (Tailwind CDN) that provides PDF and image utilities.

Features (UI placeholders + backend handlers):
- PDF: merge PDFs, delete page, PDF → images, images → PDF, watermark, encrypt/decrypt, compress PDF, (optional) Word↔PDF conversion using `docx2pdf`.
- Images: resize (by pixels), resize to target file size (approx), crop, compress, create simple collage.

Requirements
- Python 3.10+
- Windows: optional `docx2pdf` requires MS Word; `pdf2image` requires `poppler` installed and in PATH.

Install
```powershell
python -m venv .venv; .venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Run
```powershell
python manage.py migrate
python manage.py runserver
```

Notes
- Some conversions (Word↔PDF) are optional and depend on system tools.
- This scaffold aims to provide working endpoints and a dark-tailwind UI. Further improvements (validation, large file streaming, async processing) can be added.
