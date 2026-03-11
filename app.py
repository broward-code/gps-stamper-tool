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

st.set_page_config(page_title="Geotech GPS Stamper", page_icon="📍", layout="wide")

# --- SIDEBAR CALIBRATION ---
st.sidebar.header("⚙️ OCR Calibration")
left_p = st.sidebar.slider("Left %", 0, 100, 50) # Adjusted left to capture full string
top_p = st.sidebar.slider("Top %", 0, 100, 90)
right_p = st.sidebar.slider("Right %", 0, 100, 98)
bot_p = st.sidebar.slider("Bottom %", 0, 100, 98)
thresh_val = st.sidebar.slider("B&W Threshold", 0, 255, 140)
invert_img = st.sidebar.checkbox("Invert Colors", value=True)

def dms_to_decimal(degrees, minutes, seconds, direction):
    decimal = float(degrees) + float(minutes)/60 + float(seconds)/3600
    if direction in ['S', 'W']:
        decimal = -decimal
    return decimal

st.title("📍 Geotechnical GPS Stamper")

uploaded_files = st.file_uploader("Upload Photos", type=['jpg', 'jpeg'], accept_multiple_files=True)

if uploaded_files:
    map_data, processed_files, log_entries = [], [], []
    
    for i, uploaded_file in enumerate(uploaded_files):
        temp_path = f"temp_{i}_{uploaded_file.name}"
        with open(temp_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        
        try:
            img = ImageOps.exif_transpose(Image.open(temp_path))
            w, h = img.size
            crop_area = (w*(left_p/100), h*(top_p/100), w*(right_p/100), h*(bot_p/100))
            
            crop = img.crop(crop_area).convert('L')
            if invert_img: crop = ImageOps.invert(crop)
            crop = crop.point(lambda x: 0 if x < thresh_val else 255) 

            if i == 0:
                st.subheader("🔍 Calibration Preview")
                c1, c2 = st.columns([2, 1])
                draw_img = img.copy()
                ImageDraw.Draw(draw_img).rectangle(crop_area, outline="red", width=15)
                c1.image(draw_img)
                c2.image(crop, caption="OCR Target")

            # OCR - Allowing symbols for Degrees/Minutes/Seconds
            raw_text = pytesseract.image_to_string(crop, config='--oem 3 --psm 6')
            st.write(f"Raw OCR Output: `{raw_text.strip()}`") # Show user what is being read

            # Regex to find: Degrees, Minutes, Seconds, Direction
            # Pattern: (Deg)°(Min)'(Sec)"(Dir)
            parts = re.findall(r"(\d+)[^\d]+(\d+)[^\d]+(\d+\.?\d*)[^\d]+([NSEW])", raw_text)

            img.close()

            if len(parts) >= 2:
                lat = dms_to_decimal(parts[0][0], parts[0][1], parts[0][2], parts[0][3])
                lon = dms_to_decimal(parts[1][0], parts[1][1], parts[1][2], parts[1][3])
                
                # Injection
                cmd = ['exiftool', f'-GPSLatitude={lat}', f'-GPSLongitude={lon}', '-overwrite_original', temp_path]
                subprocess.run(cmd, capture_output=True)
                
                map_data.append({"lat": lat, "lon": lon, "name": uploaded_file.name})
                processed_files.append((uploaded_file.name, open(temp_path, "rb").read()))
                log_entries.append(f"✅ {uploaded_file.name}: {lat}, {lon}")
            else:
                log_entries.append(f"❌ {uploaded_file.name}: Format not recognized.")

        except Exception as e:
            log_entries.append(f"⚠️ Error: {str(e)}")
        finally:
            if os.path.exists(temp_path): os.remove(temp_path)

    if map_data:
        st.divider()
        col1, col2 = st.columns([2, 1])
        with col1:
            st.map(pd.DataFrame(map_data))
        with col2:
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w") as zf:
                for fn, data in processed_files: zf.writestr(f"GPS_{fn}", data)
            st.download_button("📥 DOWNLOAD ALL (ZIP)", zip_buffer.getvalue(), "stamped_photos.zip", use_container_width=True)
            st.dataframe(pd.DataFrame(map_data), hide_index=True)
    else:
        st.warning("No coordinates were successfully parsed. Adjust the 'Left %' slider to ensure the full string is in the red box.")

    st.text_area("Logs", value="\n".join(log_entries))
