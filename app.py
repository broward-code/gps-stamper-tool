import streamlit as st
import pytesseract
from PIL import Image, ImageOps, ImageDraw
if not hasattr(Image, 'Resampling'):  # Compatibility for older PIL versions
    Image.Resampling = Image
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
st.sidebar.info("The app now auto-rotates photos based on EXIF data. Use these to target the GPS stamp.")

col_l, col_r = st.sidebar.columns(2)
with col_l:
    left_p = st.slider("Left %", 0, 100, 70)
    top_p = st.slider("Top %", 0, 100, 85)
with col_r:
    right_p = st.slider("Right %", 0, 100, 98)
    bot_p = st.slider("Bottom %", 0, 100, 98)

thresh_val = st.sidebar.slider("B&W Threshold", 0, 255, 140)
invert_img = st.sidebar.checkbox("Invert Colors (Try if text is white)", value=True)

st.title("📍 Geotechnical GPS Stamper")
st.write("Automatically extracts GPS coordinates from image stamps and updates metadata.")

# 1. File Uploader
uploaded_files = st.file_uploader("Upload Field Photos", type=['jpg', 'jpeg'], accept_multiple_files=True)

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
            # 2. Open and CORRECT ORIENTATION
            img = Image.open(temp_path)
            
            # This line fixes the 'Portrait displayed as Landscape' issue
            img = ImageOps.exif_transpose(img) 
            
            w, h = img.size
            
            # Calculate Crop based on sidebar percentages
            left, top = w * (left_p / 100), h * (top_p / 100)
            right, bottom = w * (right_p / 100), h * (bot_p / 100)
            crop_area = (left, top, right, bottom)
            
            # 3. OCR Pre-processing
            crop = img.crop(crop_area).convert('L')
            if invert_img:
                crop = ImageOps.invert(crop)
            crop = crop.point(lambda x: 0 if x < thresh_val else 255) 
            
            # Show Preview for the first image
            if i == 0:
                st.subheader("🔍 Calibration Preview")
                c1, c2 = st.columns([2, 1])
                
                # Show where the crop is on the correctly oriented image
                draw_img = img.copy()
                draw = ImageDraw.Draw(draw_img)
                draw.rectangle(crop_area, outline="red", width=15)
                
                c1.image(draw_img, caption="Red box shows OCR target (Auto-Oriented)", use_container_width=True)
                c2.image(crop, caption="OCR Close-up", width=300)

            # 4. OCR Extraction
            custom_config = r'--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789.-'
            raw_text = pytesseract.image_to_string(crop, config=custom_config)
            
            # Clean text and find decimals
            coords = re.findall(r"[-+]?\d{1,3}\.\d{3,}", raw_text)

            img.close()

            if len(coords) >= 2:
                lat, lon = float(coords[0]), float(coords[1])
                
                # Regional Safety Check (Florida/SE US range)
                if 24 < abs(lat) < 35:
                    # 5. EXIF Injection
                    cmd = [
                        'exiftool', f'-GPSLatitude={lat}', f'-GPSLongitude={lon}', 
                        '-GPSLatitudeRef=N', '-GPSLongitudeRef=W', '-overwrite_original', temp_path
                    ]
                    subprocess.run(cmd, capture_output=True)
                    
                    map_data.append({"lat": lat, "lon": lon, "name": uploaded_file.name})
                    log_entries.append(f"✅ {uploaded_file.name}: {lat}, {lon}")
                    
                    with open(temp_path, "rb") as f:
                        processed_files.append((uploaded_file.name, f.read()))
                else:
                    log_entries.append(f"❌ {uploaded_file.name}: Rejected (Coords {lat} out of range)")
            else:
                log_entries.append(f"❌ {uploaded_file.name}: No coordinates found in stamp.")
            
        except Exception as e:
            log_entries.append(f"⚠️ {uploaded_file.name}: Error - {str(e)}")
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
            st.subheader("📦 Final Download")
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w") as zf:
                for filename, data in processed_files:
                    zf.writestr(f"STAMPED_{filename}", data)
            st.download_button("📥 Download ZIP", zip_buffer.getvalue(), "stamped_photos.zip", use_container_width=True)
            st.dataframe(pd.DataFrame(map_data), hide_index=True)

        st.divider()
        st.subheader("📋 Status Log")
        st.text_area("Logs", value="\n".join(log_entries), height=200)

st.divider()
st.caption("Precision Geotechnical Utility | Metadata Injection Engine")
