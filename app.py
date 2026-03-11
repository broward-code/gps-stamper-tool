import os
import re
import zipfile
import io
from PIL import Image
import pytesseract
import piexif

# --- CONFIGURATION ---
EXCEL_FILE = 'field_data.xlsx'
OUTPUT_FOLDER = 'processed_geotech_photos'
# Ensure Tesseract is in your PATH or specify here:
# pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

def dd_to_exif_rational(dd):
    """Converts decimal degrees to EXIF-compatible rational format."""
    dd = abs(dd)
    degrees = int(dd)
    minutes_full = (dd - degrees) * 60
    minutes = int(minutes_full)
    seconds = int(round((minutes_full - minutes) * 60 * 100, 0))
    return ((degrees, 1), (minutes, 1), (seconds, 100))

def parse_coordinates(text):
    """
    Detects and converts both DD and DMS formats from OCR text.
    Handles: N26.081078 W80.169002 OR 26°4'51"N 80°10'8"W
    """
    # Clean up common OCR noise
    text = text.replace('\n', ' ').strip()
    
    # Pattern 1: Decimal Degrees (DD) - e.g., N26.081078 W80.169002
    dd_pattern = r'([NS])\s?(\d+\.\d+)\s+([EW])\s?(\d+\.\d+)'
    
    # Pattern 2: Degrees Minutes Seconds (DMS) - e.g., 26°4\'51"N
    dms_pattern = r'(\d+)[°\s](\d+)[\'\s](\d+\.?\d*)[\"\s]([NS])\s+(\d+)[°\s](\d+)[\'\s](\d+\.?\d*)[\"\s]([EW])'

    # Try DD first (The recent failure case)
    dd_match = re.search(dd_pattern, text)
    if dd_match:
        lat_ref, lat_val, lon_ref, lon_val = dd_match.groups()
        return float(lat_val), lat_ref, float(lon_val), lon_ref

    # Try DMS
    dms_match = re.search(dms_pattern, text)
    if dms_match:
        la_d, la_m, la_s, la_ref, lo_d, lo_m, lo_s, lo_ref = dms_match.groups()
        lat_dd = int(la_d) + int(la_m)/60 + float(la_s)/3600
        lon_dd = int(lo_d) + int(lo_m)/60 + float(lo_s)/3600
        return lat_dd, la_ref, lon_dd, lo_ref

    return None

def process_photos(excel_path):
    if not os.path.exists(OUTPUT_FOLDER):
        os.makedirs(OUTPUT_FOLDER)

    with zipfile.ZipFile(excel_path, 'r') as archive:
        image_files = [f for f in archive.namelist() if f.startswith('xl/media/')]
        
        for img_name in image_files:
            img_data = archive.read(img_name)
            local_name = os.path.basename(img_name)
            local_path = os.path.join(OUTPUT_FOLDER, local_name)
            
            with open(local_path, 'wb') as f:
                f.write(img_data)

            # --- TARGETED CALIBRATION LOGIC ---
            with Image.open(local_path) as img:
                w, h = img.size
                # Crop to Lower-Right Corner (Right 40%, Bottom 25%)
                # This fixes the "Looking at lower-left" issue
                crop_box = (int(w * 0.6), int(h * 0.75), w, h)
                roi = img.crop(crop_box)
                
                # Optional: Pre-process ROI for better OCR (Grayscale)
                roi = roi.convert('L') 
                ocr_text = pytesseract.image_to_string(roi)
            
            coords = parse_coordinates(ocr_text)
            
            if coords:
                lat, lat_ref, lon, lon_ref = coords
                
                # Build EXIF
                gps_ifd = {
                    piexif.GPSIFD.GPSLatitudeRef: lat_ref,
                    piexif.GPSIFD.GPSLatitude: dd_to_exif_rational(lat),
                    piexif.GPSIFD.GPSLongitudeRef: lon_ref,
                    piexif.GPSIFD.GPSLongitude: dd_to_exif_rational(lon),
                }
                exif_dict = {"GPS": gps_ifd}
                exif_bytes = piexif.dump(exif_dict)
                
                # Save with metadata
                img = Image.open(local_path)
                img.save(local_path, exif=exif_bytes)
                print(f"✅ {local_name}: Injected {lat_ref}{lat}, {lon_ref}{lon}")
            else:
                print(f"⚠️ {local_name}: OCR text found ('{ocr_text.strip()}') but no coordinates parsed.")

if __name__ == "__main__":
    process_photos(EXCEL_FILE)
