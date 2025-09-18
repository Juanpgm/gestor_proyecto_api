"""
Manejo de errores funcional usando Result/Either patterns
"""
from typing import Generic, TypeVar, Union, Callable, Optional, Any
from dataclasses import dataclass
from enum import Enum
import logging
from datetime import datetime

T = TypeVar('T')
E = TypeVar('E')
R = TypeVar('R')  # Agregado el tipo R que faltaba

# ============================================================================
# RESULT TYPE PARA PROGRAMACIÓN FUNCIONAL
# ============================================================================

@dataclass(frozen=True)
class Ok(Generic[T]):
    """Representa un resultado exitoso"""
    value: T

@dataclass(frozen=True)
class Err(Generic[E]):
    """Representa un error"""
    error: E

# Tipo Result que puede ser Ok o Err
Result = Union[Ok[T], Err[E]]

class ResultHelper:
    """Helpers para trabajar con Result types"""
    
    @staticmethod
    def ok(value: T) -> Ok[T]:
        """Crea un resultado exitoso"""
        return Ok(value)
    
    @staticmethod
    def err(error: E) -> Err[E]:
        """Crea un resultado de error"""
        return Err(error)
    
    @staticmethod
    def is_ok(result: Result[T, E]) -> bool:
        """Verifica si el resultado es exitoso"""
        return isinstance(result, Ok)
    
    @staticmethod
    def is_err(result: Result[T, E]) -> bool:
        """Verifica si el resultado es un error"""
        return isinstance(result, Err)
    
    @staticmethod
    def unwrap(result: Result[T, E]) -> T:
        """Extrae el valor si es Ok, lanza excepción si es Err"""
        if isinstance(result, Ok):
            return result.value
        raise ValueError(f"Tried to unwrap Err: {result.error}")
    
    @staticmethod
    def unwrap_or(result: Result[T, E], default: T) -> T:
        """Extrae el valor si es Ok, retorna default si es Err"""
        if isinstance(result, Ok):
            return result.value
        return default
    
    @staticmethod
    def map_result(result: Result[T, E], fn: Callable[[T], R]) -> Result[R, E]:
        """Aplica función si es Ok, propaga error si es Err"""
        if isinstance(result, Ok):
            try:
                return Ok(fn(result.value))
            except Exception as e:
                return Err(str(e))
        return result
    
    @staticmethod
    def map_error(result: Result[T, E], fn: Callable[[E], R]) -> Result[T, R]:
        """Transforma el error si es Err"""
        if isinstance(result, Err):
            return Err(fn(result.error))
        return result
    
    @staticmethod
    def and_then(result: Result[T, E], fn: Callable[[T], Result[R, E]]) -> Result[R, E]:
        """Chain operations that can fail"""
        if isinstance(result, Ok):
            return fn(result.value)
        return result

# ============================================================================
# TIPOS DE ERROR ESPECÍFICOS
# ============================================================================

class ErrorType(Enum):
    """Tipos de errores en la aplicación"""
    VALIDATION_ERROR = "validation_error"
    NOT_FOUND = "not_found"
    DATABASE_ERROR = "database_error"
    BUSINESS_LOGIC_ERROR = "business_logic_error"
    AUTHENTICATION_ERROR = "authentication_error"
    AUTHORIZATION_ERROR = "authorization_error"
    EXTERNAL_SERVICE_ERROR = "external_service_error"
    TIMEOUT_ERROR = "timeout_error"
    RATE_LIMIT_ERROR = "rate_limit_error"

@dataclass(frozen=True)
class AppError:
    """Error estructurado de la aplicación"""
    error_type: ErrorType
    message: str
    details: Optional[dict] = None
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            object.__setattr__(self, 'timestamp', datetime.utcnow())

# ============================================================================
# FUNCIONES PARA MANEJO DE ERRORES
# ============================================================================

def safe_execute(fn: Callable[[], T]) -> Result[T, AppError]:
    """Ejecuta una función de manera segura capturando excepciones"""
    try:
        result = fn()
        return Ok(result)
    except ValueError as e:
        return Err(AppError(
            error_type=ErrorType.VALIDATION_ERROR,
            message=str(e)
        ))
    except FileNotFoundError as e:
        return Err(AppError(
            error_type=ErrorType.NOT_FOUND,
            message=str(e)
        ))
    except Exception as e:
        return Err(AppError(
            error_type=ErrorType.DATABASE_ERROR,
            message=f"Error inesperado: {str(e)}"
        ))

def validate_and_execute(
    validator: Callable[[], bool],
    executor: Callable[[], T],
    error_message: str
) -> Result[T, AppError]:
    """Valida condiciones antes de ejecutar"""
    try:
        if not validator():
            return Err(AppError(
                error_type=ErrorType.VALIDATION_ERROR,
                message=error_message
            ))
        return safe_execute(executor)
    except Exception as e:
        return Err(AppError(
            error_type=ErrorType.VALIDATION_ERROR,
            message=f"Error en validación: {str(e)}"
        ))

def combine_results(*results: Result[T, AppError]) -> Result[list, AppError]:
    """Combina múltiples resultados, falla si alguno falla"""
    values = []
    for result in results:
        if isinstance(result, Err):
            return result
        values.append(result.value)
    return Ok(values)

# ============================================================================
# LOGGING ESTRUCTURADO
# ============================================================================

class StructuredLogger:
    """Logger estructurado para la aplicación"""
    
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)
    
    def log_result(self, result: Result[T, AppError], operation: str) -> Result[T, AppError]:
        """Log del resultado de una operación"""
        if isinstance(result, Ok):
            self.logger.info(f"✅ {operation}: Success")
        else:
            self.logger.error(
                f"❌ {operation}: {result.error.error_type.value} - {result.error.message}"
            )
        return result
    
    def log_operation(self, operation: str, **context):
        """Log de operación con contexto"""
        context_str = " | ".join([f"{k}={v}" for k, v in context.items()])
        self.logger.info(f"🔄 {operation}: {context_str}")

# ============================================================================
# DECORADORES FUNCIONALES
# ============================================================================

def with_error_handling(error_type: ErrorType = ErrorType.DATABASE_ERROR):
    """Decorador para manejo automático de errores"""
    def decorator(fn):
        def wrapper(*args, **kwargs) -> Result[Any, AppError]:
            try:
                result = fn(*args, **kwargs)
                return Ok(result)
            except Exception as e:
                return Err(AppError(
                    error_type=error_type,
                    message=str(e),
                    details={"function": fn.__name__, "args": str(args)[:100]}
                ))
        return wrapper
    return decorator

def with_validation(validator: Callable[[Any], bool], error_message: str):
    """Decorador para validación automática"""
    def decorator(fn):
        def wrapper(*args, **kwargs):
            # Validar argumentos si es necesario
            if args and not validator(args[0]):
                return Err(AppError(
                    error_type=ErrorType.VALIDATION_ERROR,
                    message=error_message
                ))
            return fn(*args, **kwargs)
        return wrapper
    return decorator

def with_logging(logger: StructuredLogger, operation_name: str):
    """Decorador para logging automático"""
    def decorator(fn):
        def wrapper(*args, **kwargs):
            logger.log_operation(operation_name)
            result = fn(*args, **kwargs)
            if hasattr(result, '__class__') and 'Result' in str(type(result)):
                logger.log_result(result, operation_name)
            return result
        return wrapper
    return decorator

# ============================================================================
# HELPERS ESPECÍFICOS PARA LA APLICACIÓN
# ============================================================================

def create_validation_error(message: str, details: dict = None) -> Err[AppError]:
    """Crea un error de validación"""
    return Err(AppError(
        error_type=ErrorType.VALIDATION_ERROR,
        message=message,
        details=details
    ))

def create_not_found_error(resource: str, identifier: str = None) -> Err[AppError]:
    """Crea un error de recurso no encontrado"""
    message = f"{resource} no encontrado"
    if identifier:
        message += f" con ID: {identifier}"
    
    return Err(AppError(
        error_type=ErrorType.NOT_FOUND,
        message=message,
        details={"resource": resource, "identifier": identifier}
    ))

def create_database_error(operation: str, details: str = None) -> Err[AppError]:
    """Crea un error de base de datos"""
    message = f"Error en operación de base de datos: {operation}"
    if details:
        message += f" - {details}"
    
    return Err(AppError(
        error_type=ErrorType.DATABASE_ERROR,
        message=message,
        details={"operation": operation, "details": details}
    ))

# Instancia global del logger
app_logger = StructuredLogger("gestor_proyecto_api")