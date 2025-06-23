import pdfplumber
import pandas as pd
import re

def extract_polakof(pdf_path) -> pd.DataFrame:
    text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"

    pattern = r"Documento\s+([A]?\d+):\s+([-\d.,]+)\s+UYU"
    matches = re.findall(pattern, text)

    rows = []
    for ref, monto in matches:
        try:
            monto_float = float(monto.replace(",", ""))
            rows.append({"Referencia": ref.strip(), "Monto": monto_float})
        except ValueError:
            continue  
    return pd.DataFrame(rows)
