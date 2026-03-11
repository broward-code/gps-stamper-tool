import streamlit as st
import pytesseract
from PIL import Image
import subprocess
import os

st.title("?? Geotechnical GPS Stamper")
st.write("Upload photos to extract GPS stamps and inject them into metadata.")

uploaded_files = st.file_uploader("Choose images...", type=['jpg', 'jpeg', 'png'], accept_multiple_files=True)

if uploaded_files:
    for uploaded_file in uploaded_files:
        # 1. Load Image
        img = Image.open(uploaded_file)
        st.image(img, caption=f"Processing {uploaded_file.name}", width=300)

        # 2. OCR (Tesseract is auto-found in Linux path)
        # We use a standard crop for 1280x720; adjust as needed
        width, height = img.size
        crop_area = (width*0.7, height*0.8, width, height) 
        cropped_img = img.crop(crop_area)
        
        raw_text = pytesseract.image_to_string(cropped_img)
        st.code(f"OCR Result: {raw_text}")

        # 3. Metadata Injection via ExifTool
        # (Note: Writing back to a file in a web environment requires 
        # saving a temp file first. I can help you with that logic next!)