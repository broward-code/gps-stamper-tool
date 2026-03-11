import streamlit as st
import pytesseract
from PIL import Image, ImageOps
import subprocess
import os
import re
import zipfile
import io
import pandas as pd

# Page Config
st.set_page_config(page_title="Geotech GPS Stamper", page_icon="📍", layout="wide")

st.title("📍 Geotechnical GPS Stamper")
st.write("Extract coordinates from photo stamps, preview on a map, and download all as a ZIP.")

# 1. File Uploader
uploaded_files = st.file_uploader("Upload Field Photos (JPG/JPEG)", type=['jpg', 'jpeg'], accept_multiple_files=True)

if uploaded_files:
    map_data = [] # To store coords for the map
    processed_files = [] # To store (filename, bytes) for the ZIP

    # Create a progress bar
    progress_bar = st.progress(0)
    
    for i, uploaded_file in enumerate(uploaded_files):
        temp_path = f"temp_{uploaded_file.name}"
        with open(temp_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        
        try:
            img = Image.open(temp_path)
            w, h = img.size
            
            # Orientation Aware Cropping
            crop_area = (w * 0.35, h * 0.88, w * 0.98, h * 0.98) if h > w else (w * 0.65, h * 0.82, w * 0.98, h * 0.98)
            
            # Pre-processing
            crop = img.crop(crop_area).convert('L')
            crop = ImageOps.invert(crop).point(lambda x: 0 if x < 150 else 255) 

            # OCR
            custom_config = r'--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789.-'
            raw_text = pytesseract.image_to_string(crop, config=custom_config)
            coords = re.findall(r"[-+]?\d*\.\d+", raw_text)

            if len(coords) >= 2:
                lat, lon = float(coords[0]), float(coords[1])
                
                # ExifTool Injection
                subprocess.run(['exiftool', f'-GPSLatitude={lat}', f'-GPSLongitude={lon}', 
                                '-GPSLatitudeRef=N', '-GPSLongitudeRef=W', '-overwrite_original', temp_path])

                # Store for Map and ZIP
                map_data.append({"lat": lat, "lon": lon, "name": uploaded_file.name})
                with open(temp_path, "rb") as f:
                    processed_files.append((uploaded_file.name, f.read()))
            
        except Exception as e:
            st.error(f"Error processing {uploaded_file.name}: {e}")
        
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)
        
        progress_bar.progress((i + 1) / len(uploaded_files))

    # --- UI LAYOUT AFTER PROCESSING ---
    
    if map_data:
        st.divider()
        col1, col2 = st.columns([1, 1])

        with col1:
            st.subheader("Map Preview")
            df = pd.DataFrame(map_data)
            st.map(df) # Streamlit auto-centers this based on the points

        with col2:
            st.subheader("Bulk Download")
            st.write(f"Successfully processed {len(processed_files)} images.")
            
            # Create ZIP in memory
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w") as zf:
                for filename, data in processed_files:
                    zf.writestr(f"GPS_{filename}", data)
            
            st.download_button(
                label="🚀 Download All as ZIP",
                data=zip_buffer.getvalue(),
                file_name="stamped_geotech_photos.zip",
                mime="application/zip",
                use_container_width=True
            )
            
            # Show a small table of extracted points
            st.dataframe(df, use_container_width=True)

st.divider()
st.caption("Standard Geotechnical Tools | Florida PE Compliant Metadata Injection")
