import os
import re
import tempfile
from flask import Flask, render_template, request, jsonify
from pdf2image import convert_from_path
from PIL import Image
import cv2
import numpy as np

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'

import platform

if platform.system() == "Windows":
    POPPLER_PATH = r"C:\Van\ConvertImageToMovie\webapp\poppler\Library\bin"
else:
    POPPLER_PATH = "/usr/bin"
    
def is_valid_file(filename):
    return not filename.startswith(('.', '~', '$'))

def natural_sort_key(text):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r'(\d+)', text)]

def get_valid_images(folder):
    try:
        return [f for f in os.listdir(folder) 
               if f.lower().endswith((".jpg", ".jpeg", ".png", ".bmp", ".tiff")) 
               and is_valid_file(f)]
    except Exception:
        return []

def get_valid_pdfs(folder):
    try:
        return [f for f in os.listdir(folder) 
               if f.lower().endswith(".pdf") 
               and is_valid_file(f)]
    except Exception:
        return []

def convert_images_to_video(folder, fps, reverse):
    images = get_valid_images(folder)
    if not images:
        return False, "No valid images found"

    try:
        images.sort(key=natural_sort_key)
        if reverse:
            images.reverse()

        first_img = None
        for image in images:
            try:
                img_path = os.path.join(folder, image)
                pil_img = Image.open(img_path)
                first_img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
                break
            except Exception:
                continue

        if first_img is None:
            return False, "Could not read any images"

        height, width = first_img.shape[:2]
        output_path = os.path.join(folder, f"{os.path.basename(folder)}.mp4")
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        video = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

        if not video.isOpened():
            return False, "Could not create video file"

        valid_frames = 0
        for image in images:
            try:
                img_path = os.path.join(folder, image)
                pil_img = Image.open(img_path)
                frame = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
                
                if frame.shape[:2] != (height, width):
                    frame = cv2.resize(frame, (width, height))
                
                video.write(frame)
                valid_frames += 1
            except Exception:
                continue

        video.release()
        return True, f"Created video with {valid_frames} frames"

    except Exception as e:
        return False, f"Error: {str(e)}"

def convert_pdf_to_video(pdf_path, fps, reverse):
    try:
        images = convert_from_path(pdf_path, poppler_path=POPPLER_PATH)
        if not images:
            return False, "No pages found in PDF"

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_images = []
            for i, img in enumerate(images):
                img_path = os.path.join(temp_dir, f"page_{i+1}.jpg")
                img.save(img_path, "JPEG")
                temp_images.append(img_path)

            if reverse:
                temp_images.reverse()

            first_img = cv2.imread(temp_images[0])
            if first_img is None:
                return False, "Could not read PDF pages"

            height, width = first_img.shape[:2]
            output_path = os.path.join(os.path.dirname(pdf_path), 
                                     f"{os.path.basename(os.path.dirname(pdf_path))}.mp4")
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            video = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

            if not video.isOpened():
                return False, "Could not create video file"

            valid_frames = 0
            for img_path in temp_images:
                frame = cv2.imread(img_path)
                if frame is not None:
                    video.write(frame)
                    valid_frames += 1

            video.release()
            return True, f"Created video with {valid_frames} pages"

    except Exception as e:
        return False, f"PDF conversion failed: {str(e)}"

@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')

@app.route('/process', methods=['POST'])
def process():
    try:
        data = request.get_json()
        source_dir = data.get('source_dir')
        fps = int(data.get('fps', 10))
        reverse = data.get('reverse', False)

        if not source_dir or not os.path.isdir(source_dir):
            return jsonify({'error': 'Invalid source directory'}), 400

        results = []
        
        # Process all subfolders in source directory
        for item in os.listdir(source_dir):
            item_path = os.path.join(source_dir, item)
            if os.path.isdir(item_path) and is_valid_file(item):
                pdfs = get_valid_pdfs(item_path)
                if pdfs:
                    success, message = convert_pdf_to_video(
                        os.path.join(item_path, pdfs[0]), fps, reverse
                    )
                else:
                    success, message = convert_images_to_video(item_path, fps, reverse)
                
                results.append({
                    'folder': item,
                    'status': 'success' if success else 'error',
                    'message': message,
                    'video_path': os.path.join(item, f"{item}.mp4") if success else None
                })

        return jsonify({
            'success': True,
            'results': results
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)