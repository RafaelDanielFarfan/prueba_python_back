# Prueba de desarrollador backend con FastAPI — v2

> La versión anterior del enunciado se conserva en [`docs/legacy/README_v1.md`](docs/legacy/README_v1.md) solo como referencia histórica.

En esta prueba trabajarás sobre una API existente, construida con FastAPI, que permite a usuarios autenticados registrar **funciones implícitas** `f(x, y, z)`, calcular el **volumen** de la región `f(x, y, z) ≤ 0` dentro de un dominio acotado y **visualizarla en 3D** en el navegador.

El repositorio ya contiene una implementación parcial. Tu trabajo consiste en completarla, corregirla y dejarla lista para producción.

## Objetivo de la prueba

Evaluar tu capacidad para:

- Leer, entender y razonar sobre código existente.
- Diseñar e implementar endpoints con FastAPI siguiendo buenas prácticas.
- Validar que los resultados que entrega tu código son correctos, no solo que el código "corre".
- Trabajar con Git de forma ordenada y profesional.

**Se permite el uso de asistentes de IA.** Sin embargo, eres responsable de cada línea que entregues. En la sustentación deberás explicar cualquier parte del código y cualquier commit de tu historial.

## Metodología

- Python 3.12 gestionado con [`uv`](https://docs.astral.sh/uv/).
- FastAPI + Pydantic v2.
- **PostgreSQL 16 como base de datos (requisito obligatorio)**, con acceso asíncrono mediante SQLAlchemy 2 y `asyncpg`. Se incluye `docker/compose.yml` para levantarla en local.
- Toda configuración se lee de variables de entorno (ver `.env.example`). No se aceptan valores sensibles en el código.
- Tests con `pytest` contra una base PostgreSQL de pruebas, separada de la de desarrollo. No se aceptan tests de integración sobre SQLite.

### Puesta en marcha

```bash
cp .env.example .env            # completa los valores
docker compose -f docker/compose.yml --env-file .env up -d --wait
uv sync
uv run pytest
uv run uvicorn app.main:app --reload
```

## Conceptos

Una **función implícita** es una expresión en las variables `x`, `y`, `z`. La superficie `f(x, y, z) = 0` separa el espacio en dos regiones; nos interesa la región **interior**, `f(x, y, z) ≤ 0`.

Cada función se guarda con:

| Campo | Descripción |
|---|---|
| `name` | Nombre descriptivo |
| `expression` | Expresión en `x`, `y`, `z` (ver operadores permitidos) |
| `domain` | Caja `[[xmin, xmax], [ymin, ymax], [zmin, zmax]]` donde se evalúa |
| `resolution` | Número de muestras por eje de la rejilla regular |

### Operadores y funciones permitidos en `expression`

| Elemento | Permitido |
|---|---|
| Variables | `x`, `y`, `z` |
| Constantes | números reales, `pi`, `e` |
| Aritmética | `+`, `-`, `*`, `/`, `**` |
| Funciones | `sin`, `cos`, `tan`, `sqrt`, `exp`, `log`, `abs` |

Cualquier otra construcción debe ser rechazada.

### Ejemplos

| Nombre | Expresión | Dominio sugerido |
|---|---|---|
| Esfera | `x**2 + y**2 + z**2 - 1` | `[-1.5, 1.5]³` |
| Toro | `(sqrt(x**2 + y**2) - 1)**2 + z**2 - 0.25**2` | `[-1.5, 1.5]³` |
| Gyroide | `sin(x)*cos(y) + sin(y)*cos(z) + sin(z)*cos(x)` | `[0, 2*pi]³` |
| Esfera recíproca | `1 - 1/(x**2 + y**2 + z**2)` | `[-2, 2]³` |
| Rampa tangente | `tan(x) - z` | `[0, 3]³` |
| Hipérbola | `1/x - y` | `[-2, 2]³` |

## Endpoints

| Método y ruta | Descripción |
|---|---|
| `POST /auth/register` | Registro de usuario |
| `POST /auth/token` | Login; devuelve un JWT |
| `GET /users/{id}` | Información del usuario. Incluye `generated_at` con la fecha y hora actual (UTC) en formato `YYYY-MM-DD HH:MM:SS` |
| `POST /functions` · `GET /functions` | Crear y listar **las funciones del usuario autenticado** |
| `GET /functions/{id}` · `PATCH /functions/{id}` | Consultar y editar una función propia |
| `GET /functions/{id}/evaluate?x=&y=&z=` | Valor de `f` en un punto |
| `GET /functions/{id}/volume` | Volumen de la región `f ≤ 0` dentro del dominio |
| `GET /functions/{id}/mesh.bin` | Malla triangular de la superficie `f = 0` en formato binario |
| `GET /viewer?fn={id}` | Visor 3D de la función |

### Formato de respuesta de `GET /functions/{id}/volume`

Objeto JSON con estos campos:

| Campo | Descripción |
|---|---|
| `function_id` | Id de la función |
| `resolution` | Resolución usada en el cálculo |
| `mesh_volume` | Volumen calculado a partir de la malla de la superficie `f = 0`. Es el **valor de referencia** de la prueba |
| `voxel_volume` | Volumen estimado contando los puntos de la rejilla con `f ≤ 0` |
| `domain_volume` | Volumen de la caja del dominio |
| `generated_at` | Fecha y hora actual (UTC), formato `YYYY-MM-DD HH:MM:SS` |

Puedes añadir campos, pero estos deben mantenerse.

## Requisitos generales

1. Un usuario **solo** puede ver, editar, evaluar y visualizar sus propias funciones.
2. Todo error debe registrarse con logs estructurados.
3. La API nunca debe responder `500` ante una expresión válida.
4. El servicio debe seguir respondiendo a otras peticiones mientras calcula volúmenes o mallas.
5. Los límites de recursos (por ejemplo, la resolución máxima) deben ser configurables por variables de entorno.
6. Si el front se sirve desde un origen distinto al de la API, los orígenes permitidos (CORS) deben configurarse por variable de entorno.

## Tareas

### A. Usuarios y autorización
Completa el registro, el login y `GET /users/{id}`. Garantiza el requisito general 1 y demuéstralo con tests.

### B. Expresiones
Asegura que solo se aceptan las expresiones descritas en «Operadores y funciones permitidos». Las expresiones inválidas deben responder `422` con un mensaje claro.

### C. Volumen
`GET /functions/{id}/volume` debe ser correcto. Incluye en tu README una **tabla de convergencia** con el error relativo frente al valor analítico para la esfera, el toro y el gyroide, usando resoluciones 32, 64, 128 y 256. Explica cómo obtuviste los valores de referencia.

### D. Malla y visor
La superficie debe verse correctamente en `/viewer` para todos los ejemplos, incluso cuando el dominio está lejos del origen (por ejemplo, `x ∈ [599999, 600001]`).

### E. Robustez y recursos
Cumple los requisitos generales 3, 4 y 5.

### F. Panel de resultados (front)
Construye una interfaz web que muestre los resultados que genera tu API. **Puedes usar la tecnología que prefieras** (HTML y JavaScript, React, Vue, Svelte, etc.) y reutilizar o reemplazar el visor de `/viewer`.

El panel debe permitir:

1. Iniciar sesión con usuario y contraseña (`POST /auth/token`).
2. Ver la lista de funciones del usuario autenticado.
3. Seleccionar una función y ver su `mesh_volume`, su `voxel_volume`, su `domain_volume` y la **diferencia relativa** entre los dos primeros, expresada en porcentaje: `100 · |mesh_volume − voxel_volume| / |mesh_volume|`.
4. Ver la superficie en 3D.
5. Ver la **tabla de convergencia** de la función seleccionada para n = 32, 64, 128 y 256, con el volumen por malla y por vóxeles de cada fila.
6. Mostrar mensajes de error comprensibles cuando la API responda `401`, `404`, `422` o `503`, o cuando un valor no sea un número finito.

#### Contrato mínimo

Para poder revisar tu front con independencia de la tecnología:

- Tu `README.md` indica los comandos para instalarlo y arrancarlo, la URL en la que queda disponible y la variable de entorno que configura la URL de la API.
- Estos elementos llevan el atributo `data-testid` indicado:

| `data-testid` | Elemento |
|---|---|
| `login-username`, `login-password`, `login-submit` | Campos y botón del formulario de acceso |
| `function-list` | Contenedor de la lista de funciones |
| `function-item` | Cada función de la lista; su texto incluye el nombre |
| `volume-mesh`, `volume-voxel`, `volume-domain` | Volúmenes de la función seleccionada |
| `volume-difference` | Diferencia relativa, en porcentaje |
| `surface-view` | Contenedor de la vista 3D |
| `convergence-table` | Tabla de convergencia |
| `convergence-row` | Cada fila de la tabla; lleva además el atributo `data-n` con el valor de n |
| `convergence-mesh`, `convergence-voxel` | Celdas de la fila con el volumen por malla y por vóxeles |
| `error-message` | Mensaje de error visible |

- El texto de los valores numéricos incluye el número con al menos 4 cifras significativas.

## Entregables

1. Un **fork** de este repositorio con tu solución.
2. **Una rama por tarea** (A–E), integrada a `develop` mediante Pull Request.
3. **Commits atómicos realizados manualmente.** No se aceptan entregas con un único commit ni con *squash* de todo el trabajo. Cada mensaje de commit debe describir con precisión su contenido.
4. Un `README.md` con:
   - Descripción del proyecto y cómo ejecutarlo y probarlo.
   - La tabla de convergencia de la tarea C.
   - Cómo instalar y arrancar el front, la URL en la que queda y la variable de entorno que configura la URL de la API.
5. **Sustentación** de 45 minutos, sin asistentes de IA:
   - 20 min de demostración: levantar el proyecto y el front siguiendo tu README y mostrar los resultados.
   - 25 min de preguntas sobre tu código, tus decisiones y tu historial de commits.

## Recomendaciones sobre el uso de IA y la explicabilidad

El uso de asistentes de inteligencia artificial está permitido como herramienta de apoyo durante el desarrollo, pero ten presente estas pautas fundamentales para la evaluación:

1. **Responsabilidad y autoría sobre el código:** Eres el responsable final de cada línea, abstracción y prueba en tu entrega. Durante la sustentación se asumirá que comprendes a fondo la totalidad del código y su impacto en el sistema.
2. **Explicabilidad por encima de la automatización:** La sesión en vivo se realiza **sin asistentes de IA** y evalúa tu criterio de ingeniería. Deberás poder explicar el porqué de tus decisiones técnicas, las alternativas que descartaste, predecir el comportamiento del sistema ante diversos escenarios y justificar el contenido de cada commit.
3. **Validación crítica:** No asumas que el código generado por una IA es correcto únicamente porque "corre" o porque los tests existentes pasen en verde. Tu capacidad para verificar la exactitud de los resultados frente a valores teóricos, identificar posibles fallas de seguridad y optimizar el uso de recursos es el foco principal de la prueba.
4. **Higiene del historial en Git:** Realiza tus commits manualmente y de forma atómica, asegurando que cada mensaje describa con precisión el diff correspondiente. El historial de commits debe reflejar un proceso de razonamiento gradual, no volcados masivos o automáticos.

