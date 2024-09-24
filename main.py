import os
import re
from flask import Flask, jsonify, request
from google.cloud import vision, storage
from google.oauth2 import service_account
from werkzeug.utils import secure_filename

app = Flask(__name__)

# Tentukan folder untuk menyimpan gambar yang diunggah
BUCKET_NAME = 'elvora'

# Tentukan lokasi file kredensial JSON untuk Google Cloud Vision API
credentials = service_account.Credentials.from_service_account_file('json-key-file')

# Buat instance client Vision API
client = vision.ImageAnnotatorClient(credentials=credentials)
storage_client = storage.Client(credentials=credentials)

def upload_file_to_gcs(bucket_name, file, destination_blob_name):
    """Upload file ke Cloud Storage"""
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(destination_blob_name)

    # Upload file dari request
    blob.upload_from_file(file)

    return f"gs://{bucket_name}/{destination_blob_name}"
    # blob.make_public()  # Membuat file bersifat public (opsional)
    return blob.public_url

# Fungsi untuk memproses gambar dan mengekstrak teks menggunakan Vision API
def extract_text_from_image(gcs_uri):
    # Buka gambar dan kirim ke Vision API
    image = vision.Image()
    image.source.image_uri = gcs_uri
    response = client.text_detection(image=image)
    texts = response.text_annotations

    if response.error.message:
        raise Exception(f'{response.error.message}')

    # Ambil teks hasil OCR
    full_text = texts[0].description if texts else ""
    return full_text

# Fungsi untuk mengekstrak NIK, Nama, dan Tanggal Lahir menggunakan regex
def extract_ktp_data(text):
    data = {}

    # Regex untuk NIK (16 digit angka)
    nik_pattern = r'\b\d{16}\b'
    nik_match = re.search(nik_pattern, text)
    if nik_match:
        data['NIK'] = nik_match.group()

    # Regex untuk Nama (asumsi nama muncul setelah kata "Nama" atau "NAMA")
    name_pattern = r"(?:\b\d{16}\b\s*:\s*|\b\d{16}\b\s*)\s*([A-Z\s]+)\n"
    name_match = re.search(name_pattern, text, re.IGNORECASE)
    if name_match:
        data['Nama'] = name_match.group(1).strip()

    # Regex untuk Tanggal Lahir (format: dd-mm-yyyy atau dd/mm/yyyy)
    date_pattern = r'\b(\d{2}[-/]\d{2}[-/]\d{4})\b'
    date_match = re.search(date_pattern, text)
    if date_match:
        data['Tanggal Lahir'] = date_match.group()

    return data

@app.route('/verify-ktp', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    if file:
        # Simpan file yang diunggah
        filename = secure_filename(file.filename)
        destination_blob_name = f'ktp_file/{filename}'

        # unggah ke cloud storage
        try:
            gcs_url = upload_file_to_gcs(BUCKET_NAME, file, destination_blob_name)
        except Exception as e:
            return jsonify({"error": str(e)}), 500
        
        # Proses OCR menggunakan Vision API dari Cloud Storage
        try:
            full_text = extract_text_from_image(gcs_url)
        except Exception as e:
            return jsonify({"error": str(e)}), 500

        # Ekstrak NIK, Nama, dan Tanggal Lahir
        ktp_data = extract_ktp_data(full_text)

        # Return hasil dalam format JSON
        response = {
            "full_text": full_text,
            "ktp_data": ktp_data,
            "gcs_url" :gcs_url
        }

        return jsonify(response), 200

if __name__ == '__main__':
    app.run(debug=True)
