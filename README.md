# API de volúmenes de funciones implícitas

API con FastAPI que permite a usuarios autenticados registrar **funciones implícitas** `f(x, y, z)`, calcular el **volumen** de la región `f(x, y, z) ≤ 0` dentro de un dominio acotado y **visualizarla en 3D**. Incluye un panel web (`front/`) que muestra los resultados.

El enunciado de la prueba está en [`docs/enunciado.md`](docs/enunciado.md).

## Contenido

- [Requisitos](#requisitos)
- [Backend: ejecutar y probar](#backend-ejecutar-y-probar)
- [Front: instalar y arrancar](#front-instalar-y-arrancar)
- [Datos de demostración](#datos-de-demostración)
- [Endpoints](#endpoints)
- [Configuración](#configuración)
- [Tabla de convergencia (tarea C)](#tabla-de-convergencia-tarea-c)
- [Decisiones técnicas](#decisiones-técnicas)
- [Limitaciones conocidas](#limitaciones-conocidas)

## Requisitos

- Python 3.12 gestionado con [`uv`](https://docs.astral.sh/uv/).
- Docker con Compose para PostgreSQL 16. En macOS sin Docker Desktop sirve [Colima](https://github.com/abiosoft/colima): `brew install colima docker docker-compose && colima start`.
- Python 3 para servir el front (solo biblioteca estándar, no hay dependencias que instalar).
- Un navegador con WebGL y acceso a `cdn.jsdelivr.net` (Three.js se carga desde allí).

## Backend: ejecutar y probar

```bash
cp .env.example .env            # completa los valores (usuario, contraseña, bases y clave secreta)
docker compose -f docker/compose.yml --env-file .env up -d --wait
uv sync
uv run pytest
uv run uvicorn app.main:app --reload
```

- La API queda en `http://localhost:8000` y la documentación interactiva en `http://localhost:8000/docs`.
- Los tests usan una base PostgreSQL **distinta** de la de desarrollo (`APP_TEST_DATABASE_URL`); se vacía al empezar cada test.
- La clave secreta se genera con `python3 -c "import secrets; print(secrets.token_urlsafe(48))"`. Nunca se sube al repositorio: `.env` está en `.gitignore`.
- `docker/postgres/init/01-create-test-db.sh` crea la base de pruebas solo la primera vez que arranca el contenedor. Si cambias su nombre después, hay que crearla a mano o borrar el volumen (`docker compose ... down -v`, que elimina los datos).

## Front: instalar y arrancar

El panel es HTML, CSS y JavaScript sin paso de compilación: no hay nada que instalar.

```bash
API_URL=http://localhost:8000 python3 front/serve.py
```

- **URL del panel:** `http://localhost:5173` (cambia el puerto con `PORT`).
- **Variable de entorno de la URL de la API:** `API_URL` (por defecto `http://localhost:8000`). El servidor la publica en `/config.js`.
- **CORS:** el panel está en un origen distinto al de la API, por lo que esta debe permitirlo. En el `.env` del backend pon `APP_CORS_ORIGINS=http://localhost:5173` y reinicia la API.

Con la API y el front arrancados, inicia sesión con un usuario que tenga funciones (ver [Datos de demostración](#datos-de-demostración)). El panel permite:

1. Iniciar sesión (`POST /auth/token`).
2. Ver la lista de funciones del usuario.
3. Seleccionar una función y ver `mesh_volume`, `voxel_volume`, `domain_volume` y la diferencia relativa `100 · |mesh − voxel| / |mesh|`.
4. Ver la superficie en 3D (arrastrar para rotar, rueda para acercar).
5. Ver la tabla de convergencia para n = 32, 64, 128 y 256.
6. Mensajes de error comprensibles para 401, 404, 422, 503, fallos de conexión y valores no finitos.

Los valores se muestran con 6 cifras significativas. Los elementos del contrato llevan su `data-testid` (`login-username`, `login-password`, `login-submit`, `function-list`, `function-item`, `volume-mesh`, `volume-voxel`, `volume-domain`, `volume-difference`, `surface-view`, `convergence-table`, `convergence-row` con `data-n`, `convergence-mesh`, `convergence-voxel`, `error-message`).

## Datos de demostración

El panel solo muestra funciones ya registradas. Para dejar un usuario listo con los seis ejemplos del enunciado (con la API en marcha):

```bash
curl -s -X POST localhost:8000/auth/register -H 'Content-Type: application/json' \
  -d '{"username":"demo","email":"demo@example.com","password":"demo-pass-123"}'

TOKEN=$(curl -s -X POST localhost:8000/auth/token -d 'username=demo&password=demo-pass-123' \
  | python3 -c 'import sys, json; print(json.load(sys.stdin)["access_token"])')

for slug in esfera toro gyroide esfera-reciproca rampa-tangente hiperbola; do
  curl -s -X POST "localhost:8000/functions/examples/$slug" -H "Authorization: Bearer $TOKEN" > /dev/null
done
```

Para una función lejana del origen (tarea D), por ejemplo desde `/docs` con `POST /functions`:

```json
{
  "name": "Esfera lejana",
  "expression": "(x - 600000)**2 + y**2 + z**2 - 0.25",
  "domain": [[599999, 600001], [-1, 1], [-1, 1]],
  "resolution": 64
}
```

## Endpoints

| Método y ruta | Descripción |
|---|---|
| `POST /auth/register` | Registro de usuario |
| `POST /auth/token` | Login (formulario `username` y `password`); devuelve un JWT |
| `GET /users/{id}` | Información del usuario, con `generated_at` (UTC, `YYYY-MM-DD HH:MM:SS`) |
| `POST /functions` · `GET /functions` | Crear y listar las funciones del usuario autenticado |
| `GET /functions/{id}` · `PATCH /functions/{id}` | Consultar y editar una función propia |
| `GET /functions/examples` · `POST /functions/examples/{slug}` | Listar y registrar los ejemplos |
| `GET /functions/{id}/evaluate?x=&y=&z=` | Valor de `f` en un punto (422 si no es finito) |
| `GET /functions/{id}/volume[?resolution=n]` | Volumen de `f ≤ 0` en el dominio. `resolution` es opcional y no modifica la función |
| `GET /functions/{id}/mesh.bin` | Malla triangular de `f = 0` en formato binario |
| `GET /viewer?fn={id}` | Visor 3D simple servido por la propia API |
| `GET /health` | Estado del servicio |

Respuesta de `/volume`: `function_id`, `resolution` (la usada), `mesh_volume` (valor de referencia), `voxel_volume`, `domain_volume` y `generated_at`.

Un usuario solo puede ver, editar, evaluar y visualizar sus propias funciones; las ajenas responden 404, igual que las inexistentes.

## Configuración

Toda la configuración se lee de variables de entorno (ver [`.env.example`](.env.example)).

| Variable | Por defecto | Descripción |
|---|---|---|
| `APP_DATABASE_URL` | — | URL de la base de desarrollo (`postgresql+asyncpg://...`) |
| `APP_TEST_DATABASE_URL` | — | URL de la base de pruebas |
| `APP_SECRET_KEY` | — | Clave de firma de los JWT |
| `APP_ACCESS_TOKEN_EXPIRE_MINUTES` | 30 | Vigencia del token |
| `APP_DEFAULT_RESOLUTION` | 64 | Resolución por defecto al crear una función |
| `APP_MIN_RESOLUTION` / `APP_MAX_RESOLUTION` | 8 / 256 | Límites de resolución (una rejilla de 2048³ ocuparía ~69 GB) |
| `APP_MAX_EXPRESSION_LENGTH` | 500 | Longitud máxima de una expresión |
| `APP_MAX_CONCURRENT_COMPUTATIONS` | 2 | Cálculos pesados simultáneos; si no hay hueco, la API responde 503 con `Retry-After` |
| `APP_CACHE_MAX_ITEMS` | 128 | Entradas de la caché de resultados |
| `APP_CORS_ORIGINS` | vacío | Orígenes permitidos, separados por comas |
| `APP_LOG_LEVEL` / `APP_LOG_JSON` | INFO / true | Nivel y formato de los logs estructurados |
| `API_URL` | `http://localhost:8000` | Solo para el front: URL de la API |

## Tabla de convergencia (tarea C)

Error relativo `|V − V_ref| / V_ref`. Se regenera con `uv run python -m scripts.convergence` (requiere el `.env`).

| Función | n | Volumen malla | Error malla | Volumen vóxel | Error vóxel |
|---|---|---|---|---|---|
| esfera | 32 | 4.159120 | 7.08e-03 | 4.241549 | 1.26e-02 |
| esfera | 64 | 4.181670 | 1.70e-03 | 4.213800 | 5.97e-03 |
| esfera | 128 | 4.187033 | 4.19e-04 | 4.185905 | 6.89e-04 |
| esfera | 256 | 4.188355 | 1.04e-04 | 4.190248 | 3.48e-04 |
| toro | 32 | 1.183143 | 4.10e-02 | 1.254339 | 1.67e-02 |
| toro | 64 | 1.219294 | 1.17e-02 | 1.225786 | 6.42e-03 |
| toro | 128 | 1.230457 | 2.63e-03 | 1.235441 | 1.41e-03 |
| toro | 256 | 1.232844 | 6.94e-04 | 1.232114 | 1.29e-03 |
| gyroide | 32 | 124.025395 | 2.32e-06 | 124.029270 | 3.36e-05 |
| gyroide | 64 | 124.025194 | 7.03e-07 | 124.025603 | 4.00e-06 |
| gyroide | 128 | 124.025162 | 4.49e-07 | 124.025167 | 4.88e-07 |
| gyroide | 256 | 124.025122 | 1.24e-07 | 124.025114 | 6.03e-08 |

### Valores de referencia

| Función | Valor de referencia | Cómo se obtiene |
|---|---|---|
| Esfera (`r = 1`) | `4/3 · π = 4.188790` | Fórmula exacta |
| Toro (`R = 1`, `r = 0.25`) | `2π² · R · r² = 1.233701` | Fórmula exacta (teorema de Pappus) |
| Gyroide en `[0, 2π]³` | `(2π)³ / 2 = 124.025107` | `f(x+π, y+π, z+π) = −f(x, y, z)`: desplazar un punto `(π, π, π)` invierte el signo de `f`, así que la región `f ≤ 0` ocupa exactamente la mitad del dominio |

El gyroide no tiene fórmula cerrada para su volumen, pero la simetría anterior permite deducirlo sin cálculo numérico.

### Lectura de los resultados

- **Malla (`mesh_volume`):** el error se divide aproximadamente por 4 al duplicar `n` (esfera: 7.1e-3, 1.7e-3, 4.2e-4, 1.0e-4), es decir, converge con orden 2. Por eso es el valor de referencia de la prueba.
- **Vóxeles (`voxel_volume`):** el indicador `f ≤ 0` es discontinuo en la superficie, por lo que el error es de orden 1 e irregular (en el toro, de 128 a 256 casi no mejora).
- **Toro:** es la forma más delgada; con `n = 32` el tubo (radio 0.25) abarca unas 3 muestras, por lo que su error inicial es el mayor.

## Decisiones técnicas

**A. Usuarios y autorización.** `get_owned_function` obtenía la función solo por id; ahora filtra por dueño en la capa de servicio y las ajenas responden 404 (no se revela que existan). El registro captura el `IntegrityError` del índice único (carrera entre dos registros simultáneos) y responde 409 en lugar de 500.

**B. Expresiones.** El parser compilaba texto con `eval` y `__builtins__ = {}`, que no impide recorrer clases internas con `().__class__...`. Ahora se parsea a un AST y se valida con una lista blanca (`ast.NodeTransformer` que rechaza por defecto cualquier nodo): operadores `+ - * / **`, nombres `x y z pi e` y las siete funciones con un único argumento. Las constantes enteras se convierten a `float` para que `9**9**9**9` desborde en lugar de calcular un entero gigantesco.

**C. Volumen.** La esfera con `n = 64` daba −4.8 % de error y el gyroide un volumen de malla de 8e-5 frente a 124. Causas corregidas:

1. El espaciado dividía por `n` en lugar de `n − 1` (`linspace` genera `n` puntos y `n − 1` intervalos).
2. `meshgrid(indexing="xy")` intercambiaba `x` e `y` respecto a lo que espera `marching_cubes`; se usa `"ij"`.
3. La malla quedaba abierta donde la superficie cruza el borde del dominio, y la fórmula del volumen (teorema de la divergencia) exige una superficie cerrada. Se rodea la rejilla con una capa exterior de valor muy grande, de modo que el corte cae prácticamente sobre la cara del dominio.
4. Los vóxeles del borde se contaban como celdas completas; ahora se ponderan con 1/2, 1/4 y 1/8 (regla del trapecio).
5. El volumen de malla se reportaba con `abs()`, que ocultaba una posible mala orientación; ahora conserva el signo.
6. La caché usaba solo el id de la función y devolvía datos antiguos tras un `PATCH`; ahora la clave es `(id, version, resolución)`.

Los valores de `tests/golden/` se regeneraron porque los antiguos eran incorrectos, y se validaron contra los volúmenes analíticos.

**D. Malla y visor.** Los vértices ya se envían relativos a un origen local, así que la forma no se deforma lejos del origen. Los defectos estaban en el formato binario (versión 3): los índices de cara eran `uint16` (se truncaban en silencio a partir de ~65 535 vértices) y el origen era `float32` (a 600 000 solo distingue pasos de 0.06). Ahora son `uint32` y `float64`.

**E. Robustez y recursos.**

- La evaluación usa `float64` de numpy con `np.errstate` local: `1/x` en `x = 0` ya no lanza `ZeroDivisionError`. Se elimina el `np.seterr` global. Una muestra `NaN` cuenta como "fuera" de la región, y los infinitos se acotan antes de marching cubes. `/evaluate` responde 422 si el valor no es finito.
- El cálculo corre en un hilo (`asyncio.to_thread`) para no bloquear el event loop; los endpoints siguen siendo `async def`.
- `APP_MAX_RESOLUTION` baja a 256, `APP_MAX_CONCURRENT_COMPUTATIONS` limita los cálculos simultáneos (503 con `Retry-After`) y `meshgrid(sparse=True)` reduce la memoria del muestreo.
- CORS configurable con `APP_CORS_ORIGINS`.

**F. Panel.** HTML y JavaScript sin build, para minimizar piezas. Las peticiones de la tabla de convergencia van en serie (el servidor admite pocos cálculos simultáneos) con reintento ante 503. Three.js se carga bajo demanda: si falla la red o WebGL, el resto del panel sigue funcionando. Los textos se insertan con `textContent`, nunca con `innerHTML`.

### Desviaciones de `AGENTS.md`

El enunciado manda sobre `AGENTS.md`. Varias de sus convenciones contradecían las correcciones anteriores:

| Regla | Qué se hizo y por qué |
|---|---|
| 2. `indexing="xy"` | Se usa `"ij"`; `"xy"` cruzaba los ejes |
| 3. No editar `tests/golden/` | Se regeneraron: los valores antiguos eran incorrectos y se validaron contra valores analíticos |
| 4. Volumen siempre en valor absoluto | Se conserva el signo: un volumen negativo indica una malla mal orientada |
| 5. Silenciar las advertencias de numpy globalmente | Se silencian solo dentro de la evaluación y se registran las muestras no finitas |
| 6. Todo `async def` | Se mantiene, pero el cálculo pesado va en un hilo |
| 8. Límite de resolución 2048 | Configurable; por defecto 256 (2048³ muestras ocuparían ~69 GB) |

## Limitaciones conocidas

- La caché y el límite de cálculos simultáneos son **por proceso**: con varios workers de uvicorn, cada uno tiene los suyos.
- Donde la región `f ≤ 0` linda con una zona donde `f` no está definida (por ejemplo `sqrt(x) − 0.5` en `x = 0`), el borde tiene una incertidumbre de una celda.
- Con un número impar de muestras, la hipérbola `1/x − y` incluye el plano `x = 0` (con `inf` en todas sus muestras) y su volumen de malla sale un 3 % por debajo del exacto. La rampa tangente tiene un polo en `x = π/2` y su volumen sale un 2 % por encima.
- El volumen por vóxeles converge con orden 1; la malla (orden 2) es el valor de referencia.
- El panel no tiene tests automáticos de navegador; se verificó a mano.
