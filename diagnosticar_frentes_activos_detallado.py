"""
Script de diagnóstico para analizar valores del campo frente_activo en Firebase
"""
import asyncio
import sys
import os

# Agregar el directorio raíz al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database.firebase_config import get_firestore_client


async def diagnosticar_frentes_activos():
    """Diagnosticar valores de frente_activo en la base de datos"""
    db = get_firestore_client()
    
    if db is None:
        print("❌ Error: No se pudo conectar a Firebase")
        return
    
    docs = db.collection('unidades_proyecto').stream()
    
    valores_frente = {}
    total_docs = 0
    docs_con_frente = 0
    ejemplos_por_valor = {}  # Guardar ejemplos de UPIDs por cada valor
    
    print("🔄 Procesando documentos...")
    
    for doc in docs:
        total_docs += 1
        data = doc.to_dict()
        upid = data.get('upid', doc.id)
        
        # Revisar estructura nueva
        if 'intervenciones' in data:
            intervenciones = data['intervenciones']
            if isinstance(intervenciones, list):
                for idx, interv in enumerate(intervenciones):
                    if isinstance(interv, str):
                        import json
                        try:
                            interv = json.loads(interv)
                        except:
                            continue
                    if isinstance(interv, dict):
                        valor = interv.get('frente_activo')
                        if valor:
                            docs_con_frente += 1
                            valores_frente[valor] = valores_frente.get(valor, 0) + 1
                            
                            # Guardar ejemplo
                            if valor not in ejemplos_por_valor:
                                ejemplos_por_valor[valor] = []
                            if len(ejemplos_por_valor[valor]) < 3:
                                ejemplos_por_valor[valor].append(f"{upid} (interv {idx})")
        
        # Revisar estructura antigua
        valor = data.get('frente_activo')
        if valor:
            docs_con_frente += 1
            valores_frente[valor] = valores_frente.get(valor, 0) + 1
            
            # Guardar ejemplo
            if valor not in ejemplos_por_valor:
                ejemplos_por_valor[valor] = []
            if len(ejemplos_por_valor[valor]) < 3:
                ejemplos_por_valor[valor].append(f"{upid} (doc directo)")
        
        # Progreso cada 100 docs
        if total_docs % 100 == 0:
            print(f"   Procesados {total_docs} documentos...")
    
    print(f"\n{'='*70}")
    print(f"📊 DIAGNÓSTICO FRENTES ACTIVOS")
    print(f"{'='*70}")
    print(f"\n📈 RESUMEN:")
    print(f"   Total documentos procesados: {total_docs}")
    print(f"   Documentos/intervenciones con frente_activo: {docs_con_frente}")
    print(f"   Valores únicos encontrados: {len(valores_frente)}")
    
    if valores_frente:
        print(f"\n📋 VALORES ÚNICOS (ordenados por frecuencia):")
        print(f"{'─'*70}")
        
        for valor, count in sorted(valores_frente.items(), key=lambda x: x[1], reverse=True):
            porcentaje = (count / docs_con_frente * 100) if docs_con_frente > 0 else 0
            print(f"\n   ✓ '{valor}'")
            print(f"      Cantidad: {count} ({porcentaje:.1f}%)")
            print(f"      Longitud: {len(valor)} caracteres")
            print(f"      Repr: {repr(valor)}")
            
            # Mostrar ejemplos
            if valor in ejemplos_por_valor and ejemplos_por_valor[valor]:
                print(f"      Ejemplos: {', '.join(ejemplos_por_valor[valor][:3])}")
        
        print(f"\n{'─'*70}")
        print(f"\n⚠️  ANÁLISIS:")
        print(f"   • El endpoint busca exactamente: 'Frente activo'")
        print(f"   • La comparación es case-sensitive (distingue mayúsculas/minúsculas)")
        print(f"   • Se ignoran espacios al inicio/final")
        
        # Análisis de coincidencia
        filtro_actual = "Frente activo"
        coincide = filtro_actual in valores_frente
        
        if coincide:
            count = valores_frente[filtro_actual]
            print(f"\n   ✅ El valor '{filtro_actual}' SÍ existe ({count} casos)")
        else:
            print(f"\n   ❌ El valor exacto '{filtro_actual}' NO existe en la BD")
            print(f"   📌 Se encontraron estas variaciones:")
            for valor in valores_frente.keys():
                if 'frente' in valor.lower() and 'activo' in valor.lower():
                    print(f"      • '{valor}'")
    else:
        print(f"\n⚠️  No se encontraron registros con el campo 'frente_activo'")
    
    print(f"\n{'='*70}\n")


if __name__ == "__main__":
    asyncio.run(diagnosticar_frentes_activos())
