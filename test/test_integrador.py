import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import integrador


def test_transformacion_correcta_proveedor_a():
    raw = {
        "provider_record_id": "A-0001",
        "station": {"city_name": "Medellin", "country_code": "CO"},
        "location": {"lat": 6.242282, "lon": -75.595933},
        "measurements": {"temperature_f": 66.1, "relative_humidity": 81.3, "wind_speed_ms": 8.47},
        "observed_at": "2026-09-01T00:00:00-05:00",
    }
    reg, err = integrador.normalizar_proveedor_a(raw)
    assert err is None
    assert reg["ciudad"] == "Medellin"
    assert reg["pais"] == "CO"
    assert reg["temperatura_c"] == 18.94
    assert reg["viento_kmh"] == 30.49
    assert reg["origen"] == "proveedor_a"


def test_conversion_unidades_proveedor_b():
    raw = {
        "record_code": "B-0001",
        "municipality": "Medellin",
        "country": "CO",
        "latitude_deg": 6.261520,
        "longitude_deg": -75.575842,
        "temp_celsius": 21.55,
        "humidity_pct": 50.7,
        "wind_kmh": 21.85,
        "measurement_time": "01/09/2026 06:00",
    }
    reg, err = integrador.normalizar_proveedor_b(raw)
    assert err is None
    assert reg["temperatura_c"] == 21.55
    assert reg["humedad"] == 50.7
    assert reg["viento_kmh"] == 21.85
    assert reg["fecha_hora"] == "2026-09-01T06:00:00"


def test_registro_valido_localmente():
    reg = {
        "id_trazabilidad": "T-001",
        "ciudad": "Bogota",
        "pais": "Colombia",
        "latitud": 4.7,
        "longitud": -74.1,
        "temperatura_c": 20.0,
        "humedad": 60.0,
        "viento_kmh": 10.0,
        "fecha_hora": "2026-09-01T10:00:00",
        "origen": "proveedor_a",
    }
    assert integrador.validar_local(reg) == []


def test_registro_invalido_localmente():
    reg = {
        "id_trazabilidad": "T-002",
        "ciudad": "Bogota",
        "pais": "Colombia",
        "latitud": 91,
        "longitud": -200,
        "temperatura_c": 20.0,
        "humedad": 110,
        "viento_kmh": -1,
        "fecha_hora": "2026-09-01T10:00:00",
        "origen": "proveedor_a",
    }
    errores = integrador.validar_local(reg)
    assert "latitud fuera de rango" in errores
    assert "longitud fuera de rango" in errores
    assert "humedad fuera de rango" in errores
    assert "viento negativo" in errores


def test_caso_limite_latitud_fuera_de_rango():
    reg = {
        "id_trazabilidad": "T-003",
        "ciudad": "Cartagena",
        "pais": "Colombia",
        "latitud": -91,
        "longitud": -75.5,
        "temperatura_c": 25.0,
        "humedad": 70.0,
        "viento_kmh": 5.0,
        "fecha_hora": "2026-09-01T11:00:00",
        "origen": "proveedor_b",
    }
    errores = integrador.validar_local(reg)
    assert "latitud fuera de rango" in errores
