# Análisis final

1. ¿Qué diferencias encontró entre los contratos de los proveedores?

El proveedor A entrega los datos en formato **JSON**, con una estructura anidada organizada por `station`, `location` y `measurements`. El proveedor B entrega los datos en **CSV separado por `;`**, con columnas planas y nombres como `municipality`, `country`, `latitude_deg`, `longitude_deg`, `temp_celsius`, `humidity_pct`, `wind_kmh` y `measurement_time`.

El contrato institucional exige un formato común con los campos: `ciudad`, `pais`, `latitud`, `longitud`, `temperatura_c`, `humedad`, `viento_kmh`, `fecha_hora` y `origen`. La fecha debe quedar en formato **ISO 8601** y el país en código ISO de dos letras. La API usa el encabezado `X-Equipo` y la consulta final se hace con `GET /api/v1/mediciones?equipo=<equipo>`.

2. ¿Qué transformaciones fueron necesarias?

Para el proveedor A fue necesario:

- `station.city_name` → `ciudad`
- `station.country_code` → `pais`
- `location.lat` / `location.lon` → `latitud` / `longitud`
- `measurements.temperature_f` → `temperatura_c`, convirtiendo Fahrenheit a Celsius
- `measurements.relative_humidity` → `humedad`
- `measurements.wind_speed_ms` → `viento_kmh`, convirtiendo m/s a km/h
- `observed_at` → `fecha_hora` en ISO 8601

Para el proveedor B fue necesario:

- `municipality` → `ciudad`
- `country` → `pais`
- `latitude_deg` / `longitude_deg` → `latitud` / `longitud`
- `temp_celsius` → `temperatura_c`
- `humidity_pct` → `humedad`
- `wind_kmh` → `viento_kmh`
- `measurement_time` → `fecha_hora`, usando formato ISO 8601 con zona horaria `-05:00`

El `id_trazabilidad` solamente queda como evidencia interna y no se envía al servidor.

3. ¿Qué tipos de errores encontró antes de enviar información?

Antes del envío se encontraron varios tipos de error de normalización y validación local:

- archivo inexistente o ilegible;
- JSON con estructura no válida;
- filas CSV defectuosas o con campos vacíos;
- valores que no se pueden convertir al tipo esperado;
- fecha sin formato o sin zona horaria compatible;
- ciudad o país vacío;
- latitud o longitud fuera de rango;
- humedad fuera de rango;
- viento negativo.

Estos errores se separaron de la validación del servidor, que ocurre cuando el cliente realiza el `POST`.

4. ¿Qué diferencias encontró entre validación local y validación del servidor?

La validación local ocurre dentro del programa antes del envío. Si un registro normalizado no cumple las reglas mínimas de negocio, el registro queda como rechazado localmente y permanece en `salida/normalizadas.json`, pero no se envía a la API.

La validación del servidor se hace con la API. Allí:

- `201` significa que el registro fue aceptado;
- `409` significa duplicidad, porque el registro ya está guardado;
- `422` significa que el formato o la semántica del payload no está alineado con el contrato.

En el último reporte, el lote A aparece como `409` de duplicidad porque ya había sido aceptado antes, mientras que el lote B fue corregido y ya pudo quedar con `201` correcto.

5. ¿Qué decisión de implementación considera más importante y por qué?

La decisión más importante fue separar la lógica en dos partes. La primera es `enviar_medicion`, que solo prepara y ejecuta el `POST` con el body del contrato. La segunda es `enviar_con_reintentos`, que decide qué hacer con errores de conexión, `timeout`, `5xx` y reglas de reintento.

Esto evita mezclar transporte HTTP con normalización o validación. También permite cumplir el requisito de que las respuestas `4xx` no se reintenten, mientras que los errores de comunicación se manejan de manera controlada y sin producir un traceback no controlado.

### Evidencia resumida de la ejecución real

La ejecución real generó esta evidencia:

| Indicador | Valor |
|---|---:|
| Cantidad total de registros procesados | 400 |
| Cantidad normalizada | 391 |
| Cantidad rechazada localmente | 11 |
| Cantidad enviada a la API | 380 |
| Cantidad aceptada por la API | 190 |
| Cantidad rechazada por la API | 190 |
| Errores de normalización | 9 |
| Errores de comunicación | 0 |
| Respuesta del GET final | 200 |

La consulta final mediante `GET /api/v1/mediciones?equipo=EQUIPO-21-APPSWEB` respondió correctamente con código `200`.

Durante las pruebas se encontró un problema en el lote B: la API respondió `422` porque el campo `fecha_hora` no incluía la zona horaria requerida por el contrato. Después de corregir el formato, el lote B fue aceptado con `201`.

El lote A, al haber sido enviado anteriormente y quedar almacenado en la API, respondió posteriormente con `409` debido a la duplicidad.

## Conclusión

La implementación permitió integrar los datos de ambos proveedores en un formato común, aplicar validaciones antes del envío y manejar las respuestas de la API de forma controlada.

El proceso también generó evidencia en:

- `salida/normalizadas.json`
- `salida/reporte.json`

Durante las pruebas se confirmó que la API mantiene información entre ejecuciones. Por esto, un registro que ya fue almacenado puede generar `409` al enviarse nuevamente. También se comprobó que errores relacionados con el formato de los datos, como una fecha sin zona horaria, pueden generar `422`.

En general, el flujo mantiene una separación clara entre **lectura, normalización, validación, envío y trazabilidad**, utilizando el contrato institucional como referencia para la comunicación con la API.