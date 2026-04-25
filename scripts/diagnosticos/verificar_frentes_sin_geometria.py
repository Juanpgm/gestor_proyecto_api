"""
Script para verificar registros sin geometría en el endpoint /frentes-activos
"""
import requests
import json

# Obtener datos del endpoint
response = requests.get('http://localhost:8000/frentes-activos')
data = response.json()

print("=" * 80)
print("ANÁLISIS DE FRENTES ACTIVOS - GEOMETRÍAS")
print("=" * 80)

total_features = len(data.get('features', []))
print(f"\n✅ Total de frentes activos: {total_features}")

# Filtrar registros sin geometría válida
features_sin_geo = [
    f for f in data.get('features', []) 
    if not f.get('properties', {}).get('has_valid_geometry', True)
]

print(f"❌ Frentes sin geometría válida: {len(features_sin_geo)}")
print(f"✅ Frentes con geometría válida: {total_features - len(features_sin_geo)}")

if features_sin_geo:
    print("\n" + "=" * 80)
    print("REGISTROS SIN GEOMETRÍA VÁLIDA:")
    print("=" * 80)
    
    for i, feature in enumerate(features_sin_geo, 1):
        props = feature.get('properties', {})
        geometry = feature.get('geometry', {})
        
        print(f"\n{i}. UPID: {props.get('upid', 'N/A')}")
        print(f"   Nombre: {props.get('nombre_up', 'N/A')}")
        print(f"   Comuna: {props.get('comuna_corregimiento', 'N/A')}")
        print(f"   Centro Gestor: {props.get('nombre_centro_gestor', 'N/A')}")
        print(f"   Geometría: {geometry}")
        print(f"   N° Intervenciones: {len(props.get('intervenciones', []))}")
        
        # Verificar las intervenciones
        intervenciones = props.get('intervenciones', [])
        if intervenciones:
            print(f"   Primera intervención:")
            primera = intervenciones[0]
            print(f"      - Estado: {primera.get('estado', 'N/A')}")
            print(f"      - Frente activo: {primera.get('frente_activo', 'N/A')}")

print("\n" + "=" * 80)
print("ANÁLISIS COMPLETADO")
print("=" * 80)
