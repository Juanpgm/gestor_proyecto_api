#!/usr/bin/env python3
"""
Script de diagnóstico para verificar conexión y datos en Firestore
"""

import os
import sys

# Agregar path del proyecto
sys.path.append('.')

def test_firestore_connection():
    """Test direct Firestore connection"""
    print("🔍 DIAGNÓSTICO FIRESTORE")
    print("=" * 50)
    
    try:
        # Importar configuración
        from database.firebase_config import get_firestore_client, get_project_config
        
        # Verificar configuración
        config = get_project_config()
        print(f"📋 Configuración detectada:")
        print(f"   - Proyecto: {config['project_id']}")
        print(f"   - Entorno: {config['environment']}")
        
        # Obtener cliente Firestore
        db = get_firestore_client()
        if not db:
            print("❌ No se pudo obtener cliente Firestore")
            return False
            
        print("✅ Cliente Firestore obtenido correctamente")
        
        # Listar colecciones
        print("\n📁 Colecciones disponibles:")
        collections = db.collections()
        collection_names = []
        
        for collection in collections:
            collection_names.append(collection.id)
            print(f"   - {collection.id}")
        
        if not collection_names:
            print("   ⚠️ No hay colecciones en Firestore")
            return False
        
        # Verificar colección específica de unidades_proyecto
        target_collection = "unidades_proyecto"
        print(f"\n🎯 Verificando colección '{target_collection}':")
        
        try:
            docs = db.collection(target_collection).limit(5).stream()
            doc_count = 0
            
            for doc in docs:
                doc_count += 1
                print(f"   - Documento ID: {doc.id}")
                data = doc.to_dict()
                if data:
                    keys = list(data.keys())[:5]  # Primeras 5 claves
                    print(f"     Campos: {keys}...")
                
            print(f"📊 Total documentos encontrados: {doc_count}")
            
            if doc_count == 0:
                print("⚠️ La colección existe pero está vacía")
                
                # Verificar si hay otras colecciones con datos similares
                print("\n🔍 Buscando colecciones alternativas:")
                for col_name in collection_names:
                    if 'proyecto' in col_name.lower() or 'unidad' in col_name.lower():
                        try:
                            alt_docs = list(db.collection(col_name).limit(1).stream())
                            if alt_docs:
                                print(f"   ✅ {col_name}: {len(alt_docs)} documento(s)")
                        except:
                            continue
            
            return doc_count > 0
            
        except Exception as e:
            print(f"   ❌ Error accediendo a colección: {e}")
            return False
        
    except Exception as e:
        print(f"❌ Error general: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_api_functions():
    """Test API functions directly"""
    print("\n🔧 PRUEBA FUNCIONES API")
    print("=" * 50)
    
    try:
        from api.scripts.unidades_proyecto import (
            get_all_unidades_proyecto_simple,
            get_unidades_proyecto_geometry,
            get_unidades_proyecto_attributes,
            get_unidades_proyecto_summary
        )
        
        print("🧪 Probando get_all_unidades_proyecto_simple()...")
        result = await get_all_unidades_proyecto_simple(limit=5)
        
        if result and result.get('success'):
            data = result.get('data', [])
            print(f"✅ get_all_unidades_proyecto_simple: {len(data)} registros")
            if len(data) > 0:
                first_item = data[0]
                print(f"   Primer registro: {list(first_item.keys())[:5]}...")
        else:
            print("❌ get_all_unidades_proyecto_simple devolvió resultado vacío")
        
        print("\n🧪 Probando get_unidades_proyecto_geometry()...")
        geometry_result = await get_unidades_proyecto_geometry()
        
        if geometry_result and geometry_result.get('success'):
            geom_data = geometry_result.get('data', [])
            print(f"✅ get_unidades_proyecto_geometry: {len(geom_data)} registros")
        else:
            print("❌ get_unidades_proyecto_geometry devolvió resultado vacío")
        
        print("\n🧪 Probando get_unidades_proyecto_attributes()...")
        attr_result = await get_unidades_proyecto_attributes()
        
        if attr_result and attr_result.get('success'):
            attr_data = attr_result.get('data', [])
            print(f"✅ get_unidades_proyecto_attributes: {len(attr_data)} registros")
        else:
            print("❌ get_unidades_proyecto_attributes devolvió resultado vacío")
            
    except Exception as e:
        print(f"❌ Error probando funciones API: {e}")
        import traceback
        traceback.print_exc()

async def main():
    print("🔥 DIAGNÓSTICO FIREBASE/FIRESTORE")
    print("🎯 Proyecto: dev-test-e778d")
    print()
    
    # Test 1: Conexión Firestore
    firestore_ok = test_firestore_connection()
    
    # Test 2: Funciones API
    await test_api_functions()
    
    print("\n" + "=" * 50)
    if firestore_ok:
        print("✅ Firestore tiene datos - problema podría estar en las funciones API")
    else:
        print("⚠️ Firestore vacío o problema de conexión - necesitas agregar datos")
    print("=" * 50)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())