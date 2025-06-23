import re
import pandas as pd
import pdfplumber
from decimal import Decimal, InvalidOperation

def format_decimal_value(monto: Decimal) -> str:
    rounded = monto.quantize(Decimal("0.01"))
    formatted_str = f"{abs(rounded):.2f}".replace(".", ",")
    return f"-{formatted_str}" if monto < 0 else formatted_str

def extract_ops_ussel(pdf_path) -> pd.DataFrame:
    pattern = re.compile(
        r"(FAC|RR|NM|NA|NC)\s+Nº[:\s]*(\d{5,8})\s+por\s+\$\s*"
        r"(-?(?:\d{1,3}(?:\.\d{3})+|\d+)(?:[.,]\d+)?)"
    )
    
    with pdfplumber.open(pdf_path) as pdf:
        text = "\n".join(page.extract_text() for page in pdf.pages if page.extract_text())

    matches = pattern.findall(text)
    registros = {}

    for tipo, ref, monto_str in matches:
        try:
            if ',' in monto_str:
                monto = Decimal(monto_str.replace(".", "").replace(",", "."))
            else:
                monto = Decimal(monto_str)
        except InvalidOperation:
            continue

        formatted_monto = format_decimal_value(monto)

        registro = registros.setdefault(ref, {"Referencia": ref, "Monto Original": None, "Retención": None})
        if tipo == "RR":
            registro["Retención"] = formatted_monto
        else:
            registro["Monto Original"] = formatted_monto

    return pd.DataFrame(registros.values())
