import pdfplumber
import pandas as pd
import re

def extract_ops_macro(pdf_path) -> pd.DataFrame:
    text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"

    rows = []
    for line in text.splitlines():
        ref_match = re.search(r"\bA\d{5,8}\b", line)
        monto_match = re.findall(r"-?\d{1,3}(?:\.\d{3})*,\d{2}", line)

        if ref_match and monto_match:
            ref = ref_match.group(0).strip()
            bruto = monto_match[-1].strip()  
            try:
                monto = float(bruto.replace(".", "").replace(",", "."))
                rows.append({"Referencia": ref, "Monto": monto})
            except ValueError:
                continue

    return pd.DataFrame(rows)

