"""
Middlewares de Autenticación y Auditoría
Middlewares para verificación de tokens y logging de acciones
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, JSONResponse
from typing import List
from datetime import datetime, timezone
import time

from .constants import PUBLIC_PATHS, FIREBASE_COLLECTIONS


class AuthorizationMiddleware(BaseHTTPMiddleware):
    """
    Middleware para verificación de autenticación en todas las rutas
    excepto las rutas públicas definidas
    """
    
    def __init__(self, app, public_paths: List[str] = None):
        super().__init__(app)
        self.public_paths = public_paths or PUBLIC_PATHS
    
    async def dispatch(self, request: Request, call_next):
        # Verificar si la ruta es pública
        path = request.url.path
        
        # Logging para debug
        print(f"🔍 Middleware checking path: {path}")
        print(f"📋 Public paths: {self.public_paths}")
        
        # Permitir acceso a rutas públicas
        is_public = any(path.startswith(public_path) for public_path in self.public_paths)
        print(f"✅ Path is public: {is_public}")
        
        if is_public:
            return await call_next(request)
        
        print(f"🔐 Path requires auth: {path}")
        
        # Verificar presencia de token de autorización
        auth_header = request.headers.get("Authorization")
        
        if not auth_header or not auth_header.startswith("Bearer "):
            print(f"❌ Missing or invalid auth header: {auth_header}")
            return JSONResponse(
                status_code=401,
                content={
                    "detail": "No autorizado: Token de autenticación requerido",
                    "error": "missing_token"
                }
            )
        
        try:
            # Extraer token
            token = auth_header.split(" ")[1]
            print(f"🔑 Token extracted: {token[:20]}...")
            
            # Verificar token con Firebase
            from firebase_admin import auth
            decoded_token = auth.verify_id_token(token)
            
            # Agregar UID del usuario al request state para uso posterior
            request.state.user_uid = decoded_token['uid']
            request.state.user_email = decoded_token.get('email')
            
            # Continuar con el request
            response = await call_next(request)
            return response
            
        except auth.InvalidIdTokenError:
            return JSONResponse(
                status_code=401,
                content={
                    "detail": "Token inválido o expirado",
                    "error": "invalid_token"
                }
            )
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    "detail": f"Error verificando autenticación: {str(e)}",
                    "error": "auth_verification_failed"
                }
            )


class AuditLogMiddleware(BaseHTTPMiddleware):
    """
    Middleware para registrar todas las acciones importantes en audit_logs
    """
    
    def __init__(self, app, enable_logging: bool = True):
        super().__init__(app)
        self.enable_logging = enable_logging
        
        # Métodos que queremos auditar
        self.audit_methods = ["POST", "PUT", "DELETE", "PATCH"]
        
        # Rutas que no queremos auditar (demasiado frecuentes)
        self.skip_paths = [
            "/health",
            "/ping",
            "/metrics",
            "/docs",
            "/openapi.json"
        ]
    
    async def dispatch(self, request: Request, call_next):
        # Si el logging está deshabilitado, saltar
        if not self.enable_logging:
            return await call_next(request)
        
        # Verificar si debemos auditar este request
        should_audit = (
            request.method in self.audit_methods and
            not any(request.url.path.startswith(skip) for skip in self.skip_paths)
        )
        
        if not should_audit:
            return await call_next(request)
        
        # Datos del request
        start_time = time.time()
        user_uid = getattr(request.state, 'user_uid', None)
        user_email = getattr(request.state, 'user_email', None)
        
        # Procesar request
        response = await call_next(request)
        
        # Calcular tiempo de procesamiento
        process_time = time.time() - start_time
        
        # Registrar en audit_logs si el usuario está autenticado
        if user_uid:
            try:
                from database.firebase_config import get_firestore_client
                db = get_firestore_client()
                
                # Crear entrada de log
                log_entry = {
                    "timestamp": datetime.now(timezone.utc),
                    "user_uid": user_uid,
                    "user_email": user_email,
                    "method": request.method,
                    "endpoint": request.url.path,
                    "query_params": dict(request.query_params),
                    "status_code": response.status_code,
                    "process_time_seconds": round(process_time, 3),
                    "client_host": request.client.host if request.client else None,
                    "user_agent": request.headers.get("user-agent", "")[:200]
                }
                
                # Agregar detalles de la acción basados en el endpoint
                log_entry["action"] = self._infer_action(request.method, request.url.path)
                
                # Guardar en Firestore de forma asíncrona (sin bloquear)
                db.collection(FIREBASE_COLLECTIONS["audit_logs"]).add(log_entry)
                
            except Exception as e:
                # No fallar el request si falla el logging
                print(f"⚠️ Error registrando audit log: {e}")
        
        return response
    
    def _infer_action(self, method: str, path: str) -> str:
        """Inferir la acción basándose en el método y ruta"""
        
        actions_map = {
            "POST": {
                "/auth/register": "user_registration",
                "/auth/login": "user_login",
                "/proyectos": "create_proyecto",
                "/contratos": "create_contrato",
                "/reportes": "create_reporte",
            },
            "PUT": {
                "/proyectos": "update_proyecto",
                "/contratos": "update_contrato",
                "/users": "update_user",
            },
            "DELETE": {
                "/proyectos": "delete_proyecto",
                "/contratos": "delete_contrato",
                "/users": "delete_user",
            }
        }
        
        # Buscar coincidencia exacta
        if method in actions_map:
            for route_pattern, action in actions_map[method].items():
                if route_pattern in path:
                    return action
        
        # Acción genérica
        return f"{method.lower()}_{path.split('/')[1] if len(path.split('/')) > 1 else 'unknown'}"
