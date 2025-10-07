import pandas as pd
import os
import re
import json
from datetime import datetime
from tqdm import tqdm

def clean_column_names(df):
    """
    Limpia nombres de columnas según las reglas especificadas:
    - Convertir a minúsculas
    - Cambiar espacios por "_"
    - Eliminar conectores: por, para, de, las, los, con, etc.
    """
    print("🔄 Limpiando nombres de columnas...")
    
    # Lista de conectores a eliminar
    conectores = ['de', 'del', 'la', 'las', 'el', 'los', 'con', 'para', 'por', 'en', 'a', 'y', 'o', 'un', 'una']
    
    new_columns = []
    for col in df.columns:
        # Convertir a minúsculas
        new_col = col.lower()
        
        # Reemplazar espacios por guiones bajos
        new_col = new_col.replace(' ', '_')
        
        # Dividir por guiones bajos para procesar palabra por palabra
        words = new_col.split('_')
        
        # Filtrar conectores y palabras vacías
        filtered_words = []
        for word in words:
            word = word.strip()
            if word and word not in conectores:
                filtered_words.append(word)
        
        # Unir palabras filtradas
        new_col = '_'.join(filtered_words)
        
        # Limpiar caracteres especiales (mantener solo letras, números y guiones bajos)
        new_col = re.sub(r'[^\w]', '_', new_col)
        
        # Eliminar guiones bajos múltiples
        new_col = re.sub(r'_+', '_', new_col)
        
        # Eliminar guiones bajos al inicio y final
        new_col = new_col.strip('_')
        
        new_columns.append(new_col)
    
    df.columns = new_columns
    print(f"✅ Nombres de columnas limpiados: {len(df.columns)} columnas")
    return df

def protect_urls(df):
    """
    Protege las URLs en columnas específicas durante el procesamiento
    """
    print("🔄 Protegiendo URLs de corrupción...")
    
    # Identificar columnas que contienen URLs
    url_columns = [col for col in df.columns if 'url' in col.lower()]
    
    if url_columns:
        print(f"🔗 Columnas con URLs encontradas: {url_columns}")
        
        for col in url_columns:
            # Asegurar que las URLs se mantengan como strings sin procesamiento adicional
            df[col] = df[col].astype(str)
            
            # Reemplazar valores nan/None con string vacío para evitar problemas
            df[col] = df[col].replace(['nan', 'None', 'NaN'], '')
            
            print(f"  ✅ {col}: URLs protegidas")
    else:
        print("ℹ️ No se encontraron columnas con URLs")
    
    return df

def remove_unwanted_columns(df):
    """
    Elimina columnas específicas que no son necesarias
    """
    print("🔄 Eliminando columnas innecesarias...")
    
    # Lista de columnas a eliminar
    columns_to_remove = [
        'nit_entidad', 
        'departamento', 
        'ciudad', 
        'localización', 
        'orden', 
        'rama', 
        'condiciones_entrega'
    ]
    
    # Verificar qué columnas existen realmente en el DataFrame
    existing_columns_to_remove = [col for col in columns_to_remove if col in df.columns]
    
    if existing_columns_to_remove:
        df = df.drop(columns=existing_columns_to_remove)
        print(f"✅ Eliminadas {len(existing_columns_to_remove)} columnas: {existing_columns_to_remove}")
    else:
        print("ℹ️ No se encontraron columnas para eliminar")
    
    print(f"📊 Columnas restantes: {len(df.columns)}")
    return df

def standardize_dates(df):
    """
    Convierte fechas al estándar ISO 8601 (YYYY-MM-DD)
    """
    print("🔄 Estandarizando fechas a formato ISO 8601...")
    
    # Identificar columnas de fecha
    date_columns = [col for col in df.columns if 'fecha' in col.lower()]
    
    print(f"📅 Columnas de fecha encontradas: {len(date_columns)}")
    
    for col in tqdm(date_columns, desc="Procesando fechas"):
        try:
            # Convertir a datetime y luego a formato ISO
            df[col] = pd.to_datetime(df[col], errors='coerce')
            df[col] = df[col].dt.strftime('%Y-%m-%d')
            
            # Reemplazar NaT con None
            df[col] = df[col].replace('NaT', None)
            
        except Exception as e:
            print(f"⚠️ Error procesando fecha en columna {col}: {e}")
    
    print("✅ Fechas estandarizadas a formato ISO 8601")
    return df

def convert_monetary_to_numeric(df):
    """
    Convierte datos monetarios a valores numéricos enteros
    """
    print("🔄 Convirtiendo valores monetarios a enteros...")
    
    # Identificar columnas monetarias
    monetary_columns = [col for col in df.columns if any(keyword in col.lower() for keyword in 
                       ['valor', 'monto', 'precio', 'costo', 'pago', 'facturado', 'pendiente', 
                        'pagado', 'amortizado', 'saldo', 'cdp', 'vigencia', 'presupuesto'])]
    
    # Agregar columnas específicas que también son monetarias
    specific_monetary_columns = [
        'recursos_propios_alcaldías_gobernaciones_resguardos_indígenas',
        'recursos_propios',
        'presupuesto_general_nacion_pgn',
        'sistema_general_participaciones',
        'sistema_general_regalías',
        'recursos_credito'
    ]
    
    # Agregar columnas específicas que existen en el DataFrame
    for col in specific_monetary_columns:
        if col in df.columns and col not in monetary_columns:
            monetary_columns.append(col)
    
    print(f"💰 Columnas monetarias encontradas: {len(monetary_columns)}")
    
    for col in tqdm(monetary_columns, desc="Procesando valores monetarios"):
        try:
            # Convertir a string primero
            df[col] = df[col].astype(str)
            
            # Limpiar formato monetario
            df[col] = df[col].str.replace(r'[$,\s]', '', regex=True)  # Eliminar $, comas y espacios
            df[col] = df[col].str.replace(r'[^\d.-]', '', regex=True)  # Mantener solo dígitos, punto y guión
            
            # Convertir a numérico
            df[col] = pd.to_numeric(df[col], errors='coerce')
            
            # Convertir a entero (rellenar NaN con 0)
            df[col] = df[col].fillna(0).astype('int64')
            
        except Exception as e:
            print(f"⚠️ Error procesando valor monetario en columna {col}: {e}")
    
    print("✅ Valores monetarios convertidos a enteros")
    return df

def clean_nan_values(df):
    """
    Reemplaza valores NaN, 'NaN', 'nan' por None para mejor manejo en JSON
    """
    print("🔄 Limpiando valores NaN...")
    
    # Contar valores NaN antes de la limpieza
    nan_count_before = df.isna().sum().sum()
    
    # Reemplazar diferentes representaciones de NaN
    df = df.replace({
        'NaN': None,
        'nan': None,
        'NaT': None,
        'null': None,
        'NULL': None,
        '': None
    })
    
    # Reemplazar pandas NaN con None
    df = df.where(pd.notnull(df), None)
    
    # Contar None después de la limpieza
    none_count_after = df.isnull().sum().sum()
    
    print(f"✅ Valores NaN limpiados: {nan_count_before} → {none_count_after} valores None")
    
    return df

def enrich_bpin_from_projects(df):
    """
    Enriquece los contratos con BPIN desde datos de proyectos presupuestales
    cuando el BPIN no está disponible o es 0 en SECOP
    """
    print("🔄 Enriqueciendo BPIN desde datos de proyectos presupuestales...")
    
    # Verificar si existe el archivo de proyectos
    projects_file = 'transformation_app/app_outputs/ejecucion_presupuestal_outputs/datos_caracteristicos_proyectos.json'
    if not os.path.exists(projects_file):
        print(f"⚠️ Archivo de proyectos no encontrado: {projects_file}")
        return df
    
    try:
        # Cargar datos de proyectos
        with open(projects_file, 'r', encoding='utf-8') as f:
            projects_data = json.load(f)
        
        df_projects = pd.DataFrame(projects_data)
        print(f"✅ Cargados {len(df_projects)} proyectos presupuestales")
        
        # Contar contratos sin BPIN válido
        contratos_sin_bpin = len(df[(df['bpin'] == 0) | (df['bpin'].isna())])
        print(f"📊 Contratos sin BPIN válido: {contratos_sin_bpin}")
        
        if contratos_sin_bpin == 0:
            print("✅ Todos los contratos ya tienen BPIN válido")
            return df
        
        # Crear índice de búsqueda por palabras clave
        enriched_count = 0
        
        for idx, row in df.iterrows():
            # Solo procesar contratos sin BPIN válido
            if row['bpin'] != 0 and not pd.isna(row['bpin']):
                continue
                
            descripcion = str(row.get('descripcion_proceso', '')).lower()
            referencia = str(row.get('referencia_contrato', ''))
            
            # Buscar coincidencias por palabras clave en descripción
            palabras_clave = [palabra for palabra in descripcion.split() if len(palabra) > 4][:10]
            
            mejor_coincidencia = None
            max_coincidencias = 0
            
            for _, project in df_projects.iterrows():
                nombre_proyecto = str(project['nombre_proyecto']).lower()
                coincidencias = sum(1 for palabra in palabras_clave if palabra in nombre_proyecto)
                
                if coincidencias > max_coincidencias and coincidencias >= 2:  # Mínimo 2 palabras
                    max_coincidencias = coincidencias
                    mejor_coincidencia = project
            
            # Si se encontró una buena coincidencia, asignar el BPIN
            if mejor_coincidencia is not None:
                df.at[idx, 'bpin'] = int(mejor_coincidencia['bpin'])
                enriched_count += 1
                print(f"  ✅ BPIN {mejor_coincidencia['bpin']} asignado a contrato {referencia}")
                print(f"     Proyecto: {mejor_coincidencia['nombre_proyecto'][:60]}...")
        
        print(f"🎉 Enriquecimiento completado: {enriched_count} contratos actualizados")
        
    except Exception as e:
        print(f"❌ Error enriqueciendo BPIN: {e}")
    
    return df


def add_nombre_centro_gestor(df):
    """
    Añade la columna 'nombre_centro_gestor' basada en el BPIN desde datos de proyectos presupuestales
    """
    print("🔄 Añadiendo nombre_centro_gestor desde datos de proyectos presupuestales...")
    
    # Verificar si existe el archivo de proyectos
    projects_file = 'transformation_app/app_outputs/ejecucion_presupuestal_outputs/datos_caracteristicos_proyectos.json'
    if not os.path.exists(projects_file):
        print(f"⚠️ Archivo de proyectos no encontrado: {projects_file}")
        df['nombre_centro_gestor'] = None
        return df
    
    try:
        # Cargar datos de proyectos
        with open(projects_file, 'r', encoding='utf-8') as f:
            projects_data = json.load(f)
        
        # Crear mapeo BPIN -> nombre_centro_gestor
        bpin_to_centro_gestor = {}
        for project in projects_data:
            bpin = project.get('bpin')
            nombre_centro_gestor = project.get('nombre_centro_gestor')
            if bpin and nombre_centro_gestor:
                bpin_to_centro_gestor[int(bpin)] = nombre_centro_gestor
        
        print(f"✅ Creado mapeo de {len(bpin_to_centro_gestor)} BPIN -> nombre_centro_gestor")
        
        # Añadir columna nombre_centro_gestor
        df['nombre_centro_gestor'] = df['bpin'].map(bpin_to_centro_gestor)
        
        # Contar cuántos se añadieron exitosamente
        centro_gestor_added = df['nombre_centro_gestor'].notna().sum()
        centro_gestor_missing = df['nombre_centro_gestor'].isna().sum()
        
        print(f"✅ Nombre_centro_gestor añadido:")
        print(f"   📊 Contratos con centro gestor: {centro_gestor_added}")
        print(f"   📊 Contratos sin centro gestor: {centro_gestor_missing}")
        
        return df
        
    except Exception as e:
        print(f"❌ Error añadiendo nombre_centro_gestor: {e}")
        df['nombre_centro_gestor'] = None
        return df

def rename_and_convert_bpin(df):
    """
    Renombra 'código_bpin' a 'bpin' y convierte a entero sin decimales
    """
    print("🔄 Procesando columna BPIN...")
    
    if 'código_bpin' in df.columns:
        # Renombrar columna
        df = df.rename(columns={'código_bpin': 'bpin'})
        print("✅ Columna renombrada: 'código_bpin' → 'bpin'")
        
        # Convertir a entero sin decimales
        try:
            # Limpiar valores no numéricos
            df['bpin'] = df['bpin'].astype(str)
            df['bpin'] = df['bpin'].str.replace(r'[^\d]', '', regex=True)
            
            # Convertir a entero sin decimales
            df['bpin'] = pd.to_numeric(df['bpin'], errors='coerce')
            df['bpin'] = df['bpin'].fillna(0).astype('int64')
            
            print("✅ Columna BPIN convertida a entero sin decimales")
        except Exception as e:
            print(f"⚠️ Error convirtiendo BPIN a entero: {e}")
    else:
        # Si no existe la columna código_bpin, verificar si ya existe 'bpin'
        if 'bpin' in df.columns:
            print("✅ Columna 'bpin' ya existe, verificando formato...")
            try:
                # Asegurar que sea entero sin decimales
                df['bpin'] = pd.to_numeric(df['bpin'], errors='coerce')
                df['bpin'] = df['bpin'].fillna(0).astype('int64')
                print("✅ Columna BPIN convertida a entero sin decimales")
            except Exception as e:
                print(f"⚠️ Error convirtiendo BPIN existente a entero: {e}")
        else:
            print("⚠️ Columna 'código_bpin' o 'bpin' no encontrada")
    
    return df

def group_by_bpin_and_optimize(df):
    """
    Agrupa los registros por BPIN conservando TODOS los datos de cada registro
    """
    print("🔄 Agrupando registros por BPIN (conservando todos los datos)...")
    
    if 'bpin' not in df.columns:
        print("❌ Columna 'bpin' no encontrada para agrupar")
        return df
    
    # Agrupar por BPIN
    grouped_data = {}
    
    # Obtener estadísticas generales
    unique_bpins = df[df['bpin'] != 0]['bpin'].unique()  # Excluir valores 0
    
    for bpin_value in tqdm(unique_bpins, desc="Procesando BPINs"):
        bpin_records = df[df['bpin'] == bpin_value]
        
        # Crear estructura con todos los datos
        # Filtrar fechas válidas para estadísticas
        fechas_validas = pd.to_datetime(bpin_records['fecha_firma'], errors='coerce').dropna()
        
        bpin_data = {
            'bpin': int(bpin_value),
            'resumen': {
                'total_contratos': len(bpin_records),
                'valor_total': int(bpin_records['valor_contrato'].sum()),
                'valor_promedio': int(bpin_records['valor_contrato'].mean()),
                'entidades_participantes': list(bpin_records['nombre_entidad'].unique()),
                'tipos_contrato': list(bpin_records['tipo_contrato'].unique()),
                'estados_contrato': list(bpin_records['estado_contrato'].unique()),
                'fecha_primer_contrato': fechas_validas.min().strftime('%Y-%m-%d') if len(fechas_validas) > 0 else None,
                'fecha_ultimo_contrato': fechas_validas.max().strftime('%Y-%m-%d') if len(fechas_validas) > 0 else None
            },
            'contratos': []
        }
        
        # Agregar TODOS los contratos con TODOS sus datos
        for _, record in bpin_records.iterrows():
            # Convertir la fila completa a diccionario, preservando todos los campos
            contract = record.to_dict()
            bpin_data['contratos'].append(contract)
        
        grouped_data[str(bpin_value)] = bpin_data
    
    # Crear estructura final con metadata
    result = {
        'metadata': {
            'fecha_procesamiento': pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
            'total_bpins': len(grouped_data),
            'total_contratos': len(df[df['bpin'] != 0]),
            'contratos_por_bpin_promedio': len(df[df['bpin'] != 0]) / len(grouped_data) if len(grouped_data) > 0 else 0,
            'valor_total_todos_contratos': int(df[df['bpin'] != 0]['valor_contrato'].sum())
        },
        'datos_por_bpin': grouped_data
    }
    
    print(f"✅ Agrupación completada:")
    print(f"  📊 Total BPINs únicos: {len(grouped_data)}")
    print(f"  📊 Total contratos: {len(df[df['bpin'] != 0])}")
    print(f"  📊 Promedio contratos por BPIN: {len(df[df['bpin'] != 0])/len(grouped_data):.1f}")
    
    return result

def create_bpin_summary(df):
    """
    Crea un resumen JSON optimizado con solo los campos esenciales:
    bpin, referencia_contrato, proceso_compra, id_contrato, urlproceso
    """
    print("🔄 Creando resumen optimizado por BPIN...")
    
    if 'bpin' not in df.columns:
        print("❌ Columna 'bpin' no encontrada para el resumen")
        return {}
    
    # Filtrar solo registros con BPIN válido (diferente de 0)
    valid_bpin_df = df[df['bpin'] != 0].copy()
    
    # Seleccionar solo las columnas necesarias
    required_columns = ['bpin', 'referencia_contrato', 'proceso_compra', 'id_contrato', 'urlproceso']
    summary_df = valid_bpin_df[required_columns].copy()
    
    # Agrupar por BPIN
    grouped_summary = {}
    unique_bpins = summary_df['bpin'].unique()
    
    for bpin_value in tqdm(unique_bpins, desc="Procesando BPINs para resumen"):
        # Verificar que el BPIN no sea NaN
        if pd.isna(bpin_value):
            continue
            
        bpin_records = summary_df[summary_df['bpin'] == bpin_value]
        
        # Crear lista de contratos para este BPIN
        contratos = []
        for _, record in bpin_records.iterrows():
            contrato = {
                'referencia_contrato': record['referencia_contrato'],
                'proceso_compra': record['proceso_compra'],
                'id_contrato': record['id_contrato'],
                'urlproceso': record['urlproceso']
            }
            contratos.append(contrato)
        
        grouped_summary[str(int(bpin_value))] = {
            'bpin': int(bpin_value),
            'total_contratos': len(contratos),
            'contratos': contratos
        }
    
    print(f"✅ Resumen creado para {len(grouped_summary)} BPINs")
    return grouped_summary

def export_optimized_json(grouped_data, output_path):
    """
    Exporta el JSON optimizado agrupado por BPIN
    """
    print(f"🔄 Exportando JSON optimizado agrupado por BPIN...")
    
    # Crear directorio si no existe
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # Crear estructura final optimizada
    optimized_structure = {
        'metadata': {
            'total_bpins': len(grouped_data),
            'total_contratos': sum(bpin_data['resumen']['total_contratos'] for bpin_data in grouped_data.values()),
            'valor_total_general': sum(bpin_data['resumen']['valor_total'] for bpin_data in grouped_data.values()),
            'fecha_procesamiento': pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
        },
        'bpins': grouped_data
    }
    
    # Escribir JSON con formato legible (indentación y espacios)
    import json
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(optimized_structure, f, ensure_ascii=False, indent=2, separators=(',', ': '))
    
    # Verificar tamaño del archivo
    file_size = os.path.getsize(output_path) / (1024 * 1024)  # MB
    print(f"✅ JSON optimizado exportado: {output_path}")
    print(f"📂 Tamaño del archivo: {file_size:.1f} MB")
    print(f"📊 Estructura: {len(grouped_data)} BPINs con {optimized_structure['metadata']['total_contratos']} contratos")
    
    return optimized_structure



def load_and_filter_contratos_secop():
    """
    Lee todos los archivos de datos de contratos SECOP desde la carpeta de entrada
    y aplica filtros específicos, detectando automáticamente las extensiones.
    
    Elimina todas las filas donde:
    - Tipo de Contrato = "Prestación de servicios" O
    - Código BPIN = "No Definido"
    
    Returns:
        pd.DataFrame: DataFrame filtrado con todos los archivos combinados
    """
    
    # Ruta de la carpeta de entrada
    input_folder = "transformation_app/app_inputs/contratos_secop_input"
    
    # Verificar que la carpeta existe
    if not os.path.exists(input_folder):
        raise FileNotFoundError(f"No se encontró la carpeta: {input_folder}")
    
    # Obtener todos los archivos de la carpeta
    all_files = [f for f in os.listdir(input_folder) if os.path.isfile(os.path.join(input_folder, f))]
    
    if not all_files:
        raise FileNotFoundError(f"No se encontraron archivos en la carpeta: {input_folder}")
    
    print(f"🔄 Archivos encontrados en la carpeta: {len(all_files)}")
    for file in all_files:
        print(f"  📄 {file}")
    
    # Lista para almacenar todos los DataFrames
    all_dataframes = []
    
    # Procesar cada archivo según su extensión
    for file in all_files:
        file_path = os.path.join(input_folder, file)
        file_extension = os.path.splitext(file)[1].lower()
        
        print(f"\n🔄 Procesando archivo: {file}")
        print(f"📋 Extensión detectada: {file_extension}")
        
        try:
            if file_extension == '.csv':
                print("📊 Leyendo archivo CSV...")
                # Intentar diferentes encodings para CSV
                encodings = ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']
                df_temp = None
                
                for encoding in encodings:
                    try:
                        df_temp = pd.read_csv(file_path, low_memory=False, encoding=encoding)
                        print(f"✅ CSV leído exitosamente con encoding: {encoding}")
                        break
                    except UnicodeDecodeError:
                        continue
                
                if df_temp is None:
                    raise ValueError(f"No se pudo leer el archivo CSV con ningún encoding probado")
                
            elif file_extension in ['.xlsx', '.xls']:
                print("📊 Leyendo archivo Excel...")
                df_temp = pd.read_excel(file_path)
                
            elif file_extension == '.json':
                print("📊 Leyendo archivo JSON...")
                # Cargar JSON y extraer solo la parte de contratos
                with open(file_path, 'r', encoding='utf-8') as f:
                    json_data = json.load(f)
                
                # Si el JSON tiene estructura compleja, extraer solo contratos_encontrados
                if isinstance(json_data, dict) and 'contratos_encontrados' in json_data:
                    df_temp = pd.DataFrame(json_data['contratos_encontrados'])
                    print(f"📋 Extrayendo 'contratos_encontrados' del JSON estructurado")
                else:
                    # Intentar leer directamente si es un array simple
                    df_temp = pd.DataFrame(json_data)
                
            elif file_extension == '.parquet':
                print("📊 Leyendo archivo Parquet...")
                df_temp = pd.read_parquet(file_path)
                
            elif file_extension in ['.txt', '.tsv']:
                print("📊 Leyendo archivo de texto delimitado...")
                # Detectar delimitador
                delimiter = '\t' if file_extension == '.tsv' else ','
                df_temp = pd.read_csv(file_path, delimiter=delimiter, low_memory=False)
                
            else:
                print(f"⚠️ Extensión {file_extension} no soportada. Archivo omitido: {file}")
                print("📋 Extensiones soportadas: .csv, .xlsx, .xls, .json, .parquet, .txt, .tsv")
                continue
            
            print(f"✅ Archivo leído: {len(df_temp):,} registros")
            all_dataframes.append(df_temp)
            
        except Exception as e:
            print(f"❌ Error leyendo archivo {file}: {str(e)}")
            continue
    
    # Verificar que se leyeron archivos
    if not all_dataframes:
        raise ValueError("No se pudo leer ningún archivo de la carpeta")
    
    # Combinar todos los DataFrames
    print(f"\n🔄 Combinando {len(all_dataframes)} archivos...")
    df = pd.concat(all_dataframes, ignore_index=True, sort=False)
    
    print(f"✅ Datos combinados: {len(df):,} registros totales")
    
    # Aplicar el filtro con barra de progreso
    print("🔄 Aplicando filtros...")
    
    # Verificar que las columnas necesarias existen
    required_columns = ['Tipo de Contrato', 'Código BPIN']
    missing_columns = [col for col in required_columns if col not in df.columns]
    
    if missing_columns:
        print(f"⚠️ Columnas faltantes para filtrado: {missing_columns}")
        print("📋 Columnas disponibles:")
        for col in df.columns[:10]:  # Mostrar primeras 10 columnas
            print(f"  - {col}")
        if len(df.columns) > 10:
            print(f"  ... y {len(df.columns) - 10} más")
        return df  # Retornar sin filtrar si faltan columnas
    
    # Mostrar información antes del filtrado
    prestacion_servicios = df[df['Tipo de Contrato'] == 'Prestación de servicios']
    no_definido_bpin = df[df['Código BPIN'] == 'No Definido']
    
    print(f"📊 Registros con 'Prestación de servicios': {len(prestacion_servicios):,}")
    print(f"📊 Registros con Código BPIN 'No Definido': {len(no_definido_bpin):,}")
    
    # Crear máscara para eliminar registros que cumplan CUALQUIERA de las condiciones
    mask_to_remove = (
        (df['Tipo de Contrato'] == 'Prestación de servicios') |
        (df['Código BPIN'] == 'No Definido')
    )
    
    registros_que_cumplen_filtros = df[mask_to_remove]
    print(f"📊 Registros que serán eliminados (cualquier condición): {len(registros_que_cumplen_filtros):,}")
    
    # Aplicar filtro - eliminar todas las filas que cumplan cualquiera de las condiciones
    df_filtered = df[~mask_to_remove].copy()
    
    registros_eliminados = len(df) - len(df_filtered)
    print(f"✅ Filtrado completo: {registros_eliminados:,} registros eliminados")
    print(f"📊 Registros finales: {len(df_filtered):,}")
    
    return df_filtered

def transform_dataframe(df):
    """
    Aplica todas las transformaciones al DataFrame
    """
    print("🔄 Iniciando transformaciones del DataFrame...")
    
    # 1. Limpiar nombres de columnas
    df = clean_column_names(df)
    
    # 2. Proteger URLs antes de otras transformaciones
    df = protect_urls(df)
    
    # 3. Eliminar columnas innecesarias
    df = remove_unwanted_columns(df)
    
    # 4. Renombrar y convertir BPIN
    df = rename_and_convert_bpin(df)
    
    # 5. Enriquecer BPIN desde datos de proyectos presupuestales
    df = enrich_bpin_from_projects(df)
    
    # 6. Añadir nombre_centro_gestor basado en BPIN
    df = add_nombre_centro_gestor(df)
    
    # 7. Renombrar link_proceso a urlProceso
    if 'link_proceso' in df.columns:
        df = df.rename(columns={'link_proceso': 'urlProceso'})
        print("✅ Columna renombrada: 'link_proceso' → 'urlProceso'")
    
    # 8. Estandarizar fechas
    df = standardize_dates(df)
    
    # 9. Convertir valores monetarios
    df = convert_monetary_to_numeric(df)
    
    # 10. Limpiar valores NaN
    df = clean_nan_values(df)
    
    print("✅ Todas las transformaciones completadas")
    return df

def export_to_json(df, output_path):
    """Exporta el DataFrame a JSON con barra de progreso, preservando URLs sin escape"""
    
    print(f"🔄 Exportando {len(df):,} registros a JSON...")
    
    # Crear directorio si no existe
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # Convertir DataFrame a diccionarios para control manual del JSON
    records = df.to_dict(orient='records')
    
    # Escribir JSON manualmente para evitar escape de URLs
    import json
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(records, f, ensure_ascii=False, indent=2, separators=(',', ': '))
    
    # Verificar tamaño del archivo
    file_size = os.path.getsize(output_path) / (1024 * 1024)  # MB
    print(f"✅ Archivo JSON exportado: {output_path}")
    print(f"📂 Tamaño del archivo: {file_size:.1f} MB")
    
    # Verificar que las URLs se preservaron correctamente
    print("🔗 Verificando integridad de URLs...")
    with open(output_path, 'r', encoding='utf-8') as f:
        sample_data = f.read(2000)  # Leer una muestra más grande
        if 'https://community.secop.gov.co' in sample_data:
            print("✅ URLs de SECOP detectadas correctamente sin escape")
        elif 'https:\\/\\/' in sample_data:
            print("⚠️ URLs detectadas pero con escape excesivo")
        else:
            print("⚠️ No se detectaron URLs en la muestra del archivo")

def main():
    """Función principal para ejecutar la transformación"""
    try:
        # Cargar y filtrar los datos
        df_contratos = load_and_filter_contratos_secop()
        
        # Aplicar transformaciones de datos
        df_contratos = transform_dataframe(df_contratos)
        
        # Exportar JSON normal (individual records)
        output_path = "transformation_app/app_outputs/emprestito_outputs/contratos_secop_emprestito_transformed.json"
        export_to_json(df_contratos, output_path)
        
        # Crear resumen optimizado por BPIN
        print("\n🔄 Creando resumen optimizado por BPIN...")
        bpin_summary = create_bpin_summary(df_contratos)
        
        # Exportar resumen JSON
        summary_path = "transformation_app/app_outputs/contratos_secop_outputs/contratos_proyectos_index.json"
        os.makedirs(os.path.dirname(summary_path), exist_ok=True)
        
        import json
        with open(summary_path, 'w', encoding='utf-8') as f:
            json.dump(bpin_summary, f, ensure_ascii=False, indent=2, separators=(',', ': '))
        
        # Verificar tamaño del archivo
        summary_size = os.path.getsize(summary_path) / (1024 * 1024)  # MB
        print(f"✅ Resumen JSON exportado: {summary_path}")
        print(f"📂 Tamaño del archivo: {summary_size:.1f} MB")
        
        print("\n🎉 Proceso completado exitosamente")
        print("📁 Archivos generados:")
        print(f"  1. JSON individual: {output_path}")
        print(f"  2. Resumen por BPIN: {summary_path}")
        
        return df_contratos, bpin_summary
        
    except Exception as e:
        print(f"❌ Error durante la transformación: {str(e)}")
        raise

if __name__ == "__main__":
    df_result = main()
