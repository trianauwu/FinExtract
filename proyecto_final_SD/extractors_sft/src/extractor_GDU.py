import pdfplumber
import pandas as pd
import re

def extract_GDU(pdf_path) -> pd.DataFrame:
    def parse_monto(txt):
        return float(txt.replace(".", "").replace(",", "."))

    def format_coma(x):
        entero, decimales = f"{abs(x):.2f}".split(".")
        return f"-{entero},{decimales}" if x < 0 else f"{entero},{decimales}"

    def formatear_referencia_fa(ref: str) -> str:
        ref_nro = ref.split("-")[0]
        if len(ref_nro) == 8:
            return f"B-{ref_nro}"
        elif len(ref_nro) == 7 and ref_nro.startswith("1"):
            return f"B-{ref_nro}"
        elif len(ref_nro) == 6:
            return f"A-0{ref_nro}"
        elif len(ref_nro) == 5:
            return f"A-00{ref_nro}"
        else:
            return ref_nro  # fallback

    rows = []
    total_monto = total_descuento = total_retencion = 0.0

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue

            for line in text.splitlines():
                ref_match = re.search(r"(\d{4,8}-\d)", line)
                if not ref_match:
                    continue
                referencia_pdf = ref_match.group(1)

                montos = re.findall(r"-?\d{1,8},\d{2}", line)
                if not montos:
                    continue

                if "C.ASU" in line:
                    tipo = "C.ASU"
                elif "Fact" in line:
                    tipo = "FA"
                elif "Devol" in line:
                    tipo = "NC"
                else:
                    tipo = ""

                try:
                    monto = parse_monto(montos[0])
                except ValueError:
                    continue

                if tipo == "C.ASU":
                    total_monto += monto
                    rows.append({
                        "Referencia": referencia_pdf,
                        "Monto": format_coma(monto),
                        "Descuento": "0,00",
                        "Retención": "0,00",
                        "Tipo": "C.ASU"
                    })
                    continue

                if len(montos) < 3:
                    continue

                try:
                    descuento = parse_monto(montos[1])
                    retencion = parse_monto(montos[2])
                except ValueError:
                    continue

                total_monto += monto
                total_descuento += descuento
                total_retencion += retencion

                if tipo == "FA":
                    referencia_final = formatear_referencia_fa(referencia_pdf)
                else:
                    referencia_final = referencia_pdf

                rows.append({
                    "Referencia": referencia_final,
                    "Monto": format_coma(monto),
                    "Descuento": format_coma(descuento),
                    "Retención": format_coma(retencion),
                    "Tipo": tipo
                })

    if rows:
        rows.append({
            "Referencia": "TOTAL:",
            "Monto": format_coma(total_monto),
            "Descuento": format_coma(total_descuento),
            "Retención": format_coma(total_retencion),
            "Tipo": ""
        })

    return pd.DataFrame(rows)
