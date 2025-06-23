import pdfplumber
import pandas as pd
import re

def extract_tata(pdf_path) -> pd.DataFrame:
    referencias = []
    montos = []

    with pdfplumber.open(pdf_path) as pdf:
        text = ""
        for page in pdf.pages:
            text += page.extract_text() + "\n"

    ref_section = re.search(r"INFORMACIÓN DE REFERENCIA(.+?)Resolución", text, re.DOTALL)
    if ref_section:
        ref_lines = ref_section.group(1).splitlines()
        for line in ref_lines:
            match = re.search(r"Fac:\s*A?(\d{5,8})", line)
            if match:
                referencias.append(match.group(1).strip())

    for line in text.splitlines():
        if re.match(r"^\s*2183165\s+", line):
            parts = line.split()
            if parts:
                posible_monto = parts[-1]
                if re.match(r"\d{1,3}(?:\.\d{3})*,\d{2}", posible_monto):
                    try:
                        monto_float = float(posible_monto.replace(".", "").replace(",", "."))
                        montos.append(monto_float)
                    except ValueError:
                        continue

    # Emparejar referencias y montos
    cantidad = min(len(referencias), len(montos))
    data = [
        {"Referencia": referencias[i], "Monto": montos[i]}
        for i in range(cantidad)
    ]

    return pd.DataFrame(data)

