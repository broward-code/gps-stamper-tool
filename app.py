import streamlit as st
import pytesseract
from PIL import Image, ImageOps, ImageDraw
import subprocess
import os
import re
import zipfile
import io
import pandas as pd
from datetime import datetime

# Page Config
st.set_page_config(page_title="Geotech GPS Stamper", page_icon="📍", layout="wide")

# --- SIDEBAR CALIBRATION CONTROLS ---
st.sidebar.header("⚙️ OCR Calibration")
st.sidebar.write("Adjust these if the 'OCR View' isn't hitting the stamp.")

col_l, col_r = st.sidebar.columns(2)
with col_l:
    left_p = st.slider("Left %", 0, 100, 65)
    top_p = st.slider("Top %", 0, 100, 80)
with col_r:
    right_p = st.slider("Right %", 0, 100, 98)
    bot_p = st.slider("Bottom %", 0, 100, 98)

thresh_val = st.sidebar.slider("B&W Threshold", 0, 255, 150, help="Higher = more white, Lower = more black")
invert_img = st.sidebar.checkbox("Invert Colors (Try if text is white)", value=True)

st.title("📍 Geotechnical GPS Stamper")
st.write("Extract coordinates, inject EXIF, and download. Use the sidebar to calibrate the OCR crop.")

# 1. File Uploader
uploaded_files = st.file_uploader("Upload Field Photos (JPG/JPEG)", type=['jpg', 'jpeg'], accept_multiple_files=True)

if uploaded_files:
    map_data = [] 
    processed_files = [] 
    log_entries = [] 
    
    progress_bar = st.progress(0)
    
    for i, uploaded_file in enumerate(uploaded_files):
        temp_path = f"temp_{i}_{uploaded_file.name}"
        with open(temp_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        
        try:
            img = Image.open(temp_path)
            w, h = img.size
            
            # --- DYNAMIC CALIBRATED CROP ---
            # Converts sidebar percentages to pixel coordinates
            left, top = w * (left_p/100), h * (top_p/100)
            right, bottom = w * (right_p/100), h * (bot_p/100)
            crop_area = (left, top, right, bottom)
            
            # 2. OCR Pre-processing
            crop = img.crop(crop_area).convert('L')
            if invert_img:
                crop = ImageOps.invert(crop)
            crop = crop.point(lambda x: 0 if x < thresh_val else 255) 
            
            # Show the first image's crop for calibration
            if i == 0:
                st.subheader("🔍 Calibration Preview (First Image)")
                c1, c2 = st.columns(2)
                c1.image(uploaded_file, caption="Original (Full)", use_container_width=True)
                c2.image(crop, caption="What the OCR sees", width=300)

            # 3. OCR Extraction
            # Whitelist limited to numbers, dots, and minus signs
            custom_config = r'--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789.-'
            raw_text = pytesseract.image_to_string(crop, config=custom_config)
            
            # Regex: Looking for specific lat/long patterns (e.g. 26.123, -80.123)
            # This looks for numbers with at least 3 decimal places to avoid noise
            coords = re.findall(r"[-+]?\d{1,3}\.\d{3,}", raw_text)

            img.close()

            if len(coords) >= 2:
                lat, lon = float(coords[0]), float(coords[1])
                
                # Validation: Florida check (Lat ~24-31, Lon ~ -79 to -88)
                if 24 < abs(lat) < 32: # Basic safety check
                    # 4. ExifTool Metadata Injection
                    cmd = [
                        'exiftool', f'-GPSLatitude={lat}', f'-GPSLongitude={lon}', 
                        '-GPSLatitudeRef=N', '-GPSLongitudeRef=W', '-overwrite_original', temp_path
                    ]
                    subprocess.run(cmd, capture_output=True)
                    
                    map_data.append({"lat": lat, "lon": lon, "name": uploaded_file.name})
                    log_entries.append(f"[{datetime.now().strftime('%H:%M:%S')}] SUCCESS: {uploaded_file.name} -> {lat}, {lon}")
                    
                    with open(temp_path, "rb") as f:
                        processed_files.append((uploaded_file.name, f.read()))
                else:
                    log_entries.append(f"FAILED: {uploaded_file.name} - Valid coords not found (OCR noise).")
            else:
                log_entries.append(f"FAILED: {uploaded_file.name} - No coordinates detected.")
            
        except Exception as e:
            log_entries.append(f"ERROR: {uploaded_file.name} - {str(e)}")
        
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)
        
        progress_bar.progress((i + 1) / len(uploaded_files))

    # --- UI LAYOUT ---
    if map_data:
        st.divider()
        col1, col2 = st.columns([2, 1])
        with col1:
            st.subheader("🗺️ Map Preview")
            st.map(pd.DataFrame(map_data))
        with col2:
            st.subheader("📦 Download Results")
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w") as zf:
                for filename, data in processed_files:
                    zf.writestr(f"GPS_{filename}", data)
            st.download_button("📥 Download All (ZIP)", zip_buffer.getvalue(), "stamped_photos.zip", "application/zip", use_container_width=True)
            st.dataframe(pd.DataFrame(map_data), hide_index=True)

        st.divider()
        st.subheader("📋 Status Log")
        st.text_area("Log Output", value="\n".join(log_entries), height=200)

st.divider()
st.caption(f"Precision Geotech Utility | Florida PE Standards")
