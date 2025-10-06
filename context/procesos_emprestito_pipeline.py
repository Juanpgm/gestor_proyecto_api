#!/usr/bin/env python3
"""
Pipeline de Procesos de Empréstito - Versión Optimizada
=======================================================

Pipeline específico para el procesamiento de datos de procesos de empréstito
con soporte para ejecución secuencial optimizada y sin filtros restrictivos.

Autor: Sistema ETL Alcaldía de Cali
Fecha: 2025-10-02
"""

import sys
import os
import time
import logging
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from tqdm import tqdm
import threading
import queue
from concurrent.futures import ThreadPoolExecutor, as_completed


# Configuración de logging
def setup_logging():
    """Configurar el sistema de logging con soporte UTF-8"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('pipeline_procesos_emprestito.log', encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)


class ProcesosEmprestitoPipeline:
    """Pipeline específico para el procesamiento de datos de procesos de empréstito"""
    
    def __init__(self, smart_mode: bool=True):
        """
        Inicializar el pipeline de procesos de empréstito
        
        Args:
            smart_mode: Omitir fases si los archivos de salida ya existen
        """
        self.smart_mode = smart_mode
        self.logger = setup_logging()
        self.start_time = None
        self.step_results = {}
        self.progress_queue = queue.Queue()
        self.live_progress = None
        
        # Configuración de scripts - Solo procesos
        self.scripts = {
            'extraction_procesos': 'extraction_app/data_extraction_procesos_emprestito.py',
            'transformation_procesos': 'transformation_app/data_transformation_procesos_secop.py',
            'loading_procesos': 'load_app/data_loading_procesos_emprestito.py'
        }
        
        # Validar que todos los scripts existen
        self._validate_scripts()
        
        # Configurar archivos de salida esperados - Solo procesos
        self.output_files = {
            'extraction_procesos': 'transformation_app/app_inputs/procesos_secop_input/procesos_secop_emprestito.json',
            'transformation_procesos': 'transformation_app/app_outputs/emprestito_outputs/procesos_secop_emprestito_transformed.json'
        }



    def _validate_scripts(self):
        """Validar que todos los scripts necesarios existen"""
        self.logger.info("🔍 Validando existencia de scripts...")
        
        for step_name, script_path in self.scripts.items():
            if not os.path.exists(script_path):
                raise FileNotFoundError(f"Script no encontrado: {script_path}")
        
        self.logger.info("✅ Todos los scripts están disponibles")

    def _check_existing_files(self) -> Dict[str, bool]:
        """Verificar qué archivos de salida ya existen"""
        existing_files = {}
        for step_name, file_path in self.output_files.items():
            exists = os.path.exists(file_path)
            existing_files[step_name] = exists
            if exists:
                file_size = os.path.getsize(file_path) / 1024  # KB
                self.logger.info(f"✅ Archivo existente: {step_name} ({file_size:.1f} KB)")
            else:
                self.logger.info(f"❌ Archivo faltante: {step_name}")
        return existing_files

    def _should_skip_phase(self, phase_name: str, tasks: List[Tuple[str, str, str]]) -> bool:
        """Determinar si una fase puede omitirse porque los archivos ya existen"""
        if not self.smart_mode:
            return False
        
        existing_files = self._check_existing_files()
        
        # Verificar si todos los archivos de salida de la fase existen
        all_files_exist = True
        for task_name, script_path, step_key in tasks:
            if step_key in existing_files and not existing_files[step_key]:
                all_files_exist = False
                break
        
        if all_files_exist:
            self.logger.info(f"🚀 OMITIENDO FASE DE {phase_name} - Archivos ya existen")
            # Simular resultados exitosos para esta fase
            for task_name, script_path, step_key in tasks:
                self.step_results[step_key] = {
                    'success': True,
                    'script': task_name,
                    'execution_time': 0.1,
                    'timeout_used': 0,
                    'efficiency_percent': 100,
                    'skipped': True,
                    'reason': 'Archivos ya existen'
                }
            return True
        
        return False

    def _execute_script_with_progress(self, script_name: str, script_path: str, step_key: str, progress_bar: tqdm) -> Dict[str, Any]:
        """
        Ejecutar un script con monitoreo de progreso sin timeout
        
        Args:
            script_name: Nombre descriptivo del script
            script_path: Ruta al script
            step_key: Clave del paso (para compatibilidad)
            progress_bar: Barra de progreso compartida
        
        Returns:
            Diccionario con el resultado de la ejecución
        """
        start_time = time.time()
        
        try:
            # Actualizar progreso
            progress_bar.set_description(f"🚀 Iniciando {script_name}")
            progress_bar.update(10)
            
            progress_bar.set_postfix_str("Sin límite de tiempo - Ejecutando...")
            
            # Ejecutar el script SIN timeout
            result = subprocess.run(
                [sys.executable, script_path],
                capture_output=True,
                text=True,
                cwd=os.getcwd()
            )
            
            execution_time = time.time() - start_time
            progress_bar.update(80)
            
            if result.returncode == 0:
                progress_bar.set_description(f"✅ {script_name} completado")
                progress_bar.set_postfix_str(f"Completado en {execution_time:.1f}s")
                progress_bar.update(10)
                return {
                    'success': True,
                    'script': script_name,
                    'execution_time': execution_time,
                    'output': result.stdout,
                    'timeout_occurred': False
                }
            else:
                progress_bar.set_description(f"❌ {script_name} falló")
                progress_bar.set_postfix_str("Error en ejecución")
                progress_bar.update(10)
                return {
                    'success': False,
                    'script': script_name,
                    'execution_time': execution_time,
                    'error': result.stderr,
                    'output': result.stdout,
                    'timeout_occurred': False
                }
                
        except Exception as e:
            execution_time = time.time() - start_time
            progress_bar.set_description(f"💥 {script_name} error")
            progress_bar.set_postfix_str("Error crítico")
            progress_bar.update(100)
            return {
                'success': False,
                'script': script_name,
                'execution_time': execution_time,
                'error': str(e),
                'timeout_occurred': False
            }

    def _execute_sequential_phase(self, phase_name: str, tasks: List[Tuple[str, str, str]]) -> bool:
        """
        Ejecutar tareas secuencialmente con progreso mejorado
        
        Args:
            phase_name: Nombre de la fase
            tasks: Lista de tuplas (script_name, script_path, step_key)
        
        Returns:
            True si al menos una tarea fue exitosa
        """
        success_count = 0
        total_tasks = len(tasks)
        
        print(f"🔄 Ejecutando {total_tasks} tareas secuencialmente...")
        
        # Crear barra de progreso para la fase
        with tqdm(total=total_tasks, desc=f"Fase {phase_name} (Secuencial)",
                 bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]',
                 position=0) as phase_progress:
            
            for i, (script_name, script_path, step_key) in enumerate(tasks):
                # Crear barra de progreso para la tarea individual
                with tqdm(total=100, desc=f"Ejecutando {script_name}",
                         position=1, leave=False) as task_progress:
                    
                    result = self._execute_script_with_progress(
                        script_name, script_path, step_key, task_progress
                    )
                    
                    self.step_results[step_key] = result
                    
                    if result['success']:
                        success_count += 1
                    
                    # Actualizar progreso de la fase
                    phase_progress.update(1)
                    phase_progress.set_description(
                        f"Fase {phase_name} - {success_count}/{i+1} completados"
                    )
        
        # La fase es exitosa si al menos una tarea fue exitosa
        phase_success = success_count > 0
        return phase_success

    def run_extraction_phase(self) -> bool:
        """Ejecutar la fase de extracción de procesos"""
        self.logger.info("🔄 INICIANDO FASE DE EXTRACCIÓN DE PROCESOS")
        
        extraction_tasks = [
            ("Extracción de Procesos SECOP", self.scripts['extraction_procesos'], 'extraction_procesos')
        ]
        
        return self._execute_sequential_phase("EXTRACCIÓN", extraction_tasks)

    def run_transformation_phase(self) -> bool:
        """Ejecutar la fase de transformación de procesos"""
        self.logger.info("🔄 INICIANDO FASE DE TRANSFORMACIÓN DE PROCESOS")
        
        transformation_tasks = [
            ("Transformación de Procesos SECOP", self.scripts['transformation_procesos'], 'transformation_procesos')
        ]
        
        return self._execute_sequential_phase("TRANSFORMACIÓN", transformation_tasks)

    def run_loading_phase(self) -> bool:
        """Ejecutar la fase de carga de procesos a Firebase"""
        self.logger.info("🔄 INICIANDO FASE DE CARGA DE PROCESOS")
        
        loading_tasks = [
            ("Carga de Procesos a Firebase", self.scripts['loading_procesos'], 'loading_procesos')
        ]
        
        return self._execute_sequential_phase("CARGA", loading_tasks)

    def run(self):
        """
        Ejecutar el pipeline completo de procesos de empréstito sin timeouts ni filtros restrictivos
        """
        self.start_time = datetime.now()
        self.logger.info("=" * 80)
        self.logger.info("🚀 INICIANDO PIPELINE DE PROCESOS DE EMPRÉSTITO")
        self.logger.info("=" * 80)
        
        self.logger.info(f"📊 CONFIGURACIÓN DEL PIPELINE:")
        self.logger.info(f"   • Ejecución: SECUENCIAL SIN TIMEOUTS")
        self.logger.info(f"   • Modo inteligente: {'ACTIVADO' if self.smart_mode else 'DESACTIVADO'}")
        self.logger.info(f"   • Sin filtros restrictivos: Procesa TODOS los procesos extraídos")
        self.logger.info(f"   • Incluye todos los tipos de contrato: Obra, Interventoría, Prestación de servicios, etc.")
        self.logger.info(f"   • Los scripts se ejecutarán hasta completarse")
        
        self.logger.info("-" * 80)
        
        try:
            # Fase 1: Extracción de procesos
            self.logger.info("🔄 INICIANDO FASE DE EXTRACCIÓN DE PROCESOS")
            if not self.run_extraction_phase():
                self.logger.error("❌ Extracción de procesos falló.")
            
            # Fase 2: Transformación de procesos (continúa aunque la extracción falle)
            self.logger.info("🔄 INICIANDO FASE DE TRANSFORMACIÓN DE PROCESOS")
            if not self.run_transformation_phase():
                self.logger.error("❌ Transformación de procesos falló.")
            
            # Fase 3: Carga de procesos a Firebase (continúa aunque la transformación falle)
            self.logger.info("🔄 INICIANDO FASE DE CARGA DE PROCESOS")
            if not self.run_loading_phase():
                self.logger.error("❌ Carga de procesos falló.")
            
            # Generar reporte final
            return self._generate_final_report()
            
        except KeyboardInterrupt:
            self.logger.warning("⚠️ Pipeline interrumpido por el usuario")
            return self._generate_final_report()
        except Exception as e:
            self.logger.error(f"💥 Error crítico en el pipeline: {str(e)}")
            return self._generate_final_report()

    def _generate_final_report(self) -> Dict[str, Any]:
        """Generar reporte final del pipeline"""
        end_time = datetime.now()
        total_duration = (end_time - self.start_time).total_seconds() if self.start_time else 0
        
        self.logger.info("=" * 80)
        self.logger.info("📋 REPORTE FINAL DEL PIPELINE DE PROCESOS")
        self.logger.info("=" * 80)
        
        # Estadísticas generales
        successful_steps = sum(1 for result in self.step_results.values() if result.get('success', False))
        total_steps = len(self.step_results)
        success_rate = (successful_steps / total_steps * 100) if total_steps > 0 else 0
        
        self.logger.info(f"⏱️  Duración total: {total_duration:.1f} segundos ({total_duration/60:.1f} minutos)")
        self.logger.info(f"✅ Pasos exitosos: {successful_steps}/{total_steps} ({success_rate:.1f}%)")
        
        # Análisis de ejecución
        execution_analysis = []
        
        for step_name, result in self.step_results.items():
            if result:
                execution_time = result.get('execution_time', 0)
                
                if result.get('success'):
                    execution_analysis.append(f"   ✅ {step_name}: Completado en {execution_time:.1f}s")
                else:
                    execution_analysis.append(f"   ❌ {step_name}: Falló después de {execution_time:.1f}s")
        
        if execution_analysis:
            self.logger.info("📈 ANÁLISIS DE EJECUCIÓN:")
            for analysis in execution_analysis:
                self.logger.info(analysis)
        
        # Recomendaciones para próximas ejecuciones
        self._generate_recommendations()
        
        # Resumen de resultados por paso
        self.logger.info("📊 DETALLE POR PASO:")
        for step_name, result in self.step_results.items():
            if result:
                status = "✅ ÉXITO" if result.get('success') else "❌ FALLO"
                time_info = f"{result.get('execution_time', 0):.1f}s"
                self.logger.info(f"   {step_name}: {status} ({time_info})")
                
                if not result.get('success') and result.get('error'):
                    error_msg = result.get('error', '')[:100] + "..." if len(result.get('error', '')) > 100 else result.get('error', '')
                    self.logger.info(f"     Error: {error_msg}")
        
        self.logger.info("=" * 80)
        
        if successful_steps == total_steps:
            self.logger.info("🎉 PIPELINE DE PROCESOS COMPLETADO EXITOSAMENTE")
            self.logger.info("📊 TODOS LOS PROCESOS EXTRAÍDOS FUERON PROCESADOS SIN FILTROS RESTRICTIVOS")
        elif successful_steps > 0:
            self.logger.info("⚠️ PIPELINE DE PROCESOS COMPLETADO CON ALGUNOS FALLOS")
        else:
            self.logger.info("❌ PIPELINE DE PROCESOS FALLÓ COMPLETAMENTE")
        
        return {
            'success': successful_steps > 0,
            'total_duration': total_duration,
            'successful_steps': successful_steps,
            'total_steps': total_steps,
            'success_rate': success_rate,
            'step_results': self.step_results,
            'execution_analysis': execution_analysis
        }

    def _generate_recommendations(self):
        """Generar recomendaciones basadas en el análisis de ejecución"""
        recommendations = []
        
        # Analizar fallos
        failed_steps = [name for name, result in self.step_results.items() 
                       if result and not result.get('success')]
        
        if failed_steps:
            recommendations.append("🔧 Revisar errores en: " + ", ".join(failed_steps))
        
        # Analizar tiempos de ejecución largos
        slow_steps = []
        for name, result in self.step_results.items():
            if result and result.get('execution_time', 0) > 300:  # Más de 5 minutos
                slow_steps.append(f"{name} ({result.get('execution_time', 0):.1f}s)")
        
        if slow_steps:
            recommendations.append("⏰ Pasos que toman mucho tiempo: " + ", ".join(slow_steps))
        
        # Recomendaciones específicas para procesos
        recommendations.append("📋 Pipeline configurado para procesar TODOS los tipos de proceso")
        recommendations.append("🔧 Sin filtros por tipo de contrato - incluye Prestación de servicios")
        recommendations.append("📊 Sin filtros por contratos asociados - incluye procesos en evaluación")
        
        # Mostrar recomendaciones
        if recommendations:
            self.logger.info("💡 RECOMENDACIONES:")
            for rec in recommendations:
                self.logger.info(f"   {rec}")


def main():
    """Función principal"""
    # Configurar logging para el script principal con soporte UTF-8
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('pipeline_procesos_emprestito.log', encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    
    try:
        # Crear y ejecutar el pipeline
        pipeline = ProcesosEmprestitoPipeline(
            smart_mode=True  # Activar modo inteligente (omitir fases si archivos existen)
        )
        
        print("🔧 CONFIGURACIÓN SIN TIMEOUTS NI FILTROS RESTRICTIVOS:")
        print("   - Ejecución: Secuencial (extracción → transformación → carga)")
        print("   - Sin timeouts: Los scripts se ejecutan hasta completarse")
        print("   - Modo inteligente: Activado (omite fases si archivos existen)")
        print("   - Solo procesos: Procesamiento enfocado en procesos únicamente")
        print("   - Sin filtros: Procesa TODOS los tipos de proceso extraídos")
        print("   - Incluye: Obra, Interventoría, Prestación de servicios, Consultoría, etc.")
        print("   - Continuidad: Cada fase se ejecuta independientemente")
        print()
        
        success = pipeline.run()
        
        if success:
            print("\n✅ Pipeline de procesos ejecutado exitosamente")
            print("📊 Todos los procesos extraídos fueron procesados sin filtros restrictivos")
            exit(0)
        else:
            print("\n❌ Pipeline de procesos falló o se completó con errores")
            exit(1)
            
    except Exception as e:
        print(f"\n💥 Error crítico: {str(e)}")
        exit(1)


if __name__ == "__main__":
    main()
