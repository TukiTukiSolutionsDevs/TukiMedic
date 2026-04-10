# 09 — Contratos de API y WebSocket

## 1. Convenciones

- **Base URL**: `/api/v1`
- **Autenticación**: Bearer JWT en header `Authorization`
- **Content-Type**: `application/json` (excepto file upload: `multipart/form-data`)
- **Errores**: Formato estándar con `status`, `detail`, `code`
- **Paginación**: `?page=1&per_page=20`
- **Fechas**: ISO 8601 (UTC)

## 2. Autenticación

### POST /api/v1/auth/register

```json
// Request
{
  "email": "usuario@example.com",
  "password": "securepassword123",
  "display_name": "Juan Pérez"
}

// Response 201
{
  "user": {
    "id": "uuid",
    "email": "usuario@example.com",
    "display_name": "Juan Pérez",
    "created_at": "2026-04-05T10:00:00Z"
  },
  "tokens": {
    "access_token": "jwt...",
    "refresh_token": "jwt...",
    "expires_in": 3600
  }
}
```

### POST /api/v1/auth/login

```json
// Request
{
  "email": "usuario@example.com",
  "password": "securepassword123"
}

// Response 200
{
  "tokens": {
    "access_token": "jwt...",
    "refresh_token": "jwt...",
    "expires_in": 3600
  }
}
```

### POST /api/v1/auth/refresh

```json
// Request
{
  "refresh_token": "jwt..."
}

// Response 200
{
  "access_token": "jwt...",
  "expires_in": 3600
}
```

## 3. Cases (Casos clínicos)

### POST /api/v1/cases — Crear caso nuevo

```json
// Request
{
  "patient_context": {
    "age": 35,
    "biological_sex": "female",
    "known_conditions": ["diabetes tipo 2"],
    "current_medications": ["metformina 850mg"],
    "known_allergies": ["penicilina"]
  }
}

// Response 201
{
  "id": "uuid",
  "status": "active",
  "patient_context": { ... },
  "created_at": "2026-04-05T10:00:00Z",
  "disclaimer": "Bienvenido/a a MedAgent. Antes de comenzar..."
}
```

### GET /api/v1/cases — Listar casos del usuario

```json
// Response 200
{
  "cases": [
    {
      "id": "uuid",
      "title": "Dolor abdominal recurrente",
      "status": "active",
      "triage_level": "yellow",
      "message_count": 12,
      "active_specialties": ["gastroenterologia", "medicina_interna"],
      "created_at": "2026-04-05T10:00:00Z",
      "updated_at": "2026-04-05T11:30:00Z"
    }
  ],
  "pagination": {
    "page": 1,
    "per_page": 20,
    "total": 3
  }
}
```

### GET /api/v1/cases/{case_id} — Detalle del caso

```json
// Response 200
{
  "id": "uuid",
  "title": "Dolor abdominal recurrente",
  "status": "active",
  "chief_complaint": "Dolor en la parte baja del abdomen desde hace 3 días",
  "triage_level": "yellow",
  "patient_context": { ... },
  "active_specialties": ["gastroenterologia", "medicina_interna"],
  "message_count": 12,
  "documents_count": 2,
  "created_at": "2026-04-05T10:00:00Z",
  "updated_at": "2026-04-05T11:30:00Z"
}
```

### GET /api/v1/cases/{case_id}/summary — Resumen clínico

```json
// Response 200
{
  "case_id": "uuid",
  "summary": {
    "chief_complaint": "Dolor abdominal bajo desde hace 3 días",
    "history_present_illness": "Paciente femenina de 35 años...",
    "active_problems": ["Dolor abdominal a estudio"],
    "current_medications": ["Metformina 850mg"],
    "known_allergies": ["Penicilina"],
    "active_hypotheses": ["Gastroenteritis", "Síndrome de intestino irritable"],
    "pending_studies": ["Hemograma", "PCR", "Ecografía abdominal"],
    "alarm_signs": ["Fiebre >38.5°C", "Sangrado rectal", "Dolor que no cede"],
    "attention_level": "Consultar en 24-48 horas si persiste"
  },
  "version": 3,
  "updated_at": "2026-04-05T11:30:00Z"
}
```

## 4. Messages (Chat)

### POST /api/v1/cases/{case_id}/messages — Enviar mensaje

```json
// Request
{
  "content": "Tengo dolor en la parte baja del abdomen desde hace 3 días",
  "document_ids": []  // IDs de documentos adjuntos (opcional)
}

// Response 202 (Accepted — procesamiento asíncrono)
{
  "message_id": "uuid",
  "status": "processing",
  "stream_url": "/api/v1/chat/stream/uuid"
}
```

**Nota**: La respuesta se recibe por WebSocket (streaming).

### GET /api/v1/cases/{case_id}/messages — Historial de mensajes

```json
// Response 200
{
  "messages": [
    {
      "id": "uuid",
      "role": "system",
      "content": "Bienvenido/a a MedAgent...",
      "message_type": "text",
      "turn_number": 0,
      "created_at": "2026-04-05T10:00:00Z"
    },
    {
      "id": "uuid",
      "role": "user",
      "content": "Tengo dolor en la parte baja del abdomen...",
      "message_type": "text",
      "turn_number": 1,
      "created_at": "2026-04-05T10:00:30Z"
    },
    {
      "id": "uuid",
      "role": "assistant",
      "content": "Entiendo tu preocupación...",
      "message_type": "synthesis",
      "agents_involved": ["triage", "anamnesis", "medicina_general"],
      "turn_number": 2,
      "created_at": "2026-04-05T10:01:15Z"
    }
  ],
  "pagination": { ... }
}
```

## 5. Documents (Archivos)

### POST /api/v1/cases/{case_id}/documents — Upload

```
Content-Type: multipart/form-data

file: [binary]
```

```json
// Response 202
{
  "document_id": "uuid",
  "original_filename": "hemograma_2026.pdf",
  "file_size": 245000,
  "processing_status": "pending",
  "message": "Documento recibido. Procesando..."
}
```

### GET /api/v1/cases/{case_id}/documents — Listar documentos

```json
// Response 200
{
  "documents": [
    {
      "id": "uuid",
      "original_filename": "hemograma_2026.pdf",
      "document_type": "lab_result",
      "document_subtype": "hemograma",
      "processing_status": "done",
      "extracted_summary": "Hemograma completo - Hemoglobina: 11.2 g/dL (baja)...",
      "uploaded_at": "2026-04-05T10:05:00Z"
    }
  ]
}
```

### GET /api/v1/documents/{doc_id}/data — Datos extraídos

```json
// Response 200
{
  "document_id": "uuid",
  "document_type": "lab_result",
  "extracted_values": [
    {
      "analyte": "Hemoglobina",
      "value": 11.2,
      "unit": "g/dL",
      "reference_range": "12.0 - 16.0",
      "flag": "low",
      "interpretation": "Valor por debajo del rango normal"
    },
    {
      "analyte": "Leucocitos",
      "value": 7500,
      "unit": "/μL",
      "reference_range": "4500 - 11000",
      "flag": "normal"
    }
  ]
}
```

## 6. WebSocket — Chat Streaming

### Conexión

```
WS /api/v1/chat/stream/{case_id}
Headers: Authorization: Bearer <jwt>
```

### Eventos del servidor → cliente

```typescript
// Progreso de procesamiento
interface ProgressEvent {
  type: "progress";
  stage: string;           // "triage", "anamnesis", "specialists", etc.
  message: string;         // "Analizando tu consulta..."
  agents_active: string[]; // Agentes actualmente activos
}

// Token de respuesta (streaming)
interface TokenEvent {
  type: "token";
  content: string;         // Token individual
  agent: string;           // Agente que genera
}

// Respuesta completa
interface ResponseEvent {
  type: "response_complete";
  message_id: string;
  content: string;                    // Respuesta completa
  agents_involved: string[];          // Agentes que participaron
  triage_level: string;               // Nivel de triage
  attention_level: string;            // Recomendación de atención
  has_alarm_signs: boolean;
  follow_up_questions: string[];      // Preguntas de seguimiento opcionales
}

// Solicitud de información (el sistema pregunta)
interface ClarificationEvent {
  type: "clarification_needed";
  questions: Array<{
    question: string;
    importance: "critical" | "important" | "helpful";
    options?: string[];      // Opciones predefinidas (opcional)
  }>;
}

// Escalamiento
interface EscalationEvent {
  type: "escalation";
  urgency: "emergency" | "call_911";
  message: string;
  emergency_numbers: string[];
}

// Documento procesado
interface DocumentProcessedEvent {
  type: "document_processed";
  document_id: string;
  status: "done" | "failed";
  summary: string;
}

// Error
interface ErrorEvent {
  type: "error";
  code: string;
  message: string;
}
```

### Eventos del cliente → servidor

```typescript
// Enviar mensaje
interface SendMessageEvent {
  type: "send_message";
  content: string;
  document_ids?: string[];
}

// Typing indicator
interface TypingEvent {
  type: "typing";
  is_typing: boolean;
}

// Cancelar procesamiento
interface CancelEvent {
  type: "cancel";
}
```

## 7. Errores

### Formato estándar

```json
{
  "status": 422,
  "code": "VALIDATION_ERROR",
  "detail": "El campo 'content' no puede estar vacío",
  "timestamp": "2026-04-05T10:00:00Z"
}
```

### Códigos de error

| Código HTTP | Code | Descripción |
|-------------|------|-------------|
| 400 | BAD_REQUEST | Request malformado |
| 401 | UNAUTHORIZED | Token inválido o expirado |
| 403 | FORBIDDEN | Sin permisos para este recurso |
| 404 | NOT_FOUND | Recurso no encontrado |
| 413 | FILE_TOO_LARGE | Archivo supera el límite |
| 415 | UNSUPPORTED_FORMAT | Formato de archivo no soportado |
| 422 | VALIDATION_ERROR | Error de validación |
| 429 | RATE_LIMITED | Demasiadas requests |
| 500 | INTERNAL_ERROR | Error interno del servidor |
| 503 | SERVICE_UNAVAILABLE | LLM o servicio externo no disponible |

## 8. Rate Limiting

```yaml
rate_limits:
  chat_message:
    limit: 30 requests/minute
    burst: 5
    
  document_upload:
    limit: 10 requests/hour
    max_concurrent: 3
    
  case_creation:
    limit: 5 cases/hour
    
  auth:
    login: 5 attempts/15min
    register: 3/hour
```
