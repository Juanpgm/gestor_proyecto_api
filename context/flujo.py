import pandas as pd

# Ruta del archivo original
file_path = r"C:\Users\ASUS Vivobook\Desktop\Flujo de caja\flujo.xlsx"

# Leer el archivo
df = pd.read_excel(file_path, sheet_name="Sheet1")

# Separar columnas de Desembolso normal y REAL
columnas_desembolso = [col for col in df.columns if 'Desembolso' in col and 'REAL' not in col]
columnas_real = [col for col in df.columns if 'Desembolso REAL' in col]

# Procesar Desembolso normal
df_desembolso = df[['Organismo', 'Banco'] + columnas_desembolso].melt(
    id_vars=['Organismo', 'Banco'],
    var_name='Mes_Columna',
    value_name='Desembolso'
)
df_desembolso['Mes'] = df_desembolso['Mes_Columna'].str.extract(r'(jul-25|ago-25|sep-25|oct-25|nov-25|dic-25)')
df_desembolso = df_desembolso.dropna(subset=['Mes', 'Desembolso'])

# Procesar Desembolso REAL
df_real = df[['Organismo', 'Banco'] + columnas_real].melt(
    id_vars=['Organismo', 'Banco'],
    var_name='Mes_Columna',
    value_name='Desembolso REAL'
)
df_real['Mes'] = df_real['Mes_Columna'].str.extract(r'(jul-25|ago-25|sep-25|oct-25|nov-25|dic-25)')
df_real = df_real.dropna(subset=['Mes', 'Desembolso REAL'])

# Unir ambos DataFrames
df_final = pd.merge(
    df_desembolso[['Organismo', 'Banco', 'Mes', 'Desembolso']], 
    df_real[['Organismo', 'Banco', 'Mes', 'Desembolso REAL']], 
    on=['Organismo', 'Banco', 'Mes'], 
    how='outer'
)

# Rellenar valores nulos con 0
df_final['Desembolso'] = df_final['Desembolso'].fillna(0)
df_final['Desembolso REAL'] = df_final['Desembolso REAL'].fillna(0)

# Crear columna Periodo en formato fecha (año-mes) para Looker Studio
meses_map = {
    'jul-25': '2025-07-01',
    'ago-25': '2025-08-01', 
    'sep-25': '2025-09-01',
    'oct-25': '2025-10-01',
    'nov-25': '2025-11-01',
    'dic-25': '2025-12-01'
}
df_final['Periodo'] = pd.to_datetime(df_final['Mes'].map(meses_map))

# Reordenar columnas: Organismo, Banco, Mes, Periodo, Desembolso, Desembolso REAL
df_final = df_final[['Organismo', 'Banco', 'Mes', 'Periodo', 'Desembolso', 'Desembolso REAL']]

# Guardar el nuevo archivo
output_path = r"C:\Users\ASUS Vivobook\Desktop\Flujo de caja\Flujo_de_Caja_Largo_Con_Periodo.xlsx"
df_final.to_excel(output_path, index=False)

print(f"✅ Archivo generado correctamente en:\n{output_path}")
