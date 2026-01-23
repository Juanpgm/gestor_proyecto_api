/**
 * Cliente JavaScript para Captura 360 - URLs en Firebase
 * Este módulo proporciona funciones para integración fácil del endpoint
 */

class Captura360Client {
    constructor(baseUrl = 'http://localhost:8000') {
        this.baseUrl = baseUrl;
        this.endpoint = `${baseUrl}/unidades-proyecto/captura-estado-360`;
    }

    /**
     * Validar que una URL sea válida
     * @param {string} url - URL a validar
     * @returns {boolean} true si la URL es válida
     */
    validarURL(url) {
        if (!url || typeof url !== 'string') return false;
        return url.startsWith('http://') || url.startsWith('https://');
    }

    /**
     * Crear registro de captura 360
     * @param {Object} params - Parámetros de la captura
     * @returns {Promise<Object>} Respuesta del servidor
     */
    async crearCaptura(params) {
        const {
            upid,
            nombre_up,
            nombre_up_detalle,
            descripcion_intervencion,
            solicitud_intervencion,
            nombre_centro_gestor,
            solicitud_centro_gestor,
            estado_360,
            requiere_alcalde = false,
            entrega_publica = false,
            tipo_visita,
            registrado_por_username,
            registrado_por_email,
            coordinates_type = 'Point',
            coordinates_data, // Array [lng, lat]
            photosUrl = [], // Array de URLs
            observaciones = null
        } = params;

        // Validaciones
        if (!upid || !nombre_up || !estado_360 || !photosUrl.length) {
            throw new Error('Parámetros requeridos faltantes: upid, nombre_up, estado_360, photosUrl');
        }

        // Validar estado_360
        const estadosValidos = ['Antes', 'Durante', 'Después'];
        if (!estadosValidos.includes(estado_360)) {
            throw new Error(`estado_360 inválido. Debe ser uno de: ${estadosValidos.join(', ')}`);
        }

        // Validar URLs
        const urlsInvalidas = photosUrl.filter(url => !this.validarURL(url));
        if (urlsInvalidas.length > 0) {
            throw new Error(`URLs inválidas encontradas: ${urlsInvalidas.join(', ')}`);
        }

        // Validar tipo_visita
        const tiposValidos = ['Verificación', 'Comunicaciones'];
        if (!tiposValidos.includes(tipo_visita)) {
            throw new Error(`tipo_visita inválido. Debe ser uno de: ${tiposValidos.join(', ')}`);
        }

        // Construir FormData
        const formData = new FormData();
        formData.append('upid', upid);
        formData.append('nombre_up', nombre_up);
        formData.append('nombre_up_detalle', nombre_up_detalle);
        formData.append('descripcion_intervencion', descripcion_intervencion);
        formData.append('solicitud_intervencion', solicitud_intervencion);

        // Agregar múltiples centros gestores
        if (Array.isArray(nombre_centro_gestor)) {
            nombre_centro_gestor.forEach(gestor => {
                formData.append('nombre_centro_gestor', gestor);
            });
        } else {
            formData.append('nombre_centro_gestor', nombre_centro_gestor);
        }

        if (Array.isArray(solicitud_centro_gestor)) {
            solicitud_centro_gestor.forEach(solicitud => {
                formData.append('solicitud_centro_gestor', solicitud);
            });
        } else {
            formData.append('solicitud_centro_gestor', solicitud_centro_gestor);
        }

        formData.append('estado_360', estado_360);
        formData.append('requiere_alcalde', String(requiere_alcalde));
        formData.append('entrega_publica', String(entrega_publica));
        formData.append('tipo_visita', tipo_visita);
        formData.append('registrado_por_username', registrado_por_username);
        formData.append('registrado_por_email', registrado_por_email);
        formData.append('coordinates_type', coordinates_type);
        formData.append('coordinates_data', JSON.stringify(coordinates_data));

        // Agregar URLs de fotos
        photosUrl.forEach(url => {
            formData.append('photosUrl', url);
        });

        if (observaciones) {
            formData.append('observaciones', observaciones);
        }

        // Realizar POST
        try {
            const response = await fetch(this.endpoint, {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || `Error HTTP ${response.status}`);
            }

            return await response.json();
        } catch (error) {
            console.error('Error en crearCaptura:', error);
            throw error;
        }
    }

    /**
     * Obtener registros con filtros opcionales
     * @param {Object} filtros - Filtros opcionales
     * @returns {Promise<Object>} Registros encontrados
     */
    async obtenerRegistros(filtros = {}) {
        const params = new URLSearchParams();

        if (filtros.upid) params.append('upid', filtros.upid);
        if (filtros.estado_360) params.append('estado_360', filtros.estado_360);
        if (filtros.nombre_centro_gestor) params.append('nombre_centro_gestor', filtros.nombre_centro_gestor);
        if (filtros.tipo_visita) params.append('tipo_visita', filtros.tipo_visita);

        const url = params.toString() ? `${this.endpoint}?${params.toString()}` : this.endpoint;

        try {
            const response = await fetch(url, {
                method: 'GET'
            });

            if (!response.ok) {
                throw new Error(`Error HTTP ${response.status}`);
            }

            return await response.json();
        } catch (error) {
            console.error('Error en obtenerRegistros:', error);
            throw error;
        }
    }

    /**
     * Obtener registro por UPID
     * @param {string} upid - ID del proyecto
     * @returns {Promise<Object>} Registros del proyecto
     */
    async obtenerPorUPID(upid) {
        return this.obtenerRegistros({ upid });
    }

    /**
     * Obtener registros por estado
     * @param {string} estado_360 - Estado ('Antes', 'Durante', 'Después')
     * @returns {Promise<Object>} Registros del estado
     */
    async obtenerPorEstado(estado_360) {
        return this.obtenerRegistros({ estado_360 });
    }
}

// ============================================================================
// EJEMPLO DE USO
// ============================================================================

// Inicializar cliente
const captura360 = new Captura360Client('http://localhost:8000');

// Ejemplo 1: Crear captura con estado "Durante"
async function ejemplo1_CapturaDurante() {
    try {
        const resultado = await captura360.crearCaptura({
            upid: 'PROYECTO-2024-001',
            nombre_up: 'Parque Central',
            nombre_up_detalle: 'Renovación completa',
            descripcion_intervencion: 'Mejoramiento integral del parque',
            solicitud_intervencion: 'SOLICITUD-2024-001',
            nombre_centro_gestor: 'Secretaría de Infraestructura',
            solicitud_centro_gestor: 'Requiere revisión técnica',
            estado_360: 'Durante',
            requiere_alcalde: false,
            entrega_publica: true,
            tipo_visita: 'Verificación',
            registrado_por_username: 'Juan Pérez',
            registrado_por_email: 'juan@example.com',
            coordinates_type: 'Point',
            coordinates_data: [-76.5225, 3.4516],
            photosUrl: [
                'https://example.com/fotos/durante_1.jpg',
                'https://cloudinary.com/fotos/durante_2.jpg',
                'https://aws-cdn.example.com/fotos/durante_3.jpg'
            ],
            observaciones: 'Captura de estado del proyecto en ejecución'
        });

        console.log('✅ Captura creada:', resultado);
        return resultado;
    } catch (error) {
        console.error('❌ Error:', error.message);
    }
}

// Ejemplo 2: Crear captura con múltiples centros gestores
async function ejemplo2_MultiplesCentros() {
    try {
        const resultado = await captura360.crearCaptura({
            upid: 'PROYECTO-2024-002',
            nombre_up: 'Centro Comercial',
            nombre_up_detalle: 'Modernización',
            descripcion_intervencion: 'Actualización de infraestructura',
            solicitud_intervencion: 'SOLICITUD-2024-002',
            nombre_centro_gestor: [
                'Secretaría de Infraestructura',
                'Secretaría de Ambiente',
                'Secretaría de Comercio'
            ],
            solicitud_centro_gestor: [
                'Revisión técnica',
                'Evaluación ambiental',
                'Revisión de permisos comerciales'
            ],
            estado_360: 'Antes',
            requiere_alcalde: true,
            entrega_publica: false,
            tipo_visita: 'Comunicaciones',
            registrado_por_username: 'María López',
            registrado_por_email: 'maria@example.com',
            coordinates_type: 'Point',
            coordinates_data: [-76.5230, 3.4520],
            photosUrl: [
                'https://example.com/fotos/antes_1.jpg',
                'https://example.com/fotos/antes_2.jpg'
            ]
        });

        console.log('✅ Captura con múltiples centros creada:', resultado);
        return resultado;
    } catch (error) {
        console.error('❌ Error:', error.message);
    }
}

// Ejemplo 3: Obtener registros
async function ejemplo3_ObtenerRegistros() {
    try {
        // Obtener todos
        const todos = await captura360.obtenerRegistros();
        console.log('✅ Todos los registros:', todos);

        // Obtener por UPID
        const porUPID = await captura360.obtenerPorUPID('PROYECTO-2024-001');
        console.log('✅ Registros por UPID:', porUPID);

        // Obtener por estado
        const porEstado = await captura360.obtenerPorEstado('Durante');
        console.log('✅ Registros por estado:', porEstado);

        return { todos, porUPID, porEstado };
    } catch (error) {
        console.error('❌ Error:', error.message);
    }
}

// Exportar para uso en módulos
if (typeof module !== 'undefined' && module.exports) {
    module.exports = Captura360Client;
}

// Ejecutar ejemplos (comentar en producción)
/*
console.log('\n=== EJEMPLO 1: Captura Durante ===');
await ejemplo1_CapturaDurante();

console.log('\n=== EJEMPLO 2: Múltiples Centros ===');
await ejemplo2_MultiplesCentros();

console.log('\n=== EJEMPLO 3: Obtener Registros ===');
await ejemplo3_ObtenerRegistros();
*/
