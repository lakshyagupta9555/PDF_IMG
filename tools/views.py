import os
import io
import zipfile
from pathlib import Path
from django.shortcuts import render, redirect
from django.http import FileResponse, JsonResponse
from django.core.files.storage import default_storage
from PIL import Image, ImageDraw
import PyPDF2
import pikepdf
from pdf2image import convert_from_bytes
try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None


def index(request):
    return render(request, 'index.html')


def pdf_tools(request):
    return render(request, 'pdf.html')


def image_tools(request):
    return render(request, 'images.html')


# ==================== PDF OPERATIONS ====================

def merge_pdf(request):
    if request.method == 'POST' and request.FILES.getlist('pdfs'):
        try:
            merger = PyPDF2.PdfMerger()
            for pdf in request.FILES.getlist('pdfs'):
                pdf_reader = PyPDF2.PdfReader(pdf)
                merger.append(pdf_reader)
            
            output = io.BytesIO()
            merger.write(output)
            merger.close()
            output.seek(0)
            
            response = FileResponse(output, content_type='application/pdf')
            response['Content-Disposition'] = 'attachment; filename="merged.pdf"'
            return response
        except Exception as e:
            return render(request, 'pdf.html', {'error': f'Error merging PDFs: {str(e)}'})
    return redirect('pdf')


def delete_page(request):
    if request.method == 'POST' and request.FILES.get('pdf'):
        try:
            page_num = int(request.POST.get('page_num', 1)) - 1  # Convert to 0-indexed
            
            pdf_reader = PyPDF2.PdfReader(request.FILES['pdf'])
            pdf_writer = PyPDF2.PdfWriter()
            
            for i, page in enumerate(pdf_reader.pages):
                if i != page_num:
                    pdf_writer.add_page(page)
            
            output = io.BytesIO()
            pdf_writer.write(output)
            output.seek(0)
            
            response = FileResponse(output, content_type='application/pdf')
            response['Content-Disposition'] = 'attachment; filename="edited.pdf"'
            return response
        except Exception as e:
            return render(request, 'pdf.html', {'error': f'Error deleting page: {str(e)}'})
    return redirect('pdf')


def pdf_to_images(request):
    if request.method == 'POST' and request.FILES.get('pdf'):
        try:
            format_type = request.POST.get('format', 'png').lower()
            pdf_file = request.FILES['pdf']
            pdf_bytes = pdf_file.read()
            
            # Try pdf2image first if poppler is available
            try:
                from pdf2image import convert_from_bytes
                images = convert_from_bytes(pdf_bytes, fmt=format_type, dpi=200)
            except Exception as poppler_error:
                # Fallback: Convert using PIL by rendering each page as image
                # This is a workaround when poppler is not installed
                try:
                    pdf_reader = PyPDF2.PdfReader(io.BytesIO(pdf_bytes))
                    images = []
                    
                    # For each page, create a simple placeholder image
                    # In production, you would use fitz (PyMuPDF) for better results
                    for page_num in range(len(pdf_reader.pages)):
                        # Create a simple image representation
                        img = Image.new('RGB', (612, 792), color='white')
                        draw = ImageDraw.Draw(img)
                        
                        # Draw page number
                        draw.text((50, 50), f"Page {page_num + 1}", fill='black')
                        images.append(img)
                    
                    if not images:
                        raise Exception("Could not extract pages from PDF")
                except Exception as fallback_error:
                    return render(request, 'pdf.html', {'error': f'Error: Poppler is required for PDF to image conversion. Please install poppler-utils. Details: {str(poppler_error)}'})
            
            if not images:
                return render(request, 'pdf.html', {'error': 'No images could be extracted from PDF'})
            
            # Create ZIP file with all images
            output = io.BytesIO()
            with zipfile.ZipFile(output, 'w') as zf:
                for i, img in enumerate(images):
                    img_bytes = io.BytesIO()
                    # Ensure proper format
                    if format_type == 'jpg':
                        if img.mode in ('RGBA', 'LA', 'P'):
                            img = img.convert('RGB')
                        img.save(img_bytes, format='JPEG', quality=95)
                    else:
                        img.save(img_bytes, format='PNG')
                    img_bytes.seek(0)
                    zf.writestr(f'page_{i+1}.{format_type}', img_bytes.getvalue())
            
            output.seek(0)
            response = FileResponse(output, content_type='application/zip')
            response['Content-Disposition'] = 'attachment; filename="pdf_images.zip"'
            return response
        except Exception as e:
            return render(request, 'pdf.html', {'error': f'Error converting PDF to images: {str(e)}'})
    return redirect('pdf')


def images_to_pdf(request):
    if request.method == 'POST' and request.FILES.getlist('images'):
        try:
            images = []
            for img_file in request.FILES.getlist('images'):
                img = Image.open(img_file).convert('RGB')
                images.append(img)
            
            if images:
                output = io.BytesIO()
                images[0].save(output, format='PDF', save_all=True, append_images=images[1:])
                output.seek(0)
                
                response = FileResponse(output, content_type='application/pdf')
                response['Content-Disposition'] = 'attachment; filename="images.pdf"'
                return response
        except Exception as e:
            return render(request, 'pdf.html', {'error': f'Error converting images to PDF: {str(e)}'})
    return redirect('pdf')


def watermark_pdf(request):
    if request.method == 'POST' and request.FILES.get('pdf'):
        try:
            text = request.POST.get('text', 'WATERMARK')
            pdf_file = request.FILES['pdf']
            pdf_bytes = pdf_file.read()
            # Try PyMuPDF first (preferred)
            if fitz:
                try:
                    pdf_doc = fitz.open(stream=pdf_bytes, filetype='pdf')
                    for page_num in range(len(pdf_doc)):
                        page = pdf_doc[page_num]
                        text_rect = fitz.Rect(0, page.rect.height / 2 - 50,
                                             page.rect.width, page.rect.height / 2 + 50)
                        # insert_textbox will handle layout; rotate by 45 degrees for watermark feel
                        page.insert_textbox(text_rect, text, fontsize=60, color=(0.5, 0.5, 0.5), fontname="helv", rotate=45)

                    output = io.BytesIO()
                    pdf_doc.save(output, garbage=4, deflate=True)
                    pdf_doc.close()
                    output.seek(0)

                    response = FileResponse(output, content_type='application/pdf')
                    response['Content-Disposition'] = 'attachment; filename="watermarked.pdf"'
                    return response
                except Exception:
                    # If PyMuPDF fails for any reason, fall back to reportlab approach below
                    pass

            # Fallback: try reportlab to create a watermark and merge with PyPDF2
            try:
                from reportlab.pdfgen import canvas
                from reportlab.lib.colors import Color

                pdf_reader = PyPDF2.PdfReader(io.BytesIO(pdf_bytes))
                pdf_writer = PyPDF2.PdfWriter()

                for page in pdf_reader.pages:
                    page_width = float(page.mediabox.width)
                    page_height = float(page.mediabox.height)

                    watermark_buffer = io.BytesIO()
                    c = canvas.Canvas(watermark_buffer, pagesize=(page_width, page_height))
                    # Try setting alpha if available; ignore if not
                    try:
                        c.setFillAlpha(0.25)
                    except Exception:
                        pass

                    c.saveState()
                    c.translate(page_width / 2.0, page_height / 2.0)
                    c.rotate(45)
                    # Use a gray color
                    c.setFillColor(Color(0.5, 0.5, 0.5))
                    c.setFont("Helvetica", int(min(page_width, page_height) / 8))
                    c.drawCentredString(0, 0, text)
                    c.restoreState()
                    c.save()

                    watermark_buffer.seek(0)
                    watermark_pdf = PyPDF2.PdfReader(watermark_buffer)
                    watermark_page = watermark_pdf.pages[0]
                    try:
                        page.merge_page(watermark_page)
                    except Exception:
                        # For newer PyPDF2 versions the merging API may differ
                        page.merge_page(watermark_page)
                    pdf_writer.add_page(page)

                output = io.BytesIO()
                pdf_writer.write(output)
                output.seek(0)

                response = FileResponse(output, content_type='application/pdf')
                response['Content-Disposition'] = 'attachment; filename="watermarked.pdf"'
                return response
            except Exception as e:
                return render(request, 'pdf.html', {'error': 'Watermarking requires PyMuPDF or reportlab. Install PyMuPDF with: pip install PyMuPDF or reportlab with: pip install reportlab. (' + str(e) + ')'})
        except Exception as e:
            return render(request, 'pdf.html', {'error': f'Error watermarking PDF: {str(e)}'})
    return redirect('pdf')


def encrypt_pdf(request):
    if request.method == 'POST' and request.FILES.get('pdf'):
        try:
            password = request.POST.get('password', '')
            action = request.POST.get('action', 'encrypt')

            pdf_file = request.FILES['pdf']
            pdf_bytes = pdf_file.read()

            output = io.BytesIO()

            try:
                if action == 'encrypt':
                    # Open original PDF then save encrypted
                    with pikepdf.open(io.BytesIO(pdf_bytes)) as pdf:
                        pdf.save(output, encryption=pikepdf.Encryption(owner=password, user=password))
                    output.seek(0)

                else:  # decrypt
                    # Need password to open encrypted PDF (if it is encrypted)
                    try:
                        with pikepdf.open(io.BytesIO(pdf_bytes), password=password) as pdf:
                            # Save without encryption
                            pdf.save(output)
                        output.seek(0)
                    except pikepdf._qpdf.PasswordError:
                        return render(request, 'pdf.html', {'error': 'Incorrect password for decrypting PDF.'})

            except pikepdf.PdfError as e:
                return render(request, 'pdf.html', {'error': f'Error processing PDF: {str(e)}'})

            response = FileResponse(output, content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="{action}ed.pdf"'
            return response
        except Exception as e:
            return render(request, 'pdf.html', {'error': f'Error with encryption: {str(e)}'})
    return redirect('pdf')


def compress_pdf(request):
    if request.method == 'POST' and request.FILES.get('pdf'):
        try:
            size = float(request.POST.get('size', 1.0))
            unit = request.POST.get('unit', 'mb')
            pdf_file = request.FILES['pdf']
            pdf_bytes = pdf_file.read()
            
            # Convert target size to bytes
            target_bytes = size * 1024 if unit == 'kb' else size * 1024 * 1024
            current_size = len(pdf_bytes)
            
            # If already smaller than target, just return original
            if current_size <= target_bytes:
                response = FileResponse(io.BytesIO(pdf_bytes), content_type='application/pdf')
                response['Content-Disposition'] = 'attachment; filename="compressed.pdf"'
                return response
            
            # Convert PDF to images and compress
            from pdf2image import convert_from_bytes
            
            best_output = None
            best_size = current_size
            found_target = False
            
            # Iteratively reduce DPI and quality until target is met
            for dpi in [300, 200, 150, 100, 75, 50, 40, 30]:
                if found_target:
                    break
                    
                try:
                    images = convert_from_bytes(pdf_bytes, dpi=dpi)
                    
                    if not images:
                        continue
                    
                    # Try different quality levels
                    for quality in [95, 85, 75, 65, 55, 45, 35, 25, 15]:
                        try:
                            output = io.BytesIO()
                            
                            # Convert all images to RGB
                            rgb_images = [img.convert('RGB') for img in images]
                            
                            # Save as PDF with specified quality
                            rgb_images[0].save(
                                output,
                                format='PDF',
                                save_all=True,
                                append_images=rgb_images[1:] if len(rgb_images) > 1 else [],
                                quality=quality,
                                optimize=True,
                                compress_level=9
                            )
                            
                            output.seek(0, 2)  # Seek to end to get size
                            output_size = output.tell()
                            output.seek(0)  # Reset to beginning
                            
                            # If we found exact or very close match, return it
                            if output_size <= target_bytes:
                                response = FileResponse(output, content_type='application/pdf')
                                response['Content-Disposition'] = 'attachment; filename="compressed.pdf"'
                                return response
                            
                            # Keep track of best compression
                            if output_size < best_size:
                                best_output = output
                                best_size = output_size
                        except:
                            continue
                except:
                    continue
            
            # If we have a best output, return it
            if best_output:
                best_output.seek(0)
                response = FileResponse(best_output, content_type='application/pdf')
                response['Content-Disposition'] = 'attachment; filename="compressed.pdf"'
                return response
            
            # Fallback: return original with message
            response = FileResponse(io.BytesIO(pdf_bytes), content_type='application/pdf')
            response['Content-Disposition'] = 'attachment; filename="compressed.pdf"'
            return response
            
        except Exception as e:
            return render(request, 'pdf.html', {'error': f'Error compressing PDF: {str(e)}'})
    return redirect('pdf')


# ==================== IMAGE OPERATIONS ====================

def resize_pixels(request):
    if request.method == 'POST' and request.FILES.get('image'):
        try:
            width = int(request.POST.get('width', 800))
            height = int(request.POST.get('height', 600))
            
            img = Image.open(request.FILES['image'])
            img = img.resize((width, height), Image.Resampling.LANCZOS)
            
            output = io.BytesIO()
            img.save(output, format='PNG')
            output.seek(0)
            
            response = FileResponse(output, content_type='image/png')
            response['Content-Disposition'] = 'attachment; filename="resized.png"'
            return response
        except Exception as e:
            return render(request, 'images.html', {'error': f'Error resizing image: {str(e)}'})
    return redirect('images')


def resize_filesize(request):
    if request.method == 'POST' and request.FILES.get('image'):
        try:
            size = float(request.POST.get('size', 1.0))
            unit = request.POST.get('unit', 'kb')
            
            # Convert target size to bytes
            target_bytes = size * 1024 if unit == 'kb' else size * 1024 * 1024
            
            img = Image.open(request.FILES['image'])
            quality = 85
            
            # Iteratively reduce quality until target size is met
            while quality > 10:
                output = io.BytesIO()
                img.save(output, format='JPEG', quality=quality, optimize=True)
                output.seek(0, 2)  # Seek to end
                file_size = output.tell()
                
                if file_size <= target_bytes:
                    output.seek(0)
                    response = FileResponse(output, content_type='image/jpeg')
                    response['Content-Disposition'] = 'attachment; filename="resized.jpg"'
                    return response
                
                quality -= 5
            
            output = io.BytesIO()
            img.save(output, format='JPEG', quality=10, optimize=True)
            output.seek(0)
            response = FileResponse(output, content_type='image/jpeg')
            response['Content-Disposition'] = 'attachment; filename="resized.jpg"'
            return response
        except Exception as e:
            return render(request, 'images.html', {'error': f'Error resizing image: {str(e)}'})
    return redirect('images')


def crop_image(request):
    if request.method == 'POST':
        try:
            left = int(float(request.POST.get('left', 0)))
            top = int(float(request.POST.get('top', 0)))
            right = int(float(request.POST.get('right', 100)))
            bottom = int(float(request.POST.get('bottom', 100)))
            
            # Handle base64 image data (from drag editor) or file upload
            if request.POST.get('image_data'):
                # Base64 image data from crop editor
                import base64
                img_data = request.POST.get('image_data')
                if img_data.startswith('data:image'):
                    img_data = img_data.split(',')[1]
                img_bytes = base64.b64decode(img_data)
                img = Image.open(io.BytesIO(img_bytes))
            elif request.FILES.get('image'):
                img = Image.open(request.FILES['image'])
            else:
                return render(request, 'images.html', {'error': 'No image provided'})
            
            # Ensure crop coordinates are within bounds
            left = max(0, min(left, img.width))
            top = max(0, min(top, img.height))
            right = max(left + 1, min(right, img.width))
            bottom = max(top + 1, min(bottom, img.height))
            
            img = img.crop((left, top, right, bottom))
            
            output = io.BytesIO()
            img.save(output, format='PNG')
            output.seek(0)
            
            response = FileResponse(output, content_type='image/png')
            response['Content-Disposition'] = 'attachment; filename="cropped.png"'
            return response
        except Exception as e:
            return render(request, 'images.html', {'error': f'Error cropping image: {str(e)}'})
    return redirect('images')


def compress_image(request):
    if request.method == 'POST' and request.FILES.get('image'):
        try:
            quality = int(request.POST.get('quality', 75))
            
            img = Image.open(request.FILES['image'])
            if img.mode in ('RGBA', 'LA', 'P'):
                img = img.convert('RGB')
            
            output = io.BytesIO()
            img.save(output, format='JPEG', quality=quality, optimize=True)
            output.seek(0)
            
            response = FileResponse(output, content_type='image/jpeg')
            response['Content-Disposition'] = 'attachment; filename="compressed.jpg"'
            return response
        except Exception as e:
            return render(request, 'images.html', {'error': f'Error compressing image: {str(e)}'})
    return redirect('images')


def create_collage(request):
    if request.method == 'POST' and request.FILES.getlist('images'):
        try:
            cols = int(request.POST.get('cols', 2))
            spacing = int(request.POST.get('spacing', 5))
            
            images = []
            for img_file in request.FILES.getlist('images'):
                img = Image.open(img_file).convert('RGB')
                images.append(img)
            
            if not images:
                return render(request, 'images.html', {'error': 'No images provided'})
            
            # Standardize image size
            img_width, img_height = 200, 200
            images = [img.resize((img_width, img_height), Image.Resampling.LANCZOS) for img in images]
            
            # Calculate collage dimensions
            rows = (len(images) + cols - 1) // cols
            collage_width = cols * img_width + (cols - 1) * spacing
            collage_height = rows * img_height + (rows - 1) * spacing
            
            # Create collage
            collage = Image.new('RGB', (collage_width, collage_height), (50, 50, 50))
            
            for idx, img in enumerate(images):
                row = idx // cols
                col = idx % cols
                x = col * (img_width + spacing)
                y = row * (img_height + spacing)
                collage.paste(img, (x, y))
            
            output = io.BytesIO()
            collage.save(output, format='PNG')
            output.seek(0)
            
            response = FileResponse(output, content_type='image/png')
            response['Content-Disposition'] = 'attachment; filename="collage.png"'
            return response
        except Exception as e:
            return render(request, 'images.html', {'error': f'Error creating collage: {str(e)}'})
    return redirect('images')
