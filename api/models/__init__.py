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
    # Reporte models
    "AlertaReporte",
    "ArchivoEvidencia",
    "ReporteContratoRequest",
    "ReporteContratoResponse",
    # Proyectos presupuestales constants
    "DEFAULT_COLLECTION_NAME",
    # Availability flags
    "USER_MODELS_AVAILABLE",
    "REPORTE_MODELS_AVAILABLE",
    "PROYECTOS_PRESUPUESTALES_MODELS_AVAILABLE",
]