import pdfplumber
import pandas as pd
import re

def extract_res_ussel(pdf_path) -> pd.DataFrame:
    referencias = []
    montos = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue

            for line in text.splitlines():
                if "FA-" not in line:
                    continue

                ref_match = re.search(r"FA-(\d{5,8})", line)
                monto_match = re.search(r"\$?\s*(-?\d{1,3}(?:\.\d{3})*,\d{2})", line)

                if ref_match and monto_match:
                    referencia = ref_match.group(1)
                    monto_str = monto_match.group(1)

                    try:
                        monto = float(monto_str.replace(".", "").replace(",", "."))
                        referencias.append(referencia)
                        montos.append(monto)
                    except ValueError:
                        continue

    return pd.DataFrame({
        "Referencia": referencias,
        "Monto": montos
    })
