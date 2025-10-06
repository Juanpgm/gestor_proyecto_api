"""
Extractor de procesos SECOP usando la API de datos abiertos
Filtrado por nit_entidad = 890399011 (Alcaldía de Cali) y referencias específicas

Este módulo extrae datos del dataset de procesos de contratación SECOP (p6dx-8zbt)
usando las referencias de proceso cargadas desde el archivo JSON.
"""

import pandas as pd
from sodapy import Socrata
import time
import logging
from datetime import datetime
from pathlib import Path
from tqdm import tqdm
import json

# Config de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('extraction_logs.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Constantes del SECOP
SECOP_DOMAIN = "www.datos.gov.co"
DATASET_ID = "p6dx-8zbt"  # ID del dataset de procesos de contratación
NIT_ENTIDAD_CALI = "890399011"  # NIT de la Alcaldía de Cali
OUTPUT_DIR = Path("transformation_app/app_inputs/procesos_secop_input")
REFERENCIAS_JSON_PATH = Path("transformation_app/app_inputs/indice_procesos_emprestito/indice_procesos.json")
RECORDS_PER_REQUEST = 1000  # Límite por request del API
REQUEST_TIMEOUT = 30  # Timeout en segundos para requests


class SecopProcessExtractor:
    """Extractor de procesos SECOP."""
    
    def __init__(self):
        """Inicializar el extractor."""
        self.client = None
        self.target_references = []
        self.setup_client()
        self.setup_output_directory()
        self.load_target_references()
        
    def setup_client(self):
        """Configurar cliente SECOP sin autenticación."""
        try:
            # Cliente no autenticado para datos públicos con timeout personalizado
            self.client = Socrata(SECOP_DOMAIN, None, timeout=REQUEST_TIMEOUT)
            logger.info(f"✓ Cliente SECOP configurado para dominio: {SECOP_DOMAIN}")
            logger.info(f"⏱️  Timeout configurado: {REQUEST_TIMEOUT} segundos")
            
        except Exception as e:
            logger.error(f"❌ Error configurando cliente SECOP: {e}")
            raise
    
    def setup_output_directory(self):
        """Crear directorio de salida si no existe."""
        try:
            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            logger.info(f"✓ Directorio de salida configurado: {OUTPUT_DIR}")
            
        except Exception as e:
            logger.error(f"❌ Error creando directorio de salida: {e}")
            raise
    
    def load_target_references(self):
        """Cargar las referencias de proceso desde el archivo JSON."""
        try:
            if not REFERENCIAS_JSON_PATH.exists():
                logger.error(f"❌ No se encontró el archivo de referencias: {REFERENCIAS_JSON_PATH}")
                raise FileNotFoundError(f"Archivo no encontrado: {REFERENCIAS_JSON_PATH}")
            
            with open(REFERENCIAS_JSON_PATH, 'r', encoding='utf-8') as f:
                referencias_data = json.load(f)
            
            # Extraer referencias de proceso de los arrays, limpiando espacios
            self.target_references = []
            for item in referencias_data:
                if 'referencia_proceso' in item and isinstance(item['referencia_proceso'], list):
                    for ref in item['referencia_proceso']:
                        if ref and ref.strip():  # Solo referencias no vacías
                            self.target_references.append(ref.strip())
            
            # Eliminar duplicados manteniendo el orden
            self.target_references = list(dict.fromkeys(self.target_references))
            
            logger.info(f"✓ Cargadas {len(self.target_references)} referencias de proceso objetivo")
            logger.info(f"📋 Primeras 5 referencias: {self.target_references[:5]}")
            
        except Exception as e:
            logger.error(f"❌ Error cargando referencias objetivo: {e}")
            raise
    
    def extract_processes_by_references(self):
        """Extraer procesos específicos basados en las referencias cargadas."""
        try:
            logger.info(f"🔍 Iniciando extracción de procesos SECOP para NIT: {NIT_ENTIDAD_CALI}")
            logger.info(f"🎯 Buscando {len(self.target_references)} referencias específicas")
            
            all_processes = []
            found_references = []
            not_found_references = []
            
            # Configurar barra de progreso
            progress_bar = tqdm(
                self.target_references,
                desc="🔍 Buscando procesos",
                unit="ref"
            )
            
            for ref_proceso in progress_bar:
                try:
                    # Actualizar descripción de la barra
                    progress_bar.set_postfix({
                        'Ref': ref_proceso[:20] + "..." if len(ref_proceso) > 20 else ref_proceso,
                        'Encontrados': len(found_references)
                    })
                    
                    logger.debug(f"🔍 Buscando proceso: {ref_proceso}")
                    
                    # Construir filtros: NIT + referencia específica
                    where_clause = f"nit_entidad='{NIT_ENTIDAD_CALI}' AND referencia_del_proceso='{ref_proceso}'"
                    
                    # Realizar consulta para esta referencia específica
                    results = self.client.get(
                        DATASET_ID,
                        where=where_clause,
                        limit=RECORDS_PER_REQUEST  # Debería ser suficiente para una referencia
                    )
                    
                    if results:
                        # Agregar identificador de fuente a cada proceso
                        for process in results:
                            process['data_source'] = 'procesos_secop'
                        
                        all_processes.extend(results)
                        found_references.append(ref_proceso)
                        logger.info(f"✓ Encontrado: {ref_proceso} ({len(results)} registros)")
                    else:
                        not_found_references.append(ref_proceso)
                        logger.debug(f"⚠️ No encontrado: {ref_proceso}")
                    
                    # Pausa para no sobrecargar el API
                    time.sleep(0.3)
                    
                except Exception as e:
                    logger.warning(f"❌ Error buscando {ref_proceso}: {e}")
                    not_found_references.append(ref_proceso)
                    continue
            
            progress_bar.close()
            
            # Mostrar estadísticas finales
            logger.info(f"🎉 Extracción completada:")
            logger.info(f"   ✅ Referencias encontradas: {len(found_references)}")
            logger.info(f"   ❌ Referencias no encontradas: {len(not_found_references)}")
            logger.info(f"   📊 Total de procesos extraídos: {len(all_processes)}")
            
            if not_found_references:
                logger.info("❌ Referencias no encontradas:")
                for ref in not_found_references[:10]:  # Mostrar solo las primeras 10
                    logger.info(f"   - {ref}")
                if len(not_found_references) > 10:
                    logger.info(f"   ... y {len(not_found_references) - 10} más")
            
            return all_processes
            
        except Exception as e:
            logger.error(f"❌ Error en extracción de procesos: {e}")
            raise
    

    
    def clean_data_for_excel(self, df):
        """Limpiar datos para evitar errores de caracteres ilegales en Excel."""
        try:
            logger.info("🧹 Limpiando datos para Excel...")
            df_clean = df.copy()
            
            # Función para limpiar strings
            def clean_string(text):
                if pd.isna(text) or not isinstance(text, str):
                    return text
                
                # Remover caracteres de control y caracteres problemáticos
                import re
                # Remover caracteres de control (excepto tab, newline, carriage return)
                text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', text)
                
                # Reemplazar caracteres problemáticos específicos
                problematic_chars = {
                    '☻': '',
                    '♠': '',
                    '♣': '',
                    '♥': '',
                    '♦': '',
                    '\x01': '',
                    '\x02': '',
                    '\x03': '',
                    '\x04': '',
                    '\x05': '',
                    '\x06': '',
                    '\x07': '',
                    '\x08': '',
                }
                
                for char, replacement in problematic_chars.items():
                    text = text.replace(char, replacement)
                
                # Limpiar espacios múltiples y saltos de línea
                text = re.sub(r'\s+', ' ', text).strip()
                
                return text
            
            # Aplicar limpieza a todas las columnas de texto
            for column in df_clean.columns:
                if df_clean[column].dtype == 'object':
                    df_clean[column] = df_clean[column].apply(clean_string)
            
            logger.info("✅ Datos limpiados exitosamente")
            return df_clean
            
        except Exception as e:
            logger.warning(f"⚠️  Error limpiando datos: {e}, continuando con datos originales")
            return df

    def save_data_to_files(self, processes_data):
        """Guardar procesos en archivos."""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            results = {}
            
            # Guardar procesos SECOP si hay datos
            if processes_data:
                logger.info("💾 Guardando datos de procesos SECOP...")
                df_processes = pd.DataFrame.from_records(processes_data)
                
                # Agregar identificador de fuente
                df_processes['data_source'] = 'procesos_secop'
                df_processes_clean = self.clean_data_for_excel(df_processes)
                
                # Guardar procesos en JSON
                processes_filename = "procesos_secop_emprestito.json"
                processes_path = OUTPUT_DIR / processes_filename
                
                data_list = df_processes_clean.to_dict('records')
                cleaned_data = self.clean_data_for_json(data_list)
                
                with open(processes_path, 'w', encoding='utf-8') as f:
                    json.dump(cleaned_data, f, ensure_ascii=False, indent=2)
                
                logger.info(f"✅ Procesos guardados: {processes_path}")
                results['processes'] = {
                    "json_path": processes_path,
                    "records_count": len(df_processes)
                }
                
                # Mostrar resumen de procesos
                logger.info(f"\n📊 RESUMEN PROCESOS SECOP: {len(df_processes)} registros")
                self.show_data_summary(df_processes)
            
            return results
            
        except Exception as e:
            logger.error(f"❌ Error guardando archivos: {e}")
            raise
    
    def clean_data_for_json(self, data_list):
        """Limpiar datos para formato JSON."""
        cleaned_data = []
        for record in data_list:
            cleaned_record = {}
            for key, value in record.items():
                if pd.isna(value):
                    cleaned_record[key] = None
                elif isinstance(value, (pd.Timestamp, datetime)):
                    cleaned_record[key] = value.isoformat() if pd.notna(value) else None
                else:
                    cleaned_record[key] = value
            cleaned_data.append(cleaned_record)
        return cleaned_data
    
    def show_data_summary(self, df):
        """Mostrar resumen de los datos extraídos."""
        try:
            logger.info("\n" + "="*60)
            logger.info("📊 RESUMEN DE DATOS EXTRAÍDOS")
            logger.info("="*60)
            logger.info(f"📋 Total de procesos: {len(df):,}")
            logger.info(f"📊 Total de columnas: {len(df.columns)}")
            
            # Mostrar información de fechas si está disponible
            date_columns = [col for col in df.columns if 'fecha' in col.lower()]
            if date_columns:
                logger.info(f"📅 Columnas de fecha encontradas: {date_columns}")
                
                for date_col in date_columns[:2]:  # Mostrar hasta 2 columnas de fecha
                    if not df[date_col].isna().all():
                        try:
                            df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
                            min_date = df[date_col].min()
                            max_date = df[date_col].max()
                            logger.info(f"   📅 {date_col}: desde {min_date} hasta {max_date}")
                        except:
                            logger.debug(f"No se pudo procesar fecha en columna: {date_col}")
            
            # Mostrar algunas columnas importantes si existen
            important_columns = [
                'referencia_del_proceso', 'descripci_n_del_procedimiento', 'estado_del_procedimiento',
                'modalidad_de_contratacion', 'nombre_del_procedimiento', 'precio_base'
            ]
            
            available_important = [col for col in important_columns if col in df.columns]
            if available_important:
                logger.info(f"📄 Columnas importantes disponibles: {available_important}")
            
            # Estadísticas de presupuesto si está disponible
            budget_columns = [col for col in df.columns if 'presupuesto' in col.lower() or 'valor' in col.lower()]
            if budget_columns:
                for budget_col in budget_columns[:1]:  # Solo el primero
                    try:
                        df[budget_col] = pd.to_numeric(df[budget_col], errors='coerce')
                        total_budget = df[budget_col].sum()
                        avg_budget = df[budget_col].mean()
                        if not pd.isna(total_budget) and total_budget > 0:
                            logger.info(f"💰 {budget_col} total: ${total_budget:,.2f}")
                            logger.info(f"💰 {budget_col} promedio: ${avg_budget:,.2f}")
                    except:
                        logger.debug(f"No se pudo calcular estadísticas para: {budget_col}")
            
            # Mostrar estados de proceso si están disponibles
            if 'estado_proceso' in df.columns:
                estados = df['estado_proceso'].value_counts()
                logger.info(f"📊 Estados de procesos encontrados:")
                for estado, count in estados.head(5).items():
                    logger.info(f"   - {estado}: {count}")
            
            logger.info("="*60)
            
        except Exception as e:
            logger.warning(f"⚠️  Error mostrando resumen: {e}")
    
    def run_extraction(self):
        """Ejecutar proceso completo de extracción de procesos."""
        try:
            start_time = datetime.now()
            logger.info(f"🚀 Iniciando extracción de procesos SECOP - {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info("📋 Extrayendo datos de:")
            logger.info(f"   🔍 Procesos SECOP (Dataset: {DATASET_ID})")
            
            # 1. Extraer procesos SECOP específicos
            logger.info("\n" + "="*60)
            logger.info("🔍 EXTRACCIÓN DE PROCESOS SECOP")
            logger.info("="*60)
            processes = self.extract_processes_by_references()
            
            # 2. Guardar resultados
            logger.info("\n" + "="*60)
            logger.info("💾 GUARDANDO RESULTADOS")
            logger.info("="*60)
            
            if processes:
                save_results = self.save_data_to_files(processes)
                
                # Calcular tiempo total
                end_time = datetime.now()
                duration = end_time - start_time
                
                # Mostrar resumen final
                logger.info("\n" + "="*80)
                logger.info("🎉 EXTRACCIÓN COMPLETADA")
                logger.info("="*80)
                logger.info(f"⏱️  Tiempo total de extracción: {duration}")
                logger.info(f"📁 Archivos guardados en: {OUTPUT_DIR}")
                
                # Estadísticas detalladas
                if 'processes' in save_results:
                    logger.info(f"📄 Procesos SECOP extraídos: {save_results['processes']['records_count']:,}")
                
                # Listar archivos generados
                logger.info("\n📁 Archivos generados:")
                for key, result in save_results.items():
                    logger.info(f"   📄 {key.title().replace('_', ' ')}: {result['json_path'].name}")
                
                return save_results
                
            else:
                logger.warning("⚠️  No se encontraron datos para extraer")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error en proceso de extracción: {e}")
            raise
        
        finally:
            # Cerrar cliente
            if self.client:
                self.client.close()
                logger.info("🔒 Cliente SECOP cerrado")


def main():
    """Función principal."""
    try:
        logger.info("="*80)
        logger.info("🏛️  EXTRACTOR DE PROCESOS SECOP - ALCALDÍA DE CALI")
        logger.info("="*80)
        logger.info(f"📍 NIT de entidad: {NIT_ENTIDAD_CALI}")
        logger.info(f"🗂️  Dataset ID: {DATASET_ID}")
        logger.info(f"📂 Directorio de salida: {OUTPUT_DIR}")
        logger.info(f"📋 Archivo de referencias: {REFERENCIAS_JSON_PATH}")
        
        # Crear y ejecutar extractor
        extractor = SecopProcessExtractor()
        results = extractor.run_extraction()
        
        if results:
            logger.info("\n" + "="*50)
            logger.info("✅ PROCESO COMPLETADO EXITOSAMENTE")
            logger.info("="*50)
            
            # Mostrar estadísticas
            if 'processes' in results:
                logger.info(f"📄 Procesos SECOP extraídos: {results['processes']['records_count']:,}")
                logger.info(f"📁 Archivo de procesos: {results['processes']['json_path'].name}")
            
            logger.info(f"📂 Ubicación: {OUTPUT_DIR}")
        else:
            logger.warning("⚠️  No se generaron archivos de salida")
            
    except Exception as e:
        logger.error(f"❌ Error crítico en main: {e}")
        raise


if __name__ == "__main__":
    main()
