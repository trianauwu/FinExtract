import pandas as pd

def transform(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    df["Referencia"] = df["Referencia"].astype(str).str.extract(r"(\d{5,8})")[0]

    def format_ref(r):
        if pd.isna(r):
            return ""
        length = len(r)
        if length == 5:
            return f"A-00{r}"
        elif length == 6:
            return f"A-0{r}"
        elif length in [7, 8]:
            return f"B-{r}"
        return r

    def format_monto(x):
        entero = int(abs(x))
        decimales = f"{abs(x):.2f}".split(".")[1]
        return f"-{entero},{decimales}" if x < 0 else f"{entero},{decimales}"

    df["Referencia"] = df["Referencia"].apply(format_ref)
    if "Monto" in df.columns:
        df["Monto"] = df["Monto"].map(format_monto)

    df = df.sort_values(by="Referencia", ascending=True)
 
    return df

