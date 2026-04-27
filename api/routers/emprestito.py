# -*- coding: utf-8 -*-
"""
api/routers/emprestito.py — Endpoints principales de Gestion de Emprestito.

Cubre: contratos, procesos, ordenes de compra, convenios, pagos, RPC,
solicitudes de cambio, reportes, flujo de caja, proyecciones, SECOP.
"""

import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import (
    APIRouter,
    Body,
    File,
    Form,
    HTTPException,
    Path,
    Query,
    Request,
    UploadFile,
)
from pydantic import BaseModel, Field
from fastapi.responses import JSONResponse

from api.core.responses import clean_firebase_data, create_utf8_response
from api.core.security import optional_rate_limit

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Gestión de Empréstito"])

# ---------------------------------------------------------------------------
# Disponibilidad de operaciones
# ---------------------------------------------------------------------------
try:
    from database.firebase_config import FIREBASE_AVAILABLE, get_firestore_client
except Exception:
    FIREBASE_AVAILABLE = False
    get_firestore_client = lambda: None

try:
    from api.scripts import (
        procesar_emprestito_completo,
        verificar_proceso_existente,
        eliminar_proceso_emprestito,
        actualizar_proceso_emprestito,
        obtener_codigos_contratos,
        buscar_y_poblar_contratos_secop,
        obtener_contratos_desde_proceso_contractual,
        obtener_contratos_desde_proceso_contractual_completo,
        get_emprestito_operations_status,
        cargar_orden_compra_directa,
        cargar_convenio_transferencia,
        modificar_convenio_transferencia,
        actualizar_orden_compra_por_numero,
        eliminar_orden_compra_por_numero,
        eliminar_convenio_transferencia_por_referencia,
        actualizar_convenio_por_referencia,
        actualizar_contrato_secop_por_referencia,
        actualizar_proceso_secop_por_referencia,
        cargar_rpc_emprestito,
        cargar_pago_emprestito,
        get_pagos_emprestito_all,
        get_rpc_contratos_emprestito_all,
        actualizar_rpc_contrato_emprestito,
        get_asignaciones_emprestito_banco_centro_gestor_all,
        get_convenios_transferencia_emprestito_all,
        obtener_ordenes_compra_tvec_enriquecidas,
        get_tvec_enrich_status,
        get_ordenes_compra_emprestito_all,
        get_ordenes_compra_emprestito_by_referencia,
        get_ordenes_compra_emprestito_by_centro_gestor,
        registrar_cambio_valor,
        obtener_historial_cambios,
        EMPRESTITO_OPERATIONS_AVAILABLE,
        TVEC_ENRICH_OPERATIONS_AVAILABLE,
        ORDENES_COMPRA_OPERATIONS_AVAILABLE,
        obtener_datos_secop_completos,
        actualizar_proceso_emprestito_completo,
        procesar_todos_procesos_emprestito_completo,
        crear_tabla_proyecciones_desde_sheets,
        leer_proyecciones_emprestito,
        leer_proyecciones_no_guardadas,
        get_proyecciones_sin_proceso,
        actualizar_proyeccion_emprestito,
        get_procesos_emprestito_all,
        get_contratos_emprestito_all,
        get_contratos_emprestito_by_referencia,
        get_contratos_emprestito_by_centro_gestor,
        process_flujo_caja_excel,
        save_flujo_caja_to_firebase,
        get_flujo_caja_from_firebase,
        FLUJO_CAJA_OPERATIONS_AVAILABLE,
    )
except Exception as _e:
    logger.warning(f"Emprestito scripts not fully available: {_e}")
    EMPRESTITO_OPERATIONS_AVAILABLE = False
    TVEC_ENRICH_OPERATIONS_AVAILABLE = False
    ORDENES_COMPRA_OPERATIONS_AVAILABLE = False
    FLUJO_CAJA_OPERATIONS_AVAILABLE = False

try:
    from api.models import (
        EmprestitoRequest,
        EmprestitoResponse,
        PagoEmprestitoRequest,
        PagoEmprestitoResponse,
        ProyeccionEmprestitoUpdateRequest,
        ProyeccionEmprestitoUpdateResponse,
        ProyeccionEmprestitoRegistroRequest,
        ProyeccionEmprestitoRegistroResponse,
        RPCUpdateRequest,
        RPCUpdateResponse,
        FlujoCajaRequest,
        FlujoCajaResponse,
        FlujoCajaUploadRequest,
        FlujoCajaFilters,
    )
except Exception:
    from pydantic import BaseModel

    class EmprestitoRequest(BaseModel):
        referencia_proceso: str = ""

    class EmprestitoResponse(BaseModel):
        success: bool = True

    class PagoEmprestitoRequest(BaseModel):
        pass

    class PagoEmprestitoResponse(BaseModel):
        pass

    class ProyeccionEmprestitoUpdateRequest(BaseModel):
        pass

    class ProyeccionEmprestitoUpdateResponse(BaseModel):
        pass

    class ProyeccionEmprestitoRegistroRequest(BaseModel):
        pass

    class ProyeccionEmprestitoRegistroResponse(BaseModel):
        pass

    class RPCUpdateRequest(BaseModel):
        pass

    class RPCUpdateResponse(BaseModel):
        pass

    class FlujoCajaRequest(BaseModel):
        pass

    class FlujoCajaResponse(BaseModel):
        pass

    class FlujoCajaUploadRequest(BaseModel):
        pass

    class FlujoCajaFilters(BaseModel):
        pass


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


def _as_firestore_doc_snapshot(value: Any) -> Any:
    """Type-cast helper para documentos de Firestore."""
    return value



@router.post(
    "/emprestito/cargar-proceso",
    tags=["Gestión de Empréstito"],
    summary=" Cargar Proceso de Empréstito",
)
async def cargar_proceso_emprestito(
    referencia_proceso: str = Form(
        ..., description="Referencia del proceso (obligatorio)"
    ),
    nombre_centro_gestor: str = Form(
        ..., description="Centro gestor responsable (obligatorio)"
    ),
    nombre_banco: str = Form(..., description="Nombre del banco (obligatorio)"),
    plataforma: str = Form(..., description="Plataforma (SECOP, TVEC) (obligatorio)"),
    bp: Optional[str] = Form(None, description="Código BP (opcional)"),
    nombre_resumido_proceso: Optional[str] = Form(
        None, description="Nombre resumido del proceso (opcional)"
    ),
    id_paa: Optional[str] = Form(None, description="ID PAA (opcional)"),
    valor_proyectado: Optional[float] = Form(
        None, description="Valor proyectado (opcional)"
    ),
):
    """
    ##  POST |  Carga de Datos | Cargar Proceso de Empréstito

    Endpoint unificado para carga de procesos de empréstito con detección automática
    de plataforma (SECOP/TVEC) y validación de duplicados.

    ### [OK] Funcionalidades principales:
    - **Detección automática**: Identifica si es SECOP o TVEC basado en el campo `plataforma`
    - **Validación de duplicados**: Verifica existencia previa usando `referencia_proceso`
    - **Integración API**: Obtiene datos completos desde APIs externas (SECOP/TVEC)
    - **Almacenamiento inteligente**: Guarda en colección apropiada según plataforma

    ###  Detección de plataforma:
    **SECOP**: "SECOP", "SECOP II", "SECOP I", "SECOP 2", "SECOP 1" y variantes
    **TVEC**: "TVEC" y variantes

    ###  Almacenamiento por plataforma:
    - **SECOP** → Colección: `procesos_emprestito`
    - **TVEC** → Colección: `ordenes_compra_emprestito`

    ###  Validación de duplicados:
    Busca `referencia_proceso` en ambas colecciones antes de crear nuevo registro.

    ###  Campos obligatorios:
    - `referencia_proceso`: Referencia del proceso
    - `nombre_centro_gestor`: Centro gestor responsable
    - `nombre_banco`: Nombre del banco
    - `plataforma`: Plataforma (SECOP/TVEC)

    ###  Campos opcionales:
    - `bp`: Código BP
    - `nombre_resumido_proceso`: Nombre resumido
    - `id_paa`: ID PAA
    - `valor_proyectado`: Valor proyectado

    ###  Integración con APIs:
    **SECOP**: Obtiene datos desde API de datos abiertos (p6dx-8zbt)
    **TVEC**: Obtiene datos desde API TVEC (rgxm-mmea)

    ###  Ejemplo de request:
    ```json
    {
        "referencia_proceso": "SCMGSU-CM-003-2024",
        "nombre_centro_gestor": "Secretaría de Salud",
        "nombre_banco": "Banco Mundial",
        "bp": "BP-2024-001",
        "plataforma": "SECOP II",
        "nombre_resumido_proceso": "Suministro equipos médicos",
        "id_paa": "PAA-2024-123",
        "valor_proyectado": 1500000000.0
    }
    ```
    """
    try:
        check_emprestito_availability()

        # Crear diccionario con los datos del formulario
        datos_emprestito = {
            "referencia_proceso": referencia_proceso,
            "nombre_centro_gestor": nombre_centro_gestor,
            "nombre_banco": nombre_banco,
            "bp": bp,
            "plataforma": plataforma,
            "nombre_resumido_proceso": nombre_resumido_proceso,
            "id_paa": id_paa,
            "valor_proyectado": valor_proyectado,
        }

        # Procesar empréstito completo con todas las validaciones
        resultado = await procesar_emprestito_completo(datos_emprestito)

        # Manejar respuesta según el resultado
        if not resultado.get("success"):
            # Manejar caso especial de duplicado
            if resultado.get("duplicate"):
                return JSONResponse(
                    content={
                        "success": False,
                        "error": resultado.get("error"),
                        "duplicate": True,
                        "existing_data": resultado.get("existing_data"),
                        "message": "Ya existe un proceso con esta referencia",
                        "timestamp": datetime.now().isoformat(),
                    },
                    status_code=409,  # Conflict
                    headers={"Content-Type": "application/json; charset=utf-8"},
                )
            else:
                # Error general
                return JSONResponse(
                    content={
                        "success": False,
                        "error": resultado.get("error"),
                        "plataforma_detectada": resultado.get("plataforma_detectada"),
                        "message": "Error procesando proceso de empréstito",
                        "timestamp": datetime.now().isoformat(),
                    },
                    status_code=400,
                    headers={"Content-Type": "application/json; charset=utf-8"},
                )

        # Éxito: proceso creado correctamente
        respuesta_base = {
            "success": True,
            "message": "Proceso de empréstito cargado exitosamente",
            "data": resultado.get("data"),
            "doc_id": resultado.get("doc_id"),
            "coleccion": resultado.get("coleccion"),
            "plataforma_detectada": resultado.get("plataforma_detectada"),
            "fuente_datos": resultado.get("fuente_datos"),
            "timestamp": datetime.now().isoformat(),
        }

        # Si es un proceso SECOP, intentar actualizar con datos completos automáticamente
        if (
            resultado.get("plataforma_detectada") == "SECOP"
            and resultado.get("coleccion") == "procesos_emprestito"
        ):
            try:
                logger.info(
                    f" Actualizando automáticamente proceso SECOP: {referencia_proceso}"
                )
                resultado_actualizacion = await actualizar_proceso_emprestito_completo(
                    referencia_proceso
                )

                if resultado_actualizacion.get("success"):
                    respuesta_base["actualizacion_completa"] = {
                        "success": True,
                        "changes_count": resultado_actualizacion.get(
                            "changes_count", 0
                        ),
                        "changes_summary": resultado_actualizacion.get(
                            "changes_summary", []
                        )[
                            :5
                        ],  # Máximo 5 cambios en resumen
                        "message": f"Proceso actualizado automáticamente con {resultado_actualizacion.get('changes_count', 0)} campos adicionales",
                    }
                    logger.info(
                        f"[OK] Actualización automática exitosa: {resultado_actualizacion.get('changes_count', 0)} cambios"
                    )
                else:
                    respuesta_base["actualizacion_completa"] = {
                        "success": False,
                        "error": resultado_actualizacion.get(
                            "error", "Error desconocido"
                        ),
                        "message": "No se pudo actualizar automáticamente con datos completos",
                    }
                    logger.warning(
                        f"[WARNING] Actualización automática falló: {resultado_actualizacion.get('error')}"
                    )

            except Exception as e:
                logger.warning(f"[WARNING] Error en actualización automática: {e}")
                respuesta_base["actualizacion_completa"] = {
                    "success": False,
                    "error": str(e),
                    "message": "Error durante actualización automática (proceso principal creado exitosamente)",
                }

        return JSONResponse(
            content=respuesta_base,
            status_code=201,
            headers={"Content-Type": "application/json; charset=utf-8"},
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error en endpoint de empréstito: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": "Error interno del servidor",
                "message": "Por favor, inténtelo de nuevo más tarde",
                "code": "INTERNAL_SERVER_ERROR",
            },
        )


@router.post(
    "/emprestito/cargar-orden-compra",
    tags=["Gestión de Empréstito"],
    summary=" Cargar Orden de Compra",
)
async def cargar_orden_compra_emprestito(
    numero_orden: str = Form(
        ..., description="Número de la orden de compra (obligatorio)"
    ),
    nombre_centro_gestor: str = Form(
        ..., description="Centro gestor responsable (obligatorio)"
    ),
    nombre_banco: str = Form(..., description="Nombre del banco (obligatorio)"),
    nombre_resumido_proceso: str = Form(
        ..., description="Nombre resumido del proceso (obligatorio)"
    ),
    valor_proyectado: float = Form(..., description="Valor proyectado (obligatorio)"),
    bp: Optional[str] = Form(None, description="Código BP (opcional)"),
):
    """
    ##  POST |  Carga de Datos | Cargar Orden de Compra de Empréstito

    Endpoint para carga directa de órdenes de compra de empréstito en la colección
    `ordenes_compra_emprestito` sin procesamiento de APIs externas.

    ### [OK] Funcionalidades principales:
    - **Carga directa**: Registra directamente en `ordenes_compra_emprestito`
    - **Validación de duplicados**: Verifica existencia previa usando `numero_orden`
    - **Validación de campos**: Verifica que todos los campos obligatorios estén presentes
    - **Timestamps automáticos**: Agrega fecha de creación y actualización

    ###  Campos obligatorios:
    - `numero_orden`: Número único de la orden de compra
    - `nombre_centro_gestor`: Centro gestor responsable
    - `nombre_banco`: Nombre del banco
    - `nombre_resumido_proceso`: Nombre resumido del proceso
    - `valor_proyectado`: Valor proyectado en pesos colombianos

    ###  Campos opcionales:
    - `bp`: Código BP

    ###  Validación de duplicados:
    Busca `numero_orden` en la colección `ordenes_compra_emprestito` antes de crear nuevo registro.

    ###  Estructura de datos guardados:
    ```json
    {
        "numero_orden": "OC-2024-001",
        "nombre_centro_gestor": "Secretaría de Salud",
        "nombre_banco": "Banco Mundial",
        "nombre_resumido_proceso": "Suministro equipos médicos",
        "valor_proyectado": 1500000000.0,
        "bp": "BP-2024-001",
        "fecha_creacion": "2024-10-14T10:30:00",
        "fecha_actualizacion": "2024-10-14T10:30:00",
        "estado": "activo",
        "tipo": "orden_compra_manual"
    }
    ```

    ###  Ejemplo de request:
    ```json
    {
        "numero_orden": "OC-SALUD-003-2024",
        "nombre_centro_gestor": "Secretaría de Salud",
        "nombre_banco": "Banco Mundial",
        "nombre_resumido_proceso": "Suministro equipos médicos",
        "valor_proyectado": 1500000000.0,
        "bp": "BP-2024-001"
    }
    ```

    ### [OK] Respuesta exitosa (201):
    ```json
    {
        "success": true,
        "message": "Orden de compra OC-SALUD-003-2024 guardada exitosamente",
        "doc_id": "abc123def456",
        "data": { ... },
        "coleccion": "ordenes_compra_emprestito"
    }
    ```

    ### [ERROR] Respuesta de duplicado (409):
    ```json
    {
        "success": false,
        "error": "Ya existe una orden de compra con número: OC-SALUD-003-2024",
        "duplicate": true,
        "existing_data": { ... }
    }
    ```
    """
    try:
        check_emprestito_availability()

        # Crear diccionario con los datos del formulario
        datos_orden = {
            "numero_orden": numero_orden,
            "nombre_centro_gestor": nombre_centro_gestor,
            "nombre_banco": nombre_banco,
            "nombre_resumido_proceso": nombre_resumido_proceso,
            "valor_proyectado": valor_proyectado,
            "bp": bp,
        }

        # Procesar orden de compra
        resultado = await cargar_orden_compra_directa(datos_orden)

        # Manejar respuesta según el resultado
        if not resultado.get("success"):
            # Manejar caso especial de duplicado
            if resultado.get("duplicate"):
                return JSONResponse(
                    content={
                        "success": False,
                        "error": resultado.get("error"),
                        "duplicate": True,
                        "existing_data": resultado.get("existing_data"),
                        "message": "Ya existe una orden de compra con este número",
                        "timestamp": datetime.now().isoformat(),
                    },
                    status_code=409,  # Conflict
                    headers={"Content-Type": "application/json; charset=utf-8"},
                )
            else:
                # Error general
                return JSONResponse(
                    content={
                        "success": False,
                        "error": resultado.get("error"),
                        "message": "Error al procesar la orden de compra",
                        "timestamp": datetime.now().isoformat(),
                    },
                    status_code=400,
                    headers={"Content-Type": "application/json; charset=utf-8"},
                )

        # Respuesta exitosa
        return JSONResponse(
            content={
                "success": True,
                "message": resultado.get("message"),
                "data": resultado.get("data"),
                "doc_id": resultado.get("doc_id"),
                "coleccion": resultado.get("coleccion"),
                "timestamp": datetime.now().isoformat(),
            },
            status_code=201,
            headers={"Content-Type": "application/json; charset=utf-8"},
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error en endpoint de orden de compra: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": "Error interno del servidor",
                "message": "Por favor, inténtelo de nuevo más tarde",
                "code": "INTERNAL_SERVER_ERROR",
            },
        )


@router.post(
    "/emprestito/cargar-convenio-transferencia",
    tags=["Gestión de Empréstito"],
    summary=" Cargar Convenio de Transferencia",
)
async def cargar_convenio_transferencia_emprestito(
    referencia_contrato: str = Form(
        ..., description="Referencia del contrato/convenio (obligatorio)"
    ),
    nombre_centro_gestor: str = Form(
        ..., description="Centro gestor responsable (obligatorio)"
    ),
    banco: str = Form(..., description="Nombre del banco (obligatorio)"),
    objeto_contrato: str = Form(..., description="Objeto del contrato (obligatorio)"),
    valor_contrato: float = Form(..., description="Valor del contrato (obligatorio)"),
    bp: Optional[str] = Form(None, description="Código BP (opcional)"),
    bpin: Optional[str] = Form(None, description="Código BPIN (opcional)"),
    valor_convenio: Optional[float] = Form(
        None, description="Valor del convenio (opcional)"
    ),
    urlproceso: Optional[str] = Form(None, description="URL del proceso (opcional)"),
    fecha_inicio_contrato: Optional[str] = Form(
        None, description="Fecha de inicio del contrato (opcional)"
    ),
    fecha_fin_contrato: Optional[str] = Form(
        None, description="Fecha de fin del contrato (opcional)"
    ),
    modalidad_contrato: Optional[str] = Form(
        None, description="Modalidad del contrato (opcional)"
    ),
    ordenador_gastor: Optional[str] = Form(
        None, description="Ordenador del gasto (opcional)"
    ),
    tipo_contrato: Optional[str] = Form(
        None, description="Tipo de contrato (opcional)"
    ),
    estado_contrato: Optional[str] = Form(
        None, description="Estado del contrato (opcional)"
    ),
    sector: Optional[str] = Form(None, description="Sector (opcional)"),
    nombre_resumido_proceso: str = Form(
        ..., description="Nombre resumido del proceso (obligatorio)"
    ),
):
    """
    ##  POST |  Carga de Datos | Cargar Convenio de Transferencia de Empréstito

    Endpoint para carga directa de convenios de transferencia de empréstito en la colección
    `convenios_transferencias_emprestito` sin procesamiento de APIs externas.

    ### [OK] Funcionalidades principales:
    - **Carga directa**: Registra directamente en `convenios_transferencias_emprestito`
    - **Validación de duplicados**: Verifica existencia previa usando `referencia_contrato`
    - **Validación de campos**: Verifica que todos los campos obligatorios estén presentes
    - **Timestamps automáticos**: Agrega fecha de creación y actualización

    ###  Campos obligatorios:
    - `referencia_contrato`: Referencia única del contrato/convenio
    - `nombre_centro_gestor`: Centro gestor responsable
    - `banco`: Nombre del banco
    - `objeto_contrato`: Descripción del objeto del contrato
    - `valor_contrato`: Valor del contrato en pesos colombianos

    ###  Campos opcionales:
    - `bp`: Código BP
    - `bpin`: Código BPIN (Banco de Programas y Proyectos de Inversión Nacional)
    - `valor_convenio`: Valor específico del convenio
    - `urlproceso`: URL del proceso de contratación
    - `fecha_inicio_contrato`: Fecha de inicio del contrato
    - `fecha_fin_contrato`: Fecha de finalización del contrato
    - `modalidad_contrato`: Modalidad de contratación
    - `ordenador_gastor`: Ordenador del gasto
    - `tipo_contrato`: Tipo de contrato
    - `estado_contrato`: Estado actual del contrato
    - `sector`: Sector al que pertenece

    ###  Validación de duplicados:
    Busca `referencia_contrato` en la colección `convenios_transferencias_emprestito` antes de crear nuevo registro.

    ###  Estructura de datos guardados:
    ```json
    {
        "referencia_contrato": "CONV-2024-001",
        "nombre_centro_gestor": "Secretaría de Salud",
        "banco": "Banco Mundial",
        "objeto_contrato": "Convenio de transferencia para equipamiento médico",
        "valor_contrato": 1500000000.0,
        "valor_convenio": 1200000000.0,
        "bp": "BP-2024-001",
        "bpin": "2024000010001",
        "urlproceso": "https://...",
        "fecha_inicio_contrato": "2024-01-15",
        "fecha_fin_contrato": "2024-12-31",
        "modalidad_contrato": "Convenio de Transferencia",
        "ordenador_gastor": "Juan Pérez",
        "tipo_contrato": "Transferencia",
        "estado_contrato": "Activo",
        "sector": "Salud",
        "fecha_creacion": "2024-10-14T10:30:00",
        "fecha_actualizacion": "2024-10-14T10:30:00",
        "estado": "activo",
        "tipo": "convenio_transferencia_manual"
    }
    ```

    ###  Ejemplo de request:
    ```json
    {
        "referencia_contrato": "CONV-SALUD-003-2024",
        "nombre_centro_gestor": "Secretaría de Salud",
        "banco": "Banco Mundial",
        "objeto_contrato": "Convenio de transferencia para equipamiento médico",
        "valor_contrato": 1500000000.0,
        "valor_convenio": 1200000000.0,
        "bp": "BP-2024-001",
        "modalidad_contrato": "Convenio de Transferencia",
        "estado_contrato": "Activo"
    }
    ```

    ### [OK] Respuesta exitosa (201):
    ```json
    {
        "success": true,
        "message": "Convenio de transferencia CONV-SALUD-003-2024 guardado exitosamente",
        "doc_id": "abc123def456",
        "data": { ... },
        "coleccion": "convenios_transferencias_emprestito"
    }
    ```

    ### [ERROR] Respuesta de duplicado (409):
    ```json
    {
        "success": false,
        "error": "Ya existe un convenio de transferencia con referencia: CONV-SALUD-003-2024",
        "duplicate": true,
        "existing_data": { ... }
    }
    ```
    """
    try:
        check_emprestito_availability()

        # Crear diccionario con los datos del formulario
        datos_convenio = {
            "referencia_contrato": referencia_contrato,
            "nombre_centro_gestor": nombre_centro_gestor,
            "banco": banco,
            "objeto_contrato": objeto_contrato,
            "valor_contrato": valor_contrato,
            "bp": bp,
            "bpin": bpin,
            "valor_convenio": valor_convenio,
            "urlproceso": urlproceso,
            "fecha_inicio_contrato": fecha_inicio_contrato,
            "fecha_fin_contrato": fecha_fin_contrato,
            "modalidad_contrato": modalidad_contrato,
            "ordenador_gastor": ordenador_gastor,
            "tipo_contrato": tipo_contrato,
            "estado_contrato": estado_contrato,
            "sector": sector,
            "nombre_resumido_proceso": nombre_resumido_proceso,
        }

        # Procesar convenio de transferencia
        resultado = await cargar_convenio_transferencia(datos_convenio)

        # Manejar respuesta según el resultado
        if not resultado.get("success"):
            # Manejar caso especial de duplicado
            if resultado.get("duplicate"):
                return JSONResponse(
                    content={
                        "success": False,
                        "error": resultado.get("error"),
                        "duplicate": True,
                        "existing_data": resultado.get("existing_data"),
                        "message": "Ya existe un convenio de transferencia con esta referencia",
                        "timestamp": datetime.now().isoformat(),
                    },
                    status_code=409,  # Conflict
                    headers={"Content-Type": "application/json; charset=utf-8"},
                )
            else:
                # Error general
                return JSONResponse(
                    content={
                        "success": False,
                        "error": resultado.get("error"),
                        "message": "Error al procesar el convenio de transferencia",
                        "timestamp": datetime.now().isoformat(),
                    },
                    status_code=400,
                    headers={"Content-Type": "application/json; charset=utf-8"},
                )

        # Respuesta exitosa
        return JSONResponse(
            content={
                "success": True,
                "message": resultado.get("message"),
                "data": resultado.get("data"),
                "doc_id": resultado.get("doc_id"),
                "coleccion": resultado.get("coleccion"),
                "timestamp": datetime.now().isoformat(),
            },
            status_code=201,
            headers={"Content-Type": "application/json; charset=utf-8"},
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error en endpoint de convenio de transferencia: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": "Error interno del servidor",
                "message": "Por favor, inténtelo de nuevo más tarde",
                "code": "INTERNAL_SERVER_ERROR",
            },
        )


@router.delete(
    "/emprestito/eliminar-orden-compra/{numero_orden}",
    tags=["Gestión de Empréstito"],
    summary=" Eliminar Orden de Compra",
)
async def eliminar_orden_compra_emprestito(
    numero_orden: str = Path(..., description="Número de orden a eliminar")
):
    """
    ##  DELETE |  Gestión de Datos | Eliminar Orden de Compra de Empréstito

    Elimina un registro de la colección `ordenes_compra_emprestito` usando `numero_orden`
    como criterio de búsqueda.
    """
    try:
        check_emprestito_availability()

        resultado = await eliminar_orden_compra_por_numero(numero_orden)

        if not resultado.get("success"):
            if resultado.get("not_found"):
                return JSONResponse(
                    content={
                        "success": False,
                        "error": resultado.get("error"),
                        "numero_orden": numero_orden,
                        "message": "No existe una orden de compra con ese número",
                        "timestamp": datetime.now().isoformat(),
                    },
                    status_code=404,
                    headers={"Content-Type": "application/json; charset=utf-8"},
                )

            return JSONResponse(
                content={
                    "success": False,
                    "error": resultado.get("error"),
                    "numero_orden": numero_orden,
                    "message": "Error al eliminar la orden de compra",
                    "timestamp": datetime.now().isoformat(),
                },
                status_code=400,
                headers={"Content-Type": "application/json; charset=utf-8"},
            )

        return JSONResponse(
            content={
                "success": True,
                "message": resultado.get("message"),
                "numero_orden": resultado.get("numero_orden"),
                "doc_id": resultado.get("doc_id"),
                "deleted_data": resultado.get("deleted_data"),
                "coleccion": resultado.get("coleccion"),
                "timestamp": datetime.now().isoformat(),
            },
            status_code=200,
            headers={"Content-Type": "application/json; charset=utf-8"},
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error en endpoint eliminar orden de compra: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": "Error interno del servidor",
                "message": "Por favor, inténtelo de nuevo más tarde",
                "code": "INTERNAL_SERVER_ERROR",
            },
        )


@router.delete(
    "/emprestito/eliminar-convenio-transferencia/{referencia_contrato}",
    tags=["Gestión de Empréstito"],
    summary=" Eliminar Convenio de Transferencia",
)
async def eliminar_convenio_transferencia_emprestito(
    referencia_contrato: str = Path(
        ..., description="Referencia de contrato del convenio a eliminar"
    )
):
    """
    ##  DELETE |  Gestión de Datos | Eliminar Convenio de Transferencia de Empréstito

    Elimina un registro de la colección `convenios_transferencias_emprestito`
    usando `referencia_contrato` como criterio de búsqueda.
    """
    try:
        check_emprestito_availability()

        resultado = await eliminar_convenio_transferencia_por_referencia(
            referencia_contrato
        )

        if not resultado.get("success"):
            if resultado.get("not_found"):
                return JSONResponse(
                    content={
                        "success": False,
                        "error": resultado.get("error"),
                        "referencia_contrato": referencia_contrato,
                        "message": "No existe un convenio de transferencia con esa referencia",
                        "timestamp": datetime.now().isoformat(),
                    },
                    status_code=404,
                    headers={"Content-Type": "application/json; charset=utf-8"},
                )

            return JSONResponse(
                content={
                    "success": False,
                    "error": resultado.get("error"),
                    "referencia_contrato": referencia_contrato,
                    "message": "Error al eliminar el convenio de transferencia",
                    "timestamp": datetime.now().isoformat(),
                },
                status_code=400,
                headers={"Content-Type": "application/json; charset=utf-8"},
            )

        return JSONResponse(
            content={
                "success": True,
                "message": resultado.get("message"),
                "referencia_contrato": resultado.get("referencia_contrato"),
                "doc_id": resultado.get("doc_id"),
                "deleted_data": resultado.get("deleted_data"),
                "coleccion": resultado.get("coleccion"),
                "timestamp": datetime.now().isoformat(),
            },
            status_code=200,
            headers={"Content-Type": "application/json; charset=utf-8"},
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error en endpoint eliminar convenio de transferencia: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": "Error interno del servidor",
                "message": "Por favor, inténtelo de nuevo más tarde",
                "code": "INTERNAL_SERVER_ERROR",
            },
        )


@router.put(
    "/emprestito/modificar-convenio-transferencia",
    tags=["Gestión de Empréstito"],
    summary=" Modificar Convenio de Transferencia",
)
async def modificar_convenio_transferencia_emprestito(
    doc_id: str = Form(..., description="ID del documento a modificar (obligatorio)"),
    referencia_contrato: Optional[str] = Form(
        None, description="Referencia del contrato/convenio (opcional)"
    ),
    nombre_centro_gestor: Optional[str] = Form(
        None, description="Centro gestor responsable (opcional)"
    ),
    banco: Optional[str] = Form(None, description="Nombre del banco (opcional)"),
    objeto_contrato: Optional[str] = Form(
        None, description="Objeto del contrato (opcional)"
    ),
    valor_contrato: Optional[float] = Form(
        None, description="Valor del contrato (opcional)"
    ),
    bp: Optional[str] = Form(None, description="Código BP (opcional)"),
    bpin: Optional[str] = Form(None, description="Código BPIN (opcional)"),
    valor_convenio: Optional[float] = Form(
        None, description="Valor del convenio (opcional)"
    ),
    urlproceso: Optional[str] = Form(None, description="URL del proceso (opcional)"),
    fecha_inicio_contrato: Optional[str] = Form(
        None, description="Fecha de inicio del contrato (opcional)"
    ),
    fecha_fin_contrato: Optional[str] = Form(
        None, description="Fecha de fin del contrato (opcional)"
    ),
    modalidad_contrato: Optional[str] = Form(
        None, description="Modalidad del contrato (opcional)"
    ),
    ordenador_gastor: Optional[str] = Form(
        None, description="Ordenador del gasto (opcional)"
    ),
    tipo_contrato: Optional[str] = Form(
        None, description="Tipo de contrato (opcional)"
    ),
    estado_contrato: Optional[str] = Form(
        None, description="Estado del contrato (opcional)"
    ),
    sector: Optional[str] = Form(None, description="Sector (opcional)"),
    nombre_resumido_proceso: Optional[str] = Form(
        None, description="Nombre resumido del proceso (opcional)"
    ),
):
    """
    ##  PUT |  Actualización | Modificar Convenio de Transferencia de Empréstito

    Endpoint para modificar cualquier campo de un convenio de transferencia existente
    en la colección `convenios_transferencias_emprestito`.

    ### [OK] Funcionalidades principales:
    - **Actualización flexible**: Permite modificar cualquier campo del convenio
    - **Actualización parcial**: Solo se actualizan los campos proporcionados
    - **Validación de existencia**: Verifica que el documento exista antes de actualizar
    - **Timestamp automático**: Actualiza automáticamente `fecha_actualizacion`
    - **Preservación de datos**: Los campos no proporcionados mantienen sus valores originales

    ###  Campo obligatorio:
    - `doc_id`: ID del documento de Firestore que se desea modificar

    ###  Campos opcionales (todos):
    Cualquiera de estos campos puede ser actualizado:
    - `referencia_contrato`: Referencia del contrato/convenio
    - `nombre_centro_gestor`: Centro gestor responsable
    - `banco`: Nombre del banco
    - `objeto_contrato`: Objeto del contrato
    - `valor_contrato`: Valor del contrato
    - `bp`: Código BP
    - `bpin`: Código BPIN
    - `valor_convenio`: Valor del convenio
    - `urlproceso`: URL del proceso
    - `fecha_inicio_contrato`: Fecha de inicio
    - `fecha_fin_contrato`: Fecha de finalización
    - `modalidad_contrato`: Modalidad de contratación
    - `ordenador_gastor`: Ordenador del gasto
    - `tipo_contrato`: Tipo de contrato
    - `estado_contrato`: Estado actual
    - `sector`: Sector al que pertenece
    - `nombre_resumido_proceso`: Nombre resumido del proceso

    ###  Ejemplo de request (actualización parcial):
    ```json
    {
        "doc_id": "abc123def456",
        "estado_contrato": "Finalizado",
        "fecha_fin_contrato": "2024-12-31"
    }
    ```

    ### [OK] Respuesta exitosa (200):
    ```json
    {
        "success": true,
        "message": "Convenio de transferencia actualizado exitosamente",
        "doc_id": "abc123def456",
        "campos_actualizados": ["estado_contrato", "fecha_fin_contrato"],
        "data": { ... },
        "timestamp": "2024-11-17T10:30:00"
    }
    ```

    ### [ERROR] Respuesta de error (404):
    ```json
    {
        "success": false,
        "error": "No se encontró el convenio de transferencia con ID: abc123",
        "doc_id": "abc123"
    }
    ```

    ###  Endpoints relacionados:
    - `POST /emprestito/cargar-convenio-transferencia` - Para crear nuevos convenios
    - `GET /convenios_transferencias_all` - Para consultar convenios existentes
    """
    try:
        check_emprestito_availability()

        # Crear diccionario con los campos a actualizar
        campos_actualizar = {}

        if referencia_contrato is not None:
            campos_actualizar["referencia_contrato"] = referencia_contrato
        if nombre_centro_gestor is not None:
            campos_actualizar["nombre_centro_gestor"] = nombre_centro_gestor
        if banco is not None:
            campos_actualizar["banco"] = banco
        if objeto_contrato is not None:
            campos_actualizar["objeto_contrato"] = objeto_contrato
        if valor_contrato is not None:
            campos_actualizar["valor_contrato"] = valor_contrato
        if bp is not None:
            campos_actualizar["bp"] = bp
        if bpin is not None:
            campos_actualizar["bpin"] = bpin
        if valor_convenio is not None:
            campos_actualizar["valor_convenio"] = valor_convenio
        if urlproceso is not None:
            campos_actualizar["urlproceso"] = urlproceso
        if fecha_inicio_contrato is not None:
            campos_actualizar["fecha_inicio_contrato"] = fecha_inicio_contrato
        if fecha_fin_contrato is not None:
            campos_actualizar["fecha_fin_contrato"] = fecha_fin_contrato
        if modalidad_contrato is not None:
            campos_actualizar["modalidad_contrato"] = modalidad_contrato
        if ordenador_gastor is not None:
            campos_actualizar["ordenador_gastor"] = ordenador_gastor
        if tipo_contrato is not None:
            campos_actualizar["tipo_contrato"] = tipo_contrato
        if estado_contrato is not None:
            campos_actualizar["estado_contrato"] = estado_contrato
        if sector is not None:
            campos_actualizar["sector"] = sector
        if nombre_resumido_proceso is not None:
            campos_actualizar["nombre_resumido_proceso"] = nombre_resumido_proceso

        # Validar que se proporcionó al menos un campo para actualizar
        if not campos_actualizar:
            return JSONResponse(
                content={
                    "success": False,
                    "error": "Debe proporcionar al menos un campo para actualizar",
                    "message": "No se proporcionaron campos para modificar",
                    "timestamp": datetime.now().isoformat(),
                },
                status_code=400,
                headers={"Content-Type": "application/json; charset=utf-8"},
            )

        # Modificar convenio de transferencia
        resultado = await modificar_convenio_transferencia(doc_id, campos_actualizar)

        # Manejar respuesta según el resultado
        if not resultado.get("success"):
            status_code = 404 if "No se encontró" in resultado.get("error", "") else 400
            return JSONResponse(
                content={
                    "success": False,
                    "error": resultado.get("error"),
                    "doc_id": doc_id,
                    "message": "Error al modificar el convenio de transferencia",
                    "timestamp": datetime.now().isoformat(),
                },
                status_code=status_code,
                headers={"Content-Type": "application/json; charset=utf-8"},
            )

        # Respuesta exitosa
        return JSONResponse(
            content={
                "success": True,
                "message": resultado.get("message"),
                "doc_id": resultado.get("doc_id"),
                "campos_actualizados": resultado.get("campos_actualizados"),
                "data": resultado.get("data"),
                "coleccion": resultado.get("coleccion"),
                "timestamp": datetime.now().isoformat(),
            },
            status_code=200,
            headers={"Content-Type": "application/json; charset=utf-8"},
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Error en endpoint de modificación de convenio de transferencia: {e}"
        )
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": "Error interno del servidor",
                "message": "Por favor, inténtelo de nuevo más tarde",
                "code": "INTERNAL_SERVER_ERROR",
            },
        )


@router.post(
    "/emprestito/cargar-rpc",
    tags=["Gestión de Empréstito"],
    summary=" Cargar RPC de Empréstito",
)
async def cargar_rpc_emprestito_endpoint(
    numero_rpc: str = Form(..., description="Número del RPC (obligatorio)"),
    beneficiario_id: str = Form(..., description="ID del beneficiario (obligatorio)"),
    beneficiario_nombre: str = Form(
        ..., description="Nombre del beneficiario (obligatorio)"
    ),
    descripcion_rpc: str = Form(..., description="Descripción del RPC (obligatorio)"),
    fecha_contabilizacion: str = Form(
        ..., description="Fecha de contabilización (obligatorio)"
    ),
    fecha_impresion: str = Form(..., description="Fecha de impresión (obligatorio)"),
    estado_liberacion: str = Form(
        ..., description="Estado de liberación (obligatorio)"
    ),
    valor_rpc: float = Form(..., description="Valor del RPC (obligatorio)"),
    nombre_centro_gestor: str = Form(
        ..., description="Centro gestor responsable (obligatorio)"
    ),
    referencia_contrato: str = Form(
        ..., description="Referencia del contrato (obligatorio)"
    ),
    cdp_asociados: Optional[str] = Form(
        None, description="CDPs asociados separados por comas o JSON array (opcional)"
    ),
    programacion_pac: Optional[str] = Form(
        None, description="Programación PAC en formato JSON (opcional)"
    ),
    documentos: List[UploadFile] = File(
        ...,
        description="Documentos del RPC (PDF, DOC, DOCX, XLS, XLSX, JPG, PNG) - OBLIGATORIO",
    ),
):
    """
    ##  POST |  Carga de Datos | Cargar RPC (Registro Presupuestal de Compromiso) de Empréstito

    Endpoint para carga directa de RPC de empréstito en la colección
    `rpc_contratos_emprestito` sin procesamiento de APIs externas.

    ### [OK] Funcionalidades principales:
    - **Carga directa**: Registra directamente en `rpc_contratos_emprestito`
    - **Validación de duplicados**: Verifica existencia previa usando `numero_rpc`
    - **Validación de campos**: Verifica que todos los campos obligatorios estén presentes
    - **Carga de documentos a S3**: Los documentos son OBLIGATORIOS y se suben a AWS S3
    - **Validación de tipos de archivo**: Valida formatos permitidos (PDF, DOC, DOCX, XLS, XLSX, JPG, PNG)
    - **Timestamps automáticos**: Agrega fecha de creación y actualización
    - **Programación PAC**: Soporte para objeto JSON con valores mensuales

    ###  Campos obligatorios:
    - `numero_rpc`: Número único del RPC
    - `beneficiario_id`: Identificación del beneficiario
    - `beneficiario_nombre`: Nombre completo del beneficiario
    - `descripcion_rpc`: Descripción del compromiso
    - `fecha_contabilizacion`: Fecha de contabilización del RPC
    - `fecha_impresion`: Fecha de impresión del documento
    - `estado_liberacion`: Estado de liberación del RPC
    - `valor_rpc`: Valor monetario del RPC
    - `nombre_centro_gestor`: Centro gestor responsable
    - `referencia_contrato`: Referencia del contrato asociado
    - `documentos`: Archivos del RPC (al menos 1 archivo requerido)

    ###  Nota importante sobre BP:
    El campo `bp` ya NO es requerido en este endpoint. El valor de `bp` se hereda automáticamente
    al consultar los RPCs desde las colecciones: `contratos_emprestito`, `convenios_transferencias_emprestito`
    o `ordenes_compra_emprestito` usando la `referencia_contrato`.

    ###  Campos opcionales:
    - `cdp_asociados`: Lista de CDPs (Certificados de Disponibilidad Presupuestal) asociados
      - Puede enviarse como: `"CDP-001,CDP-002,CDP-003"` (separados por comas)
      - O como JSON array: `["CDP-001", "CDP-002", "CDP-003"]`
      - Si se deja vacío, se guardará como lista vacía `[]`
    - `programacion_pac`: Objeto JSON con programación mensual del PAC (Plan Anual de Caja)
      - Formato: `{"enero-2024": "1000000", "febrero-2024": "500000"}`
      - **IMPORTANTE**: Debe ser un objeto JSON válido si se proporciona
      - Si no es JSON válido, se ignorará y se guardará como objeto vacío `{}`

    ###  Validación de duplicados:
    Busca `numero_rpc` en la colección `rpc_contratos_emprestito` antes de crear nuevo registro.

    ###  Estructura de datos guardados:
    ```json
    {
        "numero_rpc": "RPC-2024-001",
        "beneficiario_id": "890123456",
        "beneficiario_nombre": "Proveedor XYZ S.A.S.",
        "descripcion_rpc": "Suministro de equipos médicos",
        "fecha_contabilizacion": "2024-10-15",
        "fecha_impresion": "2024-10-16",
        "estado_liberacion": "Liberado",
        "valor_rpc": 50000000.0,
        "cdp_asociados": ["CDP-2024-100", "CDP-2024-101", "CDP-2024-102"],
        "programacion_pac": {
            "enero-2024": "10000000",
            "febrero-2024": "20000000",
            "marzo-2024": "20000000"
        },
        "nombre_centro_gestor": "Secretaría de Salud",
        "referencia_contrato": "CONT-SALUD-003-2024",
        "fecha_creacion": "2024-10-14T10:30:00",
        "fecha_actualizacion": "2024-10-14T10:30:00",
        "estado": "activo",
        "tipo": "rpc_manual"
    }
    ```

    ###  Ejemplo de request:
    ```json
    {
        "numero_rpc": "RPC-SALUD-003-2024",
        "beneficiario_id": "890123456",
        "beneficiario_nombre": "Proveedor XYZ S.A.S.",
        "descripcion_rpc": "Suministro de equipos médicos",
        "fecha_contabilizacion": "2024-10-15",
        "fecha_impresion": "2024-10-16",
        "estado_liberacion": "Liberado",
        "valor_rpc": 50000000.0,
        "nombre_centro_gestor": "Secretaría de Salud",
        "referencia_contrato": "CONT-SALUD-003-2024",
        "cdp_asociados": "CDP-2024-100",
        "programacion_pac": "{\\"enero-2024\\": \\"10000000\\", \\"febrero-2024\\": \\"20000000\\"}"
    }
    ```

    ### [OK] Respuesta exitosa (201):
    ```json
    {
        "success": true,
        "message": "RPC RPC-SALUD-003-2024 guardado exitosamente",
        "doc_id": "abc123def456",
        "data": { ... },
        "coleccion": "rpc_contratos_emprestito"
    }
    ```

    ### [ERROR] Respuesta de duplicado (409):
    ```json
    {
        "success": false,
        "error": "Ya existe un RPC con número: RPC-SALUD-003-2024",
        "duplicate": true,
        "existing_data": { ... }
    }
    ```
    """
    try:
        check_emprestito_availability()

        logger.info(f" Recibiendo RPC: {numero_rpc}")
        logger.info(f" Documentos recibidos: {len(documentos)}")

        # Validar que se hayan proporcionado documentos
        if not documentos or len(documentos) == 0:
            return JSONResponse(
                content={
                    "success": False,
                    "error": "Se requiere al menos un documento para cargar el RPC",
                    "message": "Debe proporcionar al menos un archivo PDF, DOC, DOCX, XLS, XLSX, JPG o PNG",
                    "timestamp": datetime.now().isoformat(),
                },
                status_code=400,
                headers={"Content-Type": "application/json; charset=utf-8"},
            )

        # Validar tipos de archivo permitidos
        allowed_extensions = [
            ".pdf",
            ".doc",
            ".docx",
            ".xls",
            ".xlsx",
            ".jpg",
            ".jpeg",
            ".png",
        ]
        for doc in documentos:
            filename_lower = doc.filename.lower()
            if not any(filename_lower.endswith(ext) for ext in allowed_extensions):
                return JSONResponse(
                    content={
                        "success": False,
                        "error": f"Tipo de archivo no permitido: {doc.filename}",
                        "message": "Solo se permiten archivos PDF, DOC, DOCX, XLS, XLSX, JPG y PNG",
                        "allowed_types": allowed_extensions,
                        "timestamp": datetime.now().isoformat(),
                    },
                    status_code=400,
                    headers={"Content-Type": "application/json; charset=utf-8"},
                )
            logger.info(f"   - {doc.filename} ({doc.content_type})")

        # Procesar cdp_asociados: puede venir como string separado por comas o como JSON array
        cdp_asociados_processed = None
        if cdp_asociados and cdp_asociados.strip():
            # Si parece JSON array, intentar parsear
            if cdp_asociados.strip().startswith("["):
                try:
                    cdp_parsed = json.loads(cdp_asociados)
                    if isinstance(cdp_parsed, list):
                        cdp_asociados_processed = cdp_parsed
                    else:
                        # Si no es lista, usar como string
                        cdp_asociados_processed = cdp_asociados
                except json.JSONDecodeError:
                    # Si falla el parseo, usar como string
                    cdp_asociados_processed = cdp_asociados
            else:
                # Si no parece JSON, asumir que es string separado por comas o simple
                cdp_asociados_processed = cdp_asociados

        # Procesar programacion_pac si viene como string JSON
        programacion_pac_dict = {}
        if programacion_pac and programacion_pac.strip():
            # Solo intentar parsear si parece ser JSON (empieza con { o [)
            if programacion_pac.strip().startswith(
                "{"
            ) or programacion_pac.strip().startswith("["):
                try:
                    programacion_pac_dict = json.loads(programacion_pac)
                    if not isinstance(programacion_pac_dict, dict):
                        return JSONResponse(
                            content={
                                "success": False,
                                "error": "programacion_pac debe ser un objeto JSON (diccionario)",
                                "message": 'El formato de programacion_pac debe ser un objeto JSON como {"enero-2024": "1000000"}',
                                "timestamp": datetime.now().isoformat(),
                            },
                            status_code=400,
                            headers={"Content-Type": "application/json; charset=utf-8"},
                        )
                except json.JSONDecodeError as e:
                    return JSONResponse(
                        content={
                            "success": False,
                            "error": f"programacion_pac tiene formato JSON inválido: {str(e)}",
                            "message": 'El formato de programacion_pac no es un JSON válido. Debe ser un objeto como {"enero-2024": "1000000"}',
                            "timestamp": datetime.now().isoformat(),
                        },
                        status_code=400,
                        headers={"Content-Type": "application/json; charset=utf-8"},
                    )
            else:
                # Si no parece JSON, ignorar el campo con un warning
                logger.warning(
                    f"programacion_pac no parece ser JSON, ignorando valor: {programacion_pac[:50]}"
                )
                programacion_pac_dict = {}

        # Procesar documentos si se proporcionan
        documentos_procesados = []
        if documentos:
            for doc in documentos:
                # Leer contenido del archivo
                contenido = await doc.read()
                documentos_procesados.append(
                    {
                        "content": contenido,
                        "filename": doc.filename,
                        "content_type": doc.content_type,
                        "size": len(contenido),
                    }
                )
            logger.info(
                f" Procesando {len(documentos_procesados)} documentos para RPC {numero_rpc}"
            )

        # Crear diccionario con los datos del formulario
        datos_rpc = {
            "numero_rpc": numero_rpc,
            "beneficiario_id": beneficiario_id,
            "beneficiario_nombre": beneficiario_nombre,
            "descripcion_rpc": descripcion_rpc,
            "fecha_contabilizacion": fecha_contabilizacion,
            "fecha_impresion": fecha_impresion,
            "estado_liberacion": estado_liberacion,
            "valor_rpc": valor_rpc,
            "cdp_asociados": cdp_asociados_processed,
            "programacion_pac": programacion_pac_dict,
            "nombre_centro_gestor": nombre_centro_gestor,
            "referencia_contrato": referencia_contrato,
        }

        # Procesar RPC (función síncrona) con documentos
        logger.info(
            f" Procesando RPC {numero_rpc} con {len(documentos_procesados)} documentos"
        )
        resultado = cargar_rpc_emprestito(
            datos_rpc,
            documentos=documentos_procesados if documentos_procesados else None,
        )

        # Log del resultado
        if resultado.get("success"):
            logger.info(f"[OK] RPC {numero_rpc} procesado exitosamente")
        else:
            logger.error(
                f"[ERROR] Error procesando RPC {numero_rpc}: {resultado.get('error')}"
            )

        # Manejar respuesta según el resultado
        if not resultado.get("success"):
            # Manejar caso especial de duplicado
            if resultado.get("duplicate"):
                return JSONResponse(
                    content={
                        "success": False,
                        "error": resultado.get("error"),
                        "duplicate": True,
                        "existing_data": resultado.get("existing_data"),
                        "message": "Ya existe un RPC con este número",
                        "timestamp": datetime.now().isoformat(),
                    },
                    status_code=409,  # Conflict
                    headers={"Content-Type": "application/json; charset=utf-8"},
                )
            else:
                # Error general
                return JSONResponse(
                    content={
                        "success": False,
                        "error": resultado.get("error"),
                        "message": "Error al procesar el RPC",
                        "timestamp": datetime.now().isoformat(),
                    },
                    status_code=400,
                    headers={"Content-Type": "application/json; charset=utf-8"},
                )

        # Respuesta exitosa
        # Extraer URLs de documentos del resultado
        documentos_urls = []
        if resultado.get("data") and resultado.get("data").get("documentos_s3"):
            documentos_urls = [
                doc.get("url")
                for doc in resultado.get("data").get("documentos_s3")
                if doc.get("url")
            ]

        return JSONResponse(
            content={
                "success": True,
                "message": resultado.get("message"),
                "data": {
                    "numero_rpc": numero_rpc,
                    "doc_id": resultado.get("doc_id"),
                    "documentos_urls": documentos_urls,
                    "total_documentos": resultado.get("documentos_count", 0),
                    "detalles_completos": resultado.get("data"),
                },
                "coleccion": resultado.get("coleccion"),
                "timestamp": datetime.now().isoformat(),
            },
            status_code=201,
            headers={"Content-Type": "application/json; charset=utf-8"},
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error en endpoint de RPC: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": "Error interno del servidor",
                "message": "Por favor, inténtelo de nuevo más tarde",
                "code": "INTERNAL_SERVER_ERROR",
            },
        )


@router.post(
    "/emprestito/cargar-pago",
    tags=["Gestión de Empréstito"],
    summary=" Cargar Pago de Empréstito",
)
async def cargar_pago_emprestito_endpoint(
    numero_rpc: str = Form(..., description="Número del RPC (obligatorio)"),
    valor_pago: float = Form(
        ..., description="Valor del pago (obligatorio, debe ser mayor a 0)"
    ),
    fecha_transaccion: str = Form(
        ..., description="Fecha de la transacción (obligatorio)"
    ),
    referencia_contrato: str = Form(
        ..., description="Referencia del contrato (obligatorio)"
    ),
    nombre_centro_gestor: str = Form(
        ..., description="Centro gestor responsable (obligatorio)"
    ),
    documentos: List[UploadFile] = File(
        None,
        description="Documentos del pago (PDF, DOC, DOCX, XLS, XLSX, JPG, PNG) - OPCIONAL",
    ),
):
    """
    ##  POST |  Carga de Datos | Cargar Pago de Empréstito

    Endpoint para registrar un pago de empréstito en la colección `pagos_emprestito`.
    El campo `fecha_registro` se genera automáticamente con la hora actual del sistema como timestamp.

    ### [OK] Funcionalidades principales:
    - **Registro de pagos**: Guarda información de pagos realizados
    - **Carga de documentos a S3**: Los documentos son OPCIONALES y se suben a AWS S3 si se proporcionan
    - **Validación de tipos de archivo**: Valida formatos permitidos (PDF, DOC, DOCX, XLS, XLSX, JPG, PNG)
    - **Timestamp automático**: `fecha_registro` se genera automáticamente con la hora del sistema
    - **Validación de campos**: Verifica que todos los campos obligatorios estén presentes
    - **Validación de valores**: Verifica que el valor del pago sea positivo
    - **Trazabilidad**: Registra fecha de creación y actualización

    ###  Campos obligatorios:
    - `numero_rpc`: Número del RPC asociado al pago
    - `valor_pago`: Valor monetario del pago (debe ser mayor a 0)
    - `fecha_transaccion`: Fecha en que se realizó la transacción
    - `referencia_contrato`: Referencia del contrato asociado
    - `nombre_centro_gestor`: Centro gestor responsable del pago

    ###  Campos opcionales:
    - `documentos`: Archivos del pago (PDF, DOC, DOCX, XLS, XLSX, JPG, PNG)

    ###  Campos automáticos:
    - `fecha_registro`: Timestamp automático del momento de registro (NO se envía por el usuario)
    - `fecha_creacion`: Timestamp de creación del registro
    - `fecha_actualizacion`: Timestamp de última actualización
    - `estado`: "registrado" (valor por defecto)
    - `tipo`: "pago_manual" (valor por defecto)

    ###  Estructura de datos guardados:
    ```json
    {
        "numero_rpc": "RPC-2024-001",
        "valor_pago": 10000000.0,
        "fecha_transaccion": "2024-11-11",
        "referencia_contrato": "CONT-SALUD-003-2024",
        "nombre_centro_gestor": "Secretaría de Salud",
        "fecha_registro": "2024-11-11T14:30:45.123456",
        "fecha_creacion": "2024-11-11T14:30:45.123456",
        "fecha_actualizacion": "2024-11-11T14:30:45.123456",
        "estado": "registrado",
        "tipo": "pago_manual"
    }
    ```

    ###  Ejemplo de request:
    ```json
    {
        "numero_rpc": "RPC-SALUD-003-2024",
        "valor_pago": 10000000.0,
        "fecha_transaccion": "2024-11-11",
        "referencia_contrato": "CONT-SALUD-003-2024",
        "nombre_centro_gestor": "Secretaría de Salud"
    }
    ```

    ### [OK] Respuesta exitosa (201):
    ```json
    {
        "success": true,
        "message": "Pago registrado exitosamente para RPC RPC-SALUD-003-2024",
        "data": { ... },
        "doc_id": "abc123def456",
        "coleccion": "pagos_emprestito",
        "timestamp": "2024-11-11T14:30:45.123456"
    }
    ```

    ### [ERROR] Respuesta de error (400):
    ```json
    {
        "success": false,
        "error": "El campo 'numero_rpc' es obligatorio",
        "message": "Error al procesar el pago",
        "timestamp": "2024-11-11T14:30:45.123456"
    }
    ```

    ###  Notas importantes:
    - El campo `fecha_registro` NO debe ser enviado por el usuario
    - Se genera automáticamente con la hora exacta del servidor
    - El `valor_pago` debe ser un número positivo mayor a 0
    - Todos los campos de texto se limpian de espacios en blanco
    """
    try:
        check_emprestito_availability()

        logger.info(f" Recibiendo pago para RPC: {numero_rpc}")
        logger.info(f" Documentos recibidos: {len(documentos) if documentos else 0}")
        logger.info(f" Valor del pago: {valor_pago}")

        # Validar tipos de archivo permitidos solo si se proporcionaron documentos
        allowed_extensions = [
            ".pdf",
            ".doc",
            ".docx",
            ".xls",
            ".xlsx",
            ".jpg",
            ".jpeg",
            ".png",
        ]
        if documentos:
            for doc in documentos:
                filename_lower = doc.filename.lower()
                if not any(filename_lower.endswith(ext) for ext in allowed_extensions):
                    return JSONResponse(
                        content={
                            "success": False,
                            "error": f"Tipo de archivo no permitido: {doc.filename}",
                            "message": "Solo se permiten archivos PDF, DOC, DOCX, XLS, XLSX, JPG y PNG",
                            "allowed_types": allowed_extensions,
                            "timestamp": datetime.now().isoformat(),
                        },
                        status_code=400,
                        headers={"Content-Type": "application/json; charset=utf-8"},
                    )
                logger.info(f"   - {doc.filename} ({doc.content_type})")

        # Procesar documentos si se proporcionan
        documentos_procesados = []
        if documentos:
            for doc in documentos:
                # Leer contenido del archivo
                contenido = await doc.read()
                documentos_procesados.append(
                    {
                        "content": contenido,
                        "filename": doc.filename,
                        "content_type": doc.content_type,
                        "size": len(contenido),
                    }
                )
            logger.info(
                f" Procesando {len(documentos_procesados)} documentos para pago de RPC {numero_rpc}"
            )

        # Preparar datos para procesar
        datos_pago = {
            "numero_rpc": numero_rpc,
            "valor_pago": valor_pago,
            "fecha_transaccion": fecha_transaccion,
            "referencia_contrato": referencia_contrato,
            "nombre_centro_gestor": nombre_centro_gestor,
        }

        # Procesar pago (función síncrona) con documentos
        logger.info(
            f" Procesando pago para RPC {numero_rpc} con {len(documentos_procesados)} documentos"
        )
        resultado = cargar_pago_emprestito(
            datos_pago,
            documentos=documentos_procesados if documentos_procesados else None,
        )

        # Log del resultado
        if resultado.get("success"):
            logger.info(f"[OK] Pago para RPC {numero_rpc} procesado exitosamente")
        else:
            logger.error(
                f"[ERROR] Error procesando pago para RPC {numero_rpc}: {resultado.get('error')}"
            )

        # Manejar respuesta según el resultado
        if not resultado.get("success"):
            return JSONResponse(
                content={
                    "success": False,
                    "error": resultado.get("error"),
                    "message": "Error al procesar el pago",
                    "timestamp": datetime.now().isoformat(),
                },
                status_code=400,
                headers={"Content-Type": "application/json; charset=utf-8"},
            )

        # Respuesta exitosa
        # Extraer URLs de documentos del resultado
        documentos_urls = []
        if resultado.get("data") and resultado.get("data").get("documentos_s3"):
            documentos_urls = [
                doc.get("url")
                for doc in resultado.get("data").get("documentos_s3")
                if doc.get("url")
            ]

        return JSONResponse(
            content={
                "success": True,
                "message": resultado.get("message"),
                "data": {
                    "numero_rpc": numero_rpc,
                    "doc_id": resultado.get("doc_id"),
                    "valor_pago": valor_pago,
                    "documentos_urls": documentos_urls,
                    "total_documentos": resultado.get("documentos_count", 0),
                    "detalles_completos": resultado.get("data"),
                },
                "coleccion": resultado.get("coleccion"),
                "timestamp": resultado.get("timestamp"),
            },
            status_code=201,
            headers={"Content-Type": "application/json; charset=utf-8"},
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error en endpoint de pago de empréstito: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": "Error interno del servidor",
                "message": "Por favor, inténtelo de nuevo más tarde",
                "code": "INTERNAL_SERVER_ERROR",
            },
        )


@router.get(
    "/contratos_pagos_all",
    tags=["Gestión de Empréstito"],
    summary=" Obtener Todos los Pagos",
)
async def get_all_pagos_emprestito():
    """
    ##  GET |  Consultas | Obtener Todos los Pagos de Empréstito

    Endpoint para obtener todos los pagos de empréstito registrados en la colección `pagos_emprestito`.

    ### [OK] Funcionalidades principales:
    - **Listado completo**: Retorna todos los pagos registrados
    - **Datos completos**: Incluye todos los campos de cada pago
    - **Detección de documentos soporte**: Verifica si cada pago tiene documentos en S3
    - **Metadatos**: Incluye ID del documento, conteo total y timestamp
    - **Serialización JSON**: Fechas y objetos datetime convertidos correctamente
    - **Trazabilidad**: Información completa de cada transacción registrada

    ###  Información incluida:
    - Todos los campos del pago
    - ID del documento para referencia
    - Campo `tiene_documentos_soporte`: indica si el pago tiene documentos en S3 (true/false)
    - Conteo total de registros
    - Timestamp de la consulta
    - Datos serializados correctamente para JSON

    ###  Campos principales esperados:
    - **numero_rpc**: Número del RPC asociado al pago
    - **valor_pago**: Valor monetario del pago realizado
    - **fecha_transaccion**: Fecha en que se realizó la transacción
    - **referencia_contrato**: Referencia del contrato asociado
    - **nombre_centro_gestor**: Centro gestor responsable
    - **fecha_registro**: Timestamp automático del momento del registro
    - **fecha_creacion**: Fecha de creación del registro
    - **fecha_actualizacion**: Última actualización del registro
    - **estado**: Estado del pago (registrado, procesado, etc.)
    - **tipo**: Tipo de registro (pago_manual)
    - **tiene_documentos_soporte**: Boolean que indica si el pago tiene documentos en S3
    - **documentos_s3**: Array con información de documentos en S3 (si existen)

    ###  Casos de uso:
    - Obtener historial completo de pagos de empréstito
    - Consulta de pagos para reportes financieros
    - Análisis de flujo de caja y ejecución presupuestal
    - Seguimiento de transacciones por RPC
    - Dashboard de pagos realizados
    - Exportación de datos para auditorías
    - Integración con sistemas contables
    - Reportes de ejecución por centro gestor

    ###  Análisis posibles:
    - Total de pagos realizados
    - Suma de valores pagados
    - Pagos por centro gestor
    - Pagos por contrato
    - Pagos por RPC
    - Histórico de transacciones

    ### [OK] Respuesta exitosa (200):
    ```json
    {
        "success": true,
        "data": [
            {
                "id": "xyz789",
                "numero_rpc": "RPC-2024-001",
                "valor_pago": 10000000.0,
                "fecha_transaccion": "2024-11-11",
                "referencia_contrato": "CONT-SALUD-003-2024",
                "nombre_centro_gestor": "Secretaría de Salud",
                "fecha_registro": "2024-11-11T14:30:45.123456",
                "fecha_creacion": "2024-11-11T14:30:45.123456",
                "fecha_actualizacion": "2024-11-11T14:30:45.123456",
                "estado": "registrado",
                "tipo": "pago_manual",
                "tiene_documentos_soporte": true,
                "documentos_s3": [
                    {
                        "filename": "pago_001.pdf",
                        "s3_url": "https://contratos-emprestito.s3.us-east-1.amazonaws.com/...",
                        "upload_date": "2024-11-11T14:30:45.123456"
                    }
                ]
            },
            {
                "id": "abc456",
                "numero_rpc": "RPC-2024-002",
                "valor_pago": 5000000.0,
                "fecha_transaccion": "2024-11-10",
                "referencia_contrato": "CONT-INFRA-001-2024",
                "nombre_centro_gestor": "Secretaría de Infraestructura",
                "fecha_registro": "2024-11-10T10:15:30.654321",
                "fecha_creacion": "2024-11-10T10:15:30.654321",
                "fecha_actualizacion": "2024-11-10T10:15:30.654321",
                "estado": "registrado",
                "tipo": "pago_manual",
                "tiene_documentos_soporte": false,
                "documentos_s3": []
            }
        ],
        "count": 15,
        "collection": "pagos_emprestito",
        "timestamp": "2024-11-11T15:00:00.000000",
        "message": "Se obtuvieron 15 pagos exitosamente"
    }
    ```

    ### [ERROR] Respuesta de error (500):
    ```json
    {
        "success": false,
        "error": "Error obteniendo pagos de empréstito: [detalles del error]",
        "data": [],
        "count": 0
    }
    ```

    ###  Notas:
    - Los campos de tipo datetime se serializan en formato ISO 8601
    - El campo `id` corresponde al ID del documento en Firestore
    - Los datos se retornan en el orden en que fueron insertados en Firestore
    - Para consultas filtradas, considere crear endpoints específicos adicionales
    """
    try:
        check_emprestito_availability()

        # Obtener todos los pagos
        resultado = await get_pagos_emprestito_all()

        if not resultado.get("success"):
            raise HTTPException(
                status_code=500,
                detail={
                    "success": False,
                    "error": resultado.get("error", "Error desconocido"),
                    "message": "Error al obtener los pagos de empréstito",
                },
            )

        # Respuesta exitosa
        return JSONResponse(
            content={
                "success": True,
                "data": resultado.get("data", []),
                "count": resultado.get("count", 0),
                "collection": resultado.get("collection", "pagos_emprestito"),
                "timestamp": resultado.get("timestamp"),
                "message": f"Se obtuvieron {resultado.get('count', 0)} pagos exitosamente",
            },
            status_code=200,
            headers={"Content-Type": "application/json; charset=utf-8"},
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error en endpoint de consulta de pagos: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": "Error interno del servidor",
                "message": "Por favor, inténtelo de nuevo más tarde",
                "code": "INTERNAL_SERVER_ERROR",
            },
        )


@router.get(
    "/rpc_all", tags=["Gestión de Empréstito"], summary=" Obtener Todos los RPCs"
)
async def get_all_rpc_contratos_emprestito():
    """
    ##  GET |  Consultas | Obtener Todos los RPCs de Empréstito

    Endpoint para obtener todos los RPC (Registros Presupuestales de Compromiso) de empréstito
    almacenados en la colección `rpc_contratos_emprestito`.

    ### [OK] Funcionalidades principales:
    - **Listado completo**: Retorna todos los RPCs registrados
    - **Datos completos**: Incluye todos los campos de cada RPC
    - **Metadatos**: Incluye ID del documento, conteo total y timestamp
    - **Serialización JSON**: Fechas y objetos convertidos correctamente

    ###  Información incluida:
    - Todos los campos del RPC
    - ID del documento para referencia
    - Conteo total de registros
    - Timestamp de la consulta
    - Datos serializados correctamente para JSON

    ###  Campos principales esperados:
    - **numero_rpc**: Número único del RPC
    - **beneficiario_id**: Identificación del beneficiario
    - **beneficiario_nombre**: Nombre del beneficiario
    - **descripcion_rpc**: Descripción del compromiso
    - **fecha_contabilizacion**: Fecha de contabilización
    - **fecha_impresion**: Fecha de impresión del documento
    - **estado_liberacion**: Estado de liberación del RPC
    - **bp**: Código BP (Banco de Programas)
    - **valor_rpc**: Valor monetario del RPC
    - **cdp_asociados**: Lista de CDPs asociados
    - **programacion_pac**: Objeto con programación mensual del PAC
    - **nombre_centro_gestor**: Centro gestor responsable
    - **referencia_contrato**: Referencia del contrato asociado
    - **fecha_creacion**: Fecha de creación del registro
    - **fecha_actualizacion**: Última actualización
    - **estado**: Estado del registro (activo/inactivo)
    - **tipo**: Tipo de registro (rpc_manual)

    ###  Casos de uso:
    - Obtener listado completo de RPCs de empréstito
    - Exportación de datos para análisis
    - Integración con sistemas externos
    - Reportes y dashboards de seguimiento presupuestal
    - Monitoreo de compromisos presupuestales
    - Análisis de ejecución presupuestal por contrato

    ### [OK] Respuesta exitosa (200):
    ```json
    {
        "success": true,
        "data": [
            {
                "id": "abc123",
                "numero_rpc": "RPC-2024-001",
                "beneficiario_id": "890123456",
                "beneficiario_nombre": "Proveedor XYZ S.A.S.",
                "descripcion_rpc": "Suministro de equipos médicos",
                "fecha_contabilizacion": "2024-10-15",
                "fecha_impresion": "2024-10-16",
                "estado_liberacion": "Liberado",
                "bp": "BP-2024-001",
                "valor_rpc": 50000000.0,
                "cdp_asociados": ["CDP-2024-100", "CDP-2024-101"],
                "programacion_pac": {
                    "enero-2024": "10000000",
                    "febrero-2024": "20000000"
                },
                "nombre_centro_gestor": "Secretaría de Salud",
                "referencia_contrato": "CONT-SALUD-003-2024",
                "fecha_creacion": "2024-10-14T10:30:00",
                "fecha_actualizacion": "2024-10-14T10:30:00",
                "estado": "activo",
                "tipo": "rpc_manual"
            }
        ],
        "count": 25,
        "collection": "rpc_contratos_emprestito",
        "timestamp": "2024-11-11T...",
        "message": "Se obtuvieron 25 RPCs exitosamente"
    }
    ```

    ### [ERROR] Respuesta de error (500):
    ```json
    {
        "success": false,
        "error": "Error obteniendo RPCs: ...",
        "data": [],
        "count": 0
    }
    ```

    ###  Endpoints relacionados:
    - `POST /emprestito/cargar-rpc` - Para crear nuevos RPCs
    - `GET /convenios_transferencias_all` - Para consultar convenios de transferencia
    """
    try:
        check_emprestito_availability()

        # Obtener todos los RPCs
        result = await get_rpc_contratos_emprestito_all()

        if not result["success"]:
            raise HTTPException(
                status_code=500,
                detail=f"Error obteniendo RPCs: {result.get('error', 'Error desconocido')}",
            )

        # Enriquecer cada RPC con enlaces de descarga y visualización de documentos S3
        data_enriquecida = result["data"]
        total_documentos_enriquecidos = 0

        if _s3_presigned_enabled():
            try:
                presigned_expiration = _s3_presigned_expiration()

                for rpc in data_enriquecida:
                    documentos_s3 = rpc.get("documentos_s3", [])

                    if not documentos_s3 or not isinstance(documentos_s3, list):
                        rpc["documentos_con_enlaces"] = []
                        rpc["total_documentos"] = 0
                        continue

                    documentos_con_enlaces = []

                    for doc in documentos_s3:
                        if not isinstance(doc, dict):
                            continue

                        s3_url = doc.get("s3_url") or doc.get("url") or ""
                        s3_key = doc.get("s3_key") or doc.get("key") or ""

                        # Extraer bucket y key desde la URL si no tenemos s3_key
                        bucket, key_from_url = None, None
                        if s3_url:
                            bucket, key_from_url = _extract_s3_bucket_key_from_url(
                                s3_url
                            )

                        resolved_key = s3_key or key_from_url or ""
                        resolved_bucket = bucket or ""

                        presigned_url = None
                        if resolved_bucket and resolved_key:
                            presigned_url = _generate_presigned_s3_url(
                                resolved_bucket, resolved_key
                            )

                        filename = doc.get("filename") or (
                            resolved_key.split("/")[-1] if resolved_key else ""
                        )

                        documento_enriquecido = {
                            "filename": filename,
                            "s3_key": resolved_key,
                            "s3_url": s3_url,
                            "content_type": doc.get("content_type", "application/pdf"),
                            "size": doc.get("size", 0),
                            "upload_date": doc.get("upload_date", ""),
                            "url_descarga": presigned_url,
                            "url_visualizar": presigned_url,
                            "url_presigned": presigned_url,
                            "url_expiration_seconds": (
                                presigned_expiration if presigned_url else None
                            ),
                        }
                        documentos_con_enlaces.append(documento_enriquecido)

                        if presigned_url:
                            total_documentos_enriquecidos += 1

                    rpc["documentos_con_enlaces"] = documentos_con_enlaces
                    rpc["total_documentos"] = len(documentos_con_enlaces)

                logger.info(
                    f"[OK] URLs de descarga/visualización generadas para {total_documentos_enriquecidos} documentos en {len(data_enriquecida)} RPCs"
                )
            except Exception as e:
                logger.warning(
                    f"[WARNING] No se pudieron generar URLs presigned para documentos: {e}"
                )

        return JSONResponse(
            content={
                "success": True,
                "data": data_enriquecida,
                "count": result["count"],
                "collection": result["collection"],
                "timestamp": result["timestamp"],
                "documentos_enriquecidos": total_documentos_enriquecidos,
                "s3_presigned_enabled": _s3_presigned_enabled(),
                "message": f"Se obtuvieron {result['count']} RPCs exitosamente con enlaces de documentos",
            },
            status_code=200,
            headers={"Content-Type": "application/json; charset=utf-8"},
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error en endpoint de RPCs: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": "Error interno del servidor",
                "message": "Por favor, inténtelo de nuevo más tarde",
                "code": "INTERNAL_SERVER_ERROR",
            },
        )


@router.get(
    "/rpc_documentos_temporales",
    tags=["Gestión de Empréstito"],
    summary=" Obtener Enlaces Temporales de Documentos de RPC",
)
async def get_rpc_documentos_temporales(numero_rpc: str, expiration: int = 3600):
    """
    ##  GET |  Documentos | Obtener Enlaces Temporales de Documentos de RPC

    Endpoint para generar enlaces temporales (presigned URLs) para visualizar y descargar
    los documentos PDF asociados a un RPC específico almacenados en S3.

    ### [OK] Funcionalidades principales:
    - **Enlaces bajo demanda**: Genera URLs solo cuando se solicitan
    - **URLs temporales**: Enlaces seguros con tiempo de expiración configurable
    - **Acceso directo**: URLs listas para visualizar o descargar en el frontend
    - **Seguridad**: Enlaces con expiración automática (por defecto 1 hora)

    ###  Parámetros:
    - **numero_rpc** (requerido): Número del RPC para buscar sus documentos
    - **expiration** (opcional): Tiempo de expiración en segundos (default: 3600 = 1 hora)

    ###  Información retornada:
    - Lista de documentos del RPC
    - URL temporal para cada documento
    - Información del archivo (nombre, tamaño, fecha)
    - Tiempo de expiración de cada URL

    ###  Casos de uso:
    - Visualizar documentos de RPC en el frontend
    - Descargar documentos de soporte
    - Validar documentación de compromisos presupuestales
    - Auditoría de documentos

    ### [OK] Respuesta exitosa (200):
    ```json
    {
        "success": true,
        "numero_rpc": "RPC-2024-001",
        "referencia_contrato": "CONT-SALUD-003-2024",
        "documentos": [
            {
                "filename": "documento_rpc.pdf",
                "s3_key": "contratos-rpc-docs/CONT-SALUD-003-2024/documento_rpc.pdf",
                "presigned_url": "https://contratos-emprestito.s3.amazonaws.com/...",
                "size": 1048576,
                "last_modified": "2024-12-20T10:30:00",
                "url_expiration_seconds": 3600,
                "url_expires_at": "2024-12-20T11:30:00"
            }
        ],
        "count": 1,
        "message": "Se generaron 1 enlace(s) temporal(es) exitosamente"
    }
    ```

    ### [ERROR] Respuesta de error (404):
    ```json
    {
        "success": false,
        "error": "No se encontró el RPC especificado",
        "numero_rpc": "RPC-XXX"
    }
    ```

    ### [ERROR] Respuesta de error (500):
    ```json
    {
        "success": false,
        "error": "Error generando enlaces temporales: ..."
    }
    ```

    ###  Endpoints relacionados:
    - `GET /rpc_all` - Para listar todos los RPCs
    - `POST /emprestito/cargar-rpc` - Para crear nuevos RPCs con documentos
    """
    try:
        check_emprestito_availability()

        # Importar S3DocumentManager
        try:
            from api.utils.s3_document_manager import S3DocumentManager
        except ImportError:
            raise HTTPException(
                status_code=500,
                detail={
                    "success": False,
                    "error": "Servicio de almacenamiento S3 no disponible",
                    "message": "No es posible generar enlaces temporales en este momento",
                },
            )

        # Validar que se proporcionó numero_rpc
        if not numero_rpc or not numero_rpc.strip():
            raise HTTPException(
                status_code=400,
                detail={
                    "success": False,
                    "error": "El parámetro 'numero_rpc' es requerido",
                },
            )

        numero_rpc = numero_rpc.strip()

        # Buscar el RPC en Firebase para obtener la referencia_contrato
        db_client = get_firestore_client()
        if not db_client:
            raise HTTPException(
                status_code=500,
                detail={
                    "success": False,
                    "error": "Error conectando con la base de datos",
                },
            )

        # Buscar RPC por numero_rpc
        rpc_ref = db_client.collection("rpc_contratos_emprestito")
        query = rpc_ref.where("numero_rpc", "==", numero_rpc).limit(1)
        docs = list(query.stream())

        if not docs:
            raise HTTPException(
                status_code=404,
                detail={
                    "success": False,
                    "error": f"No se encontró el RPC con número: {numero_rpc}",
                    "numero_rpc": numero_rpc,
                },
            )

        rpc_data = docs[0].to_dict()
        referencia_contrato = rpc_data.get("referencia_contrato", "")

        if not referencia_contrato:
            raise HTTPException(
                status_code=500,
                detail={
                    "success": False,
                    "error": "El RPC no tiene referencia de contrato asociada",
                    "numero_rpc": numero_rpc,
                },
            )

        # Inicializar S3DocumentManager y generar URLs temporales
        try:
            s3_manager = S3DocumentManager()

            # Obtener documentos desde el campo documentos_s3 en Firebase
            documentos_firebase = rpc_data.get("documentos_s3", [])
            documentos_resultado = []

            if (
                documentos_firebase
                and isinstance(documentos_firebase, list)
                and len(documentos_firebase) > 0
            ):
                logger.info(
                    f"[OK] Encontrados {len(documentos_firebase)} documentos en Firebase para RPC {numero_rpc}"
                )

                # Generar presigned URLs para cada documento guardado en Firebase
                from datetime import timedelta

                for doc in documentos_firebase:
                    if isinstance(doc, dict):
                        # Buscar s3_key en diferentes variantes posibles
                        s3_key = (
                            doc.get("s3_key")
                            or doc.get("key")
                            or doc.get("s3_url", "").replace(
                                f"https://{s3_manager.bucket_name}.s3.{s3_manager.region}.amazonaws.com/",
                                "",
                            )
                        )

                        if s3_key:
                            # Generar presigned URL
                            presigned_url = s3_manager.generate_presigned_url(
                                s3_key, expiration=expiration
                            )

                            # Calcular tiempo de expiración
                            expiration_time = datetime.now() + timedelta(
                                seconds=expiration
                            )

                            documento_con_url = {
                                "filename": doc.get("filename", s3_key.split("/")[-1]),
                                "s3_key": s3_key,
                                "s3_url": doc.get(
                                    "s3_url",
                                    f"https://{s3_manager.bucket_name}.s3.{s3_manager.region}.amazonaws.com/{s3_key}",
                                ),
                                "size": doc.get("size", 0),
                                "content_type": doc.get(
                                    "content_type", "application/pdf"
                                ),
                                "upload_date": doc.get("upload_date", ""),
                                "presigned_url": presigned_url,
                                "url_expiration_seconds": expiration,
                                "url_expires_at": expiration_time.isoformat(),
                            }

                            documentos_resultado.append(documento_con_url)
                            logger.info(
                                f"[OK] URL temporal generada para: {documento_con_url['filename']}"
                            )
                        else:
                            logger.warning(
                                f"[WARNING]  Documento sin s3_key válido: {doc}"
                            )

                if len(documentos_resultado) == 0:
                    logger.warning(
                        f"[WARNING]  Documentos encontrados en Firebase pero ninguno con s3_key válido"
                    )
            else:
                # Si no hay documentos en Firebase, buscar directamente en S3
                logger.info(
                    f" No hay documentos en Firebase, buscando directamente en S3 para referencia: {referencia_contrato}"
                )
                documentos_resultado = s3_manager.list_documents_with_presigned_urls(
                    referencia_contrato=referencia_contrato,
                    document_type="rpc",
                    numero_rpc=None,
                    expiration=expiration,
                )

            return JSONResponse(
                content={
                    "success": True,
                    "numero_rpc": numero_rpc,
                    "referencia_contrato": referencia_contrato,
                    "documentos": documentos_resultado,
                    "count": len(documentos_resultado),
                    "expiration_seconds": expiration,
                    "message": f"Se generaron {len(documentos_resultado)} enlace(s) temporal(es) exitosamente",
                },
                status_code=200,
                headers={"Content-Type": "application/json; charset=utf-8"},
            )

        except Exception as e:
            logger.error(f"Error generando URLs temporales: {e}")
            raise HTTPException(
                status_code=500,
                detail={
                    "success": False,
                    "error": f"Error generando enlaces temporales: {str(e)}",
                },
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error en endpoint de documentos temporales: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": "Error interno del servidor",
                "message": str(e),
            },
        )


@router.get(
    "/convenios_transferencias_all",
    tags=["Gestión de Empréstito"],
    summary=" Obtener Todos los Convenios de Transferencia",
)
async def get_all_convenios_transferencia_emprestito():
    """
    ##  GET |  Consultas | Obtener Todos los Convenios de Transferencia

    Endpoint para obtener todos los convenios de transferencia de empréstito
    almacenados en la colección `convenios_transferencias_emprestito`.

    ### [OK] Funcionalidades principales:
    - **Listado completo**: Retorna todos los convenios registrados
    - **Ordenamiento**: Por fecha de creación (más recientes primero)
    - **Datos completos**: Incluye todos los campos de cada convenio
    - **Metadatos**: Incluye ID del documento, conteo total y timestamp

    ###  Información incluida:
    - Todos los campos del convenio
    - ID del documento para referencia
    - Conteo total de registros
    - Timestamp de la consulta
    - Datos serializados correctamente para JSON

    ###  Campos principales esperados:
    - **referencia_contrato**: Referencia única del contrato/convenio
    - **nombre_centro_gestor**: Centro gestor responsable
    - **banco**: Nombre del banco
    - **bp**: Código BP
    - **bpin**: Código BPIN
    - **objeto_contrato**: Descripción del objeto del contrato
    - **valor_contrato**: Valor del contrato
    - **valor_convenio**: Valor específico del convenio
    - **fecha_inicio_contrato**: Fecha de inicio
    - **fecha_fin_contrato**: Fecha de finalización
    - **modalidad_contrato**: Modalidad de contratación
    - **ordenador_gastor**: Ordenador del gasto
    - **tipo_contrato**: Tipo de contrato
    - **estado_contrato**: Estado actual
    - **sector**: Sector al que pertenece
    - **nombre_resumido_proceso**: Nombre resumido del proceso
    - **fecha_creacion**: Fecha de creación del registro
    - **fecha_actualizacion**: Última actualización
    - **estado**: Estado del registro (activo/inactivo)
    - **tipo**: Tipo de registro

    ###  Casos de uso:
    - Obtener listado completo de convenios de transferencia
    - Exportación de datos para análisis
    - Integración con sistemas externos
    - Reportes y dashboards
    - Monitoreo del estado de convenios

    ### [OK] Respuesta exitosa (200):
    ```json
    {
        "success": true,
        "data": [
            {
                "id": "abc123",
                "referencia_contrato": "CONV-2024-001",
                "nombre_centro_gestor": "Secretaría de Salud",
                "banco": "Banco Mundial",
                "objeto_contrato": "Convenio de transferencia...",
                "valor_contrato": 1500000000.0,
                "bpin": "2024000010001",
                ...
            }
        ],
        "count": 15,
        "collection": "convenios_transferencias_emprestito",
        "timestamp": "2024-11-09T...",
        "message": "Se obtuvieron 15 convenios de transferencia exitosamente"
    }
    ```

    ### [ERROR] Respuesta de error (500):
    ```json
    {
        "success": false,
        "error": "Error obteniendo convenios de transferencia: ...",
        "data": [],
        "count": 0
    }
    ```

    ###  Endpoints relacionados:
    - `POST /emprestito/cargar-convenio-transferencia` - Para crear nuevos convenios
    """
    try:
        check_emprestito_availability()

        # Obtener todos los convenios de transferencia
        result = await get_convenios_transferencia_emprestito_all()

        if not result["success"]:
            raise HTTPException(
                status_code=500,
                detail=f"Error obteniendo convenios de transferencia: {result.get('error', 'Error desconocido')}",
            )

        return JSONResponse(
            content={
                "success": True,
                "data": result["data"],
                "count": result["count"],
                "collection": result["collection"],
                "timestamp": result["timestamp"],
                "message": result["message"],
                "metadata": {
                    "sorted_by": "fecha_creacion",
                    "order": "desc",
                    "utf8_enabled": True,
                    "spanish_support": True,
                    "purpose": "Lista completa de convenios de transferencia de empréstito",
                },
            },
            status_code=200,
            headers={"Content-Type": "application/json; charset=utf-8"},
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error en endpoint de convenios de transferencia: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": "Error interno del servidor",
                "message": "Error al obtener convenios de transferencia",
                "code": "INTERNAL_SERVER_ERROR",
            },
        )


@router.get(
    "/pagos_emprestito_all",
    tags=["Gestión de Empréstito"],
    summary=" Obtener Todos los Pagos de Empréstito",
)
async def get_all_pagos_emprestito():
    """
    ##  GET |  Consultas | Obtener Todos los Pagos de Empréstito

    Endpoint para obtener todos los pagos de empréstito almacenados en la colección `pagos_emprestito`.

    ### [OK] Funcionalidades principales:
    - **Listado completo**: Retorna todos los pagos registrados
    - **Datos completos**: Incluye todos los campos de cada pago
    - **Metadatos**: Incluye ID del documento, conteo total y timestamp

    ###  Información incluida:
    - Todos los campos del pago
    - ID del documento para referencia
    - Conteo total de registros
    - Timestamp de la consulta

    ### [OK] Respuesta exitosa (200):
    ```json
    {
        "success": true,
        "data": [...],
        "count": 10,
        "collection": "pagos_emprestito",
        "timestamp": "2024-11-17T..."
    }
    ```
    """
    try:
        check_emprestito_availability()

        result = await get_pagos_emprestito_all()

        if not result["success"]:
            raise HTTPException(
                status_code=500,
                detail=f"Error obteniendo pagos de empréstito: {result.get('error', 'Error desconocido')}",
            )

        return JSONResponse(
            content={
                "success": True,
                "data": result["data"],
                "count": result["count"],
                "collection": result["collection"],
                "timestamp": result["timestamp"],
                "message": f"Se obtuvieron {result['count']} pagos de empréstito exitosamente",
            },
            status_code=200,
            headers={"Content-Type": "application/json; charset=utf-8"},
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error en endpoint de pagos de empréstito: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": "Error interno del servidor",
                "message": "Error al obtener pagos de empréstito",
                "code": "INTERNAL_SERVER_ERROR",
            },
        )


@router.get(
    "/rpc_contratos_emprestito_all",
    tags=["Gestión de Empréstito"],
    summary=" Obtener Todos los RPCs de Empréstito",
)
async def get_all_rpc_contratos_emprestito():
    """
    ##  GET |  Consultas | Obtener Todos los RPCs de Empréstito

    Endpoint para obtener todos los Registros Presupuestales de Compromiso (RPC)
    de empréstito almacenados en la colección `rpc_contratos_emprestito`.

    ### [OK] Funcionalidades principales:
    - **Listado completo**: Retorna todos los RPCs registrados
    - **Datos completos**: Incluye todos los campos de cada RPC
    - **Metadatos**: Incluye ID del documento, conteo total y timestamp

    ###  Información incluida:
    - Todos los campos del RPC
    - ID del documento para referencia
    - Conteo total de registros
    - Timestamp de la consulta

    ###  Campos principales esperados:
    - **numero_rpc**: Número único del RPC
    - **beneficiario_id**: Identificación del beneficiario
    - **beneficiario_nombre**: Nombre del beneficiario
    - **descripcion_rpc**: Descripción del compromiso
    - **fecha_contabilizacion**: Fecha de contabilización
    - **fecha_impresion**: Fecha de impresión
    - **estado_liberacion**: Estado de liberación
    - **bp**: Código BP
    - **valor_rpc**: Valor monetario del RPC
    - **nombre_centro_gestor**: Centro gestor responsable
    - **referencia_contrato**: Referencia del contrato asociado
    - **cdp_asociados**: CDPs asociados
    - **programacion_pac**: Programación PAC

    ### [OK] Respuesta exitosa (200):
    ```json
    {
        "success": true,
        "data": [...],
        "count": 15,
        "collection": "rpc_contratos_emprestito",
        "timestamp": "2024-11-17T..."
    }
    ```
    """
    try:
        check_emprestito_availability()

        result = await get_rpc_contratos_emprestito_all()

        if not result["success"]:
            raise HTTPException(
                status_code=500,
                detail=f"Error obteniendo RPCs de empréstito: {result.get('error', 'Error desconocido')}",
            )

        # Enriquecer cada RPC con enlaces de descarga y visualización de documentos S3
        data_enriquecida = result["data"]
        total_documentos_enriquecidos = 0

        if _s3_presigned_enabled():
            try:
                presigned_expiration = _s3_presigned_expiration()

                for rpc in data_enriquecida:
                    documentos_s3 = rpc.get("documentos_s3", [])

                    if not documentos_s3 or not isinstance(documentos_s3, list):
                        rpc["documentos_con_enlaces"] = []
                        rpc["total_documentos"] = 0
                        continue

                    documentos_con_enlaces = []

                    for doc in documentos_s3:
                        if not isinstance(doc, dict):
                            continue

                        s3_url = doc.get("s3_url") or doc.get("url") or ""
                        s3_key = doc.get("s3_key") or doc.get("key") or ""

                        bucket, key_from_url = None, None
                        if s3_url:
                            bucket, key_from_url = _extract_s3_bucket_key_from_url(
                                s3_url
                            )

                        resolved_key = s3_key or key_from_url or ""
                        resolved_bucket = bucket or ""

                        presigned_url = None
                        if resolved_bucket and resolved_key:
                            presigned_url = _generate_presigned_s3_url(
                                resolved_bucket, resolved_key
                            )

                        filename = doc.get("filename") or (
                            resolved_key.split("/")[-1] if resolved_key else ""
                        )

                        documento_enriquecido = {
                            "filename": filename,
                            "s3_key": resolved_key,
                            "s3_url": s3_url,
                            "content_type": doc.get("content_type", "application/pdf"),
                            "size": doc.get("size", 0),
                            "upload_date": doc.get("upload_date", ""),
                            "url_descarga": presigned_url,
                            "url_visualizar": presigned_url,
                            "url_presigned": presigned_url,
                            "url_expiration_seconds": (
                                presigned_expiration if presigned_url else None
                            ),
                        }
                        documentos_con_enlaces.append(documento_enriquecido)

                        if presigned_url:
                            total_documentos_enriquecidos += 1

                    rpc["documentos_con_enlaces"] = documentos_con_enlaces
                    rpc["total_documentos"] = len(documentos_con_enlaces)

                logger.info(
                    f"[OK] URLs de descarga/visualización generadas para {total_documentos_enriquecidos} documentos en {len(data_enriquecida)} RPCs"
                )
            except Exception as e:
                logger.warning(
                    f"[WARNING] No se pudieron generar URLs presigned para documentos: {e}"
                )

        return JSONResponse(
            content={
                "success": True,
                "data": data_enriquecida,
                "count": result["count"],
                "collection": result["collection"],
                "timestamp": result["timestamp"],
                "documentos_enriquecidos": total_documentos_enriquecidos,
                "s3_presigned_enabled": _s3_presigned_enabled(),
                "message": f"Se obtuvieron {result['count']} RPCs de empréstito exitosamente con enlaces de documentos",
            },
            status_code=200,
            headers={"Content-Type": "application/json; charset=utf-8"},
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error en endpoint de RPCs de empréstito: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": "Error interno del servidor",
                "message": "Error al obtener RPCs de empréstito",
                "code": "INTERNAL_SERVER_ERROR",
            },
        )


@router.put(
    "/emprestito/modificar-rpc",
    tags=["Gestión de Empréstito"],
    summary=" Modificar RPC de Empréstito",
)
async def actualizar_rpc_endpoint(
    numero_rpc: str = Form(..., description="Número del RPC a modificar (obligatorio)"),
    datos_actualizacion: str = Form(
        ..., description="JSON con los campos a actualizar"
    ),
):
    """
    ##  PUT |  Actualización | Modificar RPC (Registro Presupuestal de Compromiso)

    **Propósito**: Actualiza cualquier campo de un RPC existente en la colección "rpc_contratos_emprestito"
    según su "numero_rpc". Solo se modifican los campos proporcionados, los demás permanecen sin cambios.

    ### [OK] Casos de uso:
    - Actualizar valores específicos de un RPC existente
    - Corregir información incorrecta en RPCs
    - Modificar beneficiarios, valores, o fechas
    - Actualizar CDPs asociados o programación PAC
    - Cambiar estado de liberación o referencias

    ###  Funcionamiento:
    1. **Busca** el RPC por `numero_rpc` (parámetro de formulario)
    2. **Actualiza** solo los campos proporcionados en `datos_actualizacion`
    3. **Mantiene** los campos no especificados sin cambios
    4. **Registra** timestamp de última actualización automáticamente
    5. **Retorna** datos previos y actualizados para auditoría

    ###  Campos actualizables:
    - `beneficiario_id`: ID del beneficiario
    - `beneficiario_nombre`: Nombre del beneficiario
    - `descripcion_rpc`: Descripción del RPC
    - `fecha_contabilizacion`: Fecha de contabilización
    - `fecha_impresion`: Fecha de impresión
    - `estado_liberacion`: Estado de liberación
    - `bp`: Código BP
    - `valor_rpc`: Valor del RPC (numérico, >= 0)
    - `cdp_asociados`: Lista de CDPs (array o string separado por comas)
    - `programacion_pac`: Objeto con programación PAC
    - `nombre_centro_gestor`: Centro gestor responsable
    - `referencia_contrato`: Referencia del contrato
    - `estado`: Estado del RPC (activo, inactivo, etc.)

    ###  Campos protegidos (NO modificables):
    - `numero_rpc`: Identificador único (se usa para búsqueda)
    - `fecha_creacion`: Fecha de creación original
    - `tipo`: Tipo de RPC (manual, automático, etc.)

    ###  Validaciones:
    - **numero_rpc**: Debe existir en la colección
    - **valor_rpc**: Debe ser >= 0 si se proporciona
    - **strings**: Se limpian automáticamente de espacios
    - **cdp_asociados**: Acepta lista o string separado por comas
    - **programacion_pac**: Debe ser un objeto JSON válido
    - **campos opcionales**: Solo se actualizan los proporcionados

    ###  Ejemplo de uso con fetch:
    ```javascript
    const formData = new FormData();
    formData.append('numero_rpc', 'RPC-2024-001');
    formData.append('datos_actualizacion', JSON.stringify({
        valor_rpc: 500000000,
        estado_liberacion: "Liberado",
        beneficiario_nombre: "Nuevo Beneficiario S.A.S",
        cdp_asociados: ["CDP-001", "CDP-002"]
    }));

    const response = await fetch('/emprestito/modificar-rpc', {
        method: 'PUT',
        body: formData
    });
    ```

    ### [OK] Respuesta exitosa (200):
    ```json
    {
        "success": true,
        "message": "RPC RPC-2024-001 actualizado exitosamente",
        "numero_rpc": "RPC-2024-001",
        "doc_id": "abc123xyz",
        "coleccion": "rpc_contratos_emprestito",
        "datos_previos": { ... },
        "datos_actualizados": { ... },
        "campos_modificados": ["valor_rpc", "estado_liberacion", "beneficiario_nombre"],
        "timestamp": "2025-01-06T..."
    }
    ```

    ### [ERROR] Errores posibles:
    - **404**: RPC no encontrado con el numero_rpc especificado
    - **400**: Datos inválidos o formato JSON incorrecto
    - **400**: No hay campos válidos para actualizar
    - **500**: Error en la actualización de Firestore

    ###  Características:
    - **Actualización parcial**: Solo modifica campos especificados
    - **Auditoría completa**: Guarda datos previos y nuevos
    - **Búsqueda exacta**: Por numero_rpc únicamente
    - **UTF-8**: Soporte completo para caracteres especiales
    - **Timestamp automático**: Registra fecha_actualizacion
    - **Validación robusta**: Verifica existencia y tipos de datos
    - **Protección de campos**: No permite modificar campos del sistema
    """
    try:
        check_emprestito_availability()

        # Validar numero_rpc
        if not numero_rpc or not numero_rpc.strip():
            raise HTTPException(
                status_code=400,
                detail={
                    "success": False,
                    "error": "numero_rpc es requerido",
                    "message": "Debe proporcionar un numero_rpc válido",
                },
            )

        # Parsear datos_actualizacion JSON
        try:
            import json

            datos_dict = json.loads(datos_actualizacion)
        except json.JSONDecodeError as e:
            raise HTTPException(
                status_code=400,
                detail={
                    "success": False,
                    "error": "JSON inválido en datos_actualizacion",
                    "message": f"Error parseando JSON: {str(e)}",
                },
            )

        # Verificar que se proporcionen datos para actualizar
        if not datos_dict or not isinstance(datos_dict, dict):
            raise HTTPException(
                status_code=400,
                detail={
                    "success": False,
                    "error": "datos_actualizacion debe ser un objeto JSON válido",
                    "message": "Debe proporcionar al menos un campo para actualizar",
                },
            )

        # Llamar a la función de actualización
        result = await actualizar_rpc_contrato_emprestito(
            numero_rpc=numero_rpc.strip(), datos_actualizacion=datos_dict
        )

        if not result["success"]:
            # Determinar código de estado según el error
            if "No se encontró" in result.get("error", ""):
                status_code = 404
            else:
                status_code = 400

            raise HTTPException(
                status_code=status_code,
                detail={
                    "success": False,
                    "error": result.get("error", "Error desconocido"),
                    "numero_rpc": numero_rpc,
                },
            )

        return JSONResponse(
            content=result,
            status_code=200,
            headers={"Content-Type": "application/json; charset=utf-8"},
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error en endpoint de actualización de RPC: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": "Error interno del servidor",
                "message": str(e),
                "code": "INTERNAL_SERVER_ERROR",
            },
        )


@router.get(
    "/emprestito/proceso/{referencia_proceso}",
    tags=["Gestión de Empréstito"],
    summary=" Verificar Proceso Existente",
)
async def verificar_proceso_existente_endpoint(referencia_proceso: str):
    """
    ##  GET |  Consultas | Verificar Proceso Existente

    Verifica si ya existe un proceso con la referencia especificada en cualquiera
    de las colecciones de empréstito.

    ### [OK] Funcionalidades:
    - Búsqueda en `procesos_emprestito` (SECOP)
    - Búsqueda en `ordenes_compra_emprestito` (TVEC)
    - Información detallada del proceso encontrado

    ###  Respuesta si existe:
    - Datos completos del proceso
    - Colección donde se encontró
    - ID del documento

    ###  Casos de uso:
    - Validación previa antes de crear proceso
    - Búsqueda de procesos existentes
    - Prevención de duplicados

    ###  Ejemplo de respuesta (proceso existente):
    ```json
    {
        "existe": true,
        "coleccion": "procesos_emprestito",
        "documento": { ... },
        "doc_id": "xyz123",
        "timestamp": "2025-10-06T..."
    }
    ```
    """
    try:
        check_emprestito_availability()

        resultado = await verificar_proceso_existente(referencia_proceso)

        return JSONResponse(
            content={
                **resultado,
                "referencia_proceso": referencia_proceso,
                "timestamp": datetime.now().isoformat(),
            },
            status_code=200,
            headers={"Content-Type": "application/json; charset=utf-8"},
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error verificando proceso: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": "Error interno del servidor",
                "message": "Error verificando proceso existente",
            },
        )


@router.delete(
    "/emprestito/proceso/{referencia_proceso}",
    tags=["Gestión de Empréstito"],
    summary=" Eliminar Proceso",
)
async def eliminar_proceso_emprestito_endpoint(referencia_proceso: str):
    """
    ##  DELETE |  Eliminación | Eliminar Proceso de Empréstito

    Elimina un proceso de empréstito específico basado en su referencia_proceso.
    Busca automáticamente en ambas colecciones (SECOP y TVEC) y elimina el proceso encontrado.

    ### [OK] Funcionalidades principales:
    - **Búsqueda automática**: Localiza el proceso en ambas colecciones
    - **Eliminación segura**: Elimina únicamente el proceso especificado
    - **Información completa**: Retorna detalles del proceso eliminado
    - **Validación previa**: Verifica existencia antes de intentar eliminar

    ###  Colecciones de búsqueda:
    - **procesos_emprestito** (SECOP)
    - **ordenes_compra_emprestito** (TVEC)

    ### [WARNING] Consideraciones importantes:
    - La eliminación es **irreversible**
    - Solo se elimina un proceso por referencia_proceso
    - Se requiere coincidencia exacta en referencia_proceso

    ###  Respuesta exitosa:
    ```json
    {
        "success": true,
        "message": "Proceso eliminado exitosamente",
        "referencia_proceso": "SCMGSU-CM-003-2024",
        "coleccion": "procesos_emprestito",
        "documento_id": "xyz123",
        "proceso_eliminado": {
            "referencia_proceso": "SCMGSU-CM-003-2024",
            "nombre_centro_gestor": "Secretaría de Salud",
            "nombre_banco": "Banco Mundial",
            "plataforma": "SECOP II",
            "fecha_creacion": "2025-10-06T..."
        },
        "timestamp": "2025-10-06T..."
    }
    ```

    ###  Respuesta si no existe:
    ```json
    {
        "success": false,
        "error": "No se encontró ningún proceso con referencia_proceso: REFERENCIA",
        "referencia_proceso": "REFERENCIA",
        "colecciones_buscadas": ["procesos_emprestito", "ordenes_compra_emprestito"]
    }
    ```
    """
    try:
        check_emprestito_availability()

        # Validar parámetro
        if not referencia_proceso or not referencia_proceso.strip():
            raise HTTPException(
                status_code=400,
                detail={
                    "success": False,
                    "error": "referencia_proceso es requerida",
                    "message": "Debe proporcionar una referencia_proceso válida",
                },
            )

        # Eliminar proceso
        resultado = await eliminar_proceso_emprestito(referencia_proceso.strip())

        # Manejar respuesta según el resultado
        if not resultado.get("success"):
            error_msg = resultado.get("error", "")
            # Si no se encontró el proceso
            if "No se encontró" in error_msg:
                raise HTTPException(status_code=404, detail=resultado)
            # Si la función no está implementada
            elif "no implementada" in error_msg.lower():
                raise HTTPException(status_code=501, detail=resultado)
            else:
                raise HTTPException(status_code=500, detail=resultado)

        # Respuesta exitosa
        return JSONResponse(
            content=resultado,
            status_code=200,
            headers={"Content-Type": "application/json; charset=utf-8"},
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error en endpoint eliminar proceso: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": "Error interno del servidor",
                "message": "Error eliminando proceso de empréstito",
                "referencia_proceso": referencia_proceso,
            },
        )


@router.put(
    "/emprestito/modificar-valores/proceso/{referencia_proceso}",
    tags=["Gestión de Empréstito"],
    summary=" Modificar Valor de Proceso SECOP",
)
async def actualizar_valor_proceso_secop_endpoint(
    referencia_proceso: str,
    valor_publicacion: Optional[float] = Form(
        None,
        description="Valor de publicación del proceso SECOP (opcional, debe ser numérico)",
    ),
    change_motivo: str = Form(
        ..., description="Justificación del cambio (obligatorio)"
    ),
    change_support_file: UploadFile = File(
        ..., description="Documento soporte (obligatorio, PDF, XLSX, DOCX, etc.)"
    ),
):
    """
    ##  PUT |  Actualización | Modificar Valor de Publicación de Proceso SECOP

    Actualiza únicamente el campo `valor_publicacion` de un proceso SECOP existente
    identificado por `referencia_proceso`.

    ### [OK] Funcionalidades principales:
    - **Búsqueda por referencia_proceso**: Localiza el proceso en `procesos_emprestito`
    - **Actualización exclusiva de valor**: Solo modifica `valor_publicacion`
    - **Historial de cambios**: Muestra valor anterior y nuevo
    - **Persistencia garantizada**: Los cambios persisten incluso después de ejecutar endpoints POST

    ###  Colección de búsqueda:
    - **procesos_emprestito** (SECOP)

    ###  Campo actualizable:
    - `valor_publicacion`: Valor de publicación del proceso (numérico) **[Único campo modificable]**

    ###  Comportamiento:
    - **Campo vacío**: Error - debe proporcionar un valor
    - **Campo con valor**: Se actualiza en la base de datos
    - **Timestamp**: Se actualiza automáticamente `fecha_actualizacion`
    - **Validación previa**: Verifica que el proceso existe

    ###  Respuesta exitosa:
    ```json
    {
        "success": true,
        "message": "Proceso SECOP actualizado exitosamente",
        "referencia_proceso": "SCMGSU-CM-003-2024",
        "coleccion": "procesos_emprestito",
        "documento_id": "xyz123",
        "campos_modificados": ["valor_publicacion"],
        "valores_anteriores": {
            "valor_publicacion": 1000000.0
        },
        "valores_nuevos": {
            "valor_publicacion": 1500000.0
        },
        "proceso_actualizado": { ... },
        "timestamp": "2025-12-28T..."
    }
    ```

    ###  Respuesta si no existe:
    ```json
    {
        "success": false,
        "error": "No se encontró ningún proceso SECOP con referencia_proceso: SCMGSU-CM-003-2024",
        "referencia_proceso": "SCMGSU-CM-003-2024"
    }
    ```
    """
    try:
        check_emprestito_availability()

        # Validar parámetro
        if not referencia_proceso or not referencia_proceso.strip():
            raise HTTPException(
                status_code=400,
                detail={
                    "success": False,
                    "error": "referencia_proceso es requerida",
                    "message": "Debe proporcionar una referencia_proceso válida",
                },
            )

        # Validar que se proporcione al menos un valor para actualizar
        if valor_publicacion is None:
            raise HTTPException(
                status_code=400,
                detail={
                    "success": False,
                    "error": "No se proporcionaron campos para actualizar",
                    "message": "Debe proporcionar al menos valor_publicacion para actualizar",
                },
            )

        # Preparar campos para actualizar
        campos_actualizar = {"valor_publicacion": float(valor_publicacion)}

        # Actualizar proceso
        resultado = await actualizar_proceso_secop_por_referencia(
            referencia_proceso=referencia_proceso.strip(),
            campos_actualizar=campos_actualizar,
        )

        # Manejar respuesta según el resultado
        if not resultado.get("success"):
            # Si no se encontró el proceso
            if "No se encontró" in resultado.get("error", ""):
                raise HTTPException(status_code=404, detail=resultado)
            # Si no se proporcionaron campos para actualizar
            elif "No se proporcionaron campos" in resultado.get("error", ""):
                raise HTTPException(status_code=400, detail=resultado)
            else:
                # Otros errores
                raise HTTPException(status_code=500, detail=resultado)

        # [OK] Actualización exitosa - registrar en auditoría
        try:
            logger.info(
                f" Iniciando registro de auditoría para proceso: {referencia_proceso}"
            )
            auditoria_resultado = await registrar_cambio_valor(
                tipo_coleccion="procesos",
                identificador=referencia_proceso.strip(),
                campo_modificado="valor_publicacion",
                valor_anterior=resultado.get("valores_anteriores", {}).get(
                    "valor_publicacion"
                ),
                valor_nuevo=resultado.get("valores_nuevos", {}).get(
                    "valor_publicacion"
                ),
                motivo=change_motivo,
                archivo_soporte=change_support_file,
                usuario=None,  # Puede integrarse con autenticación
                endpoint_usado="/emprestito/modificar-valores/proceso",
            )

            logger.info(f" Resultado de auditoría: {auditoria_resultado}")

            # Agregar información de auditoría a la respuesta
            resultado["auditoria"] = auditoria_resultado

            if not auditoria_resultado.get("success"):
                logger.warning(
                    f"[WARNING] Auditoría no registrada: {auditoria_resultado.get('error')}"
                )
                resultado["auditoria_warning"] = (
                    "Cambio realizado pero no se pudo registrar en auditoría"
                )
            else:
                logger.info(
                    f"[OK] Auditoría registrada exitosamente: {auditoria_resultado.get('change_id')}"
                )

        except Exception as e_audit:
            logger.error(f"Error registrando auditoría: {e_audit}")
            resultado["auditoria"] = {"success": False, "error": str(e_audit)}
            resultado["auditoria_warning"] = "Cambio realizado pero auditoría falló"

        # Respuesta exitosa
        return JSONResponse(
            content=resultado,
            status_code=200,
            headers={"Content-Type": "application/json; charset=utf-8"},
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error en endpoint actualizar valor proceso SECOP: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": "Error interno del servidor",
                "message": "Error actualizando valor de proceso SECOP",
                "referencia_proceso": referencia_proceso,
            },
        )


@router.put(
    "/emprestito/modificar-valores/orden-compra/{numero_orden}",
    tags=["Gestión de Empréstito"],
    summary=" Modificar Valor de Orden de Compra",
)
async def actualizar_orden_compra_endpoint(
    numero_orden: str,
    valor_orden: Optional[float] = Form(
        None, description="Valor de la orden (opcional, debe ser numérico)"
    ),
    valor_proyectado: Optional[float] = Form(
        None, description="Valor proyectado (opcional, debe ser numérico)"
    ),
    change_motivo: str = Form(
        ..., description="Justificación del cambio (obligatorio)"
    ),
    change_support_file: UploadFile = File(
        ..., description="Documento soporte (obligatorio, PDF, XLSX, DOCX, etc.)"
    ),
):
    """
    ##  PUT |  Actualización | Actualizar Orden de Compra de Empréstito por Número de Orden

    Actualiza campos específicos de una orden de compra existente identificada por `numero_orden`.
    Solo se actualizan los campos proporcionados, manteniendo los demás valores sin cambios.

    ### [OK] Funcionalidades principales:
    - **Búsqueda por numero_orden**: Localiza la orden de compra en `ordenes_compra_emprestito`
    - **Actualización selectiva**: Solo modifica los campos proporcionados
    - **Preservación de datos**: Mantiene los campos no especificados
    - **Historial de cambios**: Muestra valores anteriores y nuevos
    - **Persistencia garantizada**: Los cambios persisten incluso después de ejecutar endpoints POST

    ###  Colección de búsqueda:
    - **ordenes_compra_emprestito** (TVEC)

    ###  Campos actualizables:
    - `valor_orden`: Valor de la orden de compra (numérico) **[Campo principal]**
    - `valor_proyectado`: Valor proyectado (numérico) **[Opcional si existe]**

    ###  Comportamiento:
    - **Campos vacíos**: Se ignoran (no se actualizan)
    - **Campos con valor**: Se actualizan en la base de datos
    - **Timestamp**: Se actualiza automáticamente `fecha_actualizacion`
    - **Validación previa**: Verifica que la orden existe
    - **Solo valores**: Ningún otro campo puede ser modificado por este endpoint

    ###  Respuesta exitosa:
    ```json
    {
        "success": true,
        "message": "Orden de compra actualizada exitosamente",
        "numero_orden": "OC-2024-001",
        "coleccion": "ordenes_compra_emprestito",
        "documento_id": "xyz123",
        "campos_modificados": ["valor_orden"],
        "valores_anteriores": {
            "valor_orden": 1000000.0
        },
        "valores_nuevos": {
            "valor_orden": 1500000.0
        },
        "orden_actualizada": { ... },
        "timestamp": "2025-12-28T..."
    }
    ```
    """
    try:
        check_emprestito_availability()

        # Validar parámetro
        if not numero_orden or not numero_orden.strip():
            raise HTTPException(
                status_code=400,
                detail={
                    "success": False,
                    "error": "numero_orden es requerido",
                    "message": "Debe proporcionar un numero_orden válido",
                },
            )

        # Validar que se proporcione al menos un valor para actualizar
        if valor_orden is None and valor_proyectado is None:
            raise HTTPException(
                status_code=400,
                detail={
                    "success": False,
                    "error": "No se proporcionaron campos para actualizar",
                    "message": "Debe proporcionar al menos uno de: valor_orden, valor_proyectado",
                },
            )

        # Preparar campos para actualizar (solo valores numéricos proporcionados)
        campos_actualizar = {}
        if valor_orden is not None:
            campos_actualizar["valor_orden"] = float(valor_orden)
        if valor_proyectado is not None:
            campos_actualizar["valor_proyectado"] = float(valor_proyectado)

        # Actualizar orden de compra
        resultado = await actualizar_orden_compra_por_numero(
            numero_orden=numero_orden.strip(), campos_actualizar=campos_actualizar
        )

        # Manejar respuesta según el resultado
        if not resultado.get("success"):
            if "No se encontró" in resultado.get("error", ""):
                raise HTTPException(status_code=404, detail=resultado)
            elif "No se proporcionaron campos" in resultado.get("error", ""):
                raise HTTPException(status_code=400, detail=resultado)
            else:
                raise HTTPException(status_code=500, detail=resultado)

        # [OK] Actualización exitosa - registrar en auditoría
        try:
            logger.info(f" Iniciando registro de auditoría para orden: {numero_orden}")
            # Determinar campo(s) modificado(s)
            campos_modificados = list(campos_actualizar.keys())
            campo_modificado = ", ".join(campos_modificados)

            auditoria_resultado = await registrar_cambio_valor(
                tipo_coleccion="ordenes",
                identificador=numero_orden.strip(),
                campo_modificado=campo_modificado,
                valor_anterior=resultado.get("valores_anteriores", {}).get(
                    "valor_orden"
                ),
                valor_nuevo=resultado.get("valores_nuevos", {}).get("valor_orden"),
                motivo=change_motivo,
                archivo_soporte=change_support_file,
                usuario=None,
                endpoint_usado="/emprestito/modificar-valores/orden-compra",
            )

            logger.info(f" Resultado de auditoría: {auditoria_resultado}")

            # Agregar información de auditoría a la respuesta
            resultado["auditoria"] = auditoria_resultado

            if not auditoria_resultado.get("success"):
                logger.warning(
                    f"[WARNING] Auditoría no registrada: {auditoria_resultado.get('error')}"
                )
                resultado["auditoria_warning"] = (
                    "Cambio realizado pero no se pudo registrar en auditoría"
                )
            else:
                logger.info(
                    f"[OK] Auditoría registrada exitosamente: {auditoria_resultado.get('change_id')}"
                )

        except Exception as e_audit:
            logger.error(f"Error registrando auditoría: {e_audit}")
            resultado["auditoria"] = {"success": False, "error": str(e_audit)}
            resultado["auditoria_warning"] = "Cambio realizado pero auditoría falló"

        # Respuesta exitosa
        return JSONResponse(
            content=resultado,
            status_code=200,
            headers={"Content-Type": "application/json; charset=utf-8"},
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error en endpoint actualizar valores orden de compra: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": "Error interno del servidor",
                "message": "Error actualizando valores de orden de compra",
                "numero_orden": numero_orden,
            },
        )


@router.put(
    "/emprestito/modificar-valores/convenio/{referencia_contrato}",
    tags=["Gestión de Empréstito"],
    summary=" Modificar Valor de Convenio",
)
async def actualizar_valor_convenio_endpoint(
    referencia_contrato: str,
    valor_contrato: Optional[float] = Form(
        None, description="Valor del contrato (opcional, debe ser numérico)"
    ),
    change_motivo: str = Form(
        ..., description="Justificación del cambio (obligatorio)"
    ),
    change_support_file: UploadFile = File(
        ..., description="Documento soporte (obligatorio, PDF, XLSX, DOCX, etc.)"
    ),
):
    """
    ##  PUT |  Actualización | Modificar Valor de Convenio de Transferencia

    Actualiza únicamente el campo `valor_contrato` de un convenio de transferencia existente
    identificado por `referencia_contrato`.

    ### [OK] Funcionalidades principales:
    - **Búsqueda por referencia_contrato**: Localiza el convenio en `convenios_transferencias_emprestito`
    - **Actualización exclusiva de valor**: Solo modifica `valor_contrato`
    - **Historial de cambios**: Muestra valor anterior y nuevo
    - **Persistencia garantizada**: Los cambios persisten incluso después de ejecutar endpoints POST

    ###  Colección de búsqueda:
    - **convenios_transferencias_emprestito**

    ###  Campo actualizable:
    - `valor_contrato`: Valor del contrato (numérico) **[Único campo modificable]**

    ###  Comportamiento:
    - **Campo vacío**: Error - debe proporcionar un valor
    - **Campo con valor**: Se actualiza en la base de datos
    - **Timestamp**: Se actualiza automáticamente `fecha_actualizacion`
    - **Validación previa**: Verifica que el convenio existe

    ###  Respuesta exitosa:
    ```json
    {
        "success": true,
        "message": "Convenio de transferencia actualizado exitosamente",
        "referencia_contrato": "CONT-2024-001",
        "coleccion": "convenios_transferencias_emprestito",
        "documento_id": "xyz123",
        "campos_modificados": ["valor_contrato"],
        "valores_anteriores": {
            "valor_contrato": 1000000.0
        },
        "valores_nuevos": {
            "valor_contrato": 1500000.0
        },
        "convenio_actualizado": { ... },
        "timestamp": "2025-12-28T..."
    }
    ```
    """
    try:
        check_emprestito_availability()

        # Validar parámetro
        if not referencia_contrato or not referencia_contrato.strip():
            raise HTTPException(
                status_code=400,
                detail={
                    "success": False,
                    "error": "referencia_contrato es requerida",
                    "message": "Debe proporcionar una referencia_contrato válida",
                },
            )

        # Validar que se proporcione al menos un valor para actualizar
        if valor_contrato is None:
            raise HTTPException(
                status_code=400,
                detail={
                    "success": False,
                    "error": "No se proporcionaron campos para actualizar",
                    "message": "Debe proporcionar al menos valor_contrato para actualizar",
                },
            )

        # Preparar campos para actualizar
        campos_actualizar = {"valor_contrato": float(valor_contrato)}

        # Actualizar convenio
        resultado = await actualizar_convenio_por_referencia(
            referencia_contrato=referencia_contrato.strip(),
            campos_actualizar=campos_actualizar,
        )

        # Manejar respuesta según el resultado
        if not resultado.get("success"):
            if "No se encontró" in resultado.get("error", ""):
                raise HTTPException(status_code=404, detail=resultado)
            elif "No se proporcionaron campos" in resultado.get("error", ""):
                raise HTTPException(status_code=400, detail=resultado)
            else:
                raise HTTPException(status_code=500, detail=resultado)

        # [OK] Actualización exitosa - registrar en auditoría
        try:
            logger.info(
                f" Iniciando registro de auditoría para convenio: {referencia_contrato}"
            )
            auditoria_resultado = await registrar_cambio_valor(
                tipo_coleccion="convenios",
                identificador=referencia_contrato.strip(),
                campo_modificado="valor_contrato",
                valor_anterior=resultado.get("valores_anteriores", {}).get(
                    "valor_contrato"
                ),
                valor_nuevo=resultado.get("valores_nuevos", {}).get("valor_contrato"),
                motivo=change_motivo,
                archivo_soporte=change_support_file,
                usuario=None,
                endpoint_usado="/emprestito/modificar-valores/convenio",
            )

            logger.info(f" Resultado de auditoría: {auditoria_resultado}")

            # Agregar información de auditoría a la respuesta
            resultado["auditoria"] = auditoria_resultado

            if not auditoria_resultado.get("success"):
                logger.warning(
                    f"[WARNING] Auditoría no registrada: {auditoria_resultado.get('error')}"
                )
                resultado["auditoria_warning"] = (
                    "Cambio realizado pero no se pudo registrar en auditoría"
                )
            else:
                logger.info(
                    f"[OK] Auditoría registrada exitosamente: {auditoria_resultado.get('change_id')}"
                )

        except Exception as e_audit:
            logger.error(f"Error registrando auditoría: {e_audit}")
            resultado["auditoria"] = {"success": False, "error": str(e_audit)}
            resultado["auditoria_warning"] = "Cambio realizado pero auditoría falló"

        # Respuesta exitosa
        return JSONResponse(
            content=resultado,
            status_code=200,
            headers={"Content-Type": "application/json; charset=utf-8"},
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error en endpoint actualizar valor convenio: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": "Error interno del servidor",
                "message": "Error actualizando valor de convenio de transferencia",
                "referencia_contrato": referencia_contrato,
            },
        )


@router.put(
    "/emprestito/modificar-valores/contrato-secop/{referencia_contrato}",
    tags=["Gestión de Empréstito"],
    summary=" Actualizar Valor Contrato SECOP",
)
async def actualizar_contrato_secop_endpoint(
    referencia_contrato: str,
    valor_contrato: Optional[float] = Form(
        None, description="Valor del contrato (opcional, debe ser numérico)"
    ),
    change_motivo: str = Form(
        ..., description="Justificación del cambio (obligatorio)"
    ),
    change_support_file: UploadFile = File(
        ..., description="Documento soporte (obligatorio, PDF, XLSX, DOCX, etc.)"
    ),
):
    """
    ##  PUT |  Actualización | Actualizar Valor de Contrato SECOP

    Actualiza únicamente el campo `valor_contrato` de un contrato SECOP existente identificado por `referencia_contrato`.
    Este endpoint está diseñado específicamente para modificar el valor del contrato, sin alterar ningún otro campo.

    ### [OK] Funcionalidades principales:
    - **Búsqueda por referencia_contrato**: Localiza el contrato en `contratos_emprestito`
    - **Actualización del valor**: Modifica solo el campo `valor_contrato`
    - **Persistencia garantizada**: Los cambios persisten incluso después de ejecutar endpoints POST
    - **Historial de cambios**: Muestra el valor anterior y el nuevo valor

    ###  Colección de búsqueda:
    - **contratos_emprestito** (SECOP)

    ###  Campo actualizable:
    - `valor_contrato`: Valor del contrato (numérico, requerido)

    ###  Comportamiento:
    - **Campo requerido**: Debe proporcionar `valor_contrato`
    - **Timestamp**: Se actualiza automáticamente `fecha_actualizacion`
    - **Validación previa**: Verifica que el contrato existe

    ###  Respuesta exitosa:
    ```json
    {
        "success": true,
        "message": "Contrato SECOP actualizado exitosamente",
        "referencia_contrato": "CONT-SECOP-2024-001",
        "coleccion": "contratos_emprestito",
        "documento_id": "xyz123",
        "campos_modificados": ["valor_contrato"],
        "valores_anteriores": {
            "valor_contrato": 1000000.0
        },
        "valores_nuevos": {
            "valor_contrato": 1500000.0
        },
        "contrato_actualizado": { ... },
        "timestamp": "2025-12-28T..."
    }
    ```
    """
    try:
        check_emprestito_availability()

        # Validar parámetro
        if not referencia_contrato or not referencia_contrato.strip():
            raise HTTPException(
                status_code=400,
                detail={
                    "success": False,
                    "error": "referencia_contrato es requerida",
                    "message": "Debe proporcionar una referencia_contrato válida",
                },
            )

        # Validar que se proporcione al menos un valor para actualizar
        if valor_contrato is None:
            raise HTTPException(
                status_code=400,
                detail={
                    "success": False,
                    "error": "No se proporcionaron campos para actualizar",
                    "message": "Debe proporcionar al menos valor_contrato para actualizar",
                },
            )

        # Preparar campos para actualizar (solo valor_contrato)
        campos_actualizar = {"valor_contrato": float(valor_contrato)}

        # Actualizar contrato
        resultado = await actualizar_contrato_secop_por_referencia(
            referencia_contrato=referencia_contrato.strip(),
            campos_actualizar=campos_actualizar,
        )

        # Manejar respuesta según el resultado
        if not resultado.get("success"):
            if "No se encontró" in resultado.get("error", ""):
                raise HTTPException(status_code=404, detail=resultado)
            elif "No se proporcionaron campos" in resultado.get("error", ""):
                raise HTTPException(status_code=400, detail=resultado)
            else:
                raise HTTPException(status_code=500, detail=resultado)

        # [OK] Actualización exitosa - registrar en auditoría
        try:
            logger.info(
                f" Iniciando registro de auditoría para contrato: {referencia_contrato}"
            )
            auditoria_resultado = await registrar_cambio_valor(
                tipo_coleccion="contratos",
                identificador=referencia_contrato.strip(),
                campo_modificado="valor_contrato",
                valor_anterior=resultado.get("valores_anteriores", {}).get(
                    "valor_contrato"
                ),
                valor_nuevo=resultado.get("valores_nuevos", {}).get("valor_contrato"),
                motivo=change_motivo,
                archivo_soporte=change_support_file,
                usuario=None,
                endpoint_usado="/emprestito/modificar-valores/contrato-secop",
            )

            logger.info(f" Resultado de auditoría: {auditoria_resultado}")

            # Agregar información de auditoría a la respuesta
            resultado["auditoria"] = auditoria_resultado

            if not auditoria_resultado.get("success"):
                logger.warning(
                    f"[WARNING] Auditoría no registrada: {auditoria_resultado.get('error')}"
                )
                resultado["auditoria_warning"] = (
                    "Cambio realizado pero no se pudo registrar en auditoría"
                )
            else:
                logger.info(
                    f"[OK] Auditoría registrada exitosamente: {auditoria_resultado.get('change_id')}"
                )

        except Exception as e_audit:
            logger.error(f"Error registrando auditoría: {e_audit}")
            resultado["auditoria"] = {"success": False, "error": str(e_audit)}
            resultado["auditoria_warning"] = "Cambio realizado pero auditoría falló"

        # Respuesta exitosa
        return JSONResponse(
            content=resultado,
            status_code=200,
            headers={"Content-Type": "application/json; charset=utf-8"},
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error en endpoint actualizar valor contrato SECOP: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": "Error interno del servidor",
                "message": "Error actualizando valor de contrato SECOP",
                "referencia_contrato": referencia_contrato,
            },
        )


@router.get(
    "/emprestito/historial-cambios",
    tags=["Gestión de Empréstito"],
    summary=" Obtener Historial de Cambios",
)
async def obtener_historial_cambios_endpoint(
    tipo_coleccion: Optional[str] = Query(
        None,
        description="Filtrar por tipo de colección (procesos, ordenes, convenios, contratos)",
    ),
    identificador: Optional[str] = Query(
        None, description="Filtrar por identificador específico"
    ),
    limite: int = Query(
        50, ge=1, le=200, description="Número máximo de registros (1-200)"
    ),
):
    """
    ##  GET | Consulta | Obtener Historial de Cambios en Valores de Empréstito

    Consulta el historial completo de cambios realizados en los valores de las colecciones de empréstito.
    Cada cambio incluye información de auditoría completa: motivo, documento soporte, valores anteriores y nuevos.

    ### [OK] Funcionalidades principales:
    - **Historial completo**: Accede a todos los cambios registrados
    - **Filtros opcionales**: Por tipo de colección o identificador específico
    - **Información detallada**: Incluye motivo, documento soporte, timestamp, valores modificados
    - **Trazabilidad**: ID único para cada cambio

    ###  Filtros disponibles:
    - **tipo_coleccion**: procesos, ordenes, convenios, contratos (opcional)
    - **identificador**: referencia_proceso, numero_orden, referencia_contrato (opcional)
    - **limite**: Número máximo de registros a retornar (1-200, default: 50)

    ###  Información por cambio:
    - `change_id`: ID único del cambio
    - `change_timestamp`: Fecha y hora del cambio
    - `change_motivo`: Justificación del cambio
    - `change_support_file`: URL del documento soporte en S3 (si existe)
    - `tipo_coleccion`: Tipo de colección modificada
    - `identificador`: Identificador del documento modificado
    - `campo_modificado`: Campo que se modificó
    - `valor_anterior`: Valor antes del cambio
    - `valor_nuevo`: Valor después del cambio
    - `diferencia`: Diferencia numérica (valor_nuevo - valor_anterior)
    - `usuario`: Usuario que realizó el cambio
    - `endpoint_usado`: Endpoint utilizado

    ###  Respuesta exitosa:
    ```json
    {
        "success": true,
        "total_cambios": 15,
        "cambios": [
            {
                "change_id": "uuid-123",
                "change_timestamp": "2025-12-28T10:30:00",
                "change_motivo": "Ajuste por modificación contractual",
                "change_support_file": "https://s3.../documento.pdf",
                "tipo_coleccion": "contratos",
                "identificador": "CONT-2024-001",
                "campo_modificado": "valor_contrato",
                "valor_anterior": 1000000.0,
                "valor_nuevo": 1500000.0,
                "diferencia": 500000.0,
                "usuario": "Sistema",
                "endpoint_usado": "/emprestito/modificar-valores/contrato-secop"
            }
        ]
    }
    ```
    """
    try:
        check_emprestito_availability()

        # Obtener historial
        resultado = await obtener_historial_cambios(
            tipo_coleccion=tipo_coleccion, identificador=identificador, limite=limite
        )

        if not resultado.get("success"):
            raise HTTPException(status_code=500, detail=resultado)

        return JSONResponse(
            content=resultado,
            status_code=200,
            headers={"Content-Type": "application/json; charset=utf-8"},
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error obteniendo historial de cambios: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": "Error interno del servidor",
                "message": "Error consultando historial de cambios",
            },
        )


# ============================================================================
# SOLICITUDES DE CAMBIO DE EMPRÉSTITO
# ============================================================================

TIPO_REGISTRO_TO_COLLECTION = {
    "contrato": "contratos_emprestito",
    "proceso": "procesos_emprestito",
    "pago": "pagos_emprestito",
    "orden_compra": "ordenes_compra_emprestito",
    "convenio": "convenios_transferencias_emprestito",
    "rpc": "rpc_contratos_emprestito",
}

SOLICITUDES_EMPRESTITO_COLLECTION = "solicitudes_cambios_emprestito"


class SolicitudCambioEmprestitoRequest(BaseModel):
    tipo_registro: str = Field(
        ...,
        description="Tipo de registro: contrato, proceso, pago, orden_compra, convenio, rpc",
    )
    referencia_id: str = Field(
        ..., description="Identificador del registro a modificar"
    )
    campos_modificados: Dict[str, Dict[str, Any]] = Field(
        ...,
        description="Campos a modificar: { campo: { anterior: valor, nuevo: valor } }",
    )
    motivo: Optional[str] = Field(None, description="Motivo de la solicitud de cambio")

    class Config:
        json_schema_extra = {
            "example": {
                "tipo_registro": "contrato",
                "referencia_id": "CONT-2024-001",
                "campos_modificados": {
                    "valor_contrato": {"anterior": 1000000, "nuevo": 1500000},
                    "estado_contrato": {
                        "anterior": "En ejecución",
                        "nuevo": "Terminado",
                    },
                },
                "motivo": "Ajuste por adición contractual",
            }
        }


@router.post(
    "/solicitudes_cambios_emprestito",
    tags=["Gestión de Empréstito"],
    summary=" Crear solicitud de cambio de empréstito",
)
@optional_rate_limit("30/minute")
async def crear_solicitud_cambio_emprestito(
    request: Request,
    payload: SolicitudCambioEmprestitoRequest = Body(
        ..., description="Datos de la solicitud de cambio"
    ),
):
    """
    ##  POST | Crear solicitud de cambio para registros de empréstito

    Crea una solicitud de cambio pendiente para cualquier tipo de registro de empréstito.
    La solicitud debe ser aprobada o rechazada posteriormente.

    ### Tipos de registro válidos:
    - `contrato`, `proceso`, `pago`, `orden_compra`, `convenio`, `rpc`
    """
    if not FIREBASE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Firebase not available")

    try:
        db = get_firestore_client()
        if db is None:
            raise HTTPException(
                status_code=503, detail="No se pudo conectar a Firestore"
            )

        tipo_registro = payload.tipo_registro.strip().lower()
        referencia_id = payload.referencia_id.strip()

        if tipo_registro not in TIPO_REGISTRO_TO_COLLECTION:
            raise HTTPException(
                status_code=400,
                detail=f"tipo_registro inválido: '{tipo_registro}'. Valores permitidos: {list(TIPO_REGISTRO_TO_COLLECTION.keys())}",
            )

        if not referencia_id:
            raise HTTPException(status_code=400, detail="referencia_id es obligatorio")

        if not payload.campos_modificados:
            raise HTTPException(
                status_code=400, detail="campos_modificados no puede estar vacío"
            )

        # Validar estructura de campos_modificados
        for campo, valores in payload.campos_modificados.items():
            if not isinstance(valores, dict) or "nuevo" not in valores:
                raise HTTPException(
                    status_code=400,
                    detail=f"Campo '{campo}' debe tener al menos la clave 'nuevo' en su valor",
                )

        now_iso = datetime.now().isoformat()
        doc_id = str(uuid.uuid4())

        solicitud_data = {
            "tipo_registro": tipo_registro,
            "coleccion_destino": TIPO_REGISTRO_TO_COLLECTION[tipo_registro],
            "referencia_id": referencia_id,
            "campos_modificados": (
                payload.campos_modificados
                if hasattr(payload.campos_modificados, "__iter__")
                and not isinstance(payload.campos_modificados, str)
                else {}
            ),
            "motivo": payload.motivo,
            "estado": "pendiente",
            "created_at": now_iso,
            "updated_at": now_iso,
        }

        # Serializar campos_modificados correctamente
        campos_serializados = {}
        for campo, valores in payload.campos_modificados.items():
            if hasattr(valores, "model_dump"):
                campos_serializados[campo] = valores.model_dump()
            elif hasattr(valores, "dict"):
                campos_serializados[campo] = valores.dict()
            else:
                campos_serializados[campo] = (
                    dict(valores) if isinstance(valores, dict) else valores
                )
        solicitud_data["campos_modificados"] = campos_serializados

        db.collection(SOLICITUDES_EMPRESTITO_COLLECTION).document(doc_id).set(
            solicitud_data
        )

        return create_utf8_response(
            {
                "success": True,
                "id": doc_id,
                "collection": SOLICITUDES_EMPRESTITO_COLLECTION,
                "estado": "pendiente",
                "data": solicitud_data,
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creando solicitud de cambio de empréstito: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error creando solicitud: {str(e)}"
        )


@router.get(
    "/solicitudes_cambios_emprestito",
    tags=["Gestión de Empréstito"],
    summary=" Consultar solicitudes de cambio de empréstito",
)
@optional_rate_limit("30/minute")
async def consultar_solicitudes_cambios_emprestito(
    request: Request,
    estado: Optional[str] = Query(
        None, description="Filtrar por estado: pendiente, aprobada, rechazada"
    ),
    tipo_registro: Optional[str] = Query(
        None,
        description="Filtrar por tipo: contrato, proceso, pago, orden_compra, convenio, rpc",
    ),
    centro_gestor: Optional[str] = Query(None, description="Filtrar por centro gestor"),
    limit: int = Query(100, ge=1, le=500, description="Máximo de registros"),
    offset: int = Query(0, ge=0, description="Offset para paginación"),
):
    """
    ##  GET | Consultar solicitudes de cambio de empréstito

    Consulta solicitudes de cambio con filtros opcionales por estado, tipo y centro gestor.
    """
    if not FIREBASE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Firebase not available")

    try:
        db = get_firestore_client()
        if db is None:
            raise HTTPException(
                status_code=503, detail="No se pudo conectar a Firestore"
            )

        query = db.collection(SOLICITUDES_EMPRESTITO_COLLECTION)

        if estado:
            query = query.where("estado", "==", estado.strip().lower())
        if tipo_registro:
            query = query.where("tipo_registro", "==", tipo_registro.strip().lower())

        docs = list(query.stream())

        solicitudes = []
        for doc in docs:
            data = doc.to_dict() or {}
            data["id"] = doc.id

            # Normalizar timestamps
            for key, value in data.items():
                if hasattr(value, "isoformat"):
                    data[key] = value.isoformat()

            # Filtro por centro_gestor (no soportado nativamente por Firestore con otros filtros compuestos)
            if centro_gestor:
                ref_id = data.get("referencia_id", "")
                if centro_gestor.lower() not in str(data).lower():
                    continue

            solicitudes.append(data)

        # Ordenar por fecha de creación descendente
        solicitudes.sort(key=lambda s: s.get("created_at", ""), reverse=True)

        # Paginar
        paged = solicitudes[offset : offset + limit]

        return create_utf8_response(
            {
                "success": True,
                "total": len(solicitudes),
                "count": len(paged),
                "offset": offset,
                "limit": limit,
                "data": paged,
                "collection": SOLICITUDES_EMPRESTITO_COLLECTION,
                "filters": {
                    "estado": estado,
                    "tipo_registro": tipo_registro,
                    "centro_gestor": centro_gestor,
                },
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error consultando solicitudes de cambio: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error consultando solicitudes: {str(e)}"
        )


@router.put(
    "/solicitudes_cambios_emprestito/{solicitud_id}/aprobar",
    tags=["Gestión de Empréstito"],
    summary="[OK] Aprobar solicitud de cambio",
)
@optional_rate_limit("10/minute")
async def aprobar_solicitud_cambio_emprestito(
    request: Request,
    solicitud_id: str = Path(..., description="ID de la solicitud a aprobar"),
):
    """
    ## [OK] PUT | Aprobar solicitud de cambio de empréstito

    Aprueba una solicitud pendiente y aplica los cambios al registro original.
    Registra cada cambio en el sistema de auditoría (emprestito_control_cambios).
    """
    if not FIREBASE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Firebase not available")

    try:
        db = get_firestore_client()
        if db is None:
            raise HTTPException(
                status_code=503, detail="No se pudo conectar a Firestore"
            )

        # Leer solicitud
        sol_ref = db.collection(SOLICITUDES_EMPRESTITO_COLLECTION).document(
            solicitud_id
        )
        sol_doc = _as_firestore_doc_snapshot(sol_ref.get())

        if not sol_doc.exists:
            raise HTTPException(
                status_code=404, detail=f"Solicitud no encontrada: {solicitud_id}"
            )

        sol_data = sol_doc.to_dict() or {}

        if sol_data.get("estado") != "pendiente":
            raise HTTPException(
                status_code=400,
                detail=f"La solicitud no está pendiente. Estado actual: {sol_data.get('estado')}",
            )

        tipo_registro = sol_data.get("tipo_registro")
        coleccion_destino = sol_data.get(
            "coleccion_destino"
        ) or TIPO_REGISTRO_TO_COLLECTION.get(tipo_registro)
        referencia_id = sol_data.get("referencia_id")
        campos_modificados = sol_data.get("campos_modificados", {})

        if not coleccion_destino or not referencia_id:
            raise HTTPException(
                status_code=400, detail="Solicitud con datos incompletos"
            )

        # Buscar el documento original por referencia
        identifier_field_map = {
            "contrato": "referencia_contrato",
            "proceso": "referencia_proceso",
            "pago": "referencia_contrato",
            "orden_compra": "numero_orden",
            "convenio": "referencia_contrato",
            "rpc": "numero_rpc",
        }
        id_field = identifier_field_map.get(tipo_registro, "referencia_contrato")

        docs_query = (
            db.collection(coleccion_destino)
            .where(id_field, "==", referencia_id)
            .limit(1)
        )
        target_docs = list(docs_query.stream())

        if not target_docs:
            raise HTTPException(
                status_code=404,
                detail=f"Registro original no encontrado en {coleccion_destino} con {id_field}={referencia_id}",
            )

        target_doc = target_docs[0]
        target_ref = db.collection(coleccion_destino).document(target_doc.id)

        # Aplicar cambios y registrar en auditoría
        update_data = {}
        cambios_aplicados = []

        for campo, valores in campos_modificados.items():
            valor_nuevo = valores.get("nuevo")
            valor_anterior = valores.get("anterior")
            update_data[campo] = valor_nuevo

            # Registrar en auditoría
            try:
                await registrar_cambio_valor(
                    tipo_coleccion=tipo_registro,
                    identificador=referencia_id,
                    campo_modificado=campo,
                    valor_anterior=valor_anterior,
                    valor_nuevo=valor_nuevo,
                    motivo=sol_data.get("motivo")
                    or f"Solicitud de cambio aprobada: {solicitud_id}",
                    usuario="sistema_solicitudes",
                    endpoint_usado=f"/solicitudes_cambios_emprestito/{solicitud_id}/aprobar",
                )
            except Exception as audit_err:
                logger.warning(
                    f"Error registrando auditoría para campo {campo}: {audit_err}"
                )

            cambios_aplicados.append(
                {
                    "campo": campo,
                    "valor_anterior": valor_anterior,
                    "valor_nuevo": valor_nuevo,
                }
            )

        # Aplicar al documento original
        update_data["updated_at"] = datetime.now().isoformat()
        target_ref.update(update_data)

        # Actualizar solicitud
        now_iso = datetime.now().isoformat()
        sol_ref.update(
            {
                "estado": "aprobada",
                "fecha_aprobacion": now_iso,
                "updated_at": now_iso,
            }
        )

        return create_utf8_response(
            {
                "success": True,
                "message": "Solicitud aprobada y cambios aplicados",
                "solicitud_id": solicitud_id,
                "estado": "aprobada",
                "registro_actualizado": {
                    "coleccion": coleccion_destino,
                    "doc_id": target_doc.id,
                    "referencia": referencia_id,
                },
                "cambios_aplicados": cambios_aplicados,
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error aprobando solicitud de cambio: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error aprobando solicitud: {str(e)}"
        )


@router.put(
    "/solicitudes_cambios_emprestito/{solicitud_id}/rechazar",
    tags=["Gestión de Empréstito"],
    summary="[ERROR] Rechazar solicitud de cambio",
)
@optional_rate_limit("10/minute")
async def rechazar_solicitud_cambio_emprestito(
    request: Request,
    solicitud_id: str = Path(..., description="ID de la solicitud a rechazar"),
    motivo_rechazo: str = Body(..., embed=True, description="Motivo del rechazo"),
):
    """
    ## [ERROR] PUT | Rechazar solicitud de cambio de empréstito

    Rechaza una solicitud pendiente con un motivo de rechazo obligatorio.
    No se aplican cambios al registro original.
    """
    if not FIREBASE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Firebase not available")

    try:
        db = get_firestore_client()
        if db is None:
            raise HTTPException(
                status_code=503, detail="No se pudo conectar a Firestore"
            )

        sol_ref = db.collection(SOLICITUDES_EMPRESTITO_COLLECTION).document(
            solicitud_id
        )
        sol_doc = _as_firestore_doc_snapshot(sol_ref.get())

        if not sol_doc.exists:
            raise HTTPException(
                status_code=404, detail=f"Solicitud no encontrada: {solicitud_id}"
            )

        sol_data = sol_doc.to_dict() or {}

        if sol_data.get("estado") != "pendiente":
            raise HTTPException(
                status_code=400,
                detail=f"La solicitud no está pendiente. Estado actual: {sol_data.get('estado')}",
            )

        if not motivo_rechazo or not motivo_rechazo.strip():
            raise HTTPException(status_code=400, detail="motivo_rechazo es obligatorio")

        now_iso = datetime.now().isoformat()
        sol_ref.update(
            {
                "estado": "rechazada",
                "motivo_rechazo": motivo_rechazo.strip(),
                "fecha_rechazo": now_iso,
                "updated_at": now_iso,
            }
        )

        return create_utf8_response(
            {
                "success": True,
                "message": "Solicitud rechazada",
                "solicitud_id": solicitud_id,
                "estado": "rechazada",
                "motivo_rechazo": motivo_rechazo.strip(),
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error rechazando solicitud de cambio: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error rechazando solicitud: {str(e)}"
        )


# ============================================================================
# REPORTES EMPRÉSTITO
# ============================================================================


@router.get(
    "/reportes_emprestito/resumen-centro-gestor",
    tags=["Gestión de Empréstito"],
    summary=" Resumen de empréstito por centro gestor",
)
@optional_rate_limit("30/minute")
async def resumen_emprestito_centro_gestor(request: Request):
    """
    ##  GET | Resumen de empréstito agrupado por centro gestor

    Agrupa: centro gestor → contratos → último avance (desde reportes_contratos).
    Reutiliza la información existente de contratos y reportes.
    """
    if not FIREBASE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Firebase not available")

    try:
        db = get_firestore_client()
        if db is None:
            raise HTTPException(
                status_code=503, detail="No se pudo conectar a Firestore"
            )

        # Cargar contratos
        contratos_docs = list(db.collection("contratos_emprestito").stream())
        contratos_by_centro: Dict[str, list] = {}

        for doc in contratos_docs:
            data = doc.to_dict() or {}
            data["_doc_id"] = doc.id
            centro = (
                data.get("nombre_centro_gestor")
                or data.get("nombreCentroGestor")
                or "Sin centro gestor"
            )
            if isinstance(centro, str):
                centro = centro.strip()
            contratos_by_centro.setdefault(centro, []).append(data)

        # Cargar reportes de contratos (últimos avances)
        reportes_docs = list(db.collection("reportes_contratos").stream())
        reportes_by_referencia: Dict[str, list] = {}

        for doc in reportes_docs:
            data = doc.to_dict() or {}
            data["_doc_id"] = doc.id
            # Normalizar timestamps
            for key, value in data.items():
                if hasattr(value, "isoformat"):
                    data[key] = value.isoformat()
            ref = data.get("referencia_contrato", "")
            reportes_by_referencia.setdefault(ref, []).append(data)

        # Construir resumen
        resumen = []
        for centro, contratos in contratos_by_centro.items():
            centro_data = {
                "nombre_centro_gestor": centro,
                "total_contratos": len(contratos),
                "contratos": [],
            }

            for contrato in contratos:
                ref = contrato.get("referencia_contrato", "")
                reportes = reportes_by_referencia.get(ref, [])
                reportes.sort(key=lambda r: r.get("created_at", ""), reverse=True)
                ultimo_reporte = reportes[0] if reportes else None

                # Normalizar timestamps en contrato
                contrato_clean = {}
                for key, value in contrato.items():
                    if key.startswith("_"):
                        continue
                    if hasattr(value, "isoformat"):
                        contrato_clean[key] = value.isoformat()
                    else:
                        contrato_clean[key] = value

                centro_data["contratos"].append(
                    {
                        "referencia_contrato": ref,
                        "estado_contrato": contrato.get("estado_contrato"),
                        "valor_contrato": contrato.get("valor_contrato"),
                        "contratista": contrato.get("nombre_contratista")
                        or contrato.get("proveedor"),
                        "ultimo_reporte": ultimo_reporte,
                        "total_reportes": len(reportes),
                    }
                )

            resumen.append(centro_data)

        resumen.sort(key=lambda c: c.get("total_contratos", 0), reverse=True)

        return create_utf8_response(
            {
                "success": True,
                "total_centros_gestores": len(resumen),
                "total_contratos": sum(c["total_contratos"] for c in resumen),
                "data": resumen,
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generando resumen por centro gestor: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error generando resumen: {str(e)}"
        )


# ============================================================================
# CRUD DELETE EMPRÉSTITO (endpoints faltantes)
# ============================================================================


@router.delete(
    "/contratos_emprestito/{referencia}",
    tags=["Gestión de Empréstito"],
    summary=" Eliminar contrato de empréstito",
)
@optional_rate_limit("10/minute")
async def eliminar_contrato_emprestito(
    request: Request,
    referencia: str = Path(..., description="Referencia del contrato a eliminar"),
):
    """
    ##  DELETE | Eliminar contrato de empréstito por referencia_contrato

    Busca y elimina el contrato con la referencia indicada de la colección `contratos_emprestito`.
    """
    if not FIREBASE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Firebase not available")

    try:
        db = get_firestore_client()
        if db is None:
            raise HTTPException(
                status_code=503, detail="No se pudo conectar a Firestore"
            )

        referencia = referencia.strip()
        docs = list(
            db.collection("contratos_emprestito")
            .where("referencia_contrato", "==", referencia)
            .limit(1)
            .stream()
        )

        if not docs:
            raise HTTPException(
                status_code=404, detail=f"Contrato no encontrado: {referencia}"
            )

        doc = docs[0]
        doc_data = doc.to_dict() or {}
        db.collection("contratos_emprestito").document(doc.id).delete()

        return create_utf8_response(
            {
                "success": True,
                "message": f"Contrato eliminado: {referencia}",
                "doc_id": doc.id,
                "referencia_contrato": referencia,
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error eliminando contrato: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error eliminando contrato: {str(e)}"
        )


@router.delete(
    "/ordenes_compra_emprestito/{numero_orden}",
    tags=["Gestión de Empréstito"],
    summary=" Eliminar orden de compra",
)
@optional_rate_limit("10/minute")
async def eliminar_orden_compra_emprestito_endpoint(
    request: Request,
    numero_orden: str = Path(
        ..., description="Número de la orden de compra a eliminar"
    ),
):
    """
    ##  DELETE | Eliminar orden de compra de empréstito

    Elimina la orden de compra con el número indicado.
    """
    if not FIREBASE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Firebase not available")

    try:
        check_emprestito_availability()
        resultado = await eliminar_orden_compra_por_numero(numero_orden.strip())

        if not resultado.get("success"):
            if resultado.get("not_found"):
                raise HTTPException(
                    status_code=404,
                    detail=resultado.get("error", "Orden no encontrada"),
                )
            raise HTTPException(
                status_code=500, detail=resultado.get("error", "Error eliminando orden")
            )

        return create_utf8_response(resultado)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error eliminando orden de compra: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error eliminando orden de compra: {str(e)}"
        )


@router.delete(
    "/convenios_emprestito/{referencia}",
    tags=["Gestión de Empréstito"],
    summary=" Eliminar convenio de transferencia",
)
@optional_rate_limit("10/minute")
async def eliminar_convenio_emprestito_endpoint(
    request: Request,
    referencia: str = Path(..., description="Referencia del convenio a eliminar"),
):
    """
    ##  DELETE | Eliminar convenio de transferencia de empréstito

    Elimina el convenio con la referencia indicada.
    """
    if not FIREBASE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Firebase not available")

    try:
        check_emprestito_availability()
        resultado = await eliminar_convenio_transferencia_por_referencia(
            referencia.strip()
        )

        if not resultado.get("success"):
            if resultado.get("not_found"):
                raise HTTPException(
                    status_code=404,
                    detail=resultado.get("error", "Convenio no encontrado"),
                )
            raise HTTPException(
                status_code=500,
                detail=resultado.get("error", "Error eliminando convenio"),
            )

        return create_utf8_response(resultado)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error eliminando convenio: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error eliminando convenio: {str(e)}"
        )


# ============================================================================
# (continúa endpoints existentes)
# ============================================================================


@router.post(
    "/emprestito/obtener-contratos-secop",
    tags=["Gestión de Empréstito"],
    summary=" Obtener Contratos SECOP - SIN LIMITACIONES",
)
async def obtener_contratos_secop_endpoint(offset: int = 0, limit: int = None):
    """
    ##  POST |  Procesamiento por Lotes | Obtener Contratos de SECOP desde Procesos

    Procesa registros de la colección 'procesos_emprestito' en lotes, busca contratos en SECOP
    para cada proceso y guarda los resultados en la nueva colección 'contratos_emprestito'.

    ###  Parámetros opcionales:
    - **offset**: Índice inicial para procesar (default: 0)
    - **limit**: Cantidad de registros a procesar (default: 10, máximo: 50)

    ###  Envío:
    ```http
    POST /emprestito/obtener-contratos-secop?offset=0&limit=10
    ```

    ###  Proceso:
    1. Leer registros de 'procesos_emprestito' desde offset hasta offset+limit
    2. Para cada proceso, extraer referencia_proceso y proceso_contractual
    3. Conectar con la API de SECOP (www.datos.gov.co) para cada proceso
    4. Buscar contratos que contengan el proceso_contractual y NIT = 890399011
    5. Transformar los datos al esquema de la colección 'contratos_emprestito'
    6. Verificar duplicados y actualizar/crear registros en Firebase
    7. Retornar resumen del lote procesado con información de paginación

    ### [OK] Respuesta exitosa:
    ```json
    {
        "success": true,
        "message": "Lote procesado: 10 procesos (offset 0-10)",
        "resumen_procesamiento": {
            "offset": 0,
            "limit": 10,
            "total_procesos_coleccion": 50,
            "procesos_en_lote": 10,
            "procesos_procesados": 9,
            "procesos_sin_contratos": 1,
            "procesos_con_errores": 0,
            "mas_registros": true,
            "siguiente_offset": 10
        },
        "criterios_busqueda": {
            "coleccion_origen": "procesos_emprestito",
            "filtro_secop": "nit_entidad = '890399011'"
        },
        "resultados_secop": {
            "total_contratos_encontrados": 12,
            "total_contratos_procesados": 12
        },
        "firebase_operacion": {
            "documentos_nuevos": 8,
            "documentos_actualizados": 3,
            "duplicados_ignorados": 1
        },
        "contratos_guardados": [
            {
                "referencia_proceso": "4151.010.32.1.0575-2025",
                "proceso_contractual": "CO1.REQ.8485621",
                "sector": "Educación",
                "referencia_contrato": "CONT-001-2025",
                "descripcion_proceso": "Descripción detallada del proceso contractual",
                "estado_contrato": "Activo",
                "valor_contrato": 150000000,
                "valor_pagado": "75000000",
                "representante_legal": "Juan Pérez García",
                "ordenador_gasto": "María López Silva",
                "supervisor": "Carlos Rodríguez Mesa",
                "fecha_firma_contrato": "2025-01-15",
                "entidad_contratante": "MUNICIPIO DE SANTIAGO DE CALI",
                "nombre_contratista": "EMPRESA XYZ LTDA",
                "nit_entidad": "890399011",
                "fuente_datos": "SECOP_API",
                "fecha_guardado": "2025-10-09T..."
            }
        ],
        "procesos_sin_contratos": [],
        "procesos_con_errores": [],
        "timestamp": "2025-10-09T..."
    }
    ```

    ###  Respuesta sin procesos:
    ```json
    {
        "success": false,
        "error": "No se encontraron procesos en la colección procesos_emprestito",
        "timestamp": "2025-10-09T..."
    }
    ```

    ###  Esquema de la colección 'contratos_emprestito':
    ** Campos heredados desde procesos_emprestito:**
    - **referencia_proceso**: Heredado desde procesos_emprestito
    - **banco**: Heredado desde 'nombre_banco' de procesos_emprestito
    - **bp**: Heredado desde procesos_emprestito
    - **nombre_centro_gestor**: Heredado desde procesos_emprestito

    ** Campos desde SECOP API:**
    - **referencia_contrato**: referencia_del_contrato desde SECOP
    - **id_contrato**: Desde SECOP
    - **proceso_contractual**: Mapeado desde 'proceso_de_compra' de SECOP (sobrescribe el heredado)
    - **sector**: Desde SECOP
    - **nombre_procedimiento**: Mapeado desde 'nombre_del_procedimiento' de SECOP
    - **descripcion_proceso**: Mapeado desde 'descripcion_del_proceso' de SECOP
    - **estado_contrato**: Mapeado desde 'estado_contrato' de SECOP
    - **valor_contrato**: Desde SECOP (campo único, sin duplicados)
    - **valor_pagado**: Desde SECOP
    - **representante_legal**: Mapeado desde 'nombre_representante_legal' de SECOP
    - **ordenador_gasto**: Mapeado desde 'nombre_ordenador_del_gasto' de SECOP
    - **supervisor**: Mapeado desde 'nombre_supervisor' de SECOP
    - **bpin**: Mapeado desde 'c_digo_bpin' de SECOP
    - **fecha_firma_contrato**: Desde SECOP
    - **objeto_contrato**: Desde SECOP
    - **modalidad_contratacion**: Desde SECOP
    - **entidad_contratante**: Desde SECOP
    - **nombre_contratista**: Mapeado desde 'nombre_del_contratista' de SECOP
    - **nit_entidad**: Desde SECOP (filtrado por 890399011)
    - **nit_contratista**: Desde SECOP

    ** Metadatos:**
    - **fecha_guardado**: Timestamp de cuando se guardó en Firebase
    - **fuente_datos**: "SECOP_API"
    - **version_esquema**: "1.1"

    ###  Integración SECOP:
    - **API**: www.datos.gov.co
    - **Dataset**: jbjy-vk9h (Contratos)
    - **Filtros**: proceso_de_compra LIKE '%{proceso_contractual}%' AND nit_entidad = '890399011'
    - **Mapeo**: proceso_de_compra → proceso_contractual (sobrescribe valor heredado)
    - **Nuevos campos**: sector desde SECOP
    - **Límite**: 2000 registros por consulta
    """
    try:
        check_emprestito_availability()

        # Si limit es None, procesar TODO sin límite
        if limit is None:
            # Procesar todos los procesos sin limitación
            resultado = await obtener_contratos_desde_proceso_contractual_completo()
        else:
            # Si se especifica limit, mantener comportamiento por lotes
            if limit > 50:
                limit = 50
            if limit < 1:
                limit = 10
            if offset < 0:
                offset = 0
            resultado = await obtener_contratos_desde_proceso_contractual(
                offset=offset, limit=limit
            )

        # Retornar resultado
        return JSONResponse(
            content=resultado,
            status_code=200 if resultado.get("success") else 404,
            headers={"Content-Type": "application/json; charset=utf-8"},
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error en endpoint obtener contratos SECOP: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": "Error interno del servidor",
                "message": "Error obteniendo contratos de SECOP",
                "detalles": str(e),
            },
        )


@router.get(
    "/contratos_emprestito_all",
    tags=["Gestión de Empréstito"],
    summary=" Todos los Contratos Empréstito",
)
@optional_rate_limit("50/minute")  # Máximo 50 requests por minuto
async def obtener_todos_contratos_emprestito(request: Request):
    """
    ##  GET |  Listados | Obtener Todos los Contratos de Empréstito

    **Propósito**: Retorna todos los registros de las colecciones "contratos_emprestito", "ordenes_compra_emprestito" y "convenios_transferencias_emprestito".

    ### [OK] Casos de uso:
    - Obtener listado completo de contratos de empréstito
    - Exportación de datos para análisis
    - Integración con sistemas externos
    - Reportes y dashboards de contratos

    ###  Información incluida:
    - Todos los campos disponibles en las tres colecciones
    - ID del documento para referencia
    - Conteo total de registros y por tipo
    - Timestamp de la consulta

    ###  Colecciones incluidas:
    1. **contratos_emprestito**: Contratos principales
    2. **ordenes_compra_emprestito**: Órdenes de compra
    3. **convenios_transferencias_emprestito**: Convenios de transferencia

    ###  Campos principales:
    - **referencia_contrato**: Referencia del contrato
    - **referencia_proceso**: Proceso de origen
    - **nombre_centro_gestor**: Entidad responsable
    - **banco**: Entidad bancaria
    - **estado_contrato**: Estado actual del contrato
    - **valor_contrato**: Valor del contrato
    - **fecha_firma_contrato**: Fecha de firma
    - **objeto_contrato**: Descripción del objeto
    - **modalidad_contratacion**: Modalidad de contratación
    - **entidad_contratante**: Entidad que contrata
    - **contratista**: Empresa contratista
    - **nombre_resumido_proceso**:  Heredado desde procesos_emprestito
    - **tipo_registro**: Identificador del tipo de registro (convenio_transferencia, contrato, orden)

    ###  Campos heredados desde procesos_emprestito:
    - **nombre_resumido_proceso**: Nombre resumido del proceso obtenido automáticamente usando referencia_proceso

    ###  Ejemplo de uso:
    ```javascript
    const response = await fetch('/contratos_emprestito_all');
    const data = await response.json();
    if (data.success) {
        console.log('Total de registros:', data.count);
        console.log('Contratos:', data.contratos_count);
        console.log('Órdenes:', data.ordenes_count);
        console.log('Convenios:', data.convenios_count);
        console.log('Datos:', data.data);
    }
    ```
    """
    if not FIREBASE_AVAILABLE or not SCRIPTS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Firebase or scripts not available")

    try:
        result = await get_contratos_emprestito_all()

        if not result["success"]:
            raise HTTPException(
                status_code=500,
                detail=f"Error obteniendo contratos de empréstito: {result.get('error', 'Error desconocido')}",
            )

        return create_utf8_response(
            {
                "success": True,
                "data": result["data"],
                "count": result["count"],
                "contratos_count": result["contratos_count"],
                "ordenes_count": result["ordenes_count"],
                "convenios_count": result.get("convenios_count", 0),
                "collections": result["collections"],
                "timestamp": datetime.now().isoformat(),
                "last_updated": "2025-10-10T00:00:00Z",
                "message": result["message"],
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error procesando contratos de empréstito: {str(e)}",
        )


@router.get(
    "/contratos_emprestito/referencia/{referencia_contrato}",
    tags=["Gestión de Empréstito"],
    summary=" Contratos por Referencia",
)
async def obtener_contratos_por_referencia(referencia_contrato: str):
    """
    ##  GET |  Consultas | Obtener Contratos por Referencia

    **Propósito**: Retorna contratos de empréstito filtrados por referencia_contrato específica.

    ### [OK] Casos de uso:
    - Búsqueda de contratos por referencia específica
    - Consulta de detalles de contrato individual
    - Validación de existencia de contrato
    - Integración con sistemas de seguimiento contractual

    ###  Filtrado:
    - **Campo**: `referencia_contrato` (coincidencia exacta)
    - **Tipo**: String - Referencia única del contrato
    - **Sensible a mayúsculas**: Sí

    ###  Información incluida:
    - Todos los campos del contrato que coincida con la referencia
    - ID del documento para referencia
    - Conteo de registros encontrados
    - Información del filtro aplicado

    ###  Ejemplo de uso:
    ```javascript
    const referencia = "CONT-001-2025";
    const response = await fetch(`/contratos_emprestito/${referencia}`);
    const data = await response.json();
    if (data.success && data.count > 0) {
        console.log('Contrato encontrado:', data.data[0]);
    } else {
        console.log('No se encontró contrato con referencia:', referencia);
    }
    ```

    ###  Notas:
    - Si no se encuentra ningún contrato, retorna array vacío
    - La referencia debe ser exacta (sin espacios adicionales)
    - Puede retornar múltiples contratos si hay duplicados
    """
    if not FIREBASE_AVAILABLE or not SCRIPTS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Firebase or scripts not available")

    try:
        result = await get_contratos_emprestito_by_referencia(referencia_contrato)

        if not result["success"]:
            raise HTTPException(
                status_code=500,
                detail=f"Error obteniendo contratos por referencia: {result.get('error', 'Error desconocido')}",
            )

        return create_utf8_response(
            {
                "success": True,
                "data": result["data"],
                "count": result["count"],
                "collection": result["collection"],
                "filter": result["filter"],
                "timestamp": datetime.now().isoformat(),
                "last_updated": "2025-10-10T00:00:00Z",
                "message": result["message"],
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error procesando consulta por referencia de contrato: {str(e)}",
        )


@router.get(
    "/contratos_emprestito/centro-gestor/{nombre_centro_gestor}",
    tags=["Gestión de Empréstito"],
)
async def obtener_contratos_por_centro_gestor(nombre_centro_gestor: str):
    """
    ##  Obtener Contratos de Empréstito por Centro Gestor

    **Propósito**: Retorna contratos de empréstito filtrados por nombre del centro gestor específico.

    ### [OK] Casos de uso:
    - Consulta de contratos por dependencia responsable
    - Reportes por entidad gestora
    - Dashboard por centro de responsabilidad
    - Análisis de distribución institucional
    - Seguimiento de contratos por secretaría/departamento

    ###  Filtrado:
    - **Campo**: `nombre_centro_gestor` (coincidencia exacta)
    - **Tipo**: String - Nombre completo del centro gestor
    - **Sensible a mayúsculas**: Sí
    - **Espacios**: Sensible a espacios adicionales

    ###  Información incluida:
    - Todos los campos de los contratos del centro gestor
    - ID del documento para referencia
    - Conteo de registros encontrados
    - Información del filtro aplicado

    ###  Ejemplo de uso:
    ```javascript
    const centroGestor = "Secretaría de Salud";
    const response = await fetch(`/contratos_emprestito/${encodeURIComponent(centroGestor)}`);
    const data = await response.json();
    if (data.success && data.count > 0) {
        console.log(`${data.count} contratos encontrados para:`, centroGestor);
        const valorTotal = data.data.reduce((sum, c) => sum + (parseFloat(c.valor_contrato) || 0), 0);
        console.log('Valor total:', valorTotal);
    }
    ```

    ###  Notas:
    - Típicamente retorna múltiples contratos por centro gestor
    - El nombre debe ser exacto (use `/centros-gestores/nombres-unicos` para obtener nombres válidos)
    - Para nombres con espacios, usar `encodeURIComponent()` en el frontend
    - Si no se encuentra ningún contrato, retorna array vacío

    ###  Endpoint relacionado:
    - `GET /centros-gestores/nombres-unicos` - Para obtener lista de centros gestores válidos
    """
    if not FIREBASE_AVAILABLE or not SCRIPTS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Firebase or scripts not available")

    try:
        result = await get_contratos_emprestito_by_centro_gestor(nombre_centro_gestor)

        if not result["success"]:
            raise HTTPException(
                status_code=500,
                detail=f"Error obteniendo contratos por centro gestor: {result.get('error', 'Error desconocido')}",
            )

        return create_utf8_response(
            {
                "success": True,
                "data": result["data"],
                "count": result["count"],
                "collection": result["collection"],
                "filter": result["filter"],
                "timestamp": datetime.now().isoformat(),
                "last_updated": "2025-10-10T00:00:00Z",
                "message": result["message"],
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error procesando consulta por centro gestor: {str(e)}",
        )


@router.get("/emprestito/ordenes-compra", tags=["Gestión de Empréstito"])
async def get_ordenes_compra_todas():
    """
    ##  Consultar Todas las Órdenes de Compra Existentes

    **Propósito**: Obtiene todas las órdenes de compra almacenadas en la colección
    `ordenes_compra_emprestito` para revisar los datos disponibles.

    ### [OK] Información que proporciona:
    - **Listado completo**: Todas las órdenes de compra existentes
    - **Campos disponibles**: Estructura de datos actual
    - **Números de orden**: Para debugging del matching con TVEC
    """
    try:
        from api.scripts.ordenes_compra_operations import (
            get_ordenes_compra_emprestito_all,
        )

        resultado = await get_ordenes_compra_emprestito_all()
        return resultado

    except Exception as e:
        logger.error(f"[ERROR] Error consultando órdenes: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Error consultando órdenes: {str(e)}"
        )


@router.post("/emprestito/obtener-ordenes-compra-TVEC", tags=["Gestión de Empréstito"])
async def obtener_ordenes_compra_tvec_endpoint(
    numero_orden: Optional[str] = Query(
        None, description="Filtrar ejecución a una única orden de compra"
    )
):
    """
    ##  Obtener y Enriquecer Órdenes de Compra con Datos de TVEC

    **Propósito**: Enriquece todas las órdenes de compra existentes en la colección
    `ordenes_compra_emprestito` con datos adicionales de la API de TVEC.

    ### [OK] Funcionalidades principales:
    - **Enriquecimiento de datos**: Obtiene datos adicionales de TVEC usando `numero_orden`
    - **Conservación de campos**: Mantiene todos los campos existentes en la colección
    - **Datos adicionales**: Agrega campos con prefijo `tvec_` para datos de la tienda virtual
    - **API Integration**: Usa la API oficial de datos abiertos de Colombia (rgxm-mmea)

    ###  Parámetros opcionales:
    - `numero_orden`: Si se envía, procesa únicamente esa orden.

    ###  Envío:
    ```http
    POST /emprestito/obtener-ordenes-compra-TVEC
    POST /emprestito/obtener-ordenes-compra-TVEC?numero_orden=OC-2024-001
    ```
    **No es necesario enviar ningún cuerpo JSON**.

    ###  Proceso:
    1. Obtener todas las órdenes de la colección `ordenes_compra_emprestito`
    2. Conectar con la API de TVEC (www.datos.gov.co/rgxm-mmea)
    3. Para cada orden, buscar datos adicionales usando `numero_orden`
    4. Enriquecer órdenes con campos adicionales con prefijo `tvec_`
    5. Actualizar registros en Firebase conservando campos originales
    6. Retornar resumen completo del enriquecimiento

    ###  Campos adicionales agregados (estructura similar a contratos):

    **Campos principales (estructura estándar):**
    - `referencia_orden`: Referencia de la orden (similar a referencia_contrato)
    - `id_orden`: Identificador único de la orden (similar a id_contrato)
    - `estado_orden`: Estado de la orden (similar a estado_contrato)
    - `modalidad_contratacion`: Modalidad de la compra (mapeado desde tipo_compra)
    - `tipo_orden`: Tipo de compra (similar a tipo_contrato)
    - `fecha_publicacion_orden`: Fecha de publicación (similar a fecha_firma_contrato)
    - `fecha_vencimiento_orden`: Fecha de vencimiento (similar a fecha_fin_contrato)
    - `entidad_compradora`: Entidad que compra (similar a entidad_contratante)
    - `nombre_proveedor`: Nombre del proveedor (similar a nombre_contratista)
    - `nit_proveedor`: NIT del proveedor (similar a nit_contratista)
    - `descripcion_orden`: Descripción detallada (similar a descripcion_proceso)
    - `objeto_orden`: Objeto de la orden (similar a objeto_contrato)
    - `sector`: Sector/categoría principal
    - `valor_orden`: Valor total como número (similar a valor_contrato)
    - `_dataset_source`: "rgxm-mmea" (similar a "jbjy-vk9h" para contratos)
    - `fuente_datos`: "TVEC_API" (similar a "SECOP_API")
    - `fecha_guardado`: Timestamp de procesamiento
    - `version_esquema`: "1.0" (versión del esquema TVEC)

    **Campos específicos TVEC (con prefijo):**
    - `tvec_agregacion`: Tipo de agregación
    - `tvec_codigo_categoria`: Código de categoría
    - `tvec_unidad_medida`: Unidad de medida
    - `tvec_cantidad`: Cantidad
    - `tvec_precio_unitario`: Precio unitario

    ###  Snippet utilizado:
    El endpoint usa exactamente el snippet proporcionado:
    ```python
    import pandas as pd
    from sodapy import Socrata

    client = Socrata("www.datos.gov.co", None)
    results = client.get("rgxm-mmea", limit=2000)
    results_df = pd.DataFrame.from_records(results)
    ```

    ### [OK] Respuesta exitosa:
    ```json
    {
        "success": true,
        "message": "Enriquecimiento completado: 15/20 órdenes enriquecidas",
        "resumen": {
            "total_ordenes_procesadas": 20,
            "ordenes_enriquecidas": 15,
            "ordenes_sin_datos_tvec": 3,
            "ordenes_con_errores": 2,
            "tasa_enriquecimiento": "75.0%"
        },
        "fuente_datos": {
            "api_tvec": "www.datos.gov.co",
            "dataset": "rgxm-mmea",
            "registros_tvec_disponibles": 1850
        },
        "operacion_firebase": {
            "coleccion": "ordenes_compra_emprestito",
            "documentos_actualizados": 15,
            "campos_preservados": true,
            "campos_agregados_prefijo": "tvec_"
        },
        "ordenes_actualizadas": [
            {
                "doc_id": "abc123",
                "numero_orden": "OC-2024-001",
                "campos_agregados": [
                    "referencia_orden", "estado_orden", "valor_orden",
                    "entidad_compradora", "nombre_proveedor", "nit_proveedor",
                    "descripcion_orden", "objeto_orden", "sector", "_dataset_source",
                    "fuente_datos", "fecha_guardado", "version_esquema"
                ],
                "datos_enriquecidos": {
                    "numero_orden": "OC-2024-001",
                    "referencia_orden": "OC-2024-001",
                    "estado_orden": "Activa",
                    "valor_orden": 1500000,
                    "entidad_compradora": "ALCALDIA DE SANTIAGO DE CALI",
                    "nombre_proveedor": "PROVEEDOR EJEMPLO S.A.S",
                    "nit_proveedor": "900123456-1",
                    "descripcion_orden": "Suministro de equipos tecnológicos",
                    "sector": "Tecnología",
                    "_dataset_source": "rgxm-mmea",
                    "fuente_datos": "TVEC_API",
                    "version_esquema": "1.0"
                }
            }
        ],
        "tiempo_total_segundos": 45.2,
        "timestamp": "2025-10-16T..."
    }
    ```

    ###  Requisitos:
    - Tener órdenes de compra registradas en `ordenes_compra_emprestito`
    - Cada orden debe tener el campo `numero_orden`
    - Conexión a internet para acceder a la API de TVEC
    - Librerías: `sodapy` y `pandas` instaladas

    ###  Características especiales:
    - **Preserva datos originales**: No modifica campos existentes
    - **Prefijo tvec_**: Evita conflictos con campos originales
    - **Matching por numero_orden**: Usa identificador único para relacionar datos
    - **Tolerante a errores**: Continúa procesando aunque algunas órdenes fallen
    - **Sin duplicados**: Solo agrega campos si no existen ya

    ###  Endpoints relacionados:
    - `POST /emprestito/cargar-orden-compra` - Para crear nuevas órdenes
    - `GET /ordenes_compra_emprestito_all` - Para consultar órdenes enriquecidas (si existe)
    """
    # Verificar disponibilidad de servicios
    if not FIREBASE_AVAILABLE or not SCRIPTS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Firebase or scripts not available")

    if not TVEC_ENRICH_OPERATIONS_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail={
                "success": False,
                "error": "TVEC enrich operations not available",
                "message": "Las operaciones de enriquecimiento TVEC no están disponibles",
                "requirements": [
                    "pip install sodapy pandas",
                    "Verificar conectividad a internet",
                    "Confirmar acceso a www.datos.gov.co",
                ],
                "code": "TVEC_SERVICES_UNAVAILABLE",
            },
        )

    try:
        # Ejecutar enriquecimiento de órdenes de compra con datos de TVEC
        resultado = await obtener_ordenes_compra_tvec_enriquecidas(
            numero_orden=numero_orden
        )

        # Determinar código de estado basado en el resultado
        status_code = 200 if resultado.get("success") else 500

        # Retornar resultado con información detallada
        return JSONResponse(
            content={
                **resultado,
                "api_info": {
                    "endpoint_name": "obtener-ordenes-compra-TVEC",
                    "version": "1.0",
                    "snippet_based": True,
                    "preserves_original_data": True,
                },
                "last_updated": "2025-10-16T00:00:00Z",
            },
            status_code=status_code,
            headers={"Content-Type": "application/json; charset=utf-8"},
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error en endpoint TVEC enriquecimiento: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": "Error interno del servidor",
                "message": "Error ejecutando enriquecimiento con datos de TVEC",
                "detalles": str(e),
                "code": "TVEC_INTERNAL_ERROR",
            },
        )


@router.get("/procesos_emprestito_all", tags=["Gestión de Empréstito"])
async def get_all_procesos_emprestito():
    """
    ## Obtener Todos los Procesos de Empréstito

    **Propósito**: Retorna todo el contenido de la colección "procesos_emprestito" en Firebase.

    ### [OK] Casos de uso:
    - Obtener listado completo de procesos de empréstito
    - Exportación de datos para análisis
    - Integración con sistemas externos
    - Reportes y dashboards de procesos
    - Monitoreo del estado de procesos

    ###  Información incluida:
    - Todos los campos disponibles en la colección
    - ID del documento para referencia
    - Conteo total de registros
    - Timestamp de la consulta
    - Datos serializados correctamente para JSON

    ###  Campos principales esperados:
    - **referencia_proceso**: Referencia única del proceso
    - **nombre_centro_gestor**: Entidad responsable
    - **nombre_banco**: Entidad bancaria
    - **plataforma**: SECOP, SECOP II, TVEC, etc.
    - **bp**: Código de proyecto base
    - **proceso_contractual**: Código del proceso contractual
    - **nombre_proceso**: Nombre del procedimiento
    - **estado_proceso**: Estado actual del proceso
    - **valor_publicacion**: Valor del proceso
    - **fecha_publicacion**: Fecha de publicación
    - **nombre_resumido_proceso**: Nombre resumido (opcional)
    - **id_paa**: ID del PAA (opcional)
    - **valor_proyectado**: Valor proyectado (opcional)

    ###  Ejemplo de uso:
    ```javascript
    const response = await fetch('/procesos_emprestito_all');
    const data = await response.json();
    if (data.success) {
        console.log('Procesos encontrados:', data.count);
        console.log('Datos:', data.data);

        // Filtrar por estado
        const activos = data.data.filter(p => p.estado_proceso === 'Activo');

        // Sumar valores
        const valorTotal = data.data.reduce((sum, p) => sum + (p.valor_publicacion || 0), 0);
    }
    ```

    ###  Características:
    - **Serialización**: Datos de Firebase convertidos correctamente a JSON
    - **UTF-8**: Soporte completo para caracteres especiales
    - **Fechas**: Timestamps convertidos a formato ISO
    - **Performance**: Consulta optimizada de toda la colección
    - **Consistencia**: Estructura de datos uniforme

    ###  Endpoints relacionados:
    - `POST /emprestito/cargar-proceso` - Para crear nuevos procesos
    - `GET /contratos_emprestito_all` - Para consultar contratos relacionados
    """
    if not FIREBASE_AVAILABLE or not SCRIPTS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Firebase or scripts not available")

    if not EMPRESTITO_OPERATIONS_AVAILABLE:
        raise HTTPException(
            status_code=503, detail="Emprestito operations not available"
        )

    try:
        result = await get_procesos_emprestito_all()

        if not result["success"]:
            raise HTTPException(
                status_code=500,
                detail=f"Error obteniendo procesos de empréstito: {result.get('error', 'Error desconocido')}",
            )

        return create_utf8_response(
            {
                "success": True,
                "data": result["data"],
                "count": result["count"],
                "collection": result["collection"],
                "timestamp": result["timestamp"],
                "last_updated": "2025-10-18T00:00:00Z",  # Endpoint creation date
                "message": result["message"],
                "metadata": {
                    "data_serialized": True,
                    "utf8_enabled": True,
                    "spanish_support": True,
                    "firebase_timestamps_converted": True,
                    "purpose": "Complete procesos_emprestito collection data",
                },
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error procesando consulta de procesos de empréstito: {str(e)}",
        )


@router.get(
    "/emprestito/obtener-procesos-bp",
    tags=["Gestión de Empréstito"],
    summary=" Obtener Procesos BP",
)
async def obtener_procesos_bp():
    """
    ## Obtener Procesos de Empréstito - Campos Básicos BP

    **Propósito**: Retorna datos específicos de la colección "procesos_emprestito" optimizados para visualización.

    ### [OK] Casos de uso:
    - Listado de procesos para dashboards
    - Exportación simplificada de datos
    - Integración con sistemas externos
    - Reportes básicos de procesos

    ###  Campos incluidos:
    - **bp**: Código de proyecto base
    - **banco**: Entidad bancaria
    - **nombre_centro_gestor**: Entidad responsable
    - **nombre_resumido_proceso**: Nombre resumido del proceso
    - **tipo_contrato**: Tipo de contrato
    - **urlproceso**: URL del proceso
    - **valor_publicacion**: Valor del proceso

    ###  Ejemplo de uso:
    ```javascript
    const response = await fetch('/emprestito/obtener-procesos-bp');
    const data = await response.json();
    if (data.success) {
        console.log('Procesos encontrados:', data.count);
        data.data.forEach(proceso => {
            console.log(`BP: ${proceso.bp}, Banco: ${proceso.banco}`);
        });
    }
    ```

    ###  Características:
    - **Optimizado**: Solo campos necesarios para reducir payload
    - **UTF-8**: Soporte completo para caracteres especiales
    """
    if not FIREBASE_AVAILABLE or not SCRIPTS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Firebase or scripts not available")

    try:
        db = get_firestore_client()
        if db is None:
            raise HTTPException(
                status_code=503, detail="No se pudo conectar a Firestore"
            )

        collection_ref = db.collection("procesos_emprestito")
        docs = collection_ref.stream()
        procesos_data = []

        for doc in docs:
            doc_data = doc.to_dict()
            # Extraer solo los campos solicitados
            proceso_filtrado = {
                "bp": doc_data.get("bp", ""),
                "banco": doc_data.get("nombre_banco", ""),
                "nombre_centro_gestor": doc_data.get("nombre_centro_gestor", ""),
                "nombre_resumido_proceso": doc_data.get("nombre_resumido_proceso", ""),
                "tipo_contrato": doc_data.get("tipo_contrato", ""),
                "urlproceso": doc_data.get("urlproceso", ""),
                "valor_publicacion": doc_data.get("valor_publicacion", 0),
            }
            procesos_data.append(proceso_filtrado)

        return create_utf8_response(
            {
                "success": True,
                "data": procesos_data,
                "count": len(procesos_data),
                "collection": "procesos_emprestito",
                "timestamp": datetime.now().isoformat(),
                "message": f"Se obtuvieron {len(procesos_data)} procesos exitosamente",
                "metadata": {
                    "fields": [
                        "bp",
                        "banco",
                        "nombre_centro_gestor",
                        "nombre_resumido_proceso",
                        "tipo_contrato",
                        "urlproceso",
                        "valor_publicacion",
                    ],
                    "utf8_enabled": True,
                    "spanish_support": True,
                },
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error obteniendo procesos BP: {str(e)}"
        )


@router.get(
    "/emprestito/obtener-contratos-bp",
    tags=["Gestión de Empréstito"],
    summary=" Obtener Contratos BP",
)
async def obtener_contratos_bp():
    """
    ## Obtener Contratos de Empréstito - Campos Básicos BP

    **Propósito**: Retorna datos específicos de las tres colecciones de empréstito optimizados para visualización.

    ###  Colecciones incluidas:
    1. **contratos_emprestito**: Contratos principales
    2. **ordenes_compra_emprestito**: Órdenes de compra
    3. **convenios_transferencias_emprestito**: Convenios de transferencia

    ### [OK] Casos de uso:
    - Listado de contratos para dashboards
    - Exportación simplificada de datos de contratos
    - Integración con sistemas externos
    - Reportes básicos de contratos
    - Seguimiento de vigencias contractuales

    ###  Campos incluidos:
    - **bp**: Código de proyecto base
    - **banco**: Entidad bancaria
    - **nombre_centro_gestor**: Entidad responsable
    - **nombre_resumido_proceso**: Nombre resumido del proceso
    - **tipo_contrato**: Tipo de contrato
    - **urlproceso**: URL del proceso
    - **valor_contrato**: Valor del contrato
    - **fecha_inicio_contrato**: Fecha de inicio del contrato
    - **fecha_fin_contrato**: Fecha de finalización del contrato
    - **sector**: Sector del contrato

    ###  Ejemplo de uso:
    ```javascript
    const response = await fetch('/emprestito/obtener-contratos-bp');
    const data = await response.json();
    if (data.success) {
        console.log('Registros encontrados:', data.count);
        console.log('Contratos:', data.contratos_count);
        console.log('Órdenes:', data.ordenes_count);
        console.log('Convenios:', data.convenios_count);
        data.data.forEach(contrato => {
            console.log(`BP: ${contrato.bp}, Banco: ${contrato.banco}`);
            console.log(`Valor: ${contrato.valor_contrato}`);
            console.log(`Vigencia: ${contrato.fecha_inicio_contrato} - ${contrato.fecha_fin_contrato}`);
        });
    }
    ```

    ###  Características:
    - **Optimizado**: Solo campos necesarios para reducir payload
    - **UTF-8**: Soporte completo para caracteres especiales
    - **Cache**: Datos cacheados por 5 minutos para mejor performance
    - **Fechas**: Incluye información de vigencia contractual
    - **Multi-colección**: Combina datos de las tres colecciones de empréstito
    """
    if not FIREBASE_AVAILABLE or not SCRIPTS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Firebase or scripts not available")

    try:
        db = get_firestore_client()
        if db is None:
            raise HTTPException(
                status_code=503, detail="No se pudo conectar a Firestore"
            )

        # Función auxiliar para extraer los campos solicitados
        def extraer_campos_bp(doc_data: dict) -> dict:
            """Extrae solo los campos solicitados manteniendo la estructura BP"""
            return {
                "bp": doc_data.get("bp", ""),
                "banco": doc_data.get("banco", ""),
                "nombre_centro_gestor": doc_data.get("nombre_centro_gestor", ""),
                "nombre_resumido_proceso": doc_data.get("nombre_resumido_proceso", ""),
                "tipo_contrato": doc_data.get("tipo_contrato", ""),
                "urlproceso": doc_data.get("urlproceso", ""),
                "valor_contrato": doc_data.get("valor_contrato", 0),
                "fecha_inicio_contrato": doc_data.get("fecha_inicio_contrato", ""),
                "fecha_fin_contrato": doc_data.get("fecha_fin_contrato", ""),
                "sector": doc_data.get("sector", ""),
            }

        # Lista para almacenar todos los datos combinados
        todos_los_datos = []

        # 1. Obtener contratos_emprestito
        collection_ref = db.collection("contratos_emprestito")
        docs = collection_ref.stream()
        contratos_count = 0

        for doc in docs:
            doc_data = doc.to_dict()
            contrato_filtrado = extraer_campos_bp(doc_data)
            todos_los_datos.append(contrato_filtrado)
            contratos_count += 1

        # 2. Obtener ordenes_compra_emprestito
        ordenes_ref = db.collection("ordenes_compra_emprestito")
        ordenes_docs = ordenes_ref.stream()
        ordenes_count = 0

        for doc in ordenes_docs:
            doc_data = doc.to_dict()
            # Mapear campos de órdenes de compra al formato BP
            orden_mapeada = {
                "bp": doc_data.get("bp", ""),
                "banco": doc_data.get(
                    "nombre_banco", ""
                ),  # Mapear nombre_banco a banco
                "nombre_centro_gestor": doc_data.get("nombre_centro_gestor", ""),
                "nombre_resumido_proceso": doc_data.get("nombre_resumido_proceso", ""),
                "tipo_contrato": doc_data.get(
                    "tipo_contrato", "Orden de Compra - TVEC"
                ),
                "urlproceso": doc_data.get("urlproceso", ""),
                "valor_contrato": (
                    int(float(doc_data.get("valor_orden", 0)))
                    if doc_data.get("valor_orden")
                    else 0
                ),
                "fecha_inicio_contrato": doc_data.get("fecha_publicacion_orden", ""),
                "fecha_fin_contrato": doc_data.get("fecha_vencimiento_orden", ""),
                "sector": doc_data.get("sector", ""),
            }
            todos_los_datos.append(orden_mapeada)
            ordenes_count += 1

        # 3. Obtener convenios_transferencias_emprestito
        convenios_ref = db.collection("convenios_transferencias_emprestito")
        convenios_docs = convenios_ref.stream()
        convenios_count = 0

        for doc in convenios_docs:
            doc_data = doc.to_dict()
            convenio_filtrado = extraer_campos_bp(doc_data)
            todos_los_datos.append(convenio_filtrado)
            convenios_count += 1

        return create_utf8_response(
            {
                "success": True,
                "data": todos_los_datos,
                "count": len(todos_los_datos),
                "contratos_count": contratos_count,
                "ordenes_count": ordenes_count,
                "convenios_count": convenios_count,
                "collections": [
                    "contratos_emprestito",
                    "ordenes_compra_emprestito",
                    "convenios_transferencias_emprestito",
                ],
                "timestamp": datetime.now().isoformat(),
                "message": f"Se obtuvieron {contratos_count} contratos, {ordenes_count} órdenes de compra y {convenios_count} convenios de transferencia exitosamente ({len(todos_los_datos)} registros totales)",
                "metadata": {
                    "fields": [
                        "bp",
                        "banco",
                        "nombre_centro_gestor",
                        "nombre_resumido_proceso",
                        "tipo_contrato",
                        "urlproceso",
                        "valor_contrato",
                        "fecha_inicio_contrato",
                        "fecha_fin_contrato",
                        "sector",
                    ],
                    "utf8_enabled": True,
                    "spanish_support": True,
                },
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error obteniendo contratos BP: {str(e)}"
        )


@router.get(
    "/ordenes_compra_emprestito/numero/{numero_orden}", tags=["Gestión de Empréstito"]
)
async def obtener_ordenes_por_numero(numero_orden: str):
    """
    ##  Obtener Órdenes de Compra por Número de Orden

    **Propósito**: Retorna órdenes de compra filtradas por número de orden específico.

    ### [OK] Casos de uso:
    - Búsqueda de órdenes por número específico
    - Consulta de detalles de orden individual
    - Validación de existencia de orden
    - Verificar datos enriquecidos de una orden específica

    ###  Filtrado:
    - **Campo**: `numero_orden` (coincidencia exacta)
    - **Tipo**: String - Número único de la orden
    - **Sensible a mayúsculas**: Sí

    ###  Información incluida:
    - Todos los campos de las órdenes que coincidan con el número
    - Datos enriquecidos de TVEC (si están disponibles)
    - ID del documento para referencia
    - Información del filtro aplicado

    ###  Ejemplo de uso:
    ```javascript
    const numeroOrden = "OC-2024-001";
    const response = await fetch(`/ordenes_compra_emprestito/numero/${numeroOrden}`);
    const data = await response.json();
    if (data.success && data.count > 0) {
        const orden = data.data[0];
        console.log('Orden encontrada:', orden.numero_orden);
        if (orden._dataset_source === 'rgxm-mmea') {
            console.log('Orden enriquecida con TVEC:', orden.valor_orden);
        }
    }
    ```
    """
    if not FIREBASE_AVAILABLE or not SCRIPTS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Firebase or scripts not available")

    try:
        result = await get_ordenes_compra_emprestito_by_referencia(numero_orden)

        if not result["success"]:
            raise HTTPException(
                status_code=500,
                detail=f"Error obteniendo órdenes por número: {result.get('error', 'Error desconocido')}",
            )

        return create_utf8_response(
            {
                "success": True,
                "data": result["data"],
                "count": result["count"],
                "collection": result["collection"],
                "filter": result["filter"],
                "timestamp": datetime.now().isoformat(),
                "last_updated": "2025-10-16T00:00:00Z",
                "message": result["message"],
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error procesando consulta por número de orden: {str(e)}",
        )


@router.get(
    "/ordenes_compra_emprestito/centro-gestor/{nombre_centro_gestor}",
    tags=["Gestión de Empréstito"],
)
async def obtener_ordenes_por_centro_gestor(nombre_centro_gestor: str):
    """
    ##  Obtener Órdenes de Compra por Centro Gestor

    **Propósito**: Retorna órdenes de compra filtradas por nombre del centro gestor específico.

    ### [OK] Casos de uso:
    - Consulta de órdenes por dependencia responsable
    - Reportes por entidad gestora
    - Dashboard por centro de responsabilidad
    - Análisis de distribución institucional de órdenes de compra

    ###  Filtrado:
    - **Campo**: `nombre_centro_gestor` (coincidencia exacta)
    - **Tipo**: String - Nombre completo del centro gestor
    - **Sensible a mayúsculas**: Sí

    ###  Información incluida:
    - Todas las órdenes del centro gestor especificado
    - Datos enriquecidos de TVEC (si están disponibles)
    - Conteo de registros encontrados
    - Información del filtro aplicado

    ###  Ejemplo de uso:
    ```javascript
    const centroGestor = "Secretaría de Salud";
    const response = await fetch(`/ordenes_compra_emprestito/centro-gestor/${encodeURIComponent(centroGestor)}`);
    const data = await response.json();
    if (data.success && data.count > 0) {
        console.log(`${data.count} órdenes encontradas para:`, centroGestor);
        const valorTotal = data.data.reduce((sum, o) => sum + (o.valor_orden || 0), 0);
        console.log('Valor total de órdenes:', valorTotal);
    }
    ```
    """
    if not FIREBASE_AVAILABLE or not SCRIPTS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Firebase or scripts not available")

    try:
        result = await get_ordenes_compra_emprestito_by_centro_gestor(
            nombre_centro_gestor
        )

        if not result["success"]:
            raise HTTPException(
                status_code=500,
                detail=f"Error obteniendo órdenes por centro gestor: {result.get('error', 'Error desconocido')}",
            )

        return create_utf8_response(
            {
                "success": True,
                "data": result["data"],
                "count": result["count"],
                "collection": result["collection"],
                "filter": result["filter"],
                "timestamp": datetime.now().isoformat(),
                "last_updated": "2025-10-16T00:00:00Z",
                "message": result["message"],
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error procesando consulta por centro gestor: {str(e)}",
        )


@router.post("/emprestito/obtener-procesos-secop", tags=["Gestión de Empréstito"])
async def obtener_procesos_secop_completo_endpoint():
    """
    ##  Obtener y Actualizar Datos Completos de SECOP para Todos los Procesos

    Endpoint para complementar los datos de TODA la colección "procesos_emprestito" con información
    adicional desde la API de SECOP, sin alterar los campos existentes ni los nombres de variables.

    ### [OK] Funcionalidades principales:
    - **Procesamiento masivo**: Actualiza TODOS los procesos de la colección automáticamente
    - **Actualización selectiva**: Solo actualiza campos que han cambiado por proceso
    - **Preservación de datos**: Mantiene todos los campos existentes intactos
    - **Mapeo desde SECOP**: Obtiene datos adicionales usando la API oficial
    - **Sin parámetros**: Lee automáticamente todas las referencias_proceso de Firebase

    ###  Campos que se actualizan/complementan:
    **Campos básicos:**
    - `adjudicado` ← adjudicado (SECOP)
    - `fase` ← fase (SECOP)
    - `estado_proceso` ← estado_del_procedimiento (SECOP)

    **Campos adicionales agregados:**
    - `fecha_publicacion_fase` ← fecha_de_publicacion_del (SECOP)
    - `fecha_publicacion_fase_1` ← null (no disponible en SECOP)
    - `fecha_publicacion_fase_2` ← null (no disponible en SECOP)
    - `fecha_publicacion_fase_3` ← fecha_de_publicacion_fase_3 (SECOP)
    - `proveedores_invitados` ← proveedores_invitados (SECOP)
    - `proveedores_con_invitacion` ← proveedores_con_invitacion (SECOP)
    - `visualizaciones_proceso` ← visualizaciones_del (SECOP)
    - `proveedores_que_manifestaron` ← proveedores_que_manifestaron (SECOP)
    - `numero_lotes` ← numero_de_lotes (SECOP)
    - `fecha_adjudicacion` ← null (no disponible en SECOP)
    - `estado_resumen` ← estado_resumen (SECOP)
    - `fecha_recepcion_respuestas` ← null (no disponible en SECOP)
    - `fecha_apertura_respuestas` ← null (no disponible en SECOP)
    - `fecha_apertura_efectiva` ← null (no disponible en SECOP)
    - `respuestas_procedimiento` ← respuestas_al_procedimiento (SECOP)
    - `respuestas_externas` ← respuestas_externas (SECOP)
    - `conteo_respuestas_ofertas` ← conteo_de_respuestas_a_ofertas (SECOP)

    ###  Validaciones:
    - Verificar que el proceso existe en la colección `procesos_emprestito`
    - Conectar con API de SECOP usando la referencia_proceso
    - Solo actualizar si hay cambios reales en los datos
    - Mantener estructura de variables sin cambios

    ###  Ejemplo de request:
    ```http
    POST /emprestito/obtener-procesos-secop
    ```
    **No requiere parámetros - procesamiento automático**

    ### [OK] Respuesta exitosa:
    ```json
    {
        "success": true,
        "message": "Se procesaron 5 procesos de empréstito exitosamente",
        "resumen_procesamiento": {
            "total_procesos_encontrados": 5,
            "procesos_procesados": 4,
            "procesos_actualizados": 3,
            "procesos_sin_cambios": 1,
            "procesos_con_errores": 1
        },
        "resultados_detallados": [
            {
                "referencia_proceso": "4163.001.32.1.718-2024",
                "success": true,
                "changes_count": 8,
                "changes_summary": [
                    "adjudicado: 'No' → 'Sí'",
                    "estado_proceso: 'En evaluación' → 'Seleccionado'"
                ]
            },
            {
                "referencia_proceso": "4164.001.32.1.719-2024",
                "success": true,
                "changes_count": 0,
                "message": "Ya está actualizado"
            }
        ],
        "estadisticas": {
            "total_campos_actualizados": 25,
            "tiempo_procesamiento": "45.2 segundos"
        },
        "timestamp": "2024-10-18T..."
    }
    ```

    ###  Respuesta sin procesos:
    ```json
    {
        "success": false,
        "error": "No se encontraron procesos en la colección procesos_emprestito",
        "total_procesos_encontrados": 0
    }
    ```

    ###  API de SECOP utilizada:
    - **Dominio**: www.datos.gov.co
    - **Dataset**: p6dx-8zbt (Procesos de contratación)
    - **Filtro**: nit_entidad='890399011' AND referencia_del_proceso='{referencia_proceso}'

    ### ⏱ Tiempo de procesamiento:
    - **Timeout extendido**: 5 minutos (300 segundos)
    - **Tiempo estimado**: ~10-15 segundos por proceso
    - **Progreso**: Se reporta en logs con ETA para procesos restantes
    - **Recomendación**: Monitor logs del servidor para ver progreso en tiempo real
    """
    try:
        check_emprestito_availability()

        # Procesar todos los procesos de empréstito automáticamente
        resultado = await procesar_todos_procesos_emprestito_completo()

        # Manejar respuesta según el resultado
        if not resultado.get("success"):
            # Si no se encontraron procesos
            if "No se encontraron procesos" in resultado.get("error", ""):
                raise HTTPException(status_code=404, detail=resultado)
            else:
                # Otros errores
                raise HTTPException(status_code=500, detail=resultado)

        # Respuesta exitosa
        return JSONResponse(
            content=resultado,
            status_code=200,
            headers={"Content-Type": "application/json; charset=utf-8"},
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error en endpoint obtener procesos SECOP completo: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": "Error interno del servidor",
                "message": "Error obteniendo datos completos de SECOP para todos los procesos",
            },
        )


@router.get(
    "/asignaciones-emprestito-banco-centro-gestor",
    tags=["Gestión de Empréstito"],
    summary=" Obtener Asignaciones Banco-Centro Gestor",
)
async def get_all_asignaciones_emprestito_banco_centro_gestor():
    """
    ##  GET |  Consultas | Obtener Todas las Asignaciones de Empréstito Banco-Centro Gestor

    Endpoint para obtener todas las asignaciones de montos de empréstito por banco y centro gestor
    almacenadas en la colección `montos_emprestito_asignados_centro_gestor`.

    ### [OK] Funcionalidades principales:
    - **Listado completo**: Retorna todas las asignaciones registradas
    - **Datos completos**: Incluye todos los campos de cada asignación
    - **Metadatos**: Incluye ID del documento, conteo total y timestamp

    ###  Información incluida:
    - Todos los campos de la asignación
    - ID del documento para referencia
    - Conteo total de registros
    - Timestamp de la consulta

    ###  Campos principales esperados:
    - **banco**: Nombre del banco financiador
    - **nombre_centro_gestor**: Nombre del centro gestor
    - **bp**: Código del proyecto presupuestal (BP)
    - **monto_programado**: Monto programado para el banco y centro gestor
    - **anio**: Año de la asignación
    - **created_at**: Fecha de creación del registro
    - **updated_at**: Fecha de última actualización
    - **data_hash**: Hash para control de duplicados

    ### [OK] Respuesta exitosa (200):
    ```json
    {
        "success": true,
        "data": [
            {
                "id": "BBVA_BP26004701_2026",
                "banco": "BBVA",
                "nombre_centro_gestor": "Secretaría de Educación",
                "bp": "BP26004701",
                "monto_programado": 1500000.00,
                "anio": 2026,
                "created_at": "2024-11-17T...",
                "updated_at": "2024-11-17T...",
                "data_hash": "abc123..."
            }
        ],
        "count": 83,
        "collection": "montos_emprestito_asignados_centro_gestor",
        "timestamp": "2024-11-17T...",
        "message": "Se obtuvieron 83 asignaciones de empréstito banco-centro gestor exitosamente"
    }
    ```
    """
    try:
        check_emprestito_availability()

        result = await get_asignaciones_emprestito_banco_centro_gestor_all()

        if not result["success"]:
            raise HTTPException(
                status_code=500,
                detail=f"Error obteniendo asignaciones de empréstito banco-centro gestor: {result.get('error', 'Error desconocido')}",
            )

        return JSONResponse(
            content={
                "success": True,
                "data": result["data"],
                "count": result["count"],
                "collection": result["collection"],
                "timestamp": result["timestamp"],
                "message": f"Se obtuvieron {result['count']} asignaciones de empréstito banco-centro gestor exitosamente",
            },
            status_code=200,
            headers={"Content-Type": "application/json; charset=utf-8"},
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Error en endpoint de asignaciones de empréstito banco-centro gestor: {e}"
        )
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": "Error interno del servidor",
                "message": "Error al obtener asignaciones de empréstito banco-centro gestor",
                "code": "INTERNAL_SERVER_ERROR",
            },
        )


# ============================================================================
# ENDPOINTS DE FLUJO DE CAJA EMPRÉSTITO
# ============================================================================


@router.post(
    "/emprestito/flujo-caja/cargar-excel",
    tags=["Gestión de Empréstito"],
    summary=" Cargar Flujos de Caja Excel",
)
async def cargar_flujo_caja_excel(
    archivo_excel: UploadFile = File(
        ..., description="Archivo Excel con flujos de caja"
    ),
    update_mode: str = Form(
        default="merge", description="Modo de actualización: merge, replace, append"
    ),
):
    """
    ##  POST |  Carga de Archivos | Cargar Flujos de Caja desde Excel

    Endpoint para procesar archivos Excel con información de flujos de caja de proyectos
    y cargarlos en la colección "flujo_caja_emprestito".

    ###  Archivo Excel esperado:
    - **Hoja**: "CONTRATOS - Seguimiento"
    - **Columnas requeridas**: Responsable, Organismo, Banco, BP Proyecto, Descripcion BP
    - **Columnas de datos**: Todas las columnas que contengan "Desembolso" en su nombre
    - **Formato de fechas**: Las columnas de desembolso deben contener fechas como jul-25, ago-25, etc.

    ###  Modos de actualización:
    - **merge**: Actualiza existentes y crea nuevos (por defecto)
    - **replace**: Reemplaza toda la colección
    - **append**: Solo agrega nuevos registros

    ###  Procesamiento:
    1. Lee datos del Excel
    2. Separa columnas de Desembolso normal y REAL
    3. Convierte a formato largo (un registro por mes)
    4. Crea campo Periodo en formato fecha
    5. Guarda en Firebase con ID único por organismo_banco_mes

    ###  Cómo usar:
    1. Selecciona archivo .xlsx con formato correcto
    2. Elige modo de actualización
    3. Haz clic en "Execute"

    ### [OK] Validaciones:
    - Solo archivos .xlsx
    - Columnas Organismo y Banco requeridas
    - Al menos una columna de Desembolso
    - Tamaño máximo: 10MB
    """
    if not FIREBASE_AVAILABLE or not SCRIPTS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Firebase o scripts no disponibles")

    if not FLUJO_CAJA_OPERATIONS_AVAILABLE:
        raise HTTPException(
            status_code=503, detail="Operaciones de flujo de caja no disponibles"
        )

    # Validar modo de actualización
    if update_mode not in ["merge", "replace", "append"]:
        raise HTTPException(
            status_code=400, detail="update_mode debe ser: merge, replace o append"
        )

    # Validar tipo de archivo
    if not archivo_excel.filename.lower().endswith((".xlsx", ".xls")):
        raise HTTPException(
            status_code=400, detail="Solo se permiten archivos Excel (.xlsx, .xls)"
        )

    # Validar tamaño del archivo (10MB máximo)
    max_size = 10 * 1024 * 1024  # 10MB
    file_content = await archivo_excel.read()
    if len(file_content) > max_size:
        raise HTTPException(status_code=400, detail="El archivo no puede exceder 10MB")

    try:
        # Procesar el archivo Excel
        result = process_flujo_caja_excel(file_content, archivo_excel.filename)

        if not result["success"]:
            raise HTTPException(
                status_code=400, detail=result.get("error", "Error procesando Excel")
            )

        # Guardar en Firebase
        save_result = await save_flujo_caja_to_firebase(result["data"], update_mode)

        if not save_result["success"]:
            raise HTTPException(
                status_code=500,
                detail=save_result.get("error", "Error guardando en Firebase"),
            )

        # Combinar resultados
        final_result = {
            "success": True,
            "message": "Flujos de caja cargados exitosamente",
            "archivo_info": {
                "nombre_archivo": archivo_excel.filename,
                "tamaño_bytes": len(file_content),
                "modo_actualizacion": update_mode,
            },
            "procesamiento": result["summary"],
            "guardado": save_result["summary"],
            "timestamp": datetime.now().isoformat(),
            "last_updated": "2025-10-20T00:00:00Z",
        }

        return create_utf8_response(final_result)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")


@router.get(
    "/emprestito/flujo-caja/all",
    tags=["Gestión de Empréstito"],
    summary=" Flujos de Caja",
)
async def get_flujos_caja_all(
    responsable: Optional[str] = Query(
        None, description="Filtrar por responsable específico"
    ),
    organismo: Optional[str] = Query(
        None, description="Filtrar por organismo específico"
    ),
    banco: Optional[str] = Query(None, description="Filtrar por banco específico"),
    bp_proyecto: Optional[str] = Query(
        None, description="Filtrar por BP Proyecto específico"
    ),
    mes: Optional[str] = Query(
        None, description="Filtrar por mes específico (ej: jul-25)"
    ),
    periodo_desde: Optional[str] = Query(
        None, description="Periodo desde (formato: YYYY-MM-DD)"
    ),
    periodo_hasta: Optional[str] = Query(
        None, description="Periodo hasta (formato: YYYY-MM-DD)"
    ),
    limit: Optional[int] = Query(
        None, ge=1, le=1000, description="Límite de registros"
    ),
):
    """
    ##  GET |  Consultas con Filtros | Obtener Todos los Flujos de Caja

    Endpoint para consultar flujos de caja almacenados en la colección "flujo_caja_emprestito".

    ### [OK] Casos de uso:
    - Consultar flujos de caja por organismo o banco
    - Filtrar por períodos específicos
    - Analizar desembolsos planeados vs reales
    - Generar reportes de flujo de caja
    - Exportar datos para dashboards

    ###  Filtros disponibles:
    - **responsable**: Filtrar por responsable específico
    - **organismo**: Filtrar por organismo específico
    - **banco**: Filtrar por banco específico
    - **bp_proyecto**: Filtrar por BP Proyecto específico
    - **mes**: Filtrar por mes específico (ej: "jul-25")
    - **periodo_desde**: Desde fecha específica (YYYY-MM-DD)
    - **periodo_hasta**: Hasta fecha específica (YYYY-MM-DD)
    - **limit**: Limitar número de resultados (máx: 1000)

    ###  Información incluida:
    - Responsable, organismo, banco y BP proyecto
    - Descripción del BP proyecto
    - Mes y período en formato fecha
    - Monto de desembolso
    - Columna origen del Excel
    - ID único del registro y metadatos de archivo origen

    ###  Ejemplo de uso:
    ```javascript
    // Obtener todos los flujos
    const response = await fetch('/emprestito/flujo-caja/all');

    // Filtrar por banco específico
    const response = await fetch('/emprestito/flujo-caja/all?banco=Banco Popular');

    // Filtrar por período
    const response = await fetch('/emprestito/flujo-caja/all?periodo_desde=2025-07-01&periodo_hasta=2025-12-31');
    ```

    ###  Características:
    - **Ordenamiento**: Por período (cronológico)
    - **Resumen**: Estadísticas agregadas incluidas
    - **Metadatos**: Organismos, bancos y meses únicos
    - **UTF-8**: Soporte completo para caracteres especiales
    """
    if not FIREBASE_AVAILABLE or not SCRIPTS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Firebase o scripts no disponibles")

    if not FLUJO_CAJA_OPERATIONS_AVAILABLE:
        raise HTTPException(
            status_code=503, detail="Operaciones de flujo de caja no disponibles"
        )

    try:
        # Construir filtros
        filters = {}

        if responsable:
            filters["responsable"] = responsable
        if organismo:
            filters["organismo"] = organismo
        if banco:
            filters["banco"] = banco
        if bp_proyecto:
            filters["bp_proyecto"] = bp_proyecto
        if mes:
            filters["mes"] = mes
        if periodo_desde:
            filters["periodo_desde"] = periodo_desde
        if periodo_hasta:
            filters["periodo_hasta"] = periodo_hasta
        if limit:
            filters["limit"] = limit

        # Obtener datos de Firebase
        result = await get_flujo_caja_from_firebase(filters)

        if not result["success"]:
            raise HTTPException(
                status_code=500,
                detail=f"Error obteniendo flujos de caja: {result.get('error', 'Error desconocido')}",
            )

        # Agregar información del endpoint
        result["last_updated"] = "2025-10-20T00:00:00Z"
        result["endpoint_info"] = {
            "filtros_aplicados": len([k for k, v in filters.items() if v is not None]),
            "total_filtros_disponibles": 6,
            "ordenamiento": "por_periodo_cronologico",
        }

        return create_utf8_response(result)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error procesando consulta de flujos de caja: {str(e)}",
        )


@router.post(
    "/emprestito/crear-tabla-proyecciones",
    tags=["Gestión de Empréstito"],
    summary=" Crear Tabla Proyecciones",
)
async def crear_tabla_proyecciones_endpoint():
    """
    ##  POST |  Integración Externa | Crear Tabla de Proyecciones desde Google Sheets

    **Propósito**: Lee datos de Google Sheets específico y los carga en la colección "proyecciones_emprestito".

    ###  Proceso automático:
    1. **Lee datos** desde Google Sheets específico (Publicados Emprestitos nuevo)
    2. **Mapea campos** según especificaciones definidas
    3. **Procesa BP** agregando prefijo "BP" automáticamente
    4. **Guarda en Firebase** en colección "proyecciones_emprestito"
    5. **Elimina temporal** y registra fecha de actualización

    ###  Mapeo de campos:
    - `Item` → `item`
    - `Nro de Proceso` → `referencia_proceso`
    - `NOMBRE ABREVIADO` → `nombre_organismo_reducido`
    - `Banco` → `nombre_banco`
    - `BP` → `BP` (con prefijo "BP" agregado)
    - `DESCRIPCION BP` → `descripcion_bp`
    - `Proyecto` → `nombre_generico_proyecto`
    - `Proyecto con su respectivo contrato` → `nombre_resumido_proceso`
    - `ID PAA` → `id_paa`
    - `LINK DEL PROCESO` → `urlProceso`
    - `valor_proyectado` → `valor_proyectado` (mapeo directo)

    **NOTA**: La columna en Google Sheets ahora se llama "valor_proyectado" directamente

    ### [OK] Características:
    - **Reemplazo completo**: Elimina datos existentes y carga nuevos
    - **Validación automática**: Verifica campos obligatorios
    - **Manejo de errores**: Reporta filas con problemas
    - **Metadatos**: Registra fecha de carga y estadísticas
    - **UTF-8**: Soporte completo para caracteres especiales
    - **URL fija**: Usa Google Sheets predefinido
    - **Service Account**: Autenticación con service account configurado

    ###  Autenticación:
    - **Service Account**: `unidad-cumplimiento-sheets@unidad-cumplimiento.iam.gserviceaccount.com`
    - **Permisos**: Debe tener acceso de lectura al Google Sheets configurado
    - **Scopes**: `spreadsheets.readonly` y `drive.readonly`
    - **Credenciales**: Configuradas en el sistema usando ADC o variable de entorno

    ###  Ejemplo de respuesta:
    ```json
    {
        "success": true,
        "message": "Tabla de proyecciones creada exitosamente",
        "resumen_operacion": {
            "filas_leidas": 150,
            "registros_procesados": 148,
            "registros_guardados": 148,
            "docs_eliminados_previos": 145
        }
    }
    ```

    ###  Notas importantes:
    - **URL fija**: Usa Google Sheets predefinido internamente
    - **Automático**: No requiere parámetros de entrada
    - **Destructivo**: Reemplaza todos los datos existentes
    - **Auditable**: Mantiene registro de fecha de última actualización
    - **Permisos**: Requiere service account con acceso al Google Sheets
    """
    if not FIREBASE_AVAILABLE or not SCRIPTS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Firebase o scripts no disponibles")

    if not EMPRESTITO_OPERATIONS_AVAILABLE:
        raise HTTPException(
            status_code=503, detail="Operaciones de empréstito no disponibles"
        )

    try:
        # URL fija del Google Sheets según especificación del usuario
        sheet_url = "https://docs.google.com/spreadsheets/d/11-sdLwINHHwRit8b9jnnXcO2phhuEVUpXM6q6yv8DYo/edit?usp=sharing"

        # Ejecutar proceso completo
        result = await crear_tabla_proyecciones_desde_sheets(sheet_url)

        if not result["success"]:
            # Verificar si es error de autorización para dar mejor mensaje
            error_msg = result.get("error", "Error desconocido")

            if "Unauthorized" in error_msg or "401" in error_msg:
                raise HTTPException(
                    status_code=403,
                    detail={
                        "error": "El Google Sheets no es público o no tiene permisos de lectura",
                        "solucion": "Para resolver este problema:",
                        "pasos": [
                            "1. Abrir el Google Sheets",
                            "2. Hacer clic en 'Compartir' (botón azul superior derecho)",
                            "3. En 'Obtener enlace', cambiar a 'Cualquier persona con el enlace'",
                            "4. Cambiar permisos a 'Lector'",
                            "5. Copiar el enlace y usarlo en el parámetro sheet_url",
                        ],
                        "error_original": error_msg,
                    },
                )
            else:
                raise HTTPException(
                    status_code=500,
                    detail=f"Error creando tabla de proyecciones: {error_msg}",
                )

        # Agregar información del endpoint
        result["last_updated"] = "2025-10-22T00:00:00Z"
        result["endpoint_info"] = {
            "sheet_url_fija": True,
            "operacion": "reemplazo_completo",
            "campos_mapeados": 10,
            "validaciones": "campos_obligatorios",
            "service_account": "unidad-cumplimiento-sheets@unidad-cumplimiento.iam.gserviceaccount.com",
        }

        return create_utf8_response(result)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error procesando creación de tabla de proyecciones: {str(e)}",
        )


@router.get(
    "/emprestito/leer-tabla-proyecciones",
    tags=["Gestión de Empréstito"],
    summary=" Tabla de Proyecciones",
)
async def leer_tabla_proyecciones_endpoint(
    sheet_url: Optional[str] = Query(
        None,
        description="URL de Google Sheets para detectar registros con Nro de Proceso que NO están en procesos_emprestito.",
    ),
    solo_no_guardados: bool = Query(
        False,
        description="Si es True y se proporciona sheet_url, devuelve solo registros que NO están en procesos_emprestito pero tienen Nro de Proceso válido",
    ),
):
    """
    ##  GET |  Listados | Leer Tabla de Proyecciones de Empréstito

    **Propósito**:
    - **Sin parámetros**: Obtiene todos los registros de la colección "proyecciones_emprestito".
    - **Con sheet_url**: Detecta registros de Google Sheets que NO están en procesos_emprestito.

    ### [OK] Casos de uso:

    #### Modo 1: Lectura de BD (sin parámetros)
    - Consultar proyecciones cargadas desde Google Sheets
    - Verificar datos después de carga
    - Exportar proyecciones para análisis
    - Integrar con dashboards y reportes
    - Auditar última fecha de actualización

    #### Modo 2: Detección de no guardados en procesos_emprestito (con sheet_url)
    - **Identifica registros pendientes**: Encuentra qué datos de Sheets tienen Nro de Proceso pero NO están en procesos_emprestito
    - **Validación de sincronización**: Verifica qué procesos faltan por crear en la BD
    - **Detección de pendientes**: Lista proyecciones que necesitan ser guardadas como procesos
    - **Control de calidad**: Asegura que todos los procesos válidos estén registrados

    ###  Condiciones para Modo 2 (Registros devueltos):
    1. [OK] Tienen valor en columna "Nro de Proceso" (no vacío, no null)
    2. [ERROR] El valor de "Nro de Proceso" NO existe en la colección `procesos_emprestito` con campo `referencia_proceso`

    ###  Información incluida (Modo 1 - Sin sheet_url):
    - **Datos mapeados**: Todos los campos según mapeo definido
    - **Metadatos**: Fecha de carga, fuente, fila origen
    - **Timestamps**: Fecha de guardado y última actualización
    - **ID único**: Identificador de Firebase para cada registro
    - **Estadísticas**: Información de la última carga realizada

    ###  Información incluida (Modo 2 - Con sheet_url):
    - **Registros no guardados**: Solo los que tienen Nro de Proceso válido pero NO existen en procesos_emprestito
    - **Comparación precisa**: Verifica contra la colección procesos_emprestito
    - **Metadata de comparación**: Estadísticas sobre registros encontrados/no encontrados
    - **Optimización**: Usa mapas en memoria para comparación rápida O(1)

    ###  Campos de respuesta:
    - `item`: Número de ítem
    - `referencia_proceso`: Número de proceso (Nro de Proceso de Sheets)
    - `nombre_organismo_reducido`: Nombre abreviado del organismo
    - `nombre_banco`: Banco asociado
    - `BP`: Código BP con prefijo agregado
    - `descripcion_bp`: Descripción del BP
    - `nombre_generico_proyecto`: Nombre del proyecto
    - `nombre_resumido_proceso`: Proyecto con contrato
    - `id_paa`: ID del PAA
    - `urlProceso`: Enlace al proceso
    - `valor_proyectado`: Valor total del proyecto (única columna de valor)
    - `_es_nuevo`: (Solo Modo 2) Indica que es un registro no guardado
    - `_motivo`: (Solo Modo 2) Razón por la cual no está guardado

    **NOTA**: NO se incluyen campos duplicados como "VALOR TOTAL" o "Valor Adjudicado"

    ###  Ejemplos de uso:

    #### Ejemplo 1: Leer todos los registros guardados en proyecciones_emprestito
    ```javascript
    const response = await fetch('/emprestito/leer-tabla-proyecciones');
    const data = await response.json();

    if (data.success) {
        console.log(`Proyecciones encontradas: ${data.count}`);
        data.data.forEach(proyeccion => {
            console.log(`${proyeccion.referencia_proceso}: ${proyeccion.valor_proyectado}`);
        });
    }
    ```

    #### Ejemplo 2: Detectar registros pendientes de guardar en procesos_emprestito
    ```javascript
    const sheetUrl = 'https://docs.google.com/spreadsheets/d/ABC123/edit';
    const response = await fetch(
        `/emprestito/leer-tabla-proyecciones?sheet_url=${encodeURIComponent(sheetUrl)}&solo_no_guardados=true`
    );
    const data = await response.json();

    if (data.success) {
        console.log(`Registros pendientes: ${data.count}`);
        console.log(`Total en Sheets: ${data.metadata.total_sheets}`);
        console.log(`Ya en procesos_emprestito: ${data.metadata.ya_en_procesos}`);
        console.log(`Sin Nro de Proceso: ${data.metadata.sin_proceso}`);

        // Procesar registros pendientes
        data.data.forEach(registro => {
            console.log(`Pendiente: ${registro.referencia_proceso} - ${registro._motivo}`);
        });
    }
    ```

    ###  Características:
    - **Ordenamiento** (Modo 1): Por fecha de carga (más recientes primero)
    - **Filtrado inteligente** (Modo 2): Solo registros con Nro Proceso válido que NO están en procesos_emprestito
    - **Validación estricta**: Verifica que referencia_proceso no sea null, vacío o solo espacios
    - **UTF-8**: Soporte completo para caracteres especiales
    - **Auditoría**: Incluye información de trazabilidad
    - **Optimización**: Búsqueda O(1) usando sets en memoria
    """
    if not FIREBASE_AVAILABLE or not SCRIPTS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Firebase o scripts no disponibles")

    if not EMPRESTITO_OPERATIONS_AVAILABLE:
        raise HTTPException(
            status_code=503, detail="Operaciones de empréstito no disponibles"
        )

    try:
        # Modo 2: Comparar con Google Sheets y devolver no guardados en procesos_emprestito
        if sheet_url and solo_no_guardados:
            result = await leer_proyecciones_no_guardadas(sheet_url)

            if not result["success"]:
                raise HTTPException(
                    status_code=500,
                    detail=f"Error comparando con Google Sheets: {result.get('error', 'Error desconocido')}",
                )

            # Agregar información del endpoint
            result["last_updated"] = "2025-11-01T00:00:00Z"
            result["endpoint_info"] = {
                "modo": "deteccion_no_guardados",
                "sheet_url": sheet_url,
                "filtro": "no_en_procesos_emprestito_con_nro_proceso_valido",
                "coleccion_comparada": "procesos_emprestito",
                "campo_comparado": "referencia_proceso",
                "optimizado": True,
            }

            return create_utf8_response(result)

        # Modo 1: Obtener proyecciones de Firebase (comportamiento original)
        result = await leer_proyecciones_emprestito()

        if not result["success"]:
            raise HTTPException(
                status_code=500,
                detail=f"Error leyendo tabla de proyecciones: {result.get('error', 'Error desconocido')}",
            )

        # Agregar información del endpoint
        result["last_updated"] = "2025-11-01T00:00:00Z"
        result["endpoint_info"] = {
            "modo": "lectura_bd",
            "coleccion_fuente": "proyecciones_emprestito",
            "ordenamiento": "por_fecha_carga_desc",
            "incluye_metadatos": True,
            "trazabilidad_completa": True,
        }

        return create_utf8_response(result)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error procesando lectura de tabla de proyecciones: {str(e)}",
        )


@router.get("/emprestito/proyecciones-sin-proceso", tags=["Gestión de Empréstito"])
async def endpoint_proyecciones_sin_proceso():
    """Devuelve proyecciones cuya 'referencia_proceso' no exista en 'procesos_emprestito'."""
    if not FIREBASE_AVAILABLE or not SCRIPTS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Firebase o scripts no disponibles")

    if not EMPRESTITO_OPERATIONS_AVAILABLE:
        raise HTTPException(
            status_code=503, detail="Operaciones de empréstito no disponibles"
        )

    try:
        result = await get_proyecciones_sin_proceso()

        if not result.get("success", False):
            raise HTTPException(
                status_code=500, detail=result.get("error", "Error desconocido")
            )

        # Agregar metadata del endpoint
        result["last_updated"] = "2025-10-23T00:00:00Z"
        result["endpoint_info"] = {
            "coleccion_origen": "proyecciones_emprestito",
            "coleccion_comparacion": "procesos_emprestito",
            "filter_field": "referencia_proceso",
            "returned_count": result.get("count", 0),
        }

        return create_utf8_response(result)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error procesando endpoint: {str(e)}"
        )


# ============================================================================
# ENDPOINTS PUT - MODIFICAR DATOS EN FIREBASE
# ============================================================================


@router.put(
    "/emprestito/modificar-orden-compra",
    tags=["Gestión de Empréstito"],
    summary=" Modificar Orden de Compra",
)
async def modificar_orden_compra(
    numero_orden: str = Query(
        ..., description="Número de orden a modificar (REQUERIDO)"
    ),
    ano_orden: Optional[int] = Query(None, description="[Opcional] Año de la orden"),
    bp: Optional[str] = Query(None, description="[Opcional] BP"),
    bpin: Optional[str] = Query(None, description="[Opcional] BPIN"),
    estado: Optional[str] = Query(None, description="[Opcional] Estado de la orden"),
    estado_orden: Optional[str] = Query(
        None, description="[Opcional] Estado de la orden (alternativo)"
    ),
    fecha_actualizacion: Optional[str] = Query(
        None, description="[Opcional] Fecha de actualización"
    ),
    fecha_creacion: Optional[str] = Query(
        None, description="[Opcional] Fecha de creación"
    ),
    fecha_enriquecimiento_tvec: Optional[str] = Query(
        None, description="[Opcional] Fecha de enriquecimiento TVEC"
    ),
    fecha_guardado: Optional[str] = Query(
        None, description="[Opcional] Fecha de guardado"
    ),
    fecha_publicacion_orden: Optional[str] = Query(
        None, description="[Opcional] Fecha de publicación de la orden"
    ),
    fecha_vencimiento_orden: Optional[str] = Query(
        None, description="[Opcional] Fecha de vencimiento de la orden"
    ),
    fuente_datos: Optional[str] = Query(None, description="[Opcional] Fuente de datos"),
    items: Optional[str] = Query(None, description="[Opcional] Items (JSON array)"),
    modalidad_contratacion: Optional[str] = Query(
        None, description="[Opcional] Modalidad de contratación"
    ),
    nit_entidad: Optional[str] = Query(
        None, description="[Opcional] NIT de la entidad"
    ),
    nit_proveedor: Optional[str] = Query(
        None, description="[Opcional] NIT del proveedor"
    ),
    nombre_banco: Optional[str] = Query(
        None, description="[Opcional] Nombre del banco"
    ),
    nombre_centro_gestor: Optional[str] = Query(
        None, description="[Opcional] Nombre del centro gestor"
    ),
    nombre_proveedor: Optional[str] = Query(
        None, description="[Opcional] Nombre del proveedor"
    ),
    nombre_resumido_proceso: Optional[str] = Query(
        None, description="[Opcional] Nombre resumido del proceso"
    ),
    objeto_orden: Optional[str] = Query(
        None, description="[Opcional] Objeto de la orden"
    ),
    observaciones: Optional[str] = Query(
        None, description="[Opcional] Observaciones sobre la orden"
    ),
    ordenador_gasto: Optional[str] = Query(
        None, description="[Opcional] Ordenador de gasto"
    ),
    plataforma_origen: Optional[str] = Query(
        None, description="[Opcional] Plataforma de origen"
    ),
    rama_entidad: Optional[str] = Query(
        None, description="[Opcional] Rama de la entidad"
    ),
    sector: Optional[str] = Query(None, description="[Opcional] Sector"),
    solicitante: Optional[str] = Query(None, description="[Opcional] Solicitante"),
    solicitud_id: Optional[str] = Query(None, description="[Opcional] ID de solicitud"),
    tipo: Optional[str] = Query(None, description="[Opcional] Tipo"),
    tipo_documento: Optional[str] = Query(
        None, description="[Opcional] Tipo de documento"
    ),
    valor_orden: Optional[float] = Query(
        None, description="[Opcional] Valor de la orden"
    ),
    valor_proyectado: Optional[float] = Query(
        None, description="[Opcional] Valor proyectado"
    ),
    datos_json: Optional[str] = Query(
        None, description="[Opcional] JSON con campos adicionales a actualizar"
    ),
):
    """
    ##  PUT |  Modificar | Modificar Orden de Compra en Firebase

    Endpoint para modificar un registro en la colección `ordenes_compra_emprestito`
    usando el campo `numero_orden` como identificador único.

    ### [OK] Funcionalidades principales:
    - **Actualización selectiva**: Solo se modifican los campos especificados
    - **Preservación de datos**: Los campos no incluidos mantienen sus valores originales
    - **Búsqueda por numero_orden**: Identifica el documento automáticamente
    - **Validación**: Verifica que el registro exista antes de actualizar
    - **Múltiples formas de entrada**: Query parameters para facilitar pruebas en Swagger
    - **Respuesta clara**: Informa el estado de la operación

    ###  Parámetros disponibles (todos opcionales excepto numero_orden):
    - `numero_orden` (string, **REQUERIDO**): El número de orden a modificar
    - `ano_orden` (int, opcional): Año de la orden
    - `bp` (string, opcional): BP
    - `bpin` (string, opcional): BPIN
    - `estado` (string, opcional): Estado de la orden
    - `estado_orden` (string, opcional): Estado de la orden (alternativo)
    - `fecha_actualizacion` (string, opcional): Fecha de actualización
    - `fecha_creacion` (string, opcional): Fecha de creación
    - `fecha_enriquecimiento_tvec` (string, opcional): Fecha de enriquecimiento TVEC
    - `fecha_guardado` (string, opcional): Fecha de guardado
    - `fecha_publicacion_orden` (string, opcional): Fecha de publicación de la orden
    - `fecha_vencimiento_orden` (string, opcional): Fecha de vencimiento de la orden
    - `fuente_datos` (string, opcional): Fuente de datos
    - `items` (string, opcional): Items (JSON array como string)
    - `modalidad_contratacion` (string, opcional): Modalidad de contratación
    - `nit_entidad` (string, opcional): NIT de la entidad
    - `nit_proveedor` (string, opcional): NIT del proveedor
    - `nombre_banco` (string, opcional): Nombre del banco
    - `nombre_centro_gestor` (string, opcional): Nombre del centro gestor
    - `nombre_proveedor` (string, opcional): Nombre del proveedor
    - `nombre_resumido_proceso` (string, opcional): Nombre resumido del proceso
    - `objeto_orden` (string, opcional): Objeto de la orden
    - `observaciones` (string, opcional): Observaciones sobre la orden
    - `ordenador_gasto` (string, opcional): Ordenador de gasto
    - `plataforma_origen` (string, opcional): Plataforma de origen
    - `rama_entidad` (string, opcional): Rama de la entidad
    - `sector` (string, opcional): Sector
    - `solicitante` (string, opcional): Solicitante
    - `solicitud_id` (string, opcional): ID de solicitud
    - `tipo` (string, opcional): Tipo
    - `tipo_documento` (string, opcional): Tipo de documento
    - `valor_orden` (float, opcional): Valor de la orden
    - `valor_proyectado` (float, opcional): Valor proyectado
    - `datos_json` (string, opcional): JSON con campos adicionales a actualizar

    ###  Ejemplos de uso en Swagger:
    ```
    numero_orden: OC-2024-001
    estado: pagado
    valor_total: 5000000
    observaciones: Orden procesada
    ```

    O incluir campos adicionales en:
    ```
    datos_json: {"campo_adicional": "valor", "otro_campo": 123}
    ```

    ### [OK] Respuesta exitosa (200):
    ```json
    {
        "success": true,
        "message": "Orden de compra actualizada correctamente",
        "numero_orden": "OC-2024-001",
        "campos_actualizados": ["estado", "valor_total", "observaciones"],
        "timestamp": "2024-11-12T10:30:45.123456"
    }
    ```

    ### [ERROR] Respuesta de error (404):
    ```json
    {
        "success": false,
        "error": "Orden de compra no encontrada",
        "numero_orden": "OC-2024-001",
        "timestamp": "2024-11-12T10:30:45.123456"
    }
    ```

    ###  Notas importantes:
    - El `numero_orden` es el identificador único
    - Los campos no especificados NO se modifican
    - La actualización es parcial (solo lo que envíes se modifica)
    - Se requiere Firebase disponible
    - Perfectamente integrado con Swagger UI para pruebas interactivas
    """
    if not FIREBASE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Firebase no está disponible")

    try:
        # Construir diccionario de datos a actualizar
        datos_actualizados = {}

        if ano_orden is not None:
            datos_actualizados["ano_orden"] = ano_orden
        if bp is not None:
            datos_actualizados["bp"] = bp
        if bpin is not None:
            datos_actualizados["bpin"] = bpin
        if estado is not None:
            datos_actualizados["estado"] = estado
        if estado_orden is not None:
            datos_actualizados["estado_orden"] = estado_orden
        if fecha_actualizacion is not None:
            datos_actualizados["fecha_actualizacion"] = fecha_actualizacion
        if fecha_creacion is not None:
            datos_actualizados["fecha_creacion"] = fecha_creacion
        if fecha_enriquecimiento_tvec is not None:
            datos_actualizados["fecha_enriquecimiento_tvec"] = (
                fecha_enriquecimiento_tvec
            )
        if fecha_guardado is not None:
            datos_actualizados["fecha_guardado"] = fecha_guardado
        if fecha_publicacion_orden is not None:
            datos_actualizados["fecha_publicacion_orden"] = fecha_publicacion_orden
        if fecha_vencimiento_orden is not None:
            datos_actualizados["fecha_vencimiento_orden"] = fecha_vencimiento_orden
        if fuente_datos is not None:
            datos_actualizados["fuente_datos"] = fuente_datos
        if items is not None:
            try:
                datos_actualizados["items"] = (
                    json.loads(items) if isinstance(items, str) else items
                )
            except:
                datos_actualizados["items"] = items
        if modalidad_contratacion is not None:
            datos_actualizados["modalidad_contratacion"] = modalidad_contratacion
        if nit_entidad is not None:
            datos_actualizados["nit_entidad"] = nit_entidad
        if nit_proveedor is not None:
            datos_actualizados["nit_proveedor"] = nit_proveedor
        if nombre_banco is not None:
            datos_actualizados["nombre_banco"] = nombre_banco
        if nombre_centro_gestor is not None:
            datos_actualizados["nombre_centro_gestor"] = nombre_centro_gestor
        if nombre_proveedor is not None:
            datos_actualizados["nombre_proveedor"] = nombre_proveedor
        if nombre_resumido_proceso is not None:
            datos_actualizados["nombre_resumido_proceso"] = nombre_resumido_proceso
        if objeto_orden is not None:
            datos_actualizados["objeto_orden"] = objeto_orden
        if observaciones is not None:
            datos_actualizados["observaciones"] = observaciones
        if ordenador_gasto is not None:
            datos_actualizados["ordenador_gasto"] = ordenador_gasto
        if plataforma_origen is not None:
            datos_actualizados["plataforma_origen"] = plataforma_origen
        if rama_entidad is not None:
            datos_actualizados["rama_entidad"] = rama_entidad
        if sector is not None:
            datos_actualizados["sector"] = sector
        if solicitante is not None:
            datos_actualizados["solicitante"] = solicitante
        if solicitud_id is not None:
            datos_actualizados["solicitud_id"] = solicitud_id
        if tipo is not None:
            datos_actualizados["tipo"] = tipo
        if tipo_documento is not None:
            datos_actualizados["tipo_documento"] = tipo_documento
        if valor_orden is not None:
            datos_actualizados["valor_orden"] = valor_orden
        if valor_proyectado is not None:
            datos_actualizados["valor_proyectado"] = valor_proyectado

        # Parsear JSON adicional si se proporciona
        if datos_json:
            try:
                datos_json_dict = json.loads(datos_json)
                datos_actualizados.update(datos_json_dict)
            except json.JSONDecodeError:
                raise HTTPException(
                    status_code=400,
                    detail="El parámetro 'datos_json' debe ser un JSON válido",
                )

        # Validar que se proporcionaron datos para actualizar
        if not datos_actualizados:
            raise HTTPException(
                status_code=400,
                detail="Debes proporcionar al menos un campo para actualizar o un JSON válido en datos_json",
            )

        db = get_firestore_client()
        if not db:
            raise HTTPException(
                status_code=503, detail="No se pudo obtener cliente de Firebase"
            )

        # Buscar el documento por numero_orden
        coleccion = db.collection("ordenes_compra_emprestito")
        query = coleccion.where("numero_orden", "==", numero_orden)
        docs = list(query.stream())

        if not docs:
            raise HTTPException(
                status_code=404,
                detail=f"Orden de compra con número '{numero_orden}' no encontrada",
            )

        # Obtener el ID del documento
        doc_id = docs[0].id

        # Actualizar solo los campos proporcionados
        campos_actualizados = list(datos_actualizados.keys())
        coleccion.document(doc_id).update(datos_actualizados)

        return create_utf8_response(
            {
                "success": True,
                "message": "Orden de compra actualizada correctamente",
                "numero_orden": numero_orden,
                "campos_actualizados": campos_actualizados,
                "timestamp": datetime.now().isoformat(),
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error al modificar orden de compra: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Error al actualizar la orden de compra: {str(e)}"
        )


@router.put(
    "/emprestito/modificar-proceso",
    tags=["Gestión de Empréstito"],
    summary=" Modificar Proceso de Empréstito",
)
async def modificar_proceso(
    referencia_proceso: str = Query(
        ..., description="Referencia del proceso a modificar (REQUERIDO)"
    ),
    adjudicado: Optional[str] = Query(None, description="[Opcional] Adjudicado"),
    bp: Optional[str] = Query(None, description="[Opcional] BP"),
    conteo_respuestas_ofertas: Optional[int] = Query(
        None, description="[Opcional] Conteo de respuestas de ofertas"
    ),
    descripcion_proceso: Optional[str] = Query(
        None, description="[Opcional] Descripción del proceso"
    ),
    duracion: Optional[int] = Query(None, description="[Opcional] Duración"),
    estado_proceso: Optional[str] = Query(
        None, description="[Opcional] Estado del proceso"
    ),
    estado_resumen: Optional[str] = Query(
        None, description="[Opcional] Estado resumen"
    ),
    fase: Optional[str] = Query(None, description="[Opcional] Fase"),
    fecha_actualizacion: Optional[str] = Query(
        None, description="[Opcional] Fecha de actualización"
    ),
    fecha_actualizacion_completa: Optional[str] = Query(
        None, description="[Opcional] Fecha de actualización completa"
    ),
    fecha_creacion: Optional[str] = Query(
        None, description="[Opcional] Fecha de creación"
    ),
    fecha_publicacion: Optional[str] = Query(
        None, description="[Opcional] Fecha de publicación"
    ),
    fecha_publicacion_fase: Optional[str] = Query(
        None, description="[Opcional] Fecha de publicación fase"
    ),
    fecha_publicacion_fase_3: Optional[str] = Query(
        None, description="[Opcional] Fecha de publicación fase 3"
    ),
    id_paa: Optional[str] = Query(None, description="[Opcional] ID PAA"),
    modalidad_contratacion: Optional[str] = Query(
        None, description="[Opcional] Modalidad de contratación"
    ),
    nombre_banco: Optional[str] = Query(
        None, description="[Opcional] Nombre del banco"
    ),
    nombre_centro_gestor: Optional[str] = Query(
        None, description="[Opcional] Nombre del centro gestor"
    ),
    nombre_proceso: Optional[str] = Query(
        None, description="[Opcional] Nombre del proceso"
    ),
    nombre_resumido_proceso: Optional[str] = Query(
        None, description="[Opcional] Nombre resumido del proceso"
    ),
    nombre_unidad: Optional[str] = Query(
        None, description="[Opcional] Nombre de unidad"
    ),
    numero_lotes: Optional[int] = Query(None, description="[Opcional] Número de lotes"),
    observaciones_test: Optional[str] = Query(
        None, description="[Opcional] Observaciones test"
    ),
    plataforma: Optional[str] = Query(None, description="[Opcional] Plataforma"),
    proceso_contractual: Optional[str] = Query(
        None, description="[Opcional] Proceso contractual"
    ),
    proveedores_con_invitacion: Optional[str] = Query(
        None, description="[Opcional] Proveedores con invitación"
    ),
    proveedores_invitados: Optional[str] = Query(
        None, description="[Opcional] Proveedores invitados"
    ),
    proveedores_que_manifestaron: Optional[str] = Query(
        None, description="[Opcional] Proveedores que manifestaron"
    ),
    respuestas_externas: Optional[str] = Query(
        None, description="[Opcional] Respuestas externas"
    ),
    respuestas_procedimiento: Optional[str] = Query(
        None, description="[Opcional] Respuestas procedimiento"
    ),
    tipo_contrato: Optional[str] = Query(
        None, description="[Opcional] Tipo de contrato"
    ),
    unidad_duracion: Optional[str] = Query(
        None, description="[Opcional] Unidad de duración"
    ),
    urlproceso: Optional[str] = Query(None, description="[Opcional] URL del proceso"),
    valor_proyectado: Optional[float] = Query(
        None, description="[Opcional] Valor proyectado"
    ),
    valor_publicacion: Optional[float] = Query(
        None, description="[Opcional] Valor de publicación"
    ),
    visualizaciones_proceso: Optional[int] = Query(
        None, description="[Opcional] Visualizaciones del proceso"
    ),
    datos_json: Optional[str] = Query(
        None, description="[Opcional] JSON con campos adicionales a actualizar"
    ),
):
    """
    ##  PUT |  Modificar | Modificar Proceso de Empréstito en Firebase

    Endpoint para modificar un registro en la colección `procesos_emprestito`
    usando el campo `referencia_proceso` como identificador único.

    ### [OK] Funcionalidades principales:
    - **Actualización selectiva**: Solo se modifican los campos especificados
    - **Preservación de datos**: Los campos no incluidos mantienen sus valores originales
    - **Búsqueda por referencia_proceso**: Identifica el documento automáticamente
    - **Validación**: Verifica que el registro exista antes de actualizar
    - **Múltiples formas de entrada**: Query parameters para facilitar pruebas en Swagger
    - **Respuesta clara**: Informa el estado de la operación

    ###  Parámetros disponibles (todos opcionales excepto referencia_proceso):
    - `referencia_proceso` (string, **REQUERIDO**): La referencia del proceso a modificar
    - `adjudicado` (string, opcional): Adjudicado
    - `bp` (string, opcional): BP
    - `conteo_respuestas_ofertas` (int, opcional): Conteo de respuestas de ofertas
    - `descripcion_proceso` (string, opcional): Descripción del proceso
    - `duracion` (int, opcional): Duración
    - `estado_proceso` (string, opcional): Estado del proceso
    - `estado_resumen` (string, opcional): Estado resumen
    - `fase` (string, opcional): Fase
    - `fecha_actualizacion` (string, opcional): Fecha de actualización
    - `fecha_actualizacion_completa` (string, opcional): Fecha de actualización completa
    - `fecha_creacion` (string, opcional): Fecha de creación
    - `fecha_publicacion` (string, opcional): Fecha de publicación
    - `fecha_publicacion_fase` (string, opcional): Fecha de publicación fase
    - `fecha_publicacion_fase_3` (string, opcional): Fecha de publicación fase 3
    - `id_paa` (string, opcional): ID PAA
    - `modalidad_contratacion` (string, opcional): Modalidad de contratación
    - `nombre_banco` (string, opcional): Nombre del banco
    - `nombre_centro_gestor` (string, opcional): Nombre del centro gestor
    - `nombre_proceso` (string, opcional): Nombre del proceso
    - `nombre_resumido_proceso` (string, opcional): Nombre resumido del proceso
    - `nombre_unidad` (string, opcional): Nombre de unidad
    - `numero_lotes` (int, opcional): Número de lotes
    - `observaciones_test` (string, opcional): Observaciones test
    - `plataforma` (string, opcional): Plataforma
    - `proceso_contractual` (string, opcional): Proceso contractual
    - `proveedores_con_invitacion` (string, opcional): Proveedores con invitación
    - `proveedores_invitados` (string, opcional): Proveedores invitados
    - `proveedores_que_manifestaron` (string, opcional): Proveedores que manifestaron
    - `respuestas_externas` (string, opcional): Respuestas externas
    - `respuestas_procedimiento` (string, opcional): Respuestas procedimiento
    - `tipo_contrato` (string, opcional): Tipo de contrato
    - `unidad_duracion` (string, opcional): Unidad de duración
    - `urlproceso` (string, opcional): URL del proceso
    - `valor_proyectado` (float, opcional): Valor proyectado
    - `valor_publicacion` (float, opcional): Valor de publicación
    - `visualizaciones_proceso` (int, opcional): Visualizaciones del proceso
    - `datos_json` (string, opcional): JSON con campos adicionales a actualizar

    ###  Ejemplos de uso en Swagger:
    ```
    referencia_proceso: PROC-SALUD-2024-001
    estado_proceso: ejecutado
    valor_total: 25000000
    fecha_cierre: 2024-11-12
    observaciones: Proceso completado exitosamente
    ```

    ### [OK] Respuesta exitosa (200):
    ```json
    {
        "success": true,
        "message": "Proceso de empréstito actualizado correctamente",
        "referencia_proceso": "PROC-SALUD-2024-001",
        "campos_actualizados": ["estado_proceso", "valor_total", "fecha_cierre", "observaciones"],
        "timestamp": "2024-11-12T10:35:22.654321"
    }
    ```

    ### [ERROR] Respuesta de error (404):
    ```json
    {
        "success": false,
        "error": "Proceso de empréstito no encontrado",
        "referencia_proceso": "PROC-SALUD-2024-001",
        "timestamp": "2024-11-12T10:35:22.654321"
    }
    ```

    ###  Notas importantes:
    - La `referencia_proceso` es el identificador único
    - Los campos no especificados NO se modifican
    - La actualización es parcial (solo lo que envíes se modifica)
    - Se requiere Firebase disponible
    - Perfectamente integrado con Swagger UI para pruebas interactivas
    """
    if not FIREBASE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Firebase no está disponible")

    try:
        # Construir diccionario de datos a actualizar
        datos_actualizados = {}

        if adjudicado is not None:
            datos_actualizados["adjudicado"] = adjudicado
        if bp is not None:
            datos_actualizados["bp"] = bp
        if conteo_respuestas_ofertas is not None:
            datos_actualizados["conteo_respuestas_ofertas"] = conteo_respuestas_ofertas
        if descripcion_proceso is not None:
            datos_actualizados["descripcion_proceso"] = descripcion_proceso
        if duracion is not None:
            datos_actualizados["duracion"] = duracion
        if estado_proceso is not None:
            datos_actualizados["estado_proceso"] = estado_proceso
        if estado_resumen is not None:
            datos_actualizados["estado_resumen"] = estado_resumen
        if fase is not None:
            datos_actualizados["fase"] = fase
        if fecha_actualizacion is not None:
            datos_actualizados["fecha_actualizacion"] = fecha_actualizacion
        if fecha_actualizacion_completa is not None:
            datos_actualizados["fecha_actualizacion_completa"] = (
                fecha_actualizacion_completa
            )
        if fecha_creacion is not None:
            datos_actualizados["fecha_creacion"] = fecha_creacion
        if fecha_publicacion is not None:
            datos_actualizados["fecha_publicacion"] = fecha_publicacion
        if fecha_publicacion_fase is not None:
            datos_actualizados["fecha_publicacion_fase"] = fecha_publicacion_fase
        if fecha_publicacion_fase_3 is not None:
            datos_actualizados["fecha_publicacion_fase_3"] = fecha_publicacion_fase_3
        if id_paa is not None:
            datos_actualizados["id_paa"] = id_paa
        if modalidad_contratacion is not None:
            datos_actualizados["modalidad_contratacion"] = modalidad_contratacion
        if nombre_banco is not None:
            datos_actualizados["nombre_banco"] = nombre_banco
        if nombre_centro_gestor is not None:
            datos_actualizados["nombre_centro_gestor"] = nombre_centro_gestor
        if nombre_proceso is not None:
            datos_actualizados["nombre_proceso"] = nombre_proceso
        if nombre_resumido_proceso is not None:
            datos_actualizados["nombre_resumido_proceso"] = nombre_resumido_proceso
        if nombre_unidad is not None:
            datos_actualizados["nombre_unidad"] = nombre_unidad
        if numero_lotes is not None:
            datos_actualizados["numero_lotes"] = numero_lotes
        if observaciones_test is not None:
            datos_actualizados["observaciones_test"] = observaciones_test
        if plataforma is not None:
            datos_actualizados["plataforma"] = plataforma
        if proceso_contractual is not None:
            datos_actualizados["proceso_contractual"] = proceso_contractual
        if proveedores_con_invitacion is not None:
            datos_actualizados["proveedores_con_invitacion"] = (
                proveedores_con_invitacion
            )
        if proveedores_invitados is not None:
            datos_actualizados["proveedores_invitados"] = proveedores_invitados
        if proveedores_que_manifestaron is not None:
            datos_actualizados["proveedores_que_manifestaron"] = (
                proveedores_que_manifestaron
            )
        if respuestas_externas is not None:
            datos_actualizados["respuestas_externas"] = respuestas_externas
        if respuestas_procedimiento is not None:
            datos_actualizados["respuestas_procedimiento"] = respuestas_procedimiento
        if tipo_contrato is not None:
            datos_actualizados["tipo_contrato"] = tipo_contrato
        if unidad_duracion is not None:
            datos_actualizados["unidad_duracion"] = unidad_duracion
        if urlproceso is not None:
            datos_actualizados["urlproceso"] = urlproceso
        if valor_proyectado is not None:
            datos_actualizados["valor_proyectado"] = valor_proyectado
        if valor_publicacion is not None:
            datos_actualizados["valor_publicacion"] = valor_publicacion
        if visualizaciones_proceso is not None:
            datos_actualizados["visualizaciones_proceso"] = visualizaciones_proceso

        # Parsear JSON adicional si se proporciona
        if datos_json:
            try:
                datos_json_dict = json.loads(datos_json)
                datos_actualizados.update(datos_json_dict)
            except json.JSONDecodeError:
                raise HTTPException(
                    status_code=400,
                    detail="El parámetro 'datos_json' debe ser un JSON válido",
                )

        # Validar que se proporcionaron datos para actualizar
        if not datos_actualizados:
            raise HTTPException(
                status_code=400,
                detail="Debes proporcionar al menos un campo para actualizar o un JSON válido en datos_json",
            )

        db = get_firestore_client()
        if not db:
            raise HTTPException(
                status_code=503, detail="No se pudo obtener cliente de Firebase"
            )

        # Buscar el documento por referencia_proceso
        coleccion = db.collection("procesos_emprestito")
        query = coleccion.where("referencia_proceso", "==", referencia_proceso)
        docs = list(query.stream())

        if not docs:
            raise HTTPException(
                status_code=404,
                detail=f"Proceso de empréstito con referencia '{referencia_proceso}' no encontrado",
            )

        # Obtener el ID del documento
        doc_id = docs[0].id

        # Actualizar solo los campos proporcionados
        campos_actualizados = list(datos_actualizados.keys())
        coleccion.document(doc_id).update(datos_actualizados)

        return create_utf8_response(
            {
                "success": True,
                "message": "Proceso de empréstito actualizado correctamente",
                "referencia_proceso": referencia_proceso,
                "campos_actualizados": campos_actualizados,
                "timestamp": datetime.now().isoformat(),
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error al modificar proceso de empréstito: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error al actualizar el proceso de empréstito: {str(e)}",
        )


@router.put(
    "/emprestito/modificar-contrato",
    tags=["Gestión de Empréstito"],
    summary=" Modificar Contrato de Empréstito",
)
async def modificar_contrato(
    referencia_contrato: str = Query(
        ..., description="Referencia del contrato a modificar (REQUERIDO)"
    ),
    _dataset_source: Optional[str] = Query(
        None, description="[Opcional] Fuente del dataset"
    ),
    banco: Optional[str] = Query(None, description="[Opcional] Banco"),
    bp: Optional[str] = Query(None, description="[Opcional] BP"),
    bpin: Optional[str] = Query(None, description="[Opcional] BPIN"),
    descripcion_proceso: Optional[str] = Query(
        None, description="[Opcional] Descripción del proceso"
    ),
    entidad_contratante: Optional[str] = Query(
        None, description="[Opcional] Entidad contratante"
    ),
    estado_contrato: Optional[str] = Query(
        None, description="[Opcional] Estado del contrato"
    ),
    fecha_actualizacion: Optional[str] = Query(
        None, description="[Opcional] Fecha de actualización"
    ),
    fecha_fin_contrato: Optional[str] = Query(
        None, description="[Opcional] Fecha de fin del contrato"
    ),
    fecha_firma_contrato: Optional[str] = Query(
        None, description="[Opcional] Fecha de firma del contrato"
    ),
    fecha_guardado: Optional[str] = Query(
        None, description="[Opcional] Fecha de guardado"
    ),
    fecha_inicio_contrato: Optional[str] = Query(
        None, description="[Opcional] Fecha de inicio del contrato"
    ),
    fuente_datos: Optional[str] = Query(None, description="[Opcional] Fuente de datos"),
    id_contrato: Optional[str] = Query(None, description="[Opcional] ID del contrato"),
    modalidad_contratacion: Optional[str] = Query(
        None, description="[Opcional] Modalidad de contratación"
    ),
    nit_contratista: Optional[str] = Query(
        None, description="[Opcional] NIT del contratista"
    ),
    nit_entidad: Optional[str] = Query(
        None, description="[Opcional] NIT de la entidad"
    ),
    nombre_centro_gestor: Optional[str] = Query(
        None, description="[Opcional] Nombre del centro gestor"
    ),
    nombre_contratista: Optional[str] = Query(
        None, description="[Opcional] Nombre del contratista"
    ),
    nombre_procedimiento: Optional[str] = Query(
        None, description="[Opcional] Nombre del procedimiento"
    ),
    objeto_contrato: Optional[str] = Query(
        None, description="[Opcional] Objeto del contrato"
    ),
    observaciones_test: Optional[str] = Query(
        None, description="[Opcional] Observaciones test"
    ),
    ordenador_gasto: Optional[str] = Query(
        None, description="[Opcional] Ordenador de gasto"
    ),
    proceso_contractual: Optional[str] = Query(
        None, description="[Opcional] Proceso contractual"
    ),
    referencia_proceso: Optional[str] = Query(
        None, description="[Opcional] Referencia del proceso"
    ),
    representante_legal: Optional[str] = Query(
        None, description="[Opcional] Representante legal"
    ),
    sector: Optional[str] = Query(None, description="[Opcional] Sector"),
    supervisor: Optional[str] = Query(None, description="[Opcional] Supervisor"),
    tipo_contrato: Optional[str] = Query(
        None, description="[Opcional] Tipo de contrato"
    ),
    urlproceso: Optional[str] = Query(None, description="[Opcional] URL del proceso"),
    valor_contrato: Optional[float] = Query(
        None, description="[Opcional] Valor del contrato"
    ),
    valor_pagado: Optional[float] = Query(None, description="[Opcional] Valor pagado"),
    version_esquema: Optional[str] = Query(
        None, description="[Opcional] Versión del esquema"
    ),
    datos_json: Optional[str] = Query(
        None, description="[Opcional] JSON con campos adicionales a actualizar"
    ),
):
    """
    ##  PUT |  Modificar | Modificar Contrato de Empréstito en Firebase

    Endpoint para modificar un registro en la colección `contratos_emprestito`
    usando el campo `referencia_contrato` como identificador único.

    ### [OK] Funcionalidades principales:
    - **Actualización selectiva**: Solo se modifican los campos especificados
    - **Preservación de datos**: Los campos no incluidos mantienen sus valores originales
    - **Búsqueda por referencia_contrato**: Identifica el documento automáticamente
    - **Validación**: Verifica que el registro exista antes de actualizar
    - **Múltiples formas de entrada**: Query parameters para facilitar pruebas en Swagger
    - **Respuesta clara**: Informa el estado de la operación

    ###  Parámetros disponibles (todos opcionales excepto referencia_contrato):
    - `referencia_contrato` (string, **REQUERIDO**): La referencia del contrato a modificar
    - `_dataset_source` (string, opcional): Fuente del dataset
    - `banco` (string, opcional): Banco
    - `bp` (string, opcional): BP
    - `bpin` (string, opcional): BPIN
    - `descripcion_proceso` (string, opcional): Descripción del proceso
    - `entidad_contratante` (string, opcional): Entidad contratante
    - `estado_contrato` (string, opcional): Estado del contrato
    - `fecha_actualizacion` (string, opcional): Fecha de actualización
    - `fecha_fin_contrato` (string, opcional): Fecha de fin del contrato
    - `fecha_firma_contrato` (string, opcional): Fecha de firma del contrato
    - `fecha_guardado` (string, opcional): Fecha de guardado
    - `fecha_inicio_contrato` (string, opcional): Fecha de inicio del contrato
    - `fuente_datos` (string, opcional): Fuente de datos
    - `id_contrato` (string, opcional): ID del contrato
    - `modalidad_contratacion` (string, opcional): Modalidad de contratación
    - `nit_contratista` (string, opcional): NIT del contratista
    - `nit_entidad` (string, opcional): NIT de la entidad
    - `nombre_centro_gestor` (string, opcional): Nombre del centro gestor
    - `nombre_contratista` (string, opcional): Nombre del contratista
    - `nombre_procedimiento` (string, opcional): Nombre del procedimiento
    - `objeto_contrato` (string, opcional): Objeto del contrato
    - `observaciones_test` (string, opcional): Observaciones test
    - `ordenador_gasto` (string, opcional): Ordenador de gasto
    - `proceso_contractual` (string, opcional): Proceso contractual
    - `referencia_proceso` (string, opcional): Referencia del proceso
    - `representante_legal` (string, opcional): Representante legal
    - `sector` (string, opcional): Sector
    - `supervisor` (string, opcional): Supervisor
    - `tipo_contrato` (string, opcional): Tipo de contrato
    - `urlproceso` (string, opcional): URL del proceso
    - `valor_contrato` (float, opcional): Valor del contrato
    - `valor_pagado` (float, opcional): Valor pagado
    - `version_esquema` (string, opcional): Versión del esquema
    - `datos_json` (string, opcional): JSON con campos adicionales a actualizar

    ###  Ejemplos de uso en Swagger:
    ```
    referencia_contrato: CONT-SALUD-003-2024
    estado_contrato: ejecutado
    valor_contrato: 50000000
    fecha_cierre: 2024-11-12
    observaciones: Contrato completado
    ```

    ### [OK] Respuesta exitosa (200):
    ```json
    {
        "success": true,
        "message": "Contrato de empréstito actualizado correctamente",
        "referencia_contrato": "CONT-SALUD-003-2024",
        "campos_actualizados": ["estado_contrato", "valor_contrato", "fecha_cierre", "observaciones"],
        "timestamp": "2024-11-12T11:45:30.987654"
    }
    ```

    ### [ERROR] Respuesta de error (404):
    ```json
    {
        "success": false,
        "error": "Contrato de empréstito no encontrado",
        "referencia_contrato": "CONT-SALUD-003-2024",
        "timestamp": "2024-11-12T11:45:30.987654"
    }
    ```

    ###  Notas importantes:
    - La `referencia_contrato` es el identificador único
    - Los campos no especificados NO se modifican
    - La actualización es parcial (solo lo que envíes se modifica)
    - Se requiere Firebase disponible
    - Perfectamente integrado con Swagger UI para pruebas interactivas
    """
    if not FIREBASE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Firebase no está disponible")

    try:
        # Construir diccionario de datos a actualizar
        datos_actualizados = {}

        if _dataset_source is not None:
            datos_actualizados["_dataset_source"] = _dataset_source
        if banco is not None:
            datos_actualizados["banco"] = banco
        if bp is not None:
            datos_actualizados["bp"] = bp
        if bpin is not None:
            datos_actualizados["bpin"] = bpin
        if descripcion_proceso is not None:
            datos_actualizados["descripcion_proceso"] = descripcion_proceso
        if entidad_contratante is not None:
            datos_actualizados["entidad_contratante"] = entidad_contratante
        if estado_contrato is not None:
            datos_actualizados["estado_contrato"] = estado_contrato
        if fecha_actualizacion is not None:
            datos_actualizados["fecha_actualizacion"] = fecha_actualizacion
        if fecha_fin_contrato is not None:
            datos_actualizados["fecha_fin_contrato"] = fecha_fin_contrato
        if fecha_firma_contrato is not None:
            datos_actualizados["fecha_firma_contrato"] = fecha_firma_contrato
        if fecha_guardado is not None:
            datos_actualizados["fecha_guardado"] = fecha_guardado
        if fecha_inicio_contrato is not None:
            datos_actualizados["fecha_inicio_contrato"] = fecha_inicio_contrato
        if fuente_datos is not None:
            datos_actualizados["fuente_datos"] = fuente_datos
        if id_contrato is not None:
            datos_actualizados["id_contrato"] = id_contrato
        if modalidad_contratacion is not None:
            datos_actualizados["modalidad_contratacion"] = modalidad_contratacion
        if nit_contratista is not None:
            datos_actualizados["nit_contratista"] = nit_contratista
        if nit_entidad is not None:
            datos_actualizados["nit_entidad"] = nit_entidad
        if nombre_centro_gestor is not None:
            datos_actualizados["nombre_centro_gestor"] = nombre_centro_gestor
        if nombre_contratista is not None:
            datos_actualizados["nombre_contratista"] = nombre_contratista
        if nombre_procedimiento is not None:
            datos_actualizados["nombre_procedimiento"] = nombre_procedimiento
        if objeto_contrato is not None:
            datos_actualizados["objeto_contrato"] = objeto_contrato
        if observaciones_test is not None:
            datos_actualizados["observaciones_test"] = observaciones_test
        if ordenador_gasto is not None:
            datos_actualizados["ordenador_gasto"] = ordenador_gasto
        if proceso_contractual is not None:
            datos_actualizados["proceso_contractual"] = proceso_contractual
        if referencia_proceso is not None:
            datos_actualizados["referencia_proceso"] = referencia_proceso
        if representante_legal is not None:
            datos_actualizados["representante_legal"] = representante_legal
        if sector is not None:
            datos_actualizados["sector"] = sector
        if supervisor is not None:
            datos_actualizados["supervisor"] = supervisor
        if tipo_contrato is not None:
            datos_actualizados["tipo_contrato"] = tipo_contrato
        if urlproceso is not None:
            datos_actualizados["urlproceso"] = urlproceso
        if valor_contrato is not None:
            datos_actualizados["valor_contrato"] = valor_contrato
        if valor_pagado is not None:
            datos_actualizados["valor_pagado"] = valor_pagado
        if version_esquema is not None:
            datos_actualizados["version_esquema"] = version_esquema

        # Parsear JSON adicional si se proporciona
        if datos_json:
            try:
                datos_json_dict = json.loads(datos_json)
                datos_actualizados.update(datos_json_dict)
            except json.JSONDecodeError:
                raise HTTPException(
                    status_code=400,
                    detail="El parámetro 'datos_json' debe ser un JSON válido",
                )

        # Validar que se proporcionaron datos para actualizar
        if not datos_actualizados:
            raise HTTPException(
                status_code=400,
                detail="Debes proporcionar al menos un campo para actualizar o un JSON válido en datos_json",
            )

        db = get_firestore_client()
        if not db:
            raise HTTPException(
                status_code=503, detail="No se pudo obtener cliente de Firebase"
            )

        # Buscar el documento por referencia_contrato
        coleccion = db.collection("contratos_emprestito")
        query = coleccion.where("referencia_contrato", "==", referencia_contrato)
        docs = list(query.stream())

        if not docs:
            raise HTTPException(
                status_code=404,
                detail=f"Contrato de empréstito con referencia '{referencia_contrato}' no encontrado",
            )

        # Obtener el ID del documento
        doc_id = docs[0].id

        # Actualizar solo los campos proporcionados
        campos_actualizados = list(datos_actualizados.keys())
        coleccion.document(doc_id).update(datos_actualizados)

        return create_utf8_response(
            {
                "success": True,
                "message": "Contrato de empréstito actualizado correctamente",
                "referencia_contrato": referencia_contrato,
                "campos_actualizados": campos_actualizados,
                "timestamp": datetime.now().isoformat(),
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error al modificar contrato de empréstito: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error al actualizar el contrato de empréstito: {str(e)}",
        )
