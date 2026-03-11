import streamlit as st
import os
import re
import zipfile
import io
from PIL import Image
import pytesseract
import piexif

# --- STREAMLIT UI ---
st.title("📍 Geotech Photo GPS Stamper")
st.write("Upload your Excel workbook to extract photos and inject GPS metadata.")

# File Uploader replaces EXCEL_FILE variable
uploaded_file = st.file_uploader("Choose an Excel workbook (.xlsx)", type="xlsx")

def dd_to_exif_rational(dd):
    dd = abs(dd)
    degrees = int(dd)
    minutes_full = (dd - degrees) * 60
    minutes = int(minutes_full)
    seconds = int(round((minutes_full - minutes) * 60 * 100, 0))
    return ((degrees, 1), (minutes, 1), (seconds, 100))

def parse_coordinates(text):
    text = text.replace('\n', ' ').strip()
    dd_pattern = r'([NS])\s?(\d+\.\d+)\s+([EW])\s?(\d+\.\d+)'
    dms_pattern = r'(\d+)[°\s](\d+)[\'\s](\d+\.?\d*)[\"\s]([NS])\s+(\d+)[°\s](\d+)[\'\s](\d+\.?\d*)[\"\s]([EW])'

    dd_match = re.search(dd_pattern, text)
    if dd_match:
        lat_ref, lat_val, lon_ref, lon_val = dd_match.groups()
        return float(lat_val), lat_ref, float(lon_val), lon_ref

    dms_match = re.search(dms_pattern, text)
    if dms_match:
        la_d, la_m, la_s, la_ref, lo_d, lo_m, lo_s, lo_ref = dms_match.groups()
        lat_dd = int(la_d) + int(la_m)/60 + float(la_s)/3600
        lon_dd = int(lo_d) + int(lo_m)/60 + float(lo_s)/3600
        return lat_dd, la_ref, lon_dd, lo_ref
    return None

if uploaded_file:
    output_zip = io.BytesIO()
    
    with zipfile.ZipFile(output_zip, 'w') as new_zip:
        # Open the uploaded Excel as a zip to extract media
        with zipfile.ZipFile(uploaded_file, 'r') as archive:
            image_files = [f for f in archive.namelist() if f.startswith('xl/media/')]
            
            if not image_files:
                st.error("No images found in the uploaded workbook.")
            
            for img_name in image_files:
                img_data = archive.read(img_name)
                img_io = io.BytesIO(img_data)
                
                with Image.open(img_io) as img:
                    # Fix Orientation and Crop for OCR
                    w, h = img.size
                    crop_box = (int(w * 0.6), int(h * 0.75), w, h)
                    roi = img.crop(crop_box).convert('L')
                    
                    ocr_text = pytesseract.image_to_string(roi)
                    coords = parse_coordinates(ocr_text)
                    
                    if coords:
                        lat, lat_ref, lon, lon_ref = coords
                        gps_ifd = {
                            piexif.GPSIFD.GPSLatitudeRef: lat_ref,
                            piexif.GPSIFD.GPSLatitude: dd_to_exif_rational(lat),
                            piexif.GPSIFD.GPSLongitudeRef: lon_ref,
                            piexif.GPSIFD.GPSLongitude: dd_to_exif_rational(lon),
                        }
                        exif_dict = {"GPS": gps_ifd}
                        exif_bytes = piexif.dump(exif_dict)
                        
                        # Save processed image to memory
                        img_byte_arr = io.BytesIO()
                        img.save(img_byte_arr, format=img.format, exif=exif_bytes)
                        new_zip.writestr(os.path.basename(img_name), img_byte_arr.getvalue())
                        st.success(f"Processed: {os.path.basename(img_name)} ({lat_ref}{lat})")
                    else:
                        st.warning(f"Could not read coordinates on {os.path.basename(img_name)}")
                        new_zip.writestr(os.path.basename(img_name), img_data)

    st.download_button(
        label="Download Processed Photos (ZIP)",
        data=output_zip.getvalue(),
        file_name="geotech_photos_with_gps.zip",
        mime="application/zip"
    )
