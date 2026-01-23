#!/usr/bin/env bash
# -*- coding: utf-8 -*-
# Ejemplos de uso del endpoint Captura 360 con URLs
# Este archivo contiene comandos cURL listos para ejecutar

echo "=========================================="
echo "EJEMPLOS: Captura 360 con URLs"
echo "=========================================="
echo ""

# Variables de configuración
API_URL="http://localhost:8000"
ENDPOINT="/unidades-proyecto/captura-estado-360"

# Ejemplo 1: Captura básica - Estado "Durante"
echo "📸 EJEMPLO 1: Captura básica - Estado Durante"
echo "============================================="
echo ""
echo "curl -X POST ${API_URL}${ENDPOINT} \\"
curl -X POST ${API_URL}${ENDPOINT} \
  -F "upid=EJEMPLO-001" \
  -F "nombre_up=Parque Central Renovado" \
  -F "nombre_up_detalle=Renovación integral del parque" \
  -F "descripcion_intervencion=Mejoramiento de áreas verdes" \
  -F "solicitud_intervencion=SOLICITUD-2024-001" \
  -F "nombre_centro_gestor=Secretaría de Infraestructura" \
  -F "solicitud_centro_gestor=Requiere revisión técnica" \
  -F "estado_360=Durante" \
  -F "requiere_alcalde=false" \
  -F "entrega_publica=true" \
  -F "tipo_visita=Verificación" \
  -F "registrado_por_username=Juan Pérez García" \
  -F "registrado_por_email=juan.perez@example.com" \
  -F "coordinates_type=Point" \
  -F "coordinates_data=[-76.5225, 3.4516]" \
  -F "photosUrl=https://example.com/fotos/durante_01.jpg" \
  -F "photosUrl=https://cloudinary.com/fotos/durante_02.jpg" \
  -F "photosUrl=https://aws-cdn.example.com/fotos/durante_03.jpg" \
  -H "Content-Type: multipart/form-data"

echo ""
echo ""

# Ejemplo 2: Captura "Antes" con menos URLs
echo "📸 EJEMPLO 2: Captura - Estado Antes"
echo "====================================="
echo ""
curl -X POST ${API_URL}${ENDPOINT} \
  -F "upid=EJEMPLO-002" \
  -F "nombre_up=Plaza del Mercado" \
  -F "nombre_up_detalle=Modernización de instalaciones" \
  -F "descripcion_intervencion=Mejora de infraestructura comercial" \
  -F "solicitud_intervencion=SOLICITUD-2024-002" \
  -F "nombre_centro_gestor=Secretaría de Comercio" \
  -F "solicitud_centro_gestor=Revisión de permisos comerciales" \
  -F "estado_360=Antes" \
  -F "requiere_alcalde=true" \
  -F "entrega_publica=false" \
  -F "tipo_visita=Comunicaciones" \
  -F "registrado_por_username=María López" \
  -F "registrado_por_email=maria.lopez@example.com" \
  -F "coordinates_type=Point" \
  -F "coordinates_data=[-76.5230, 3.4520]" \
  -F "photosUrl=https://example.com/fotos/antes_01.jpg" \
  -F "photosUrl=https://example.com/fotos/antes_02.jpg" \
  -H "Content-Type: multipart/form-data"

echo ""
echo ""

# Ejemplo 3: Captura "Después" con una URL
echo "📸 EJEMPLO 3: Captura - Estado Después"
echo "======================================="
echo ""
curl -X POST ${API_URL}${ENDPOINT} \
  -F "upid=EJEMPLO-003" \
  -F "nombre_up=Biblioteca Pública" \
  -F "nombre_up_detalle=Ampliación de servicios" \
  -F "descripcion_intervencion=Aumento de salas de lectura" \
  -F "solicitud_intervencion=SOLICITUD-2024-003" \
  -F "nombre_centro_gestor=Secretaría de Cultura" \
  -F "solicitud_centro_gestor=Evaluación de impacto cultural" \
  -F "estado_360=Después" \
  -F "requiere_alcalde=false" \
  -F "entrega_publica=true" \
  -F "tipo_visita=Verificación" \
  -F "registrado_por_username=Carlos Rodriguez" \
  -F "registrado_por_email=carlos.rodriguez@example.com" \
  -F "coordinates_type=Point" \
  -F "coordinates_data=[-76.5240, 3.4510]" \
  -F "photosUrl=https://example.com/fotos/despues_01.jpg" \
  -H "Content-Type: multipart/form-data"

echo ""
echo ""

# Ejemplo 4: OBTENER registros
echo "🔍 EJEMPLO 4: Obtener registros"
echo "================================"
echo ""
echo "# Obtener TODOS los registros"
echo "curl -X GET ${API_URL}${ENDPOINT}"
curl -X GET ${API_URL}${ENDPOINT}

echo ""
echo ""

echo "# Filtrar por UPID específico"
echo "curl -X GET '${API_URL}${ENDPOINT}?upid=EJEMPLO-001'"
curl -X GET "${API_URL}${ENDPOINT}?upid=EJEMPLO-001"

echo ""
echo ""

echo "# Filtrar por estado_360"
echo "curl -X GET '${API_URL}${ENDPOINT}?estado_360=Durante'"
curl -X GET "${API_URL}${ENDPOINT}?estado_360=Durante"

echo ""
echo ""

echo "# Filtrar por centro gestor"
echo "curl -X GET '${API_URL}${ENDPOINT}?nombre_centro_gestor=Secretaría de Infraestructura'"
curl -X GET "${API_URL}${ENDPOINT}?nombre_centro_gestor=Secretaría de Infraestructura"

echo ""
echo ""

echo "✅ Ejemplos completados"
echo "========================"
echo ""
echo "Notas:"
echo "  • Los URLs deben ser válidos y públicamente accesibles"
echo "  • Se categorizan automáticamente según estado_360"
echo "  • Múltiples capturas para el mismo UPID/estado combinan URLs"
echo "  • Ver documentación para más detalles"
echo ""
