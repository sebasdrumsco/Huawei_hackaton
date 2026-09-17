# Bitacora de uso de GLM 5.2

## Sesion: NEXUS LIVE // T-80

### Prompt inicial de arquitectura

**Prompt:**
> Revisa el RETO_3_NEXUS_LIVE.md y ejecuta las 3 fases indicadas en una arquitectura hexagonal dentro de `codigo/`. Crea `requerimientos.txt` y sigue las reglas de Documentacion.md y Promts.md.

**Respuesta de GLM 5.2:**
- Analizo el enunciado completo (993 lineas).
- Identifico 4 fases + bonos + casos limite.
- Propuso arquitectura hexagonal con Python 3.11 + FastAPI.
- Definio la estructura de carpetas:
  ```
  codigo/
  ├── src/nexus_live/
  │   ├── domain/           # Entidades, enums, excepciones, servicios
  │   ├── application/      # Casos de uso + puertos (interfaces)
  │   ├── infrastructure/   # Adaptadores concretos (en memoria, mock)
  │   └── adapters/         # API REST + interfaz web
  ├── tests/
  └── docs/
  ```

---

### Prompt que permitio resolver un problema importante

**Problema:** Como garantizar que 100 solicitudes concurrentes sobre un mismo asiento produzcan exactamente 1 ganador.

**Analisis de GLM 5.2:**
- El GIL de Python no protege operaciones compuestas (leer + escribir).
- Se necesita un lock explicito alrededor de la seccion critica.
- La seccion critica es: verificar disponibilidad + reservar asientos + crear hold.

**Solucion:**
- `InMemorySeatRepository` usa `threading.RLock`.
- `HoldSeatsUseCase._create_hold()` adquiere el lock antes de verificar y libera en `finally`.
- El lock es reentrante (RLock) para permitir operaciones anidadas.

**Resultado:** 200 hilos concurrentes -> 1 ganador, 199 rechazadas, 0 overselling.

---

### Propuesta de GLM 5.2 que hubo que corregir

**Propuesta original:** En caso de TIMEOUT del proveedor de pagos, liberar el hold inmediatamente.

**Correccion del equipo:** NO liberar el hold en TIMEOUT o ERROR porque:
1. El pago podria haberse procesado correctamente (doble cobro al reintentar).
2. Liberar un asiento mientras existe una operacion potencialmente pendiente es incoherente.
3. El enunciado explicitamente dice: "Un timeout NO significa automaticamente que el pago fue rechazado".

**Decision final:**
| Resultado | Accion sobre el hold | Accion sobre asientos |
|---|---|---|
| APPROVED | CONFIRMED | HELD -> SOLD |
| DECLINED | CANCELLED | HELD -> AVAILABLE |
| ERROR | Permanece ACTIVE | Sin cambio |
| TIMEOUT | Permanece ACTIVE | Sin cambio |

---

### Error encontrado con ayuda del agente

**Error:** Al ejecutar el test de 100 usuarios concurrentes, ocasionalmente aparecian 2 ganadores.

**Diagnostico de GLM 5.2:**
- El `Barrier` sincroniza el inicio, pero sin el lock del repositorio, dos hilos pueden leer el asiento como AVAILABLE antes de que cualquiera lo marque como HELD.
- La operacion de verificar + reservar no era atomica.

**Fix:** Mover la adquisicion del lock al inicio de `_create_hold()`, antes de `get_many()`, y liberarlo despues de `save_many()`.

---

### Decision donde el equipo no siguio la primera recomendacion

**Recomendacion de GLM 5.2:** Usar `asyncio` con `asyncio.Lock` para toda la aplicacion.

**Decision del equipo:** Usar FastAPI con endpoints sincronos + `threading.RLock` porque:
1. FastAPI ejecuta endpoints sincronos en un threadpool, dando concurrencia real.
2. `threading.Lock` es mas simple y demostrable que `asyncio.Lock` para este caso.
3. Los tests de concurrencia con `ThreadPoolExecutor` son mas directos.
4. El enunciado pide demostrar thread-safety, no async-safety.

---

## Resumen de actividades con GLM 5.2

| Actividad | Prompts | Resultado |
|---|---|---|
| Analisis del enunciado | 1 | Plan completo |
| Diseno de arquitectura | 1 | Hexagonal + Python/FastAPI |
| Implementacion FASE 1 | 3 | Seat, Hold, repos, use cases |
| Implementacion FASE 2 | 2 | Locks + idempotencia |
| Implementacion FASE 3 | 2 | Pago mock + circuit breaker |
| Implementacion FASE 4 | 1 | API REST + interfaz web |
| Tests | 2 | 30+ tests, todos pasan |
| Debugging concurrencia | 1 | Fix de race condition |
| Documentacion | 1 | README + bitacora + requerimientos |
