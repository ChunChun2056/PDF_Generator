import os
import io
import pandas as pd
import zipfile
from flask import Flask, render_template, request, send_file, jsonify, send_from_directory, session
from werkzeug.utils import secure_filename
from PIL import Image
from reportlab.pdfgen import canvas
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from reportlab.lib.utils import ImageReader
from reportlab.lib import colors
import numpy as np
import multiprocessing

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Configuration
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # Limit file upload size to 16MB
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'csv', 'zip'}

# Constants
cm = 28.3464567
BRAND_BLUE = (27 / 255, 156 / 255, 213 / 255)

# Ensure upload and output directories exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Register font (make sure Poppins-Medium.ttf is in the same directory or provide the correct path)
try:
    pdfmetrics.registerFont(TTFont("Poppins-Medium", "Poppins-Medium.ttf"))
except Exception as e:
    print(f"Warning: Poppins-Medium.ttf font not found. {e}")

# --- Helper Functions ---

def allowed_file(filename, allowed_extensions=ALLOWED_EXTENSIONS):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in allowed_extensions

def process_image(img):
    if img.mode == "RGBA":
        background = Image.new("RGB", img.size, (255, 255, 255))
        background.paste(img, mask=img.split()[3])
        img = background
    elif img.mode != "RGB":
        img = img.convert("RGB")
    return img

def normalize_name(name):
    name = ' '.join(name.split()).lower()
    name = name.replace(' ', '_')
    return name

def fit_image_to_container(img, container_width, container_height):
    img_aspect = img.width / img.height
    container_aspect = container_width / container_height

    if img_aspect > container_aspect:
        new_width = container_width
        new_height = container_width / img_aspect
        y_offset = (container_height - new_height) / 2
        x_offset = 0
    else:
        new_height = container_height
        new_width = container_height * img_aspect
        x_offset = (container_width - new_width) / 2
        y_offset = 0

    return new_width, new_height, x_offset, y_offset

def create_logo_object(img, container_w, container_h):
    container_w_px = container_w * 300 / 72
    container_h_px = container_h * 300 / 72

    new_width, new_height, x_offset, y_offset = fit_image_to_container(
        img, container_w_px, container_h_px
    )

    new_width_px = int(new_width)
    new_height_px = int(new_height)
    img = img.resize((new_width_px, new_height_px), Image.Resampling.LANCZOS)

    img_buffer = io.BytesIO()
    img.save(img_buffer, format='PNG', optimize=False)
    img_buffer.seek(0)

    return ImageReader(img_buffer), x_offset * 72 / 300, y_offset * 72 / 300, new_width * 72 / 300, new_height * 72 / 300

def create_image_object(img, photo_w, photo_h):
    img_aspect = img.width / img.height
    container_aspect = photo_w / photo_h

    if img_aspect > container_aspect:
        scale_factor = photo_h / img.height
    else:
        scale_factor = photo_w / img.width

    scale_factor *= 300 / 72
    new_width = int(img.width * scale_factor)
    new_height = int(img.height * scale_factor)

    img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

    x_offset = int((new_width - (photo_w * 300 / 72)) / 2) if new_width > photo_w * 300 / 72 else 0
    y_offset = int((new_height - (photo_h * 300 / 72)) / 2) if new_height > photo_h * 300 / 72 else 0

    img = img.crop((x_offset,
                    y_offset,
                    x_offset + (photo_w * 300 / 72),
                    y_offset + (photo_h * 300 / 72)))

    img_buffer = io.BytesIO()
    img.save(img_buffer, format='PNG', optimize=False)
    img_buffer.seek(0)

    return ImageReader(img_buffer)

def generate_single_pdf_content(name, quote, photo_path, logo_path, name_color="#000000", quote_color="#000000"):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=(10.1529 * cm, 9.652 * cm))
    c.setPageCompression(0)

    create_first_page(c, name, logo_path, name_color)
    c.showPage()

    create_second_page(c, quote, photo_path, quote_color)
    c.save()

    buffer.seek(0)
    return buffer.getvalue()

def create_first_page(c, name, logo_path, name_color):
    logo_container_w = 7.1301 * cm
    logo_container_h = 3.8261 * cm
    gap = 3 * cm

    content_height = logo_container_h + gap + (18 / 72 * cm)
    content_y_start = (9.652 * cm - content_height) / 2

    img = Image.open(logo_path)
    img = process_image(img)
    logo_obj, x_offset, y_offset, actual_width, actual_height = create_logo_object(
        img, logo_container_w, logo_container_h
    )

    logo_x = (10.1529 * cm - actual_width) / 2
    logo_y = content_y_start + gap + (18 / 72 * cm)

    c.drawImage(
        logo_obj,
        logo_x,
        logo_y,
        width=actual_width,
        height=actual_height,
        mask='auto'
    )

    c.setFont("Poppins-Medium", 18)
    try:
        c.setFillColor(name_color)
    except ValueError:
        print("Invalid name color provided. Using black as default.")
        c.setFillColor("#000000")
    text_width = c.stringWidth(name, "Poppins-Medium", 18)
    x_pos = (10.1529 * cm - text_width) / 2
    c.drawString(x_pos, content_y_start, name)

def create_second_page(c, quote, photo_path, quote_color):
    photo_w, photo_h = 7 * cm, 4 * cm
    gap = 12 / 72 * cm
    text_margin = 28 / 72 * cm

    lines = []
    text_block_height = 0
    if quote:
        c.setFont("Poppins-Medium", 10 / 0.75)
        words = quote.split()
        line = ""
        for word in words:
            test_line = f"{line} {word}".strip()
            if c.stringWidth(test_line, "Poppins-Medium", 10 / 0.75) <= (10.1529 * cm - 2 * text_margin):
                line = test_line
            else:
                lines.append(line)
                line = word
        lines.append(line)
        line_gap = 12 / 0.75
        text_block_height = len(lines) * line_gap

    # Adjust content_y_start if photo is not present
    if photo_path:
        content_height = photo_h + gap + text_block_height
    else:
        content_height = text_block_height

    content_y_start = (9.652 * cm - content_height) / 2

    if photo_path:
        try:
            img = Image.open(photo_path)
            img = process_image(img)
            image_obj = create_image_object(img, photo_w, photo_h)

            image_y = content_y_start + text_block_height + gap if quote else content_y_start

            c.drawImage(
                image_obj,
                (10.1529 * cm - photo_w) / 2,
                image_y,
                width=photo_w,
                height=photo_h,
                mask='auto',
                preserveAspectRatio=True
            )
        except Exception as e:
            print(f"Error processing image: {e}")

    if quote:
        try:
            c.setFillColor(quote_color)
        except ValueError:
            print("Invalid quote color provided. Using black as default.")
            c.setFillColor("#000000")
        y_pos = content_y_start + text_block_height if not photo_path else content_y_start
        for line in lines:
            text_width = c.stringWidth(line, "Poppins-Medium", 10 / 0.75)
            x_pos = (10.1529 * cm - text_width) / 2
            y_pos -= line_gap
            c.drawString(x_pos, y_pos, line)

def find_photo_in_zip(name, zip_ref):
    normalized_name = normalize_name(name)
    for ext in ['.jpg', '.jpeg', '.png']:
        try:
            photo_filename = f"{normalized_name}{ext}"
            for filename in zip_ref.namelist():
                if filename.lower().endswith(photo_filename):
                    return zip_ref.open(filename)
        except KeyError:
            pass
    return None

# --- Flask Routes ---

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/generate_pdf', methods=['POST'])
def generate_pdf():
    # Get data from the AJAX request
    name = request.form.get('name') or ''  # Optional: default to empty string
    quote = request.form.get('quote') or ''  # Optional: default to empty string
    name_color = request.form.get('nameColor', '#000000')
    quote_color = request.form.get('quoteColor', '#000000')

    # Handle logo upload (REQUIRED)
    if 'logo' not in request.files:
        return jsonify({'error': 'No logo file provided'}), 400
    logo_file = request.files['logo']
    if logo_file.filename == '':
        return jsonify({'error': 'No logo file selected'}), 400
    if logo_file and allowed_file(logo_file.filename):
        logo_filename = secure_filename(logo_file.filename)
        logo_path = os.path.join(app.config['UPLOAD_FOLDER'], logo_filename)
        logo_file.save(logo_path)
    else:
        return jsonify({'error': 'Invalid logo file type'}), 400

    # Handle photo upload (optional)
    photo_path = None
    if 'photo' in request.files:
        photo_file = request.files['photo']
        if photo_file.filename != '':
            if photo_file and allowed_file(photo_file.filename):
                photo_filename = secure_filename(photo_file.filename)
                photo_path = os.path.join(app.config['UPLOAD_FOLDER'], photo_filename)
                photo_file.save(photo_path)
            else:
                return jsonify({'error': 'Invalid photo file type'}), 400

    # Generate PDF content
    try:
        pdf_content = generate_single_pdf_content(name, quote, photo_path, logo_path, name_color, quote_color)
    except Exception as e:
        return jsonify({'error': f'Error generating PDF: {e}'}), 500

    # Send PDF content as a response
    return send_file(
        io.BytesIO(pdf_content),
        mimetype='application/pdf',
        as_attachment=True,
        download_name=f"{normalize_name(name) or 'generated'}.pdf"
    )

# Global variables to hold the process and event
pdf_generation_process = None
cancel_event = None
zip_file_path = None

def generate_pdfs_in_process(data, zip_file_path, logo_path, cancel_event, output_zip_path, name_color="#000000", quote_color="#000000"):
    """Generates PDFs and adds them to a ZIP archive (runs in a separate process)."""
    try:
        with zipfile.ZipFile(zip_file_path, 'r') as zip_ref:
            with zipfile.ZipFile(output_zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
                for i, (_, row) in enumerate(data.iterrows()):
                    if cancel_event.is_set():
                        break

                    name = row['name']
                    quote = str(row.get('quote', ''))
                    photo_data = find_photo_in_zip(name, zip_ref)

                    if photo_data is not None:
                        photo_path = photo_data
                    else:
                        print(f"Warning: No photo found for {name} in the ZIP file.")
                        photo_path = None

                    try:
                        if cancel_event.is_set():
                            break
                        pdf_content = generate_single_pdf_content(name, quote, photo_path, logo_path, name_color, quote_color)
                        pdf_filename = f"{normalize_name(name)}.pdf"
                        zipf.writestr(pdf_filename, pdf_content)
                    except Exception as e:
                        print(f"Error generating PDF for {name}: {e}")

    except Exception as e:
        print(f"An error occurred: {e}")

@app.route('/generate_bulk_pdfs', methods=['POST'])
def generate_bulk_pdfs():
    global pdf_generation_process
    global cancel_event
    global zip_file_path

    # Handle logo upload
    if 'logo' not in request.files:
        return jsonify({'error': 'No logo file provided'}), 400
    logo_file = request.files['logo']
    if logo_file.filename == '':
        return jsonify({'error': 'No logo file selected'}), 400
    if logo_file and allowed_file(logo_file.filename):
        logo_filename = secure_filename(logo_file.filename)
        logo_path = os.path.join(app.config['UPLOAD_FOLDER'], logo_filename)
        logo_file.save(logo_path)
    else:
        return jsonify({'error': 'Invalid logo file type'}), 400

    # Handle CSV upload
    if 'csv' not in request.files:
        return jsonify({'error': 'No CSV file provided'}), 400
    csv_file = request.files['csv']
    if csv_file.filename == '':
        return jsonify({'error': 'No CSV file selected'}), 400
    if csv_file and allowed_file(csv_file.filename, {'csv'}):
        csv_filename = secure_filename(csv_file.filename)
        csv_path = os.path.join(app.config['UPLOAD_FOLDER'], csv_filename)
        csv_file.save(csv_path)
        try:
            data = pd.read_csv(csv_path, encoding='utf-8', dtype={'quote': str})
            data['quote'] = data['quote'].fillna('')
        except Exception as e:
            return jsonify({'error': f'Error reading CSV file: {e}'}), 500
    else:
        return jsonify({'error': 'Invalid CSV file type'}), 400

    # Handle ZIP upload
    if 'photosZip' not in request.files:
        return jsonify({'error': 'No ZIP file provided'}), 400
    zip_file = request.files['photosZip']
    if zip_file.filename == '':
        return jsonify({'error': 'No ZIP file selected'}), 400
    if zip_file and allowed_file(zip_file.filename, {'zip'}):
        zip_file_path = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(zip_file.filename))
        zip_file.save(zip_file_path)
    else:
        return jsonify({'error': 'Invalid ZIP file type'}), 400

    # Get text color from request
    name_color = request.form.get('nameColor', '#000000')
    quote_color = request.form.get('quoteColor', '#000000')

    # Define the path for the output ZIP file
    output_zip_path = os.path.join(app.config['UPLOAD_FOLDER'], "generated_pdfs.zip")

    # Create a multiprocessing Event for cancellation
    cancel_event = multiprocessing.Event()

    # Start the PDF generation process
    pdf_generation_process = multiprocessing.Process(
        target=generate_pdfs_in_process,
        args=(data, zip_file_path, logo_path, cancel_event, output_zip_path, name_color, quote_color)
    )
    pdf_generation_process.start()

    return jsonify({'message': 'PDF generation started.'})

@app.route('/check_bulk_pdfs_status', methods=['GET'])
def check_bulk_pdfs_status():
    global pdf_generation_process

    if pdf_generation_process is None:
        return jsonify({'status': 'not_started'})

    if pdf_generation_process.is_alive():
        return jsonify({'status': 'running'})
    else:
        exitcode = pdf_generation_process.exitcode
        if exitcode == 0:
            return jsonify({'status': 'completed'})
        elif exitcode is None:
            return jsonify({'status': 'cancelled'})
        else:
            return jsonify({'status': 'error', 'exitcode': exitcode})

@app.route('/cancel', methods=['POST'])
def cancel():
    global pdf_generation_process
    global cancel_event

    if cancel_event:
        cancel_event.set()  # Signal the process to cancel

    if pdf_generation_process:
        pdf_generation_process.terminate()  # Terminate the process
        pdf_generation_process.join()  # Wait for the process to finish
        pdf_generation_process = None

    return jsonify({'message': 'Cancellation requested.'})

@app.route('/download_zip')
def download_zip():
    zip_path = os.path.join(app.config['UPLOAD_FOLDER'], "generated_pdfs.zip")
    if os.path.exists(zip_path):
        return send_file(
            zip_path,
            mimetype='application/zip',
            as_attachment=True,
            download_name="generated_pdfs.zip"
        )
    else:
        return jsonify({'error': 'ZIP file not found'}), 404

if __name__ == "__main__":
    app.secret_key = os.urandom(24)
    app.run(debug=True)