"""
API Models Package
Modelos Pydantic para validación de datos
"""

try:
    from .user_models import (
        # Request models
        UserRegistrationRequest,
        UserLoginRequest,
        PasswordUpdateRequest,
        PasswordResetRequest,
        GoogleAuthRequest,
        PhoneAuthInitRequest,
        PhoneAuthVerifyRequest,
        SessionValidationRequest,
        TokenRevocationRequest,
        UserDeletionRequest,
        # Empréstito models
        EmprestitoRequest,
        EmprestitoResponse,
        ProyeccionEmprestitoUpdateRequest,
        ProyeccionEmprestitoUpdateResponse,
        ProyeccionEmprestitoRegistroRequest,
        ProyeccionEmprestitoRegistroResponse,
        PagoEmprestitoRequest,
        PagoEmprestitoResponse,
        RPCUpdateRequest,
        RPCUpdateResponse,
        # Response models
        UserResponse,
        AuthMethodsResponse,
        UserStatisticsResponse,
        StandardResponse,
        ValidationErrorResponse,
        # Filter models
        UserListFilters,
        # Validation models
        EmailValidationRequest,
        PasswordValidationRequest,
        PhoneValidationRequest,
        # Config models
        SystemConfigResponse,
    )
    USER_MODELS_AVAILABLE = True
except ImportError as e:
    print(f"Warning: User models not available: {e}")
    USER_MODELS_AVAILABLE = False

try:
    from .reporte_models import (
        # Reporte models
        AlertaReporte,
        ArchivoEvidencia,
        ReporteContratoRequest,
        ReporteContratoResponse,
    )
    REPORTE_MODELS_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Reporte models not available: {e}")
    REPORTE_MODELS_AVAILABLE = False

try:
    from .proyectos_presupuestales_models import (
        # Constants only
        PROYECTOS_PRESUPUESTALES_MODELS_AVAILABLE,
        DEFAULT_COLLECTION_NAME,
    )
    PROYECTOS_PRESUPUESTALES_MODELS_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Proyectos presupuestales models not available: {e}")
    PROYECTOS_PRESUPUESTALES_MODELS_AVAILABLE = False

try:
    from .flujo_caja_models import (
        # Flujo de caja models
        FlujoCajaRequest,
        FlujoCajaResponse,
        FlujoCajaUploadRequest,
        FlujoCajaFilters,
        FLUJO_CAJA_MODELS_AVAILABLE,
    )
    FLUJO_CAJA_MODELS_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Flujo caja models not available: {e}")
    FLUJO_CAJA_MODELS_AVAILABLE = False

try:
    from .captura_360_models import (
        # Captura 360 models
        CapturaEstado360Request,
        CapturaEstado360Response,
        UpEntorno,
        CoordinatesGPS,
        PhotosUrl,
        CAPTURA_360_MODELS_AVAILABLE,
        COLLECTION_NAME as CAPTURA_360_COLLECTION_NAME,
        ESTADO_360_MAPPING,
    )
    CAPTURA_360_MODELS_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Captura 360 models not available: {e}")
    CAPTURA_360_MODELS_AVAILABLE = False

__all__ = [
    # Request models
    "UserRegistrationRequest",
    "UserLoginRequest", 
    "PasswordUpdateRequest",
    "PasswordResetRequest",
    "GoogleAuthRequest",
    "PhoneAuthInitRequest",
    "PhoneAuthVerifyRequest",
    "SessionValidationRequest",
    "TokenRevocationRequest",
    "UserDeletionRequest",
    # Empréstito models
    "EmprestitoRequest",
    "EmprestitoResponse",
    "ProyeccionEmprestitoUpdateRequest",
    "ProyeccionEmprestitoUpdateResponse",
    "ProyeccionEmprestitoRegistroRequest",
    "ProyeccionEmprestitoRegistroResponse",
    "PagoEmprestitoRequest",
    "PagoEmprestitoResponse",
    # Response models
    "UserResponse",
    "AuthMethodsResponse",
    "UserStatisticsResponse", 
    "StandardResponse",
    "ValidationErrorResponse",
    # Filter models
    "UserListFilters",
    # Validation models
    "EmailValidationRequest",
    "PasswordValidationRequest",
    "PhoneValidationRequest",
    # Config models
    "SystemConfigResponse",
    # Flujo de caja models
    "FlujoCajaRequest",
    "FlujoCajaResponse", 
    "FlujoCajaUploadRequest",
    "FlujoCajaFilters",
    # Reporte models
    "AlertaReporte",
    "ArchivoEvidencia",
    "ReporteContratoRequest",
    "ReporteContratoResponse",
    # Captura 360 models
    "CapturaEstado360Request",
    "CapturaEstado360Response",
    "UpEntorno",
    "CoordinatesGPS",
    "PhotosUrl",
    "CAPTURA_360_COLLECTION_NAME",
    "ESTADO_360_MAPPING",
    # Proyectos presupuestales constants
    "DEFAULT_COLLECTION_NAME",
    # Availability flags
    "USER_MODELS_AVAILABLE",
    "REPORTE_MODELS_AVAILABLE",
    "PROYECTOS_PRESUPUESTALES_MODELS_AVAILABLE",
    "FLUJO_CAJA_MODELS_AVAILABLE",
    "CAPTURA_360_MODELS_AVAILABLE",
]