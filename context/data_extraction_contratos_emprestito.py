#!/usr/bin/env python
"""
Script para extraer contratos específicos de empréstito usando la API del SECOP (Socrata)
Extrae datos completos de todas las referencias de contrato válidas del archivo emp_contratos_index.json
"""

import json
import os
import re
import time
from sodapy import Socrata
import logging
from datetime import datetime
from typing import List, Dict, Any

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('extraction_logs.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class ContractosEmprestitoExtractor:
    """Extractor especializado para contratos de empréstito usando referencias específicas"""
    
    def __init__(self):
        # Cliente SECOP sin autenticación (solo datos públicos) con timeout más corto
        self.client = Socrata("www.datos.gov.co", None, timeout=10)  # Timeout reducido
        
        # Dataset IDs de SECOP - Solo usaremos contratos
        self.datasets = {
            'contratos': 'jbjy-vk9h'  # Contratos SECOP I - Dataset principal
        }
        
        # Configuración de reintentos robusta
        self.max_retries = 3  # Más reintentos para garantizar éxito
        self.base_delay = 1   # Delay base en segundos
        self.max_delay = 30   # Delay máximo en segundos
        
        # Rutas de archivos
        self.base_path = "transformation_app/app_inputs/contratos_secop_input"
        self.input_file = "transformation_app/app_inputs/indice_procesos_emprestito/indice_procesos.json"
        self.output_file = os.path.join(self.base_path, "contratos_secop_emprestito.json")
        
        os.makedirs(self.base_path, exist_ok=True)
    
    def _optimized_api_call(self, dataset_key: str, where_clause: str, limit: int = 5000) -> List[Dict]:
        """
        Llamada robusta a la API con reintentos y validación de respuestas
        """        
        last_exception = None
        
        for attempt in range(self.max_retries + 1):
            try:
                logger.debug(f"Intento {attempt + 1}/{self.max_retries + 1} para dataset {dataset_key}")
                
                # Realizar la llamada a la API
                results = self.client.get(
                    self.datasets[dataset_key],
                    where=where_clause,
                    select="*",
                    limit=limit
                )
                
                # Validar que la respuesta sea válida
                if results is not None:
                    if isinstance(results, list):
                        logger.debug(f"API retornó {len(results)} registros")
                        return results
                    else:
                        logger.warning(f"API retornó tipo inesperado: {type(results)}")
                        return []
                else:
                    logger.warning("API retornó None")
                    if attempt < self.max_retries:
                        continue
                    return []
                
            except Exception as e:
                last_exception = e
                error_msg = str(e)
                
                if attempt < self.max_retries:
                    # Calcular tiempo de espera con backoff exponencial
                    wait_time = min(self.base_delay * (2 ** attempt), self.max_delay)
                    
                    logger.warning(f"Intento {attempt + 1} falló: {error_msg[:200]}. Reintentando en {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    logger.error(f"Error final después de {self.max_retries + 1} intentos: {error_msg[:200]}")
        
        # Si llegamos aquí, todos los intentos fallaron
        logger.error(f"Todos los intentos fallaron para {dataset_key} con where: {where_clause}")
        if last_exception:
            logger.error(f"Última excepción: {last_exception}")
        
        return []  # Siempre retorna una lista vacía en caso de fallo total
    
    def load_contratos_index(self) -> List[Dict]:
        """Cargar y filtrar referencias de contrato válidas"""
        logger.info("Cargando índice de contratos de empréstito...")
        
        try:
            with open(self.input_file, 'r', encoding='utf-8') as f:
                contratos_index = json.load(f)
            
            logger.info(f"Cargados {len(contratos_index)} registros")
            
            # Filtrar solo registros con referencia_contrato válida
            valid_contracts = []
            for item in contratos_index:
                if 'referencia_contrato' in item and isinstance(item['referencia_contrato'], list):
                    # Omitir arrays vacíos
                    if not item['referencia_contrato']:
                        continue
                    
                    for ref_contrato in item['referencia_contrato']:
                        if ref_contrato and str(ref_contrato).strip():  # No vacío y no None
                            # Crear un registro por cada referencia de contrato
                            contract_record = item.copy()
                            contract_record['referencia_contrato'] = str(ref_contrato).strip()
                            valid_contracts.append(contract_record)
            
            logger.info(f"Encontrados {len(valid_contracts)} registros con referencia_contrato válida")
            return valid_contracts
            
        except FileNotFoundError:
            logger.error(f"No se encontró el archivo: {self.input_file}")
            return []
        except json.JSONDecodeError as e:
            logger.error(f"Error al decodificar JSON: {e}")
            return []
    
    def extract_individual_references(self, contratos_index: List[Dict]) -> List[Dict]:
        """Extraer referencias individuales, creando un registro por cada referencia"""
        logger.info("Extrayendo referencias individuales y creando registros separados...")
        
        expanded_records = []
        
        for item in contratos_index:
            ref_contrato = item.get('referencia_contrato', '').strip()
            if ref_contrato:
                # Manejar múltiples referencias separadas por comas
                if ',' in ref_contrato:
                    refs = [ref.strip() for ref in ref_contrato.split(',')]
                    for ref in refs:
                        # Limpiar espacios y guiones adicionales de manera más agresiva
                        clean_ref = self.clean_contract_reference(ref)
                        if clean_ref:
                            # Crear un nuevo registro para cada referencia
                            new_record = item.copy()
                            new_record['referencia_contrato'] = clean_ref
                            new_record['referencia_contrato_original'] = ref  # Guardar original
                            new_record['_multiple_refs'] = True
                            new_record['_original_refs'] = ref_contrato
                            expanded_records.append(new_record)
                else:
                    # Referencia única
                    clean_ref = self.clean_contract_reference(ref_contrato)
                    if clean_ref:
                        new_record = item.copy()
                        new_record['referencia_contrato'] = clean_ref
                        new_record['referencia_contrato_original'] = ref_contrato  # Guardar original
                        new_record['_multiple_refs'] = False
                        new_record['_original_refs'] = ref_contrato
                        expanded_records.append(new_record)
        
        logger.info(f"Total de registros expandidos: {len(expanded_records)}")
        return expanded_records
    
    def clean_contract_reference(self, ref: str) -> str:
        """Limpiar referencia de contrato con múltiples estrategias"""
        if not ref:
            return ""
        
        # Limpiar espacios al inicio y final
        clean_ref = ref.strip()
        
        # Quitar espacios alrededor de guiones: "4151.010.26.1.0932 - 2025" -> "4151.010.26.1.0932-2025"
        clean_ref = re.sub(r'\s*-\s*', '-', clean_ref)
        
        # Quitar espacios dentro de números: "4151 . 010 . 26" -> "4151.010.26"
        clean_ref = re.sub(r'\s*\.\s*', '.', clean_ref)
        
        # Quitar espacios múltiples
        clean_ref = re.sub(r'\s+', ' ', clean_ref)
        
        # Si hay espacios restantes en medio de la referencia, quitarlos
        # Ejemplo: "4151.010.26.1.0932 2025" -> "4151.010.26.1.0932-2025"
        parts = clean_ref.split()
        if len(parts) == 2 and parts[1].isdigit() and len(parts[1]) == 4:
            clean_ref = f"{parts[0]}-{parts[1]}"
        
        return clean_ref.strip()

    def process_contract_data(self, contract: Dict) -> Dict:
        """Procesar y limpiar datos del contrato según estándares del proyecto"""
        processed = contract.copy()
        
        # Convertir campos de valor_ a enteros
        valor_fields = [k for k in processed.keys() if k.startswith('valor_')]
        for field in valor_fields:
            if processed.get(field):
                try:
                    # Limpiar el valor (quitar espacios, comas, etc.)
                    valor_str = str(processed[field]).replace(',', '').replace(' ', '').strip()
                    if valor_str and valor_str != 'null' and valor_str.lower() != 'none':
                        processed[field] = int(float(valor_str))
                    else:
                        processed[field] = 0
                except (ValueError, TypeError):
                    processed[field] = 0
        
        # Renombrar y convertir c_digo_bpin a bpin (entero)
        if 'c_digo_bpin' in processed:
            try:
                bpin_value = processed.pop('c_digo_bpin')
                if bpin_value and str(bpin_value).strip() and str(bpin_value).strip() != 'null':
                    processed['bpin'] = int(float(str(bpin_value).replace(',', '').replace(' ', '').strip()))
                else:
                    processed['bpin'] = None
            except (ValueError, TypeError):
                processed['bpin'] = None
        
        # Convertir campos de fecha_ al formato ISO 8601
        fecha_fields = [k for k in processed.keys() if k.startswith('fecha_')]
        for field in fecha_fields:
            if processed.get(field):
                try:
                    fecha_str = str(processed[field]).strip()
                    if fecha_str and fecha_str != 'null' and fecha_str.lower() != 'none':
                        # Intentar diferentes formatos de fecha
                        fecha_formats = [
                            '%Y-%m-%dT%H:%M:%S.%f',  # 2025-08-27T00:00:00.000
                            '%Y-%m-%dT%H:%M:%S',     # 2025-08-27T00:00:00
                            '%Y-%m-%d',              # 2025-08-27
                            '%d/%m/%Y',              # 27/08/2025
                            '%m/%d/%Y',              # 08/27/2025
                            '%Y%m%d',                # 20250827
                        ]
                        
                        fecha_parsed = None
                        for fmt in fecha_formats:
                            try:
                                fecha_parsed = datetime.strptime(fecha_str, fmt)
                                break
                            except ValueError:
                                continue
                        
                        if fecha_parsed:
                            # Convertir a formato ISO 8601: YYYY-MM-DD
                            processed[field] = fecha_parsed.strftime('%Y-%m-%d')
                        else:
                            processed[field] = None
                    else:
                        processed[field] = None
                except (ValueError, TypeError):
                    processed[field] = None
        
        return processed
    
    def search_contract_by_exact_reference(self, referencia: str, limit: int = 50) -> List[Dict]:
        """Buscar contrato por referencia exacta con validación robusta"""
        logger.info(f"Buscando contrato: {referencia}")
        
        # Validar entrada
        if not referencia or not referencia.strip():
            logger.warning("Referencia vacía o inválida")
            return []
        
        referencia = referencia.strip()
        all_results = []
        
        # Campos de referencia a buscar SOLO en el dataset de contratos SECOP
        search_fields = [
            ('contratos', 'referencia_del_contrato'),  # Campo principal que funciona
            ('contratos', 'id_contrato'),
            ('contratos', 'proceso_de_compra')
        ]
        
        for dataset_key, field_name in search_fields:
            try:
                # Búsqueda exacta primero
                where_clause = f"{field_name} = '{referencia}'"
                logger.debug(f"Búsqueda exacta en {dataset_key}.{field_name}")
                
                results = self._optimized_api_call(dataset_key, where_clause, limit)
                
                # Validar y procesar resultados
                if results and isinstance(results, list) and len(results) > 0:
                    logger.info(f"✅ Encontrados {len(results)} registros exactos para {referencia} en {dataset_key}.{field_name}")
                    
                    for result in results:
                        if isinstance(result, dict):
                            # Agregar metadatos de búsqueda
                            result['_dataset_source'] = dataset_key
                            result['_search_field'] = field_name
                            result['_referencia_buscada'] = referencia
                            result['_search_type'] = 'exact'
                            result['_total_campos'] = len(result.keys())
                            all_results.append(result)
                    
                    # Si encontramos resultados exactos, no necesitamos buscar similares
                    continue
                
                # Si no encuentra exacto, buscar con LIKE para variaciones
                logger.debug(f"Búsqueda similar en {dataset_key}.{field_name}")
                where_clause = f"{field_name} like '%{referencia}%'"
                results = self._optimized_api_call(dataset_key, where_clause, limit)
                
                if results and isinstance(results, list) and len(results) > 0:
                    logger.info(f"📝 Encontrados {len(results)} registros similares para {referencia} en {dataset_key}.{field_name}")
                    
                    for result in results:
                        if isinstance(result, dict):
                            result['_dataset_source'] = dataset_key
                            result['_search_field'] = field_name
                            result['_referencia_buscada'] = referencia
                            result['_search_type'] = 'similar'
                            result['_total_campos'] = len(result.keys())
                            all_results.append(result)
                
                # Búsqueda adicional sin guiones para casos como "4151010261093220925"
                if not results and '-' in referencia:
                    ref_sin_guiones = referencia.replace('-', '').replace('.', '')
                    where_clause = f"{field_name} like '%{ref_sin_guiones}%'"
                    results = self._optimized_api_call(dataset_key, where_clause, limit)
                    
                    if results:
                        logger.info(f"Encontrados {len(results)} registros sin guiones para {referencia} en {dataset_key}.{field_name}")
                        for result in results:
                            result['_dataset_source'] = dataset_key
                            result['_search_field'] = field_name
                            result['_referencia_buscada'] = referencia
                            result['_search_type'] = 'sin_guiones'
                            result['_total_campos'] = len(result.keys())
                        all_results.extend(results)
                
                # Búsqueda con solo los últimos números (año)
                if not results and referencia.count('-') > 0:
                    year_part = referencia.split('-')[-1]  # Último segmento después del guion
                    if year_part.isdigit() and len(year_part) == 4:
                        base_part = referencia.rsplit('-', 1)[0]  # Todo menos el año
                        where_clause = f"{field_name} like '%{base_part}%{year_part}%'"
                        results = self._optimized_api_call(dataset_key, where_clause, limit)
                        
                        if results:
                            logger.info(f"Encontrados {len(results)} registros por partes para {referencia} en {dataset_key}.{field_name}")
                            for result in results:
                                result['_dataset_source'] = dataset_key
                                result['_search_field'] = field_name
                                result['_referencia_buscada'] = referencia
                                result['_search_type'] = 'por_partes'
                                result['_total_campos'] = len(result.keys())
                            all_results.extend(results)
                
                # Búsqueda adicional: Buscar solo los números centrales (ej: 4134.010.26.1.0252)
                if not results:
                    # Extraer la parte principal sin el año: 4134.010.26.1.0252
                    if '-' in referencia:
                        base_without_year = referencia.rsplit('-', 1)[0]  # 4134.010.26.1.0252
                        where_clause = f"{field_name} like '%{base_without_year}%'"
                        results = self._optimized_api_call(dataset_key, where_clause, limit)
                        
                        if results:
                            logger.info(f"Encontrados {len(results)} registros por base para {referencia} en {dataset_key}.{field_name}")
                            for result in results:
                                result['_dataset_source'] = dataset_key
                                result['_search_field'] = field_name
                                result['_referencia_buscada'] = referencia
                                result['_search_type'] = 'por_base'
                                result['_total_campos'] = len(result.keys())
                            all_results.extend(results)
                
                # Búsqueda con variaciones de formato: cambiar último número
                if not results and '.' in referencia:
                    # Para 4134.010.26.1.0252-2025, probar 4134.010.26.1.0253-2025, 4134.010.26.1.0251-2025
                    parts = referencia.split('.')
                    if len(parts) >= 5:  # Asegurar que tiene el formato esperado
                        try:
                            # Extraer el número antes del guión
                            last_part_with_year = parts[-1]  # "0252-2025"
                            if '-' in last_part_with_year:
                                number_part, year_part = last_part_with_year.split('-')
                                base_number = int(number_part)
                                
                                # Probar números adyacentes (±5)
                                for offset in range(-5, 6):
                                    if offset == 0:
                                        continue  # Ya probamos el original
                                    
                                    new_number = base_number + offset
                                    # Mantener el formato con ceros a la izquierda
                                    new_number_str = str(new_number).zfill(len(number_part))
                                    
                                    # Construir nueva referencia
                                    new_parts = parts[:-1] + [f"{new_number_str}-{year_part}"]
                                    new_ref = '.'.join(new_parts)
                                    
                                    where_clause = f"{field_name} = '{new_ref}'"
                                    results = self._optimized_api_call(dataset_key, where_clause, limit)
                                    
                                    if results:
                                        logger.info(f"Encontrados {len(results)} registros con variación +{offset} ({new_ref}) para {referencia} en {dataset_key}.{field_name}")
                                        for result in results:
                                            result['_dataset_source'] = dataset_key
                                            result['_search_field'] = field_name
                                            result['_referencia_buscada'] = referencia
                                            result['_referencia_encontrada'] = new_ref
                                            result['_search_type'] = f'variacion_{offset:+d}'
                                            result['_total_campos'] = len(result.keys())
                                        all_results.extend(results)
                                        break  # Solo tomar la primera variación que encuentre
                        except (ValueError, IndexError):
                            pass  # Si hay error en el parsing, continuar
                
            except Exception as e:
                logger.warning(f"Error buscando {referencia} en {dataset_key}.{field_name}: {e}")
                continue
        
        return all_results
    
    def extract_all_contracts(self, expanded_records: List[Dict]) -> List[Dict]:
        """Extraer todos los datos de contratos para los registros expandidos"""
        logger.info(f"Extrayendo datos de {len(expanded_records)} registros expandidos...")
        
        all_contracts = []
        extracted_count = 0
        
        for i, record in enumerate(expanded_records, 1):
            referencia = record['referencia_contrato']
            logger.info(f"Procesando {i}/{len(expanded_records)}: {referencia}")
            
            try:
                contract_data = self.search_contract_by_exact_reference(referencia)
                
                # Validar que contract_data sea una lista válida
                if contract_data and isinstance(contract_data, list) and len(contract_data) > 0:
                    logger.info(f"✅ Encontrados {len(contract_data)} contratos para {referencia}")
                    
                    # Procesar cada contrato encontrado
                    processed_contracts = []
                    for contract in contract_data:
                        if not isinstance(contract, dict):
                            logger.warning(f"Contrato inválido (no es dict): {type(contract)}")
                            continue
                            
                        try:
                            # Procesar y limpiar datos del contrato
                            processed_contract = self.process_contract_data(contract)
                            
                            # Agregar información del registro original
                            processed_contract['_registro_origen'] = {
                                'banco': record.get('banco'),
                                'id_origen': record.get('id'),
                                'referencia_proceso': record.get('referencia_proceso'),
                                'fecha_extraccion': record.get('fecha_extraccion'),
                                'multiple_refs': record.get('_multiple_refs', False),
                                'refs_originales': record.get('_original_refs'),
                                'referencia_original': record.get('referencia_contrato_original', referencia)
                            }
                            processed_contracts.append(processed_contract)
                            
                        except Exception as e:
                            logger.error(f"Error procesando contrato individual: {e}")
                            continue
                    
                    if processed_contracts:
                        all_contracts.extend(processed_contracts)
                        extracted_count += 1
                        logger.info(f"✅ Procesados {len(processed_contracts)} contratos para {referencia}")
                    else:
                        logger.warning(f"❌ No se pudieron procesar contratos para {referencia}")
                else:
                    logger.warning(f"❌ No se encontraron contratos para {referencia}")
                    # Agregar un registro de "no encontrado" para tracking
                    not_found_record = {
                        'referencia_contrato_no_encontrada': referencia,
                        'motivo': 'no_encontrado_en_secop',
                        '_registro_origen': record,
                        '_timestamp_busqueda': datetime.now().isoformat()
                    }
                    all_contracts.append(not_found_record)
                
            except Exception as e:
                logger.error(f"Error procesando {referencia}: {e}")
                # Crear un registro de error para mantener trazabilidad
                error_record = {
                    'referencia_contrato_buscada': referencia,
                    'estado_busqueda': f'Error: {str(e)}',
                    '_registro_origen': {
                        'banco': record.get('banco'),
                        'id_origen': record.get('id'),
                        'referencia_proceso': record.get('referencia_proceso'),
                        'fecha_extraccion': record.get('fecha_extraccion'),
                        'multiple_refs': record.get('_multiple_refs', False),
                        'refs_originales': record.get('_original_refs')
                    }
                }
                all_contracts.append(error_record)
                continue
        
        logger.info(f"Extracción completada: {extracted_count}/{len(expanded_records)} registros procesados exitosamente")
        logger.info(f"Total de registros en resultado: {len(all_contracts)}")
        
        return all_contracts
    
    def save_contracts(self, contracts: List[Dict], expanded_records: List[Dict]) -> Dict[str, Any]:
        """Guardar contratos extraídos en formato JSON"""
        logger.info(f"Guardando {len(contracts)} registros...")
        
        try:
            # Separar contratos encontrados de los no encontrados
            found_contracts = [c for c in contracts if 'estado_busqueda' not in c]
            not_found_records = [c for c in contracts if 'estado_busqueda' in c]
            
            # Preparar datos para guardar
            output_data = {
                'metadata': {
                    'timestamp': datetime.now().isoformat(),
                    'total_registros': len(contracts),
                    'contratos_encontrados': len(found_contracts),
                    'registros_no_encontrados': len(not_found_records),
                    'registros_originales': len(set(r.get('_registro_origen', {}).get('id_origen') for r in contracts if '_registro_origen' in r)),
                    'registros_expandidos': len(expanded_records),
                    'datasets_consultados': list(self.datasets.keys()),
                    'archivo_origen': 'emp_contratos_index.json'
                },
                'contratos_encontrados': found_contracts,
                'registros_no_encontrados': not_found_records,
                'estadisticas': {
                    'por_banco': {},
                    'referencias_multiples': 0,
                    'referencias_unicas': 0
                }
            }
            
            # Calcular estadísticas
            for record in expanded_records:
                banco = record.get('banco', 'Sin banco')
                if banco not in output_data['estadisticas']['por_banco']:
                    output_data['estadisticas']['por_banco'][banco] = 0
                output_data['estadisticas']['por_banco'][banco] += 1
                
                if record.get('_multiple_refs'):
                    output_data['estadisticas']['referencias_multiples'] += 1
                else:
                    output_data['estadisticas']['referencias_unicas'] += 1
            
            # Guardar archivo principal
            with open(self.output_file, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Registros guardados en: {self.output_file}")
            
            # Crear resumen adicional
            summary = {
                'archivo_salida': self.output_file,
                'total_registros': len(contracts),
                'contratos_encontrados': len(found_contracts),
                'registros_no_encontrados': len(not_found_records),
                'registros_expandidos': len(expanded_records),
                'timestamp': datetime.now().isoformat()
            }
            
            return summary
            
        except Exception as e:
            logger.error(f"Error guardando contratos: {e}")
            raise
    
    def run_extraction(self) -> Dict[str, Any]:
        """Ejecutar extracción completa"""
        logger.info("=== INICIANDO EXTRACCIÓN DE CONTRATOS POR REFERENCIA ===")
        
        try:
            # 1. Cargar índice y filtrar referencias válidas
            contratos_index = self.load_contratos_index()
            if not contratos_index:
                logger.error("No se encontraron referencias de contrato válidas")
                return {}
            
            # 2. Expandir registros para crear uno por cada referencia individual
            expanded_records = self.extract_individual_references(contratos_index)
            if not expanded_records:
                logger.error("No se pudieron expandir los registros")
                return {}
            
            # 3. Extraer datos de contratos para cada registro expandido
            contracts = self.extract_all_contracts(expanded_records)
            
            # 4. Guardar resultados
            if contracts:
                summary = self.save_contracts(contracts, expanded_records)
                
                # Calcular estadísticas finales
                found_contracts = [c for c in contracts if 'estado_busqueda' not in c]
                not_found = [c for c in contracts if 'estado_busqueda' in c]
                
                summary['contratos_encontrados'] = len(found_contracts)
                summary['registros_no_encontrados'] = len(not_found)
                summary['registros_expandidos'] = len(expanded_records)
                summary['registros_originales'] = len(contratos_index)
                
                logger.info("=== EXTRACCIÓN COMPLETADA EXITOSAMENTE ===")
                logger.info(f"Registros originales: {len(contratos_index)}")
                logger.info(f"Registros expandidos: {len(expanded_records)}")
                logger.info(f"Contratos encontrados: {len(found_contracts)}")
                logger.info(f"Registros no encontrados: {len(not_found)}")
                logger.info(f"Archivo guardado: {self.output_file}")
                
                return summary
            else:
                logger.warning("No se extrajeron contratos")
                return {'error': 'No se encontraron contratos'}
            
        except Exception as e:
            logger.error(f"Error durante la extracción: {e}")
            raise

def main():
    """Función principal"""
    extractor = ContractosEmprestitoExtractor()
    
    try:
        resultado = extractor.run_extraction()
        
        # Mostrar resumen
        print("\n" + "="*60)
        print("RESUMEN DE EXTRACCIÓN DE CONTRATOS DE EMPRÉSTITO")
        print("="*60)
        
        if 'error' in resultado:
            print(f"Error: {resultado['error']}")
        else:
            print(f"📊 Registros originales: {resultado.get('registros_originales', 0)}")
            print(f"📈 Registros expandidos: {resultado.get('registros_expandidos', 0)}")
            print(f"Contratos encontrados: {resultado.get('contratos_encontrados', 0)}")
            print(f"Registros no encontrados: {resultado.get('registros_no_encontrados', 0)}")
            print(f"📁 Archivo guardado: {resultado.get('archivo_salida', 'N/A')}")
        
        print("="*60)
        
    except Exception as e:
        logger.error(f"Error en ejecución principal: {e}")
        print(f"Error durante la ejecución: {e}")

if __name__ == "__main__":
    main()
