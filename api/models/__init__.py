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
    # Availability flags
    "USER_MODELS_AVAILABLE",
]