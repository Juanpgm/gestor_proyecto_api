"""
Script para diagnosticar la discrepancia entre el conteo esperado (88) y el real (119)
"""
import asyncio
import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database.firebase_config import get_firestore_client


async def diagnosticar_discrepancia():
    """Diagnosticar discrepancia en el conteo de frentes activos"""
    db = get_firestore_client()
    
    if db is None:
        print("❌ Error: No se pudo conectar a Firebase")
        return
    
    docs = db.collection('unidades_proyecto').stream()
    
    # Contadores detallados
    unidades_con_frente_activo = []
    total_intervenciones_frente_activo = 0
    unidades_con_multiples_intervenciones = []
    
    print("🔄 Analizando estructura de datos...\n")
    
    for doc in docs:
        data = doc.to_dict()
        upid = data.get('upid', doc.id)
        
        tiene_frente_activo = False
        intervenciones_frente_activo_en_unidad = 0
        total_intervenciones_en_unidad = 0
        
        # Revisar estructura nueva (con array de intervenciones)
        if 'intervenciones' in data and isinstance(data['intervenciones'], list):
            intervenciones = data['intervenciones']
            total_intervenciones_en_unidad = len(intervenciones)
            
            for idx, interv in enumerate(intervenciones):
                # Parsear si es string
                if isinstance(interv, str):
                    try:
                        interv = json.loads(interv)
                    except:
                        continue
                
                if isinstance(interv, dict):
                    valor = interv.get('frente_activo')
                    if valor == 'Frente activo':
                        tiene_frente_activo = True
                        intervenciones_frente_activo_en_unidad += 1
                        total_intervenciones_frente_activo += 1
        
        # Revisar estructura antigua (campo directo)
        elif data.get('frente_activo') == 'Frente activo':
            tiene_frente_activo = True
            intervenciones_frente_activo_en_unidad = 1
            total_intervenciones_frente_activo += 1
            total_intervenciones_en_unidad = 1
        
        # Si la unidad tiene frente activo, guardarla
        if tiene_frente_activo:
            info = {
                'upid': upid,
                'total_intervenciones': total_intervenciones_en_unidad,
                'intervenciones_con_frente_activo': intervenciones_frente_activo_en_unidad,
                'nombre_up': data.get('nombre_up', 'N/A')
            }
            unidades_con_frente_activo.append(info)
            
            # Detectar unidades con múltiples intervenciones
            if total_intervenciones_en_unidad > 1:
                unidades_con_multiples_intervenciones.append(info)
    
    print(f"{'='*80}")
    print(f"📊 DIAGNÓSTICO DE DISCREPANCIA - FRENTES ACTIVOS")
    print(f"{'='*80}\n")
    
    print(f"📈 CONTEO TOTAL:")
    print(f"   • Unidades con al menos 1 frente activo: {len(unidades_con_frente_activo)}")
    print(f"   • Total de intervenciones con frente activo: {total_intervenciones_frente_activo}")
    print(f"   • Diferencia: {len(unidades_con_frente_activo) - total_intervenciones_frente_activo}")
    
    print(f"\n📌 ANÁLISIS DE LA DISCREPANCIA:")
    print(f"   • Esperado (del diagnóstico anterior): 88 intervenciones")
    print(f"   • Reportado por frontend: 119 registros")
    print(f"   • Unidades detectadas ahora: {len(unidades_con_frente_activo)}")
    
    if len(unidades_con_frente_activo) == 119:
        print(f"   ✅ El frontend está contando UNIDADES (no intervenciones)")
    elif total_intervenciones_frente_activo == 119:
        print(f"   ✅ El frontend está contando INTERVENCIONES")
    else:
        print(f"   ⚠️ Hay otra discrepancia que investigar")
    
    print(f"\n🔍 UNIDADES CON MÚLTIPLES INTERVENCIONES:")
    print(f"   Total: {len(unidades_con_multiples_intervenciones)}")
    
    if unidades_con_multiples_intervenciones:
        print(f"\n   📋 Primeros 10 ejemplos:")
        for i, info in enumerate(unidades_con_multiples_intervenciones[:10], 1):
            print(f"\n   {i}. {info['upid']} - {info['nombre_up'][:50]}")
            print(f"      Total intervenciones: {info['total_intervenciones']}")
            print(f"      Con frente activo: {info['intervenciones_con_frente_activo']}")
            print(f"      Sin frente activo: {info['total_intervenciones'] - info['intervenciones_con_frente_activo']}")
    
    # Calcular cuántas intervenciones SIN frente activo se están incluyendo
    intervenciones_sin_frente_incluidas = sum(
        info['total_intervenciones'] - info['intervenciones_con_frente_activo']
        for info in unidades_con_frente_activo
    )
    
    print(f"\n⚠️  PROBLEMA DETECTADO:")
    print(f"   • Total de intervenciones en las unidades retornadas:")
    total_intervenciones_retornadas = sum(info['total_intervenciones'] for info in unidades_con_frente_activo)
    print(f"     {total_intervenciones_retornadas}")
    print(f"   • De las cuales tienen 'Frente activo': {total_intervenciones_frente_activo}")
    print(f"   • De las cuales NO tienen 'Frente activo': {intervenciones_sin_frente_incluidas}")
    
    print(f"\n💡 EXPLICACIÓN DE LA DISCREPANCIA:")
    if total_intervenciones_retornadas == 119:
        print(f"   ✅ El endpoint retorna {len(unidades_con_frente_activo)} unidades,")
        print(f"      pero el frontend está contando TODAS las intervenciones ({total_intervenciones_retornadas})")
        print(f"      incluyendo las {intervenciones_sin_frente_incluidas} que NO tienen 'Frente activo'")
        print(f"\n   🔧 SOLUCIÓN NECESARIA:")
        print(f"      El filtro debe eliminar las intervenciones sin 'Frente activo'")
        print(f"      de cada unidad antes de retornarla.")
    elif len(unidades_con_frente_activo) == 119:
        print(f"   ⚠️ Hay 119 unidades con frente activo, pero el diagnóstico")
        print(f"      anterior contó 88 intervenciones. Posible doble conteo.")
    
    # Verificar si hay unidades que aparecen múltiples veces
    print(f"\n🔎 VERIFICANDO DUPLICADOS:")
    upids = [info['upid'] for info in unidades_con_frente_activo]
    upids_unicos = set(upids)
    if len(upids) != len(upids_unicos):
        duplicados = len(upids) - len(upids_unicos)
        print(f"   ⚠️ Se detectaron {duplicados} UPIDs duplicados")
        
        from collections import Counter
        conteo = Counter(upids)
        duplicados_lista = [(upid, count) for upid, count in conteo.items() if count > 1]
        print(f"\n   Ejemplos de duplicados:")
        for upid, count in duplicados_lista[:5]:
            print(f"      • {upid}: aparece {count} veces")
    else:
        print(f"   ✅ No hay UPIDs duplicados ({len(upids_unicos)} únicos)")
    
    print(f"\n{'='*80}\n")


if __name__ == "__main__":
    asyncio.run(diagnosticar_discrepancia())
