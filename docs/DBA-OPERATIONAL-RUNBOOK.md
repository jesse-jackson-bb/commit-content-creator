# Database Administration (DBA) Operational Runbook & Disaster Recovery Plan

Este runbook documenta los estándares de administración de bases de datos, optimización de índices, retención de datos, salvaguardas de integridad referencial, sanitización de datos (PII/GDPR) y protocolos de recuperación ante desastres (DR) para **LaborIN / Commit Content Creator**.

---

## 1. Arquitectura de Persistencia y Topología

La capa de datos se estructura en un modelo reactivo multi-inquilino sobre Convex, garantizando consistencia ACID por documento y suscripciones en tiempo real.

| Capa | Componente | Función Principal |
| :--- | :--- | :--- |
| **Motor DB** | Convex Document Store | Almacenamiento transaccional, ordenamiento indexado y streams en tiempo real. |
| **Integración Backend** | FastAPI Gateway (`ConvexGateway`) | Conexión tipada y validación de esquemas vía Pydantic. |
| **Capa de Diagnóstico** | `convex/convex/diagnostics.ts` & `dba_healthcheck.py` | Auditoría de integridad referencial y telemetría de latencia. |
| **Capa de Retención** | `convex/convex/retention.ts` | Purga automatizada de sesiones WhatsApp y rotación de logs. |
| **Sanitización & Masking** | `apps/backend/scripts/dba_data_masker.py` | Anonimización de PII para entornos de staging / pre-producción. |

---

## 2. Estrategia de Indexación y Patrones de Consulta

Para prevenir escaneos de tabla completa (*table scans*), todas las consultas de alta concurrencia están respaldadas por índices compuestos dedicados en `convex/convex/schema.ts`:

### Tabla de Índices Críticos

| Colección | Nombre de Índice | Campos | Propósito Operativo |
| :--- | :--- | :--- | :--- |
| `commits` | `by_repository_status` | `["repositoryId", "status"]` | Búsqueda O(log N) de commits pendientes de análisis IA. |
| `commits` | `by_repository_committed_at` | `["repositoryId", "committedAt"]` | Ordenamiento temporal eficiente en digest histórico. |
| `stories` | `by_user_status` | `["userId", "status"]` | Filtrado instantáneo de historias aprobadas/detectadas por usuario. |
| `stories` | `by_repository_status` | `["repositoryId", "status"]` | Filtrado por repositorio y ciclo de vida de historia. |
| `posts` | `by_user_status` | `["userId", "status"]` | Lista de publicaciones en borrador o pendientes de aprobación. |
| `posts` | `by_user_created_at` | `["userId", "createdAt"]` | Historial paginado cronológico en Dashboard. |
| `approvalRequests`| `by_user_status` | `["userId", "status"]` | Bandeja de entrada de aprobaciones WhatsApp por usuario. |
| `approvalRequests`| `by_phone_status` | `["recipientPhone", "status"]` | Enrutamiento de respuestas inbound de WhatsApp. |
| `whatsappSessions`| `by_expires_at` | `["expiresAt"]` | Sweep y purga por lotes de sesiones vencidas (24h TTL). |
| `activityEvents`  | `by_timestamp` | `["timestamp"]` | Rotación y poda de logs antiguos sin escaneo de colección. |

---

## 3. Políticas de Retención de Datos y Purga Automatizada

### 3.1 TTL de Sesiones WhatsApp (24 Horas)
- Las sesiones interactivas de WhatsApp caducan a las 24 horas del último mensaje (`expiresAt = lastInboundAt + 24h`).
- La mutación `retention:purgeExpiredSessions` ejecuta la limpieza por lotes (`batchSize: 100`) indexada por `by_expires_at`.

### 3.2 Rotación de Logs de Actividad (`activityEvents`)
- Retención predeterminada: **30 días**.
- La mutación `retention:pruneActivityLogs` poda eventos más antiguos que el umbral de retención mediante el índice `by_timestamp`.

---

## 4. Auditoría de Integridad Referencial y Diagnóstico DBA

Para verificar que no existan registros huérfanos entre colecciones relacionales, ejecutar la herramienta de diagnóstico:

```bash
# Diagnóstico completo de latencia, volumen e integridad referencial
uv run python apps/backend/scripts/dba_healthcheck.py

# Salida estructurada JSON para alertas e integraciones CI/CD
uv run python apps/backend/scripts/dba_healthcheck.py --json
```

### Métricas de Integridad Auditadas
1. **Stories $\rightarrow$ Users & Repositories:** Confirma que toda historia apunte a un usuario y repositorio válidos.
2. **Posts $\rightarrow$ Users & Stories:** Valida pertenencia de borradores a historias generadas.
3. **ApprovalRequests $\rightarrow$ Posts & PostVersions:** Valida coherencia del flujo de aprobación WhatsApp.

---

## 5. Sanitización de Datos (PII / GDPR) y Carga en Staging

Para clonar datos de producción a entornos de prueba o staging sin violar regulaciones de privacidad:

1. **Teléfonos WhatsApp:** Se enmascaran preservando código de país (`+51987654321` $\rightarrow$ `+51900000000`).
2. **Correos Electrónicos:** Se anonimizan con pseudónimo determinístico (`dev_<sha256>@domain.com`).
3. **Tokens OAuth Cifrados:** Se sustituyen por tokens sintéticos seguros (`mock_enc_tok_<hash>`).
4. **Verificación de Integridad:** Se genera un checksum criptográfico SHA-256 (`compute_snapshot_checksum`) para validar la consistencia del snapshot.

Ejecución de la suite de pruebas DBA:
```bash
uv run pytest apps/backend/tests/test_dba_tools.py
```

---

## 6. Acuerdos de Nivel de Servicio (SLA) & Disaster Recovery (DR)

### Objetivos de Continuidad del Negocio
- **RPO (Recovery Point Objective):** $\le 5\text{ minutos}$ (respaldo continuo transaccional).
- **RTO (Recovery Time Objective):** $\le 15\text{ minutos}$ (restauración del endpoint y reconciliación de esquemas).

### Procedimiento de Emergencia y Rollback
1. **Detección de Anomalía:** Alerta disparada por `dba_healthcheck.py` con código de salida no-cero (`status: DEGRADED`).
2. **Congelamiento de Mutaciones:** Deshabilitar temporalmente los webhooks de entrada en FastAPI si hay riesgo de corrupción de datos.
3. **Restauración Point-in-Time (PITR):** Restaurar el deployment de Convex al snapshot estable previo a la anomalía.
4. **Validación de Esquema:** Ejecutar `pnpm --filter @proof-of-work/convex typecheck` y verificar con `dba_healthcheck.py`.
5. **Reanudación del Tráfico:** Reactivar webhooks y validar procesamiento de eventos en vivo.
