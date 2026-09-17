# NEXUS LIVE // T-80 — Motor de Reservas de Alta Concurrencia

## Stack seleccionado

- **Lenguaje:** Python 3.11+
- **Framework web:** FastAPI
- **Servidor ASGI:** Uvicorn
- **Validacion:** Pydantic v2
- **Testing:** pytest + pytest-asyncio + httpx
- **Arquitectura:** Hexagonal (Ports & Adapters)

## Arquitectura

```
codigo/
├── src/nexus_live/
│   ├── domain/              # Nucleo: entidades, enums, excepciones, servicios
│   │   ├── enums.py         # SeatStatus, HoldStatus, PaymentResult, CircuitState
│   │   ├── exceptions.py    # Excepciones del dominio
│   │   ├── models.py        # Seat, Hold, Confirmation, Transition
│   │   └── services.py      # IdGenerator, PricingService, HoldFactory, PayloadHasher
│   ├── application/         # Casos de uso + puertos (interfaces)
│   │   ├── ports/           # Interfaces: SeatRepository, HoldRepository, PaymentGateway, etc.
│   │   ├── dto.py           # Objetos de transferencia de datos
│   │   ├── hold_seats.py    # Crear HOLD (FASE 1 + 2)
│   │   ├── confirm_hold.py  # Confirmar compra (FASE 3)
│   │   ├── simulate_race.py # Simular carrera (FASE 2)
│   │   └── ...
│   ├── infrastructure/      # Adaptadores concretos (driven)
│   │   ├── in_memory_seat_repository.py    # Thread-safe con RLock
│   │   ├── mock_payment_gateway.py         # Pago mock con circuit breaker
│   │   ├── circuit_breaker.py              # Circuit breaker thread-safe
│   │   └── ...
│   └── adapters/            # Adaptadores de entrada (driving)
│       ├── api/             # API REST (FastAPI)
│       └── web/static/      # Interfaz web HTML
├── tests/                   # Tests de las 3 fases + race condition
├── docs/sesion_ia.md        # Bitacora de uso de GLM 5.2
├── requirements.txt         # Dependencias de Python
├── requerimientos.txt       # Requerimientos funcionales y no funcionales
└── main.py                  # Punto de entrada
```

### Capas hexagonales

| Capa | Responsabilidad | Direccion |
|---|---|---|
| **domain** | Entidades, reglas de negocio, excepciones | Nucleo (sin dependencias externas) |
| **application** | Casos de uso, puertos (interfaces) | Orquesta el dominio |
| **infrastructure** | Implementaciones de puertos (en memoria, mock) | Driven adapters |
| **adapters** | API REST, interfaz web | Driving adapters |

## Como instalar dependencias

```bash
cd codigo
pip install -r requirements.txt
```

## Como iniciar el sistema

```bash
cd codigo
python main.py
```

O con parametros personalizados:

```bash
python main.py --port 8080 --ttl 30 --max-seats 4
```

El servidor estara disponible en:
- **Interfaz web:** http://localhost:8000
- **API docs (Swagger):** http://localhost:8000/docs
- **API REST:** http://localhost:8000/api

## Como ejecutar pruebas

```bash
cd codigo
pytest -v
```

## Como abrir la interfaz

1. Iniciar el servidor: `python main.py`
2. Abrir http://localhost:8000 en el navegador
3. Usar las pestañas: Asientos, Reservas, Carrera, Pagos & CB

## Como simular concurrencia

### Desde la interfaz web
1. Pestaña "Carrera"
2. Ingresar el asiento (ej. `VIP-A-001`)
3. Ingresar numero de usuarios (ej. 20)
4. Click "SIMULAR CARRERA"

### Desde la API
```bash
curl -X POST http://localhost:8000/api/simulate/race \
  -H "Content-Type: application/json" \
  -d '{"seat_id": "VIP-A-001", "num_users": 100}'
```

### Desde los tests
```bash
pytest tests/test_race_condition.py -v
```

## Estrategia de idempotencia

- El cliente envia un header `Idempotency-Key` opcional.
- Se calcula un hash del payload: `user_id|event_id|sorted(seat_ids)`.
- **Misma clave + mismo payload:** retorna el resultado cacheado (no crea otro HOLD).
- **Misma clave + payload diferente:** retorna `IDEMPOTENCY_CONFLICT` (HTTP 409).
- **Sin clave:** la operacion no es idempotente (comportamiento normal).
- El orden de los `seat_ids` no afecta el hash (se ordenan antes de hashear).

## Estrategia para evitar overselling

- **Mecanismo:** `threading.RLock` en `InMemorySeatRepository`.
- **Secuencia critica atomica:**
  1. Adquirir lock del repositorio.
  2. Verificar que TODOS los asientos esten AVAILABLE.
  3. Verificar el limite de asientos del usuario.
  4. Marcar todos los asientos como HELD.
  5. Crear y guardar el HOLD.
  6. Liberar el lock.
- El lock es reentrante (RLock) para permitir operaciones anidadas.
- **Garantia:** Ningun otro hilo puede leer/modificar los asientos mientras se ejecuta la secuencia.

## Manejo de expiracion de HOLDs

- Cada HOLD tiene un `expires_at = created_at + TTL`.
- TTL configurable (default: 120 segundos).
- `ExpireHoldsUseCase` recorre los holds activos y expira los vencidos.
- Al expirar: `HELD -> AVAILABLE` para cada asiento del hold.
- Se puede ejecutar manualmente via `POST /api/expire` o como background task.

## Estrategia ante fallos del proveedor de pagos

| Resultado | Accion | Razon |
|---|---|---|
| **APPROVED** | `HELD -> SOLD`, compra confirmada | Pago exitoso |
| **DECLINED** | `HELD -> AVAILABLE`, hold cancelado | Pago rechazado, liberar asientos |
| **ERROR** | Hold permanece `ACTIVE` | Resultado ambiguo, no liberar sin certeza |
| **TIMEOUT** | Hold permanece `ACTIVE` | El pago podria haberse procesado, no doble-cobrar |
| **CB OPEN** | `PAYMENT_SERVICE_UNAVAILABLE` | Circuit breaker protege el sistema |

### Circuit Breaker

- **CLOSED:** Las llamadas pasan normalmente.
- **3 fallos consecutivos -> OPEN:** No se hacen llamadas al proveedor.
- **15 segundos -> HALF_OPEN:** Se permite 1 llamada de prueba.
- **Exito en HALF_OPEN -> CLOSED:** Servicio recuperado.
- **Fallo en HALF_OPEN -> OPEN:** Servicio sigue degradado.

## Trazabilidad

Cada cambio de estado registra una `Transition` con:
- `hold_id`, `seat_id`, `user_id`
- `from_state`, `to_state`
- `reason` (hold_created, hold_expired, payment_approved, etc.)
- `timestamp`

Consulta via `GET /api/audit/{hold_id}`.

## Bonos implementados

- **Bono B - Prueba de concurrencia real:** Test con 200 hilos concurrentes sobre 1 asiento, demostrando 1 ganador y 199 rechazadas.
- **Bono C - Registro de auditoria reproducible:** Trazabilidad completa de transiciones consultable via API.

## Endpoints de la API

| Metodo | Path | Descripcion |
|---|---|---|
| GET | `/api/seats` | Listar asientos |
| GET | `/api/seats?only_available=true` | Listar asientos disponibles |
| POST | `/api/holds` | Crear reserva (HOLD) |
| GET | `/api/holds/{hold_id}` | Consultar reserva |
| DELETE | `/api/holds/{hold_id}` | Liberar reserva |
| POST | `/api/holds/confirm` | Confirmar compra |
| POST | `/api/simulate/race` | Simular carrera |
| GET | `/api/audit/{hold_id}` | Trazabilidad |
| GET | `/api/circuit-breaker` | Estado del circuit breaker |
| POST | `/api/expire` | Expirar holds vencidos |
| GET | `/api/config` | Configuracion del sistema |
