# Manual de Usuario - NEXUS LIVE // Control Room

## Como ejecutar pruebas manualmente desde la interfaz grafica

---

## 1. Iniciar el sistema

### Paso 1: Instalar dependencias

Abrir una terminal y ejecutar:

```bash
cd sebastian-betancourt-g3/codigo
pip install -r requirements.txt
```

### Paso 2: Iniciar el servidor

```bash
python main.py
```

Debera aparecer el banner de NEXUS LIVE indicando que el servidor esta activo.

### Paso 3: Abrir la interfaz

Abrir el navegador en:

```
http://localhost:8000
```

La interfaz tiene 4 pestañas:

| Pestaña | Funcionalidad |
|---|---|
| **Asientos** | Mapa de asientos y creacion de reservas |
| **Reservas** | Consultar, liberar y confirmar reservas |
| **Carrera** | Simulacion de concurrencia |
| **Pagos & CB** | Circuit breaker y control del proveedor de pagos |

### Leyenda de colores de asientos

| Color | Estado | Significado |
|---|---|---|
| Verde | AVAILABLE | Disponible para reservar |
| Amarillo | HELD | Reservado temporalmente |
| Rojo | SOLD | Vendido |

---

## 2. Escenario A - Reserva normal

**Objetivo:** Verificar que un asiento disponible pasa a HELD y luego a SOLD tras el pago.

### Pasos

1. **Pestaña "Asientos"**
2. Hacer click sobre un asiento verde (ej. `A-101`). El asiento se resaltara con borde cyan.
3. Hacer click sobre un segundo asiento verde (ej. `A-102`).
4. Verificar que el campo "Asientos seleccionados" muestra: `A-101, A-102`.
5. En "User ID", ingresar: `usr_judge_001`
6. En "Event ID", ingresar: `aurora-bogota-2026`
7. Click en **"Crear HOLD"**.

### Resultado esperado

- Aparece una tarjeta con:
  - **Hold ID:** (ej. `hold_00001`)
  - **Estado:** `HELD`
  - **Total:** `$420000 COP`
  - **Expira en:** `120s` (o el TTL configurado)
- En el mapa de asientos, `A-101` y `A-102` cambian a color amarillo (HELD).

### Continuar con la confirmacion

8. **Pestaña "Reservas"**
9. El "Hold ID" ya deberia estar autocompletado.
10. En "Payment Token", ingresar: `tok_test_91827`
11. Click en **"Confirmar Compra"**.

### Resultado esperado

- Mensaje verde: `COMPRA CONFIRMADA`
- Volver a la pestaña "Asientos" y refrescar: `A-101` y `A-102` ahora estan en rojo (SOLD).

---

## 3. Escenario B - Reserva expirada

**Objetivo:** Verificar que un HOLD expira automaticamente y el asiento vuelve a AVAILABLE.

> **Nota:** Para una demo rapida, iniciar el servidor con TTL corto:
> ```bash
> python main.py --ttl 10
> ```

### Pasos

1. **Pestaña "Asientos"**
2. Seleccionar un asiento verde (ej. `A-103`).
3. Click en **"Crear HOLD"**.
4. Verificar que el asiento cambia a amarillo (HELD).
5. **No confirmar la compra.**
6. Esperar a que pase el TTL (10 segundos si se inicio con `--ttl 10`).
7. **Pestaña "Pagos & CB"**
8. Click en **"Expirar Holds Vencidos"**.

### Resultado esperado

- Mensaje: `Holds expirados: 1`
- Volver a "Asientos" y refrescar: `A-103` vuelve a verde (AVAILABLE).

---

## 4. Escenario C - Concurrencia (carrera)

**Objetivo:** Demostrar que N usuarios compitiendo por 1 asiento producen exactamente 1 ganador.

### Pasos

1. **Pestaña "Carrera"**
2. En "Asiento", ingresar: `VIP-A-001`
3. En "N usuarios", ingresar: `20`
4. Click en **"SIMULAR CARRERA"**.
5. Esperar unos segundos (el sistema lanza 20 hilos concurrentes).

### Resultado esperado

```
20 solicitudes -> 1 asiento (VIP-A-001)
1 ganador
19 rechazadas
0 overselling
```

- Solo un usuario obtiene un Hold ID.
- Los otros 19 son rechazados con `seat_not_available`.

### Probar con mas usuarios

- Cambiar "N usuarios" a `100` o `200`.
- El resultado siempre debe ser: **1 ganador, N-1 rechazadas**.

---

## 5. Escenario D - Reintento idempotente

**Objetivo:** Verificar que repetir la misma solicitud con la misma `Idempotency-Key` no crea un segundo HOLD.

### Pasos

1. **Pestaña "Asientos"**
2. Seleccionar un asiento verde (ej. `A-104`).
3. En "Idempotency", ingresar: `reserve-test-001`
4. Click en **"Crear HOLD"**.
5. Anotar el **Hold ID** mostrado (ej. `hold_00003`).
6. **Sin cambiar la seleccion**, hacer click en **"Crear HOLD"** nuevamente.

### Resultado esperado

- Se muestra el **mismo Hold ID** (`hold_00003`).
- No se crea un segundo HOLD.
- El resultado es identico al primero.

---

## 6. Escenario E - Conflicto de idempotencia

**Objetivo:** Verificar que reutilizar una `Idempotency-Key` con un payload diferente genera un conflicto.

### Pasos

1. **Pestaña "Asientos"**
2. Seleccionar el asiento `A-105`.
3. En "Idempotency", ingresar: `reserve-test-002`
4. Click en **"Crear HOLD"**. Anotar el Hold ID.
5. Ahora **deseleccionar** `A-105` (click sobre el) y **seleccionar** `A-106`.
6. Mantener la misma Idempotency: `reserve-test-002`
7. Click en **"Crear HOLD"**.

### Resultado esperado

- Respuesta de error: `IDEMPOTENCY_CONFLICT`
- No se crea ningun HOLD nuevo.
- El asiento `A-105` permanece en HELD (del primer HOLD).
- El asiento `A-106` permanece en AVAILABLE.

---

## 7. Escenario F - Pago degradado (Circuit Breaker)

**Objetivo:** Demostrar que el circuit breaker protege al sistema cuando el proveedor de pagos falla repetidamente.

### Paso 1: Forzar errores de pago

1. **Pestaña "Pagos & CB"**
2. En "Resultado", seleccionar: `ERROR`
3. Click en **"Aplicar"**.
4. Verificar el estado del circuit breaker: `CLOSED`, fallos: `0`.

### Paso 2: Crear un HOLD

5. **Pestaña "Asientos"**
6. Seleccionar `A-107` y crear un HOLD.
7. Anotar el Hold ID.

### Paso 3: Intentar confirmar 3 veces (provocar OPEN)

8. **Pestaña "Reservas"**
9. Ingresar el Hold ID del paso 7.
10. Click en **"Confirmar Compra"**. Resultado: `payment_error`.
11. Click en **"Confirmar Compra"** nuevamente. Resultado: `payment_error`.
12. Click en **"Confirmar Compra"** nuevamente. Resultado: `payment_error`.

### Paso 4: Verificar circuit breaker OPEN

13. **Pestaña "Pagos & CB"**
14. Click en **"Refrescar estado"**.
15. Verificar: estado `OPEN`, fallos: `3`.

### Paso 5: Intentar confirmar con CB OPEN

16. **Pestaña "Reservas"**
17. Crear otro HOLD sobre `A-108`.
18. Click en **"Confirmar Compra"**.

### Resultado esperado

- Respuesta: `PAYMENT_SERVICE_UNAVAILABLE`
- El asiento `A-108` **NO** se marca como SOLD.
- Permanece en HELD.

### Paso 6: Recuperar el circuit breaker (HALF_OPEN -> CLOSED)

19. **Pestaña "Pagos & CB"**
20. En "Resultado", seleccionar: `APPROVED`
21. Click en **"Aplicar"**.
22. Esperar 15 segundos (recovery timeout del circuit breaker).
23. Click en **"Refrescar estado"**. Deberia mostrar: `HALF_OPEN`.
24. **Pestaña "Reservas"**
25. Ingresar el Hold ID del asiento `A-108`.
26. Click en **"Confirmar Compra"**.

### Resultado esperado

- `COMPRA CONFIRMADA`. El pago pasa.
- El circuit breaker vuelve a `CLOSED`.

---

## 8. Escenario G - Pago rechazado (DECLINED)

**Objetivo:** Verificar que un pago rechazado libera los asientos.

### Pasos

1. **Pestaña "Pagos & CB"**
2. En "Resultado", seleccionar: `DECLINED`. Click en **"Aplicar"**.
3. **Pestaña "Asientos"**
4. Seleccionar `A-109` y crear un HOLD.
5. **Pestaña "Reservas"**
6. Click en **"Confirmar Compra"**.

### Resultado esperado

- Respuesta: `payment_declined`
- El hold se cancela.
- `A-109` vuelve a verde (AVAILABLE).
- Se puede crear un nuevo HOLD sobre el mismo asiento.

---

## 9. Escenario H - Pago con TIMEOUT

**Objetivo:** Verificar que un timeout NO libera el asiento ni marca SOLD.

### Pasos

1. **Pestaña "Pagos & CB"**
2. En "Resultado", seleccionar: `TIMEOUT`. Click en **"Aplicar"**.
3. **Pestaña "Asientos"**
4. Seleccionar `A-110` y crear un HOLD.
5. **Pestaña "Reservas"**
6. Click en **"Confirmar Compra"**.

### Resultado esperado

- Respuesta: `payment_timeout`
- Mensaje: "Hold remains active. Payment may have succeeded; do NOT double-charge."
- El asiento `A-110` **permanece en HELD** (amarillo).
- El hold sigue activo y se puede reintentar.

### Reintento despues de timeout

7. Cambiar el resultado a `APPROVED` (Pestaña "Pagos & CB").
8. Volver a "Reservas" y click en **"Confirmar Compra"**.
9. Resultado: `COMPRA CONFIRMADA`. El asiento pasa a SOLD.

---

## 10. Escenario I - Liberar un HOLD manualmente

**Objetivo:** Verificar que se puede liberar una reserva sin confirmar compra.

### Pasos

1. **Pestaña "Asientos"**
2. Seleccionar `B-001` y crear un HOLD.
3. **Pestaña "Reservas"**
4. El Hold ID deberia estar autocompletado.
5. Click en **"Liberar HOLD"**.

### Resultado esperado

- Mensaje: `HOLD liberado`
- `B-001` vuelve a verde (AVAILABLE).

---

## 11. Escenario J - Limite de asientos por usuario

**Objetivo:** Verificar que un usuario no puede tener mas de 6 asientos en reservas activas.

### Pasos

1. **Pestaña "Asientos"**
2. Seleccionar 6 asientos verdes (ej. `B-001` a `B-006`).
3. Click en **"Crear HOLD"**. Deberia ser exitoso.
4. Seleccionar 1 asiento mas (`B-007`).
5. Click en **"Crear HOLD"**.

### Resultado esperado

- Respuesta: `REJECTED - seat_limit_exceeded`
- No se crea el segundo HOLD.
- `B-007` permanece en AVAILABLE.

---

## 12. Escenario K - Reserva todo-o-nada

**Objetivo:** Verificar que si un asiento no esta disponible, no se reserva parcialmente.

### Pasos

1. **Pestaña "Asientos"**
2. Seleccionar `A-101` y crear un HOLD. (A-101 pasa a HELD)
3. Seleccionar `A-101`, `A-102` y `A-103` simultaneamente.
4. Click en **"Crear HOLD"**.

### Resultado esperado

- Respuesta: `REJECTED - seat_not_available`
- `A-102` y `A-103` **no** se reservan (permanecen AVAILABLE).
- La operacion falla completa, no hay reserva parcial.

---

## 13. Consultar trazabilidad de una reserva

**Objetivo:** Ver el historial de transiciones de estado de una reserva.

### Pasos

1. Crear un HOLD sobre `A-111` (siguiendo el Escenario A).
2. Confirmar la compra (pago APPROVED).
3. En una terminal o navegador, abrir:

```
http://localhost:8000/api/audit/hold_XXXXX
```

(reemplazar `hold_XXXXX` con el Hold ID real)

### Resultado esperado

```json
[
  {
    "hold_id": "hold_00001",
    "seat_id": "A-111",
    "from_state": "AVAILABLE",
    "to_state": "HELD",
    "reason": "hold_created",
    "timestamp": "2026-09-17T..."
  },
  {
    "hold_id": "hold_00001",
    "seat_id": "A-111",
    "from_state": "HELD",
    "to_state": "SOLD",
    "reason": "payment_approved",
    "timestamp": "2026-09-17T..."
  }
]
```

---

## 14. Ejecutar pruebas automatizadas

Ademas de las pruebas manuales desde la interfaz, el sistema incluye 39 pruebas automatizadas:

```bash
cd sebastian-betancourt-g3/codigo
pytest -v
```

### Resultado esperado

```
39 passed in ~10s
```

### Ejecutar solo una fase

```bash
pytest tests/test_phase1_seat_lock.py -v          # FASE 1
pytest tests/test_phase2_concurrency_idempotency.py -v  # FASE 2
pytest tests/test_phase3_payment_circuit_breaker.py -v  # FASE 3
pytest tests/test_race_condition.py -v            # Bono B
```

---

## 15. API REST (alternativa a la interfaz)

Todos los escenarios tambien se pueden ejecutar via API REST:

### Listar asientos
```bash
curl http://localhost:8000/api/seats
```

### Crear HOLD
```bash
curl -X POST http://localhost:8000/api/holds \
  -H "Content-Type: application/json" \
  -d '{"user_id":"usr_001","event_id":"aurora-bogota-2026","seat_ids":["A-101"]}'
```

### Crear HOLD con idempotencia
```bash
curl -X POST http://localhost:8000/api/holds \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: reserve-001" \
  -d '{"user_id":"usr_001","event_id":"aurora-bogota-2026","seat_ids":["A-101"]}'
```

### Confirmar compra
```bash
curl -X POST http://localhost:8000/api/holds/confirm \
  -H "Content-Type: application/json" \
  -d '{"hold_id":"hold_00001","payment_token":"tok_test"}'
```

### Simular carrera
```bash
curl -X POST http://localhost:8000/api/simulate/race \
  -H "Content-Type: application/json" \
  -d '{"seat_id":"VIP-A-001","num_users":100}'
```

### Ver circuit breaker
```bash
curl http://localhost:8000/api/circuit-breaker
```

### Ver trazabilidad
```bash
curl http://localhost:8000/api/audit/hold_00001
```

### Documentacion interactiva (Swagger)
```
http://localhost:8000/docs
```

---

## Resumen de escenarios

| Escenario | Descripcion | Resultado esperado |
|---|---|---|
| A | Reserva normal | AVAILABLE -> HELD -> SOLD |
| B | Reserva expirada | HELD -> AVAILABLE tras TTL |
| C | Concurrencia | N usuarios -> 1 ganador, N-1 rechazadas |
| D | Reintento idempotente | Misma key + mismo payload = mismo hold |
| E | Conflicto idempotencia | Misma key + payload diferente = IDEMPOTENCY_CONFLICT |
| F | Pago degradado | Circuit breaker OPEN -> PAYMENT_SERVICE_UNAVAILABLE |
| G | Pago rechazado | DECLINED -> asientos liberados |
| H | Pago timeout | TIMEOUT -> hold permanece activo |
| I | Liberar HOLD | HELD -> AVAILABLE manualmente |
| J | Limite de asientos | >6 asientos -> seat_limit_exceeded |
| K | Todo-o-nada | 1 asiento no disponible -> operacion falla completa |
