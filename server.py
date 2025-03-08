import pandas as pd
import os
from flask import Flask, request, jsonify, send_file
from datetime import datetime

app = Flask(__name__)
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
CSV_FILE = "previous_kilometer_data.csv"

def get_report_filename():
    """ Generate a filename for the report with the current date """
    date_str = datetime.now().strftime("%Y-%m-%d")
    return f"km_deviation_report_{date_str}.csv"

def clear_upload_folder():
    """ Delete all files in the upload folder before a new upload """
    for filename in os.listdir(UPLOAD_FOLDER):
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        try:
            if os.path.isfile(file_path):
                os.unlink(file_path)
        except Exception as e:
            print(f"Error deleting file {file_path}: {e}")

def load_previous_data():
    """ Load previous data if available, otherwise initialize empty """
    if os.path.exists(CSV_FILE):
        return pd.read_csv(CSV_FILE)
    return pd.DataFrame(columns=["קבוצה", "רישוי", "קילומטרז'", "חריגה"])

def update_kilometer_status(excel_path):
    """ Load new data, compare with previous data, and update deviations """
    
    print("🔹 File received:", excel_path)
    
    # Load Excel file
    xls = pd.ExcelFile(excel_path)
    df = pd.read_excel(xls, sheet_name="Grid", skiprows=2)
    
    df.columns = df.columns.str.strip()
    print("📌 Column names in file:", df.columns.tolist())  
    
    # Find mileage column
    kilometer_col = next((col for col in df.columns if "קילומטרז" in col), None)
    if not kilometer_col:
        print("❌ Error: Mileage column not found!")
        return {"error": "Mileage column not found"}
    
    df = df[['קבוצה', 'רישוי', kilometer_col]].dropna()
    df.rename(columns={kilometer_col: "קילומטרז'"}, inplace=True)
    df["קילומטרז'"] = pd.to_numeric(df["קילומטרז'"], errors='coerce')
    
    # Load previous data
    previous_data = load_previous_data()
    print("📊 Previous data loaded:", previous_data.shape)
    
    if previous_data.empty:
        df["חריגה"] = 0
        df.to_csv(CSV_FILE, index=False)
        print("✅ No previous data, initialized to 0.")
        return df.to_dict(orient="records")
    
    # Define deviation thresholds
    thresholds = {
        "4 נוסעים": 20000,
        "6 נוסעים": 25000,
        "8 נוסעים": 15000,
        "14 נוסעים": 40000,
        "19 נוסעים": 40000,
    }
    
    # Compare data
    merged = df.merge(previous_data, on=["קבוצה", "רישוי"], how="left", suffixes=("_חדש", "_קודם"))
    merged["הפרש יומי"] = merged["קילומטרז'_חדש"] - merged["קילומטרז'_קודם"]
    
    # Check for deviations
    merged["חריגה"] = merged.apply(
        lambda row: "חריגה" if row["הפרש יומי"] > thresholds.get(row["קבוצה"], float('inf')) else "תקין",
        axis=1
    )
    
    # Save deviation report
    report_filename = get_report_filename()
    merged.to_csv(report_filename, index=False, encoding="utf-8-sig")
    print(f"✅ Deviation report saved as {report_filename}")
    
    # Only update previous data if there are deviations
    if "חריגה" in merged.columns and all(merged["חריגה"] == "תקין"):
        print("✅ All data is OK, not updating previous records.")
    else:
        df.to_csv(CSV_FILE, index=False, encoding="utf-8-sig")
        print("⚠️ Deviations found - previous records updated!")
    
    return merged.to_dict(orient="records"), report_filename

@app.route("/upload", methods=["POST"])
def upload_file():
    clear_upload_folder()  # Delete previous files before uploading a new one
    
    if 'file' not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400
    
    file_path = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(file_path)
    
    result, report_filename = update_kilometer_status(file_path)
    return jsonify({"result": result, "report_filename": report_filename})

@app.route("/download_report", methods=["GET"])
def download_report():
    report_filename = get_report_filename()
    if os.path.exists(report_filename):
        return send_file(report_filename, as_attachment=True)
    return jsonify({"error": "Deviation report not found"}), 404

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
