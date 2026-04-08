"""
Script para verificar que el endpoint esté registrado en la aplicación FastAPI
"""
import sys
from main import app

# Obtener todas las rutas registradas
routes = []
for route in app.routes:
    if hasattr(route, 'path'):
        routes.append({
            'path': route.path,
            'name': getattr(route, 'name', 'N/A'),
            'methods': getattr(route, 'methods', set())
        })

# Buscar el endpoint de asignaciones
print("🔍 Buscando endpoint de asignaciones...\n")
found = False
for route in routes:
    if 'asignacion' in route['path'].lower():
        print(f"✅ ENCONTRADO:")
        print(f"   Path: {route['path']}")
        print(f"   Name: {route['name']}")
        print(f"   Methods: {route['methods']}")
        found = True

if not found:
    print("❌ Endpoint NO encontrado en las rutas registradas")
    print(f"\n📊 Total de rutas registradas: {len(routes)}")
    print("\n🔍 Rutas relacionadas con empréstito:")
    for route in routes:
        if 'emprestito' in route['path'].lower():
            print(f"   - {route['path']} [{route['methods']}]")
else:
    print(f"\n✅ Endpoint registrado correctamente")
    print(f"📊 Total de rutas en la aplicación: {len(routes)}")
