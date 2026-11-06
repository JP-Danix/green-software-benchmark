import json
import sys
import time
from codecarbon import EmissionsTracker

# ---- Parámetros de carga de trabajo (ajustables) ----

# Fase 1: elementos por pasada
PASADA_BUSQUEDA = 40_000
# 1A es O(n^2): 2 pasadas de 40k => ~5 s en total
VUELTAS_LISTA = 2
# 1B es O(n): 500 pasadas de 40k => ~5 s en total
VUELTAS_CONJUNTO = 500

# Fase 2A: concatenaciones con f-string (cuadrático garantizado); 60k => ~5 s
APPENDS_STRING = 60_000

# Fase 2B: pasadas de APPENDS_PASADA_JOIN fragmentos; 8000 pasadas => ~4 s
APPENDS_PASADA_JOIN = 10_000
VUELTAS_JOIN = 8_000

# Fase 3: segundos durmiendo (servidor al raso / "punto muerto")
SEGUNDOS_PUNTO_MUERTO = 6

# Fase 4: registro de negocio típico; el pipeline es el mismo en ambas
# arquitecturas; cambia SOLO la granularidad de servicios.
# Calibrado: 4A ~4.3 us/registro, 4B ~52 us/registro con 2 cruces JSON.
# 900k => ~3.9 s (4A); 60k => ~3.1 s (4B). La comparación justa se hace
# normalizado POR REGISTRO (las cargas son distintas a propósito, como
# en las fases 1 y 2).
REGISTROS_MONOLITO = 900_000
REGISTROS_MICROSERVICIOS = 60_000
# 3 servicios => 2 cruces de red entre ellos
SERVICIOS_CADENA = 3

FRAGMENTO = "Software-Verde-2026;"


def buscar_duplicados_con_lista(vueltas: int) -> int:
    """O(n^2): `valor in lista` recorre la lista desde el inicio."""
    duplicados = 0
    for _ in range(vueltas):
        vistos: list[int] = []
        for i in range(PASADA_BUSQUEDA):
            valor = valor_en(i)
            if valor in vistos:          
                duplicados += 1
            else:
                vistos.append(valor)
    return duplicados


def buscar_duplicados_con_conjunto(vueltas: int) -> int:
    """O(n) total: membresía en set es O(1) promedio (tabla hash)."""
    duplicados = 0
    for _ in range(vueltas):
        vistos: set[int] = set()
        for i in range(PASADA_BUSQUEDA):
            valor = valor_en(i)
            if valor in vistos:          
                duplicados += 1
            else:
                vistos.add(valor)
    return duplicados


def concatenar_con_fstring(n: int) -> int:
    """Antipatrón: `s = f"{s}{frag}"` construye un string NUEVO en cada
    iteración y copia todo lo acumulado => O(n^2).

    Por qué no usamos `s += frag`: CPython optimiza ese caso específico
    cuando `s` es una variable local con una sola referencia (realloc
    in-place), lo que enmascara el costo cuadrático. El antipatrón con
    f-string SIEMPRE copia el contenido anterior."""
    s = ""
    for _ in range(n):
        s = f"{s}{FRAGMENTO}"
    return len(s)


def concatenar_con_join(vueltas: int) -> int:
    """Patrón idiomático: `"".join(...)` construye la cadena en O(n)
    (calcula el tamaño total, reserva una vez y copia cada fragmento
    exactamente una vez). Casi no genera basura intermedia."""
    total = 0
    for _ in range(vueltas):
        partes: list[str] = []
        for _ in range(APPENDS_PASADA_JOIN):
            partes.append(FRAGMENTO)
        total += len("".join(partes))    # O(len(partes)) amortizado
    return total


def punto_muerto(segundos: int) -> int:
    """Zona neutral de energía: el 'servidor encendido sin trabajo'.
    No procesa nada; igualmente consume. Es la ilustración en vivo de
    la proporcionalidad de energía (pág. 5 del curso) y del antipatrón
    de arquitectura always-on (pág. 8)."""
    time.sleep(segundos)
    return segundos


# ---- FASE 4: ¿monolito o microservicios? El mismo pipeline de negocio,
#      dos granularidades de servicio. ----

def registro(i: int) -> dict:
    """Registro de negocio típico (inmueble). Determinista (sin random)."""
    return {
        "id": i,
        "nombre": f"inmueble-{i:07d}",
        "tipo": i % 5,
        "valores": [i % 97, (i * 3) % 89, (i * 7) % 83, (i * 11) % 79],
        "estado": "activo",
        "zona": f"z{i % 9}",
        "peso": round(i * 0.37, 3),
        "prioridad": (i * 13) % 100,
        "nota": f"n{i:05d}",
        "flag": i % 2 == 0,
    }


def validar(r: dict) -> None:
    """Validación de negocio que cada servicio hace al recibir un registro."""
    if r["id"] < 0 or r["prioridad"] > 99:
        raise ValueError("registro invalido")


def procesar(r: dict) -> int:
    """La única 'lógica de negocio' del pipeline: idéntica en ambas
    arquitecturas. Todo lo demás en 4B es peaje de granularidad."""
    v = r["valores"]
    return ((r["id"] % 13) + sum(v) + len(r["nombre"])) % 1013


def arq_monolito(n_registros: int) -> int:
    """Arquitectura A: TODO el pipeline en un proceso. Pasar el registro
    de la etapa de entrada a la de cálculo no cuesta nada: es un
    pasamanos de referencias en memoria."""
    total = 0
    for i in range(n_registros):
        total += procesar(registro(i))
    return total


def arq_microservicios(n_registros: int) -> int:
    """Arquitectura B: mismo pipeline en una cadena de SERVICIOS_CADENA
    servicios. Cada cruce entre servicios paga el peaje: serialize(),
    'viajar por la red', deserialize() y validar() en cada borde.

    En producción el dumps/loads sería HTTP+TLS (y el costo real sería
    MAYOR: aquí no hay RTT de red ni GC de buffers de socket: solo
    simulamos el costo de CPU del borde)."""
    total = 0
    for i in range(n_registros):
        carga = json.dumps(registro(i))            # entra por la red
        for _ in range(SERVICIOS_CADENA - 1):      # cruces entre servicios
            r = json.loads(carga)
            validar(r)                             # cada borde valida
            carga = json.dumps(r)                  # reenvía al siguiente
        r = json.loads(carga)
        validar(r)
        total += procesar(r)                       # servicio final calcula
    return total


def valor_en(i: int) -> int:
    """Determinista (sin random): 2/3 de los valores repiten."""
    return (i * 7919 + 101) % (PASADA_BUSQUEDA // 3)


def medir(nombre: str, funcion, n: int) -> None:
    """Mide una fase con CodeCarbon: duración, energía y CO2."""
    tracker = EmissionsTracker(
        project_name=nombre,
        output_dir=".",            # escribe emissions.csv aquí
        measure_power_secs=2,      # intervalo de muestreo (por defecto 15 s)
        log_level="error",
    )
    tracker.start()
    inicio = time.perf_counter()
    checksum = funcion(n)
    duracion = time.perf_counter() - inicio
    co2_kg = tracker.stop()        # kg de CO2-eq de este bloque
    if co2_kg is None:
        print(f"{nombre:<34} {duracion:8.2f} s   CO2: (medición falló esta vez)   "
              f"checksum = {checksum:,}")
    else:
        print(f"{nombre:<34} {duracion:8.2f} s   CO2: {co2_kg * 1_000:8.4f} g   "
              f"checksum = {checksum:,}")


def main() -> None:
    rapido = "--rapido" in sys.argv
    if rapido:
        # Modo de prueba: reduce el trabajo hasta segundos para verificar que
        # todo corre (las mediciones del modo --rapido NO son válidas: son
        # más cortas que el intervalo de muestreo de CodeCarbon).
        global PASADA_BUSQUEDA, VUELTAS_LISTA, VUELTAS_CONJUNTO, APPENDS_STRING
        global VUELTAS_JOIN, SEGUNDOS_PUNTO_MUERTO
        global REGISTROS_MONOLITO, REGISTROS_MICROSERVICIOS
        PASADA_BUSQUEDA //= 50
        VUELTAS_LISTA //= 2
        VUELTAS_CONJUNTO //= 30
        APPENDS_STRING //= 10
        VUELTAS_JOIN //= 100
        SEGUNDOS_PUNTO_MUERTO //= 3
        REGISTROS_MONOLITO //= 300
        REGISTROS_MICROSERVICIOS //= 300

    print("============================================================")
    print(" Benchmark de Software Verde (Python + CodeCarbon)")
    print(f" Python {sys.version.split()[0]} | {sys.platform}")
    print("============================================================")
    print("Las mediciones se guardan en emissions.csv.")
    print()
    print("--- FASE 1: eficiencia de carbono, misma búsqueda, 2 estructuras ---")
    medir("1A) lista 'in'    [O(n^2)]", buscar_duplicados_con_lista, VUELTAS_LISTA)
    medir("1B) set 'in'      [O(n)  ]", buscar_duplicados_con_conjunto, VUELTAS_CONJUNTO)
    print()
    print("--- FASE 2: eficiencia de carbono, 2 estilos de construccion de string ---")
    medir("2A) f-string en ciclo [O(n^2)]", concatenar_con_fstring, APPENDS_STRING)
    medir("2B) ''.join(...)      [O(n)  ]", concatenar_con_join, VUELTAS_JOIN)
    print()
    print("--- FASE 3: proporcionalidad de energia (trabajo 0, servidor encendido) ---")
    medir("3) punto muerto (sleep)", punto_muerto, SEGUNDOS_PUNTO_MUERTO)
    print()
    print("--- FASE 4: la misma logica de negocio, 2 arquitecturas ---")
    medir("4A) monolito (pipeline directo)", arq_monolito, REGISTROS_MONOLITO)
    medir("4B) microservicios (3 srv/2 cruces)", arq_microservicios, REGISTROS_MICROSERVICIOS)
    print()
    print("============================================================")
    print(" Fin. Ahora corre el análisis para ver gráficas y resumen:")
    print("   .venv\\Scripts\\python.exe analisis.py")
    print(" (emissions.csv: 7 filas: 1A, 1B, 2A, 2B, punto muerto, 4A y 4B)")
    print("============================================================")


if __name__ == "__main__":
    main()
