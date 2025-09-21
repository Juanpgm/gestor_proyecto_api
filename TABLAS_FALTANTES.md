# 🗄️ TABLAS ADICIONALES NECESARIAS EN LA BASE DE DATOS

## ⚠️ IMPORTANTE: CREAR ESTAS TABLAS EN POSTGRESQL

Para completar el sistema de "Gestión de Datos de Usuario", necesitas crear las siguientes tablas adicionales en tu base de datos PostgreSQL:

---

## 1. 📊 **sesiones_activas** - Registro de sesiones de usuario

```sql
CREATE TABLE sesiones_activas (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    usuario_id VARCHAR(36) NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    token_jti VARCHAR(255) NOT NULL UNIQUE, -- JWT ID para identificar token
    ip_address INET,
    user_agent TEXT,
    ubicacion_geografica VARCHAR(200),
    dispositivo VARCHAR(100),
    navegador VARCHAR(100),
    fecha_inicio TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    fecha_ultima_actividad TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    fecha_expiracion TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    activa BOOLEAN DEFAULT TRUE,
    tipo_sesion VARCHAR(20) DEFAULT 'web', -- web, mobile, api
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_sesiones_usuario_id ON sesiones_activas(usuario_id);
CREATE INDEX idx_sesiones_activa ON sesiones_activas(activa);
CREATE INDEX idx_sesiones_token_jti ON sesiones_activas(token_jti);
CREATE INDEX idx_sesiones_expiracion ON sesiones_activas(fecha_expiracion);
```

---

## 2. 🚫 **tokens_blacklist** - Lista negra de tokens JWT

```sql
CREATE TABLE tokens_blacklist (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    token_jti VARCHAR(255) NOT NULL UNIQUE, -- JWT ID
    usuario_id VARCHAR(36) REFERENCES usuarios(id) ON DELETE CASCADE,
    fecha_blacklist TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    fecha_expiracion TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    razon VARCHAR(100), -- logout, security_breach, password_change
    ip_address INET,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_blacklist_token_jti ON tokens_blacklist(token_jti);
CREATE INDEX idx_blacklist_expiracion ON tokens_blacklist(fecha_expiracion);
```

---

## 3. 🔐 **intentos_login** - Control de intentos de login fallidos

```sql
CREATE TABLE intentos_login (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    identificador VARCHAR(150) NOT NULL, -- email, username o telefono
    ip_address INET NOT NULL,
    user_agent TEXT,
    exitoso BOOLEAN NOT NULL DEFAULT FALSE,
    razon_fallo VARCHAR(100), -- wrong_password, user_not_found, account_locked
    timestamp_intento TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    ubicacion_geografica VARCHAR(200),
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_intentos_identificador ON intentos_login(identificador);
CREATE INDEX idx_intentos_ip ON intentos_login(ip_address);
CREATE INDEX idx_intentos_timestamp ON intentos_login(timestamp_intento);
CREATE INDEX idx_intentos_exitoso ON intentos_login(exitoso);
```

---

## 4. 📱 **codigos_verificacion** - Códigos de verificación SMS/Email

```sql
CREATE TABLE codigos_verificacion (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    usuario_id VARCHAR(36) REFERENCES usuarios(id) ON DELETE CASCADE,
    codigo VARCHAR(10) NOT NULL,
    codigo_hash VARCHAR(255) NOT NULL, -- Hash del código para seguridad
    tipo VARCHAR(20) NOT NULL, -- sms, email, phone_login
    contacto VARCHAR(150) NOT NULL, -- telefono o email destino
    intentos_verificacion INTEGER DEFAULT 0,
    max_intentos INTEGER DEFAULT 3,
    usado BOOLEAN DEFAULT FALSE,
    ip_address INET,
    fecha_generacion TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    fecha_expiracion TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    fecha_uso TIMESTAMP WITHOUT TIME ZONE,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_codigos_usuario_id ON codigos_verificacion(usuario_id);
CREATE INDEX idx_codigos_tipo ON codigos_verificacion(tipo);
CREATE INDEX idx_codigos_usado ON codigos_verificacion(usado);
CREATE INDEX idx_codigos_expiracion ON codigos_verificacion(fecha_expiracion);
```

---

## 5. 📋 **logs_auditoria** - Registro de auditoría del sistema

```sql
CREATE TABLE logs_auditoria (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    usuario_id VARCHAR(36) REFERENCES usuarios(id) ON DELETE SET NULL,
    accion VARCHAR(50) NOT NULL, -- login, logout, register, password_change, etc.
    entidad VARCHAR(50), -- usuarios, roles, tokens
    entidad_id VARCHAR(50),
    detalles JSONB,
    ip_address INET,
    user_agent TEXT,
    resultado VARCHAR(20) NOT NULL, -- success, failure, error
    mensaje TEXT,
    metadatos JSONB,
    timestamp_accion TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_logs_usuario_id ON logs_auditoria(usuario_id);
CREATE INDEX idx_logs_accion ON logs_auditoria(accion);
CREATE INDEX idx_logs_timestamp ON logs_auditoria(timestamp_accion);
CREATE INDEX idx_logs_resultado ON logs_auditoria(resultado);
CREATE INDEX idx_logs_entidad ON logs_auditoria(entidad);
```

---

## 6. ⚙️ **configuracion_sistema** - Configuraciones dinámicas

```sql
CREATE TABLE configuracion_sistema (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    clave VARCHAR(100) NOT NULL UNIQUE,
    valor TEXT,
    tipo VARCHAR(20) DEFAULT 'string', -- string, integer, boolean, json
    categoria VARCHAR(50) DEFAULT 'general', -- auth, email, sms, security
    descripcion TEXT,
    es_sensitiva BOOLEAN DEFAULT FALSE, -- Para datos como API keys
    activa BOOLEAN DEFAULT TRUE,
    usuario_modificacion VARCHAR(36) REFERENCES usuarios(id),
    fecha_modificacion TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_config_clave ON configuracion_sistema(clave);
CREATE INDEX idx_config_categoria ON configuracion_sistema(categoria);
CREATE INDEX idx_config_activa ON configuracion_sistema(activa);
```

---

## 7. 🔄 **Modificaciones a tabla existente `usuarios`**

```sql
-- Agregar campos adicionales a la tabla usuarios existente
ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS fecha_ultimo_cambio_password TIMESTAMP WITHOUT TIME ZONE;
ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS intentos_login_fallidos INTEGER DEFAULT 0;
ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS fecha_bloqueo TIMESTAMP WITHOUT TIME ZONE;
ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS ip_ultimo_login INET;
ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS configuracion_notificaciones JSONB DEFAULT '{"email": true, "sms": false, "push": false}';
ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS metadatos JSONB DEFAULT '{}';

-- Crear índices adicionales
CREATE INDEX IF NOT EXISTS idx_usuarios_fecha_bloqueo ON usuarios(fecha_bloqueo);
CREATE INDEX IF NOT EXISTS idx_usuarios_intentos_fallidos ON usuarios(intentos_login_fallidos);
```

---

## 📝 **Variables de entorno adicionales**

Agregar a tu archivo `.env.local`:

```env
# JWT Configuration
JWT_SECRET_KEY=tu-clave-secreta-muy-segura-aqui-cambiar-en-produccion
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7

# Security Settings
MAX_LOGIN_ATTEMPTS=5
LOCKOUT_DURATION_MINUTES=15
PASSWORD_RESET_EXPIRE_HOURS=24
PHONE_VERIFICATION_EXPIRE_MINUTES=10

# Email Configuration (opcional)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=tu-email@gmail.com
SMTP_PASSWORD=tu-app-password
SMTP_TLS=true

# SMS Configuration (opcional)
SMS_PROVIDER=twilio
SMS_API_KEY=tu-api-key
SMS_API_SECRET=tu-api-secret
SMS_FROM_NUMBER=+57xxxxxxxxxx

# Google OAuth (opcional)
GOOGLE_CLIENT_ID=tu-google-client-id
GOOGLE_CLIENT_SECRET=tu-google-client-secret

# Security
BCRYPT_ROUNDS=12
SESSION_TIMEOUT_HOURS=24
```

---

## 🚀 **Datos iniciales recomendados**

Después de crear las tablas, ejecutar:

```sql
-- Insertar configuraciones iniciales
INSERT INTO configuracion_sistema (clave, valor, categoria, descripcion) VALUES
('max_login_attempts', '5', 'auth', 'Máximo número de intentos de login fallidos'),
('lockout_duration_minutes', '15', 'auth', 'Duración del bloqueo en minutos'),
('password_min_length', '8', 'auth', 'Longitud mínima de contraseña'),
('session_timeout_hours', '24', 'auth', 'Tiempo de expiración de sesión en horas'),
('email_verification_required', 'true', 'auth', 'Requiere verificación de email'),
('phone_verification_required', 'false', 'auth', 'Requiere verificación de teléfono');

-- Insertar roles por defecto si no existen
INSERT INTO roles (id, nombre, descripcion, nivel) VALUES
(1, 'Usuario básico', 'Acceso básico de lectura a proyectos', 1),
(2, 'Supervisor', 'Supervisión de proyectos y equipos', 2),
(3, 'Jefe', 'Gestión de departamento y proyectos', 3),
(4, 'Director', 'Dirección de secretaría/dependencia', 4),
(5, 'Admin', 'Administración completa del sistema', 5)
ON CONFLICT (id) DO NOTHING;
```

---

## ⚡ **Comando de ejecución**

Ejecuta estos scripts SQL en tu base de datos PostgreSQL para completar la implementación del sistema de gestión de usuarios.

**¡IMPORTANTE!** 🚨 Asegúrate de hacer backup de tu base de datos antes de ejecutar estos scripts.
