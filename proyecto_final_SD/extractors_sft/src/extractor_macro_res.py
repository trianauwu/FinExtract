import pdfplumber
import pandas as pd
import re
from collections import Counter

def extract_res_macro(pdf_path) -> pd.DataFrame:
    def format_monto(x):
        return f"-{int(abs(x))},{str(abs(x)).split('.')[-1][:2]}" if x < 0 else f"{int(x)},{str(x).split('.')[-1][:2]}"

    rows = []
    prefixes = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue

            for line in text.splitlines():
                ref_match = re.search(r"\bA\d{5,8}\b", line)
                if ref_match:
                    prefixes.append(ref_match.group(0)[:2])

    if not prefixes:
        return pd.DataFrame()

    mayoritario = Counter(prefixes).most_common(1)[0][0]

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue

            for line in text.splitlines():
                ref_match = re.search(r"\bA\d{5,8}\b", line)
                montos = re.findall(r"-?\d{1,3}(?:\.\d{3})*,\d{2}", line)

                if not ref_match or len(montos) < 2:
                    continue

                ref = ref_match.group(0)
                base = float(montos[-2].replace(".", "").replace(",", "."))
                ret = float(montos[-1].replace(".", "").replace(",", "."))

                monto = base if ref[:2] == mayoritario else round(base * 1.22, 2)
                ajustado = "No" if ref[:2] == mayoritario else "Sí"

                rows.append({
                    "Referencia": ref,
                    "Monto": monto,
                    "Retención": format_monto(ret),
                    "Ajustado": ajustado
                })

    return pd.DataFrame(rows)