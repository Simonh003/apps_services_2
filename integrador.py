import json
import csv
import os
from datetime import datetime

# --- Punto 13: configuración ---
URL_BASE = "https://appsweb.quantaiot.co"
EQUIPO = "EQUIPO_XX"  # cámbialo por el identificador real que les dieron

PAISES = {"CO": "Colombia"}
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
    except (FileNotFoundError, json.JSONDecodeError):
        return []
    return data.get("records", [])


def leer_proveedor_b(path):
    registros = []
    try:
        with open(path, encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f, delimiter=";")
            for row in reader:
                registros.append(row)
    except FileNotFoundError:
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
        "ciudad": ciudad, "pais": pais,
        "latitud": lat, "longitud": lon,
        "temperatura_c": temp_c, "humedad": humedad, "viento_kmh": viento_kmh,
        "fecha_hora": fecha_hora, "origen": "proveedor_a"
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
        fecha_hora = datetime.strptime(raw["measurement_time"], "%d/%m/%Y %H:%M").isoformat()
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
def procesar():
    crudos_a = leer_proveedor_a("datos/proveedor_a.json")
    crudos_b = leer_proveedor_b("datos/proveedor_b.csv")

    normalizados = []
    errores_normalizacion = []

    for raw in crudos_a:
        reg, err = normalizar_proveedor_a(raw)
        (normalizados if reg else errores_normalizacion).append(reg or err)

    for raw in crudos_b:
        reg, err = normalizar_proveedor_b(raw)
        (normalizados if reg else errores_normalizacion).append(reg or err)

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

    guardar_normalizadas(validos + rechazados_localmente)
    return validos, rechazados_localmente, errores_normalizacion


# --- Punto 7: integración HTTP (envío) ---
import requests  # necesitas: pip install requests

def enviar_medicion(registro):
    body = {k: v for k, v in registro.items() if k in CAMPOS_CONTRATO}
    headers = {"Content-Type": "application/json", "X-Equipo": EQUIPO}
    try:
        return requests.post(f"{URL_BASE}/api/v1/mediciones", json=body, headers=headers, timeout=10)
    except requests.exceptions.RequestException:
        return None


if __name__ == "__main__":
    validos, rechazados, errores = procesar()
    print(f"Válidos: {len(validos)} | Rechazados localmente: {len(rechazados)} | Errores normalización: {len(errores)}")