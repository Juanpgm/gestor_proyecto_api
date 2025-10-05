"""
Script de testing basado en filtros reales del endpoint /filters
Identifica qué combinaciones de filtros realmente tienen datos
"""
import asyncio
import aiohttp
import json
from datetime import datetime

class RealFiltersValidator:
    def __init__(self):
        self.base_url = "http://localhost:8000"
        self.real_filters = {}
        self.results = {
            'working_combinations': [],
            'empty_combinations': [],
            'error_combinations': [],
            'data_summary': {}
        }
    
    async def load_real_filters(self):
        """Cargar filtros reales del endpoint"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.base_url}/unidades-proyecto/filters") as response:
                    if response.status == 200:
                        data = await response.json()
                        self.real_filters = data.get('filters', {})
                        print("✅ Filtros reales cargados:")
                        for key, values in self.real_filters.items():
                            if isinstance(values, list):
                                print(f"  {key}: {len(values)} valores")
                            else:
                                print(f"  {key}: {type(values)}")
                        return True
                    else:
                        print(f"❌ Error cargando filtros: {response.status}")
                        return False
        except Exception as e:
            print(f"❌ Error: {e}")
            return False
    
    async def test_single_filter(self, session, filter_name, filter_value, test_name):
        """Probar un filtro individual"""
        try:
            params = {filter_name: filter_value}
            url = f"{self.base_url}/unidades-proyecto/geometry"
            
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    features = data.get('features', [])
                    count = len(features)
                    
                    result = {
                        'test_name': test_name,
                        'filter': {filter_name: filter_value},
                        'count': count,
                        'status': 'success',
                        'has_data': count > 0
                    }
                    
                    if count > 0:
                        # Extraer información de los registros encontrados
                        sample_data = {}
                        for feature in features[:2]:  # Solo primeros 2
                            props = feature.get('properties', {})
                            upid = props.get('upid', 'N/A')
                            comuna = props.get('comuna_corregimiento', 'N/A')
                            barrio = props.get('barrio_vereda', 'N/A')
                            sample_data[upid] = {'comuna': comuna, 'barrio': barrio}
                        
                        result['sample_data'] = sample_data
                        self.results['working_combinations'].append(result)
                        print(f"✅ {test_name}: {count} registros")
                    else:
                        self.results['empty_combinations'].append(result)
                        print(f"⚪ {test_name}: 0 registros")
                        
                else:
                    error_result = {
                        'test_name': test_name,
                        'filter': {filter_name: filter_value},
                        'status': 'error',
                        'error_code': response.status
                    }
                    self.results['error_combinations'].append(error_result)
                    print(f"❌ {test_name}: Error {response.status}")
                    
        except Exception as e:
            error_result = {
                'test_name': test_name,
                'filter': {filter_name: filter_value},
                'status': 'exception',
                'error': str(e)
            }
            self.results['error_combinations'].append(error_result)
            print(f"❌ {test_name}: Exception - {e}")
    
    async def test_combined_filters(self, session, test_combinations):
        """Probar combinaciones de filtros"""
        print("\n🔍 Probando combinaciones de filtros...")
        
        for i, combo in enumerate(test_combinations, 1):
            test_name = f"Combo-{i}"
            try:
                url = f"{self.base_url}/unidades-proyecto/geometry"
                async with session.get(url, params=combo) as response:
                    if response.status == 200:
                        data = await response.json()
                        features = data.get('features', [])
                        count = len(features)
                        
                        result = {
                            'test_name': test_name,
                            'filter': combo,
                            'count': count,
                            'status': 'success',
                            'has_data': count > 0
                        }
                        
                        if count > 0:
                            self.results['working_combinations'].append(result)
                            print(f"✅ {test_name}: {count} registros - {combo}")
                        else:
                            self.results['empty_combinations'].append(result)
                            print(f"⚪ {test_name}: 0 registros - {combo}")
                            
            except Exception as e:
                print(f"❌ {test_name}: Exception - {e}")
    
    async def run_comprehensive_test(self):
        """Ejecutar pruebas comprehensivas basadas en filtros reales"""
        print("🚀 Iniciando validación basada en filtros reales...")
        
        # Cargar filtros reales
        if not await self.load_real_filters():
            return
        
        async with aiohttp.ClientSession() as session:
            print("\n📊 FASE 1: Probando filtros individuales")
            
            # Probar comunas individuales (primeras 10)
            if 'comunas' in self.real_filters:
                comunas = [c for c in self.real_filters['comunas'] if not '\n' in str(c)][:10]
                for i, comuna in enumerate(comunas):
                    await self.test_single_filter(session, 'comuna_corregimiento', comuna, f"Comuna-{i+1}")
            
            # Probar barrios individuales (primeros 20)
            if 'barrios_veredas' in self.real_filters:
                barrios = [b for b in self.real_filters['barrios_veredas'] if not '\n' in str(b)][:20]
                for i, barrio in enumerate(barrios):
                    await self.test_single_filter(session, 'barrio_vereda', barrio, f"Barrio-{i+1}")
            
            # Probar estados
            if 'estados' in self.real_filters:
                for i, estado in enumerate(self.real_filters['estados']):
                    await self.test_single_filter(session, 'estado', estado, f"Estado-{i+1}")
            
            print("\n📊 FASE 2: Probando combinaciones específicas")
            
            # Combinaciones basadas en datos que sabemos que existen
            test_combinations = [
                {'comuna_corregimiento': 'COMUNA 01'},
                {'barrio_vereda': 'Vista Hermosa'},
                {'barrio_vereda': 'Bajo Aguacatal'},
                {'comuna_corregimiento': 'COMUNA 01', 'barrio_vereda': 'Vista Hermosa'},
                {'comuna_corregimiento': 'COMUNA 01', 'barrio_vereda': 'Bajo Aguacatal'},
                {'estado': 'En ejecución'},
                {'estado': 'Finalizado'},
                {'tipo_intervencion': 'Obra nueva'},
                {'tipo_intervencion': 'Mejoramiento'},
                {'comuna_corregimiento': 'COMUNA 02'},
                {'comuna_corregimiento': 'COMUNA 04'},
                {'comuna_corregimiento': 'COMUNA 10'},
            ]
            
            await self.test_combined_filters(session, test_combinations)
    
    def generate_report(self):
        """Generar reporte de resultados"""
        print("\n" + "="*80)
        print("📊 REPORTE FINAL - VALIDACIÓN DE FILTROS REALES")
        print("="*80)
        
        working = len(self.results['working_combinations'])
        empty = len(self.results['empty_combinations'])
        errors = len(self.results['error_combinations'])
        total = working + empty + errors
        
        print(f"\n📈 RESUMEN GENERAL:")
        print(f"  Total pruebas: {total}")
        print(f"  ✅ Con datos: {working} ({working/total*100:.1f}%)")
        print(f"  ⚪ Sin datos: {empty} ({empty/total*100:.1f}%)")
        print(f"  ❌ Con errores: {errors} ({errors/total*100:.1f}%)")
        
        print(f"\n✅ COMBINACIONES QUE SÍ TIENEN DATOS ({working}):")
        for result in self.results['working_combinations']:
            filter_str = ', '.join([f"{k}={v}" for k, v in result['filter'].items()])
            print(f"  • {result['test_name']}: {result['count']} registros - {filter_str}")
            if 'sample_data' in result:
                for upid, data in result['sample_data'].items():
                    print(f"    └─ {upid}: {data['comuna']} / {data['barrio']}")
        
        if empty > 0:
            print(f"\n⚪ MUESTRA DE COMBINACIONES SIN DATOS (primeras 10 de {empty}):")
            for result in self.results['empty_combinations'][:10]:
                filter_str = ', '.join([f"{k}={v}" for k, v in result['filter'].items()])
                print(f"  • {result['test_name']}: {filter_str}")
        
        if errors > 0:
            print(f"\n❌ ERRORES ENCONTRADOS ({errors}):")
            for result in self.results['error_combinations']:
                filter_str = ', '.join([f"{k}={v}" for k, v in result['filter'].items()])
                print(f"  • {result['test_name']}: {filter_str} - {result.get('error_code', result.get('error', 'Unknown'))}")
        
        # Guardar resultados detallados
        with open('real_filters_validation_results.json', 'w', encoding='utf-8') as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False)
        
        print(f"\n📄 Resultados detallados guardados en 'real_filters_validation_results.json'")
        
        return {
            'total_tests': total,
            'working_combinations': working,
            'empty_combinations': empty,
            'error_combinations': errors,
            'success_rate': working/total*100 if total > 0 else 0
        }

async def main():
    validator = RealFiltersValidator()
    await validator.run_comprehensive_test()
    summary = validator.generate_report()
    
    print(f"\n🎯 CONCLUSIÓN:")
    if summary['working_combinations'] > 0:
        print(f"   ✅ Sistema funcional - {summary['working_combinations']} combinaciones tienen datos")
        print(f"   📊 Tasa de éxito: {summary['success_rate']:.1f}%")
        if summary['empty_combinations'] > summary['working_combinations']:
            print(f"   ⚠️  ADVERTENCIA: {summary['empty_combinations']} filtros disponibles no tienen datos reales")
            print(f"      Esto sugiere inconsistencia entre filtros mostrados y datos existentes")
    else:
        print("   ❌ Ninguna combinación de filtros tiene datos - Problema crítico")

if __name__ == "__main__":
    asyncio.run(main())