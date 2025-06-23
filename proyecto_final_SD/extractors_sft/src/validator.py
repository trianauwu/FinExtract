from pathlib import Path
import pandas as pd

def validate_excel(file_path: Path, original_pdf_name: str) -> None:
    try:
        df = pd.read_excel(file_path)
    except Exception as e:
        print(f"Error abriendo {file_path.name}: {e}")
        return

    logs = [f"[Validación de {original_pdf_name}]"]

    def log(msg): logs.append(f"{msg}")

    if "Referencia" in df.columns and "Monto" in df.columns:
        for i, row in df.iterrows():
            ref = str(row["Referencia"]).strip()
            if ref.startswith("A-0") and not ref.startswith("A-00"):
                try:
                    monto = float(str(row["Monto"]).replace(",", ".").strip())
                    if monto < 0:
                        log(f"Referencia {ref} tiene monto negativo: {monto:.2f}")
                except:
                    continue

    if "Referencia" in df.columns:
        refs = df["Referencia"].astype(str)
        duplicados = refs[refs != "TOTAL:"].value_counts()
        for ref, count in duplicados.items():
            if count >= 2:
                log(f"Referencia duplicada: {ref} aparece {count} veces")

    # 3. Referencias con más de 7 dígitos
    for ref in df.get("Referencia", []):
        if pd.notna(ref):
            digitos = ''.join(filter(str.isdigit, str(ref)))
            if len(digitos) > 7:
                log(f"Referencia con más de 7 dígitos: {ref}")

    # 4. Verificación de totales (si hay fila TOTAL:)
    if "Referencia" in df.columns and "TOTAL:" in df["Referencia"].astype(str).values:
        totales = df[df["Referencia"] == "TOTAL:"].iloc[0]
        datos = df[df["Referencia"] != "TOTAL:"]
        for col in ["Monto", "Descuento", "Retención"]:
            if col in df.columns:
                try:
                    datos_col = datos[col].astype(str).str.replace(",", ".").astype(float)
                    suma = datos_col.dropna().sum()
                    declarado = float(str(totales[col]).replace(",", "."))
                    if abs(suma - declarado) > 0.01:
                        log(f"Total en '{col}' incorrecto: declarado {declarado:.2f} vs suma real {suma:.2f}")
                except:
                    continue

    for i, row in df.iterrows():
        ref = row.get("Referencia")
        monto = row.get("Monto")
        monto_original = row.get("Monto Original")

        ref_valida = pd.notna(ref) and str(ref).strip().lower() != "nan" and str(ref).strip() != ""

        monto_valido = False
        for val in [monto, monto_original]:
            try:
                val_float = float(str(val).replace(",", ".").strip())
                if not pd.isna(val_float):
                    monto_valido = True
                    break
            except:
                continue

        if not ref_valida or not monto_valido:
            log(f"Fila {i + 2} con campos faltantes (Referencia o Monto/Monto Original)")

    if len(logs) == 1:
        logs.append("Sin advertencias detectadas.")

    output_path = file_path.with_name(f"{file_path.stem}_validation.txt")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(logs))
