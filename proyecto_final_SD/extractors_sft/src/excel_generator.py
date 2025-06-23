import pandas as pd

def to_excel(df: pd.DataFrame, output_path: str):
    try:
        writer = pd.ExcelWriter(
            output_path,
            engine='xlsxwriter',
            engine_kwargs={'options': {'strings_to_numbers': True}}
        )

        df.to_excel(writer, sheet_name='Sheet1', index=False, header=False, startrow=1)

        workbook = writer.book
        worksheet = writer.sheets['Sheet1']

        header_format = workbook.add_format({
            'bold': True,
            'text_wrap': True,
            'valign': 'top',
            'fg_color': '#1F4E78',  
            'font_color': 'white',
            'border': 1
        })

        cell_format = workbook.add_format({'border': 1})
        
        for col_num, value in enumerate(df.columns.values):
            worksheet.write(0, col_num, value, header_format)

        data_range = f'A2:{chr(ord("A") + len(df.columns) - 1)}{len(df) + 1}'
        worksheet.conditional_format(data_range, {'type': 'no_blanks', 'format': cell_format})

        format_impar = workbook.add_format({'bg_color': '#F2F2F2', 'border': 1})
        format_par = workbook.add_format({'bg_color': 'white', 'border': 1})
        
        worksheet.conditional_format(data_range, {
            'type': 'formula',
            'criteria': '=MOD(ROW(),2)=1', 
            'format': format_par
        })
        worksheet.conditional_format(data_range, {
            'type': 'formula',
            'criteria': '=MOD(ROW(),2)=0', 
            'format': format_impar
        })

        for idx, col in enumerate(df.columns):
            series = df[col]
            max_len = max(
                (
                    series.astype(str).map(len).max(),
                    len(str(series.name))
                )
            ) + 2  
            worksheet.set_column(idx, idx, max_len)

        writer.close()
        print(f"Excel estilizado generado: {output_path}")

    except Exception as e:
        print(f"Error al guardar Excel en {output_path}: {e}")