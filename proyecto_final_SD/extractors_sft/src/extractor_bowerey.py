import pdfplumber
import pandas as pd
import re

def extract_bowerey(pdf_path) -> pd.DataFrame:
    referencias = []
    montos = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue

            glosa_matches = re.findall(r"[Gg]losa\s+(\d{5,8})z(?:\d*[A-Z]*)?", text)
            referencias.extend(glosa_matches)

            for line in text.splitlines():
                posibles = re.findall(r"\d{1,3}(?:\.\d{3})*,\d{2}", line)
                if len(posibles) == 3:
                    valor_retencion = posibles[2]
                    try:
                        monto = float(valor_retencion.replace(".", "").replace(",", "."))
                        montos.append(monto)
                    except ValueError:
                        continue

    min_len = min(len(referencias), len(montos))
    referencias = referencias[:min_len]
    montos = montos[:min_len]

    return pd.DataFrame({
        "Referencia": referencias,
        "Monto": montos
    })
