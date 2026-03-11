import streamlit as st
import re
import io
from PIL import Image, ImageOps
import pytesseract
import piexif

st.title("📸 Universal GPS Text-to-EXIF")
st.write("Upload site photos with text overlays. The script will auto-rotate, read the GPS, and inject it into the file metadata.")

uploaded_files = st.file_uploader("Upload Photos", type=["jpg", "jpeg", "png"], accept_multiple_files=True)

def dd_to_exif_rational(dd):
    dd = abs(dd)
    degrees = int(dd)
    minutes_full = (dd - degrees) * 60
    minutes = int(minutes_full)
    seconds = int(round((minutes_full - minutes) * 60 * 100, 0))
    return ((degrees, 1), (minutes, 1), (seconds, 100))

def parse_coordinates(text):
    text = text.replace('\n', ' ').strip()
    # Matches N26.081078 W80.169002 (Decimal) or DMS formats
    dd_pattern = r'([NS])\s?(\d+\.\d+)\s+([EW])\s?(\d+\.\d+)'
    dms_pattern = r'(\d+)[°\s](\d+)[\'\s](\d+\.?\d*)[\"\s]([NS])\s+(\d+)[°\s](\d+)[\'\s](\d+\.?\d*)[\"\s]([EW])'

    match = re.search(dd_pattern, text)
    if match:
        lat_ref, lat_val, lon_ref, lon_val = match.groups()
        return float(lat_val), lat_ref, float(lon_val), lon_ref

    match = re.search(dms_pattern, text)
    if match:
        la_d, la_m, la_s, la_ref, lo_d, lo_m, lo_s, lo_ref = match.groups()
        return (int(la_d) + int(la_m)/60 + float(la_s)/3600), la_ref, \
               (int(lo_d) + int(lo_m)/60 + float(lo_s)/3600), lo_ref
    return None

if uploaded_files:
    for uploaded_file in uploaded_files:
        img_bytes = uploaded_file.read()
        img = Image.open(io.BytesIO(img_bytes))

        # --- FIX ORIENTATION ---
        # This handles the "Portrait vs Landscape" issue by applying the EXIF orientation tag
        img = ImageOps.exif_transpose(img)
        
        w, h = img.size
        # To be safe, we'll scan both bottom corners (Lower 25% of the image)
        crop_box = (0, int(h * 0.75), w, h)
        roi = img.crop(crop_box).convert('L')
        
        ocr_text = pytesseract.image_to_string(roi)
        coords = parse_coordinates(ocr_text)

        if coords:
            lat, lat_ref, lon, lon_ref = coords
            
            # Prepare EXIF
            gps_ifd = {
                piexif.GPSIFD.GPSLatitudeRef: lat_ref,
                piexif.GPSIFD.GPSLatitude: dd_to_exif_rational(lat),
                piexif.GPSIFD.GPSLongitudeRef: lon_ref,
                piexif.GPSIFD.GPSLongitude: dd_to_exif_rational(lon),
            }
            exif_dict = {"GPS": gps_ifd}
            exif_bytes = piexif.dump(exif_dict)

            # Save back to a downloadable buffer
            buf = io.BytesIO()
            img.save(buf, format="JPEG", exif=exif_bytes)
            
            st.success(f"✅ {uploaded_file.name}: Injected {lat_ref}{lat}, {lon_ref}{lon}")
            st.download_button(f"Download {uploaded_file.name}", buf.getvalue(), file_name=f"gps_{uploaded_file.name}")
        else:
            st.error(f"❌ {uploaded_file.name}: Could not find coordinates in the bottom 25% of the image.")
            with st.expander("See what the OCR saw"):
                st.write(f"Raw Text: {ocr_text}")
                st.image(roi, caption="This is the area being scanned")
