#SIMON HERRERA ACOSTA
#Juan David Arias Ospina
import json
import csv
import os
from datetime import datetime
import requests

# --- Punto 13
URL_BASE = "https://appsweb.quantaiot.co"
EQUIPO = "EQUIPO-21-APPSWEB"


PAISES = {"CO": "CO"}
CAMPOS_CONTRATO = {
    "ciudad", "pais", "latitud", "longitud",
    "temperatura_c", "humedad", "viento_kmh",
    "fecha_hora", "origen"
}


# --- Punto 2: lectura de datos ---
def leer_proveedor_a(path):
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, OSError, UnicodeDecodeError, json.JSONDecodeError):
        return []

    if not isinstance(data, dict):
        return []
    return data.get("records", []) if isinstance(data.get("records", []), list) else []


def leer_proveedor_b(path):
    registros = []
    try:
        with open(path, encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f, delimiter=";")
            for row in reader:
                try:
                    if None in row:
                        continue
                    if not all(row.get(col) is not None for col in row):
                        continue
                    registros.append(row)
                except (csv.Error, UnicodeDecodeError, TypeError, ValueError):
                    continue
    except (FileNotFoundError, OSError, UnicodeDecodeError, csv.Error):
        return []
    return registros


# --- Punto 3: normalización ---
def normalizar_proveedor_a(raw):
    try:
        ciudad = raw["station"]["city_name"]
        pais = PAISES.get(raw["station"]["country_code"], raw["station"]["country_code"])
        lat = float(raw["location"]["lat"])
        lon = float(raw["location"]["lon"])
        temp_c = round((float(raw["measurements"]["temperature_f"]) - 32) * 5 / 9, 2)
        humedad = float(raw["measurements"]["relative_humidity"])
        viento_kmh = round(float(raw["measurements"]["wind_speed_ms"]) * 3.6, 2)
        fecha_hora = datetime.fromisoformat(raw["observed_at"]).isoformat()
    except (KeyError, TypeError, ValueError):
        return None, {"id": raw.get("provider_record_id", "desconocido"), "motivo": "error_normalizacion"}

    registro = {
        "id_trazabilidad": raw.get("provider_record_id", "desconocido"),
        "ciudad": ciudad, 
        "pais": pais,
        "latitud": lat, 
        "longitud": lon,
        "temperatura_c": temp_c, 
        "humedad": humedad, 
        "viento_kmh": viento_kmh,
        "fecha_hora": fecha_hora, 
        "origen": "proveedor_a"
    }
    return registro, None


def normalizar_proveedor_b(raw):
    try:
        ciudad = raw["municipality"]
        pais = PAISES.get(raw["country"], raw["country"])
        lat = float(raw["latitude_deg"])
        lon = float(raw["longitude_deg"])
        temp_c = round(float(raw["temp_celsius"]), 2)
        humedad = float(raw["humidity_pct"])
        viento_kmh = round(float(raw["wind_kmh"]), 2)
        fecha_dt = datetime.strptime(raw["measurement_time"], "%d/%m/%Y %H:%M")
        fecha_hora = fecha_dt.strftime("%Y-%m-%dT%H:%M:%S")
    except (KeyError, TypeError, ValueError):
        return None, {"id": raw.get("record_code", "desconocido"), "motivo": "error_normalizacion"}

    registro = {
        "id_trazabilidad": raw.get("record_code", "desconocido"),
        "ciudad": ciudad, "pais": pais,
        "latitud": lat, "longitud": lon,
        "temperatura_c": temp_c, "humedad": humedad, "viento_kmh": viento_kmh,
        "fecha_hora": fecha_hora, "origen": "proveedor_b"
    }
    return registro, None


# --- Punto 4: validación local ---
def validar_local(registro):
    errores = []
    if not registro["ciudad"]:
        errores.append("ciudad vacía")
    if not registro["pais"]:
        errores.append("pais vacío")
    if not (-90 <= registro["latitud"] <= 90):
        errores.append("latitud fuera de rango")
    if not (-180 <= registro["longitud"] <= 180):
        errores.append("longitud fuera de rango")
    if not (0 <= registro["humedad"] <= 100):
        errores.append("humedad fuera de rango")
    if registro["viento_kmh"] < 0:
        errores.append("viento negativo")
    return errores


# --- Punto 6: guardar evidencia de normalización ---
def guardar_normalizadas(registros):
    os.makedirs("salida", exist_ok=True)
    with open("salida/normalizadas.json", "w", encoding="utf-8") as f:
        json.dump(registros, f, ensure_ascii=False, indent=2)


# --- Orquestación de los puntos 2 a 6 (trazabilidad incluida en cada registro) ---
def leer_proveedores():
    crudos_a = leer_proveedor_a("datos/proveedor_a.json")
    crudos_b = leer_proveedor_b("datos/proveedor_b.csv")
    return crudos_a, crudos_b


def normalizar_registros(crudos_a, crudos_b):
    normalizados = []
    errores_normalizacion = []

    for raw in crudos_a:
        reg, err = normalizar_proveedor_a(raw)
        (normalizados if reg else errores_normalizacion).append(reg or err)

    for raw in crudos_b:
        reg, err = normalizar_proveedor_b(raw)
        (normalizados if reg else errores_normalizacion).append(reg or err)

    return normalizados, errores_normalizacion


def separar_registros_locales(normalizados):
    validos, rechazados_localmente = [], []

    for reg in normalizados:
        errores = validar_local(reg)
        if errores:
            reg["estado_validacion"] = "rechazado_localmente"
            reg["motivos_rechazo"] = errores
            rechazados_localmente.append(reg)
        else:
            reg["estado_validacion"] = "valido"
            validos.append(reg)

    return validos, rechazados_localmente


def procesar():
    crudos_a, crudos_b = leer_proveedores()
    normalizados, errores_normalizacion = normalizar_registros(crudos_a, crudos_b)
    validos, rechazados_localmente = separar_registros_locales(normalizados)

    guardar_normalizadas(validos + rechazados_localmente)
    return validos, rechazados_localmente, errores_normalizacion



# --- Punto 7: integración HTTP (envío) ---
def enviar_medicion(registro):  # POST puro
    body = {
        "ciudad": registro["ciudad"],
        "pais": registro["pais"],
        "latitud": registro["latitud"],
        "longitud": registro["longitud"],
        "temperatura_c": registro["temperatura_c"],
        "humedad": registro["humedad"],
        "viento_kmh": registro["viento_kmh"],
        "fecha_hora": registro["fecha_hora"],
        "origen": registro["origen"],
    }

    headers = {
        "Content-Type": "application/json",
        "X-Equipo": EQUIPO,
    }

    try:
        respuesta = requests.post(
            f"{URL_BASE}/api/v1/mediciones",
            json=body,
            headers=headers,
            timeout=10
        )
        return respuesta
    except requests.exceptions.Timeout:
        return "timeout"
    except requests.exceptions.ConnectionError:
        return "conexion"
    except requests.exceptions.RequestException:
        return "error_request"


def es_respuesta_json(resp):
    """Devuelve True si el Response de requests expone JSON válido."""
    try:
        if not hasattr(resp, "headers"):
            return False
        content_type = str(resp.headers.get("Content-Type", "")).lower()
        if "application/json" not in content_type:
            return False
        resp.json()
        return True
    except (AttributeError, TypeError, ValueError, requests.exceptions.JSONDecodeError):
        return False


def enviar_con_reintentos(registro):  # lógica de reintentos
    for intento in range(3):
        respuesta = enviar_medicion(registro)

        if respuesta in {"timeout", "conexion", "error_request"}:
            if intento == 2:
                return None, "error_comunicacion"
            continue

        if not hasattr(respuesta, "status_code"):
            return None, "error_comunicacion"

        if respuesta.status_code in {400, 409, 422}:
            return respuesta, "rechazado_por_api"

        if 500 <= respuesta.status_code < 600:
            if intento == 2:
                return respuesta, "error_comunicacion"
            continue

        if respuesta.status_code == 201:
            if not es_respuesta_json(respuesta):
                return respuesta, "respuesta_no_json"
            return respuesta, "aceptado"

        if not es_respuesta_json(respuesta):
            return respuesta, "respuesta_no_json"

        return respuesta, "codigo_http_no_esperado"

    return None, "error_comunicacion"


def consultar_mediciones(equipo=EQUIPO):
    try:
        respuesta = requests.get(
            f"{URL_BASE}/api/v1/mediciones",
            params={"equipo": equipo},
            headers={"Content-Type": "application/json"},
            timeout=10,
        )
        return respuesta
    except requests.exceptions.Timeout:
        return "timeout"
    except requests.exceptions.ConnectionError:
        return "conexion"
    except requests.exceptions.RequestException:
        return "error_request"


def interpretar_respuesta(resp):  # clasificación de Response
    if not hasattr(resp, "status_code"):
        return "error_comunicacion"
    if resp.status_code == 200:
        return "consulta_ok"
    if resp.status_code == 201:
        return "aceptado"
    if resp.status_code == 400:
        return "rechazado_400"
    if resp.status_code == 409:
        return "rechazado_409"
    if resp.status_code == 422:
        return "rechazado_422"
    if 500 <= resp.status_code < 600:
        return "error_5xx"
    if not es_respuesta_json(resp):
        return "respuesta_no_json"
    return "codigo_http_no_esperado"


def guardar_reporte(reporte):
    os.makedirs("salida", exist_ok=True)
    with open(os.path.join("salida", "reporte.json"), "w", encoding="utf-8") as f:
        json.dump(reporte, f, ensure_ascii=False, indent=2)


def generar_reporte(validos, rechazados_localmente, errores_normalizacion, resultados_envio, consulta):
    aceptados = sum(1 for item in resultados_envio if item["estado"] == "aceptado")
    rechazados_api = sum(1 for item in resultados_envio if item["estado"] == "rechazado_por_api")
    errores_comunicacion = sum(1 for item in resultados_envio if item["estado"] == "error_comunicacion")

    consulta_estado = interpretar_respuesta(consulta) if hasattr(consulta, "status_code") else "error_comunicacion"
    consulta_status_code = consulta.status_code if hasattr(consulta, "status_code") else None

    reporte = {
        "registros_procesados": len(validos) + len(rechazados_localmente) + len(errores_normalizacion),
        "registros_normalizados": len(validos) + len(rechazados_localmente),
        "errores_normalizacion": len(errores_normalizacion),
        "registros_validos_localmente": len(validos),
        "registros_rechazados_localmente": len(rechazados_localmente),
        "registros_enviados": len(resultados_envio),
        "registros_aceptados_por_api": aceptados,
        "registros_rechazados_por_api": rechazados_api,
        "errores_comunicacion": errores_comunicacion,
        "consulta_get": {
            "estado": consulta_estado,
            "status_code": consulta_status_code,
            "equipo": EQUIPO,
        },
        "trazabilidad": [
            {
                "id_trazabilidad": item["id_trazabilidad"],
                "estado": item["estado"],
                "status_code": item.get("status_code"),
                "origen": item.get("origen"),
            }
            for item in resultados_envio
        ],
    }
    return reporte


def ejecutar_integracion():
    validos, rechazados_localmente, errores_normalizacion = procesar()

    resultados_envio = []
    for reg in validos:
        respuesta, estado = enviar_con_reintentos(reg)
        resultados_envio.append({
            "id_trazabilidad": reg.get("id_trazabilidad"),
            "estado": estado,
            "status_code": getattr(respuesta, "status_code", None),
            "origen": reg.get("origen"),
        })

    consulta = consultar_mediciones(EQUIPO)
    reporte = generar_reporte(
        validos,
        rechazados_localmente,
        errores_normalizacion,
        resultados_envio,
        consulta,
    )
    guardar_reporte(reporte)
    return reporte


if __name__ == "__main__":
    try:
        ejecutar_integracion()
    except (FileNotFoundError, OSError, json.JSONDecodeError, UnicodeDecodeError, csv.Error, ValueError,
            requests.exceptions.Timeout, requests.exceptions.ConnectionError,
            requests.exceptions.RequestException) as exc:
        print(f"Error controlado: {exc.__class__.__name__}: {exc}")
    except Exception as exc:
        print(f"Error controlado: {exc.__class__.__name__}: {exc}")