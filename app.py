import streamlit as st
import pytesseract
from PIL import Image, ImageOps
import subprocess
import os
import re
import zipfile
import io
import pandas as pd
from datetime import datetime

# Page Config
st.set_page_config(page_title="Geotech GPS Stamper", page_icon="📍", layout="wide")

st.title("📍 Geotechnical GPS Stamper")
st.write("Extract coordinates from photo stamps, inject EXIF metadata, and generate a status log.")

# 1. File Uploader
uploaded_files = st.file_uploader("Upload Field Photos (JPG/JPEG)", type=['jpg', 'jpeg'], accept_multiple_files=True)

if uploaded_files:
    map_data = [] # To store coords for the map
    processed_files = [] # To store (filename, bytes) for the ZIP
    log_entries = [] # To store text for the Status Log
    
    progress_bar = st.progress(0)
    
    for i, uploaded_file in enumerate(uploaded_files):
        # Create a unique temp path for this specific file
        temp_path = f"temp_{i}_{uploaded_file.name}"
        with open(temp_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        
        try:
            # 2. Open Image & Determine Orientation
            img = Image.open(temp_path)
            w, h = img.size
            
            # Orientation Aware Cropping (Portrait vs Landscape)
            if h > w:
                # Portrait: Bottom-ish right area
                crop_area = (w * 0.35, h * 0.88, w * 0.98, h * 0.98)
            else:
                # Landscape: Bottom-right corner
                crop_area = (w * 0.65, h * 0.82, w * 0.98, h * 0.98)
            
            # 3. OCR Pre-processing
            crop = img.crop(crop_area).convert('L')
            crop = ImageOps.invert(crop).point(lambda x: 0 if x < 150 else 255) 
            
            # Extract text
            custom_config = r'--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789.-'
            raw_text = pytesseract.image_to_string(crop, config=custom_config)
            coords = re.findall(r"[-+]?\d*\.\d+", raw_text)

            # Close image handle BEFORE calling ExifTool to prevent file locking
            img.close()

            if len(coords) >= 2:
                lat, lon = float(coords[0]), float(coords[1])
                
                # 4. ExifTool Metadata Injection
                cmd = [
                    'exiftool', 
                    f'-GPSLatitude={lat}', 
                    f'-GPSLongitude={lon}', 
                    '-GPSLatitudeRef=N', 
                    '-GPSLongitudeRef=W', 
                    '-overwrite_original', 
                    temp_path
                ]
                
                result = subprocess.run(cmd, capture_output=True, text=True)
                
                if result.returncode == 0:
                    # Store for Map, ZIP, and Log
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    map_data.append({"lat": lat, "lon": lon, "name": uploaded_file.name})
                    log_entries.append(f"[{timestamp}] SUCCESS: {uploaded_file.name} -> Lat: {lat}, Lon: {lon}")
                    
                    with open(temp_path, "rb") as f:
                        processed_files.append((uploaded_file.name, f.read()))
                else:
                    log_entries.append(f"FAILED: {uploaded_file.name} - ExifTool error.")
            else:
                log_entries.append(f"FAILED: {uploaded_file.name} - No coordinates detected in stamp.")
            
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
            df = pd.DataFrame(map_data)
            st.map(df)

        with col2:
            st.subheader("📦 Final Output")
            st.write(f"Processed: {len(processed_files)} images")
            
            # Create ZIP in memory
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w") as zf:
                for filename, data in processed_files:
                    zf.writestr(f"GPS_{filename}", data)
            
            st.download_button(
                label="📥 Download All Stamped Photos (ZIP)",
                data=zip_buffer.getvalue(),
                file_name="stamped_field_photos.zip",
                mime="application/zip",
                use_container_width=True
            )
            
            st.dataframe(df, hide_index=True)

        # --- STATUS LOG SECTION ---
        st.divider()
        st.subheader("📋 Processing Status Log")
        log_text = "\n".join(log_entries)
        st.text_area("Copy and paste these logs into your report:", value=log_text, height=200)
        
        # Download log as TXT
        st.download_button(
            label="📄 Download Log as .txt",
            data=log_text,
            file_name="processing_log.txt",
            mime="text/plain"
        )

st.divider()
st.caption(f"Geotechnical Field Utility | System Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
