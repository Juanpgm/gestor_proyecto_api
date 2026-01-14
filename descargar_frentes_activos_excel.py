"""
Script para descargar datos del endpoint /frentes-activos y guardarlos en Excel
"""

import requests
import pandas as pd
from datetime import datetime
import json

def descargar_frentes_activos_excel(url='http://localhost:8000', output_filename=None):
    """
    Descarga datos del endpoint /frentes-activos y los guarda en Excel
    
    Args:
        url: URL base de la API (default: http://localhost:8000)
        output_filename: Nombre del archivo de salida (default: frentes_activos_YYYYMMDD_HHMMSS.xlsx)
    """
    
    # URL completa del endpoint
    endpoint = f"{url}/frentes-activos"
    
    print(f"📡 Consultando endpoint: {endpoint}")
    
    try:
        # Realizar petición GET
        response = requests.get(endpoint)
        response.raise_for_status()
        
        data = response.json()
        
        print(f"✅ Datos recibidos correctamente")
        print(f"📊 Total de features: {len(data.get('features', []))}")
        
        # Extraer información de properties globales
        if 'properties' in data:
            print(f"📈 Total frentes activos: {data['properties'].get('total_frentes_activos', 'N/A')}")
            print(f"📍 Total unidades con frentes: {data['properties'].get('total_unidades_con_frentes', 'N/A')}")
        
        # Procesar features y convertir a DataFrame
        features = data.get('features', [])
        
        if not features:
            print("⚠️ No se encontraron features en la respuesta")
            return
        
        # Extraer propiedades de cada feature
        records = []
        for feature in features:
            properties = feature.get('properties', {})
            geometry = feature.get('geometry', {})
            
            record = {
                'id': feature.get('id', ''),
                'tipo': feature.get('type', ''),
                # Propiedades principales solicitadas
                'nombre_up': properties.get('nombre_up', ''),
                'nombre_up_detalle': properties.get('nombre_up_detalle', ''),
                'comuna': properties.get('comuna_corregimiento', ''),
                'barrio': properties.get('barrio', ''),
                'direccion': properties.get('direccion', ''),
                # Otras propiedades relevantes
                'UPID': properties.get('UPID', ''),
                'NOMBRE_UP': properties.get('NOMBRE_UP', ''),
                'COD_ZONA': properties.get('COD_ZONA', ''),
                'NOMBRE_ZONA': properties.get('NOMBRE_ZONA', ''),
                'GRUPO': properties.get('GRUPO', ''),
                'ABSCISA_INICIAL': properties.get('ABSCISA_INICIAL', ''),
                'ABSCISA_FINAL': properties.get('ABSCISA_FINAL', ''),
                'CALZADA': properties.get('CALZADA', ''),
                'ANCHO': properties.get('ANCHO', ''),
                'LARGO': properties.get('LARGO', ''),
                'AREA': properties.get('AREA', ''),
                'estado': properties.get('estado', ''),
                # Información de frentes activos
                'frentes_activos_count': properties.get('frentes_activos_count', 0),
                # Información de intervenciones
                'intervenciones_count': properties.get('intervenciones_count', 0),
                # Geometría
                'geometry_type': geometry.get('type', ''),
                'coordinates': str(geometry.get('coordinates', ''))
            }
            
            # Si hay información de frentes activos, agregar detalles
            if 'frentes_activos' in properties and properties['frentes_activos']:
                frentes = properties['frentes_activos']
                if isinstance(frentes, list) and frentes:
                    record['primer_frente_activo'] = json.dumps(frentes[0], ensure_ascii=False)
                    record['todos_frentes_activos'] = json.dumps(frentes, ensure_ascii=False)
            
            records.append(record)
        
        # Crear DataFrame
        df = pd.DataFrame(records)
        
        # Generar nombre de archivo si no se proporcionó
        if output_filename is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_filename = f'frentes_activos_{timestamp}.xlsx'
        
        # Guardar a Excel
        with pd.ExcelWriter(output_filename, engine='openpyxl') as writer:
            # Hoja principal con todos los datos
            df.to_excel(writer, sheet_name='Frentes Activos', index=False)
            
            # Crear hoja de resumen
            resumen = pd.DataFrame({
                'Métrica': [
                    'Total Features',
                    'Total Frentes Activos',
                    'Total Unidades con Frentes',
                    'Fecha de Descarga'
                ],
                'Valor': [
                    len(features),
                    data.get('properties', {}).get('total_frentes_activos', 'N/A'),
                    data.get('properties', {}).get('total_unidades_con_frentes', 'N/A'),
                    datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                ]
            })
            resumen.to_excel(writer, sheet_name='Resumen', index=False)
            
            # Si hay columnas específicas de interés, crear una vista simplificada
            columnas_principales = ['nombre_up', 'nombre_up_detalle', 'comuna', 'barrio', 'direccion',
                                   'frentes_activos_count', 'intervenciones_count', 'estado', 'UPID']
            # Filtrar solo las columnas que existen en el DataFrame
            columnas_disponibles = [col for col in columnas_principales if col in df.columns]
            df_simple = df[columnas_disponibles]
            df_simple.to_excel(writer, sheet_name='Vista Simplificada', index=False)
        
        print(f"✅ Archivo Excel generado: {output_filename}")
        print(f"📄 Hojas creadas: Frentes Activos, Resumen, Vista Simplificada")
        print(f"📊 Total de registros: {len(df)}")
        
        return output_filename
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Error en la petición HTTP: {e}")
        return None
    except Exception as e:
        print(f"❌ Error procesando los datos: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Descargar frentes activos a Excel')
    parser.add_argument('--url', default='http://localhost:8000', 
                       help='URL base de la API (default: http://localhost:8000)')
    parser.add_argument('--output', default=None,
                       help='Nombre del archivo de salida (default: frentes_activos_YYYYMMDD_HHMMSS.xlsx)')
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("📥 DESCARGA DE FRENTES ACTIVOS A EXCEL")
    print("=" * 60)
    
    resultado = descargar_frentes_activos_excel(args.url, args.output)
    
    if resultado:
        print("\n" + "=" * 60)
        print("✅ DESCARGA COMPLETADA EXITOSAMENTE")
        print("=" * 60)
    else:
        print("\n" + "=" * 60)
        print("❌ LA DESCARGA FALLÓ")
        print("=" * 60)
