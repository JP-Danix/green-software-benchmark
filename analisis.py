import csv
import json
import pathlib
import sys

import matplotlib

matplotlib.use("Agg")  # sin ventana: guarda PNG directamente
import matplotlib.pyplot as plt

CSV_PATH = pathlib.Path("emissions.csv")
MEZCLA_PATH = (
    pathlib.Path(".venv")
    / "Lib"
    / "site-packages"
    / "codecarbon"
    / "data"
    / "private_infra"
    / "global_energy_mix.json"
)

# Operaciones ejecutadas por fase, importadas del benchmark para que cuadren
try:
    from benchmark_estructuras import (
        APPENDS_PASADA_JOIN,
        APPENDS_STRING,
        PASADA_BUSQUEDA,
        REGISTROS_MICROSERVICIOS,
        REGISTROS_MONOLITO,
        VUELTAS_CONJUNTO,
        VUELTAS_JOIN,
        VUELTAS_LISTA,
    )
    OPERACIONES = {
        "1A": PASADA_BUSQUEDA * VUELTAS_LISTA,
        "1B": PASADA_BUSQUEDA * VUELTAS_CONJUNTO,
        "2A": APPENDS_STRING,
        "2B": APPENDS_PASADA_JOIN * VUELTAS_JOIN,
        "4A": REGISTROS_MONOLITO,
        "4B": REGISTROS_MICROSERVICIOS,
    }
except ImportError:
    OPERACIONES = {}

ROJO = "#e5484d"
VERDE = "#30a46c"
GRIS = "#8b949e"

# Metadatos de las fases: clave -> (etiqueta corta, tipo, color)
FASES = {
    "1A": ("1A lista 'in'  O(n²)", "Ineficiente", ROJO),
    "1B": ("1B set 'in'   O(n) ", "Eficiente", VERDE),
    "2A": ("2A f-string    O(n²)", "Ineficiente", ROJO),
    "2B": ("2B ''.join     O(n) ", "Eficiente", VERDE),
    "3":  ("punto muerto (sleep)", "Punto muerto", GRIS),
    "4A": ("4A monolito   (directo)", "Menos energía", VERDE),
    "4B": ("4B microserv. (2 cruces)", "Más energía", ROJO),
}

# Fases que hacen trabajo "real" (todo excepto el punto muerto): se usan
# para la gráfica de países, el donut de proporcionalidad y el FinOps.
PRODUCTIVAS = ("1A", "1B", "2A", "2B", "4A", "4B")


def fmt(x: float, dec: int = 2) -> str:
    """Formato es: R x.xxx  (punto de miles, coma decimal)."""
    s = f"{x:,.{dec}f}"
    return s.replace(",", "§").replace(".", ",").replace("§", ".")


def cargar_fases() -> dict:
    """Lee emissions.csv y devuelve {clave: métricas} para cada fase."""
    fases: dict[str, dict] = {}
    with CSV_PATH.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            for clave, (etiqueta, tipo, color) in FASES.items():
                if row["project_name"].startswith(clave + ")") or (
                    clave == "3" and "punto muerto" in row["project_name"]
                ):
                    fases[clave] = {
                        "etiqueta": etiqueta,
                        "tipo": tipo,
                        "color": color,
                        "duracion_s": float(row.get("duration") or 0),
                        "kwh": float(row.get("energy_consumed") or 0),
                        "energia_j": (float(row.get("energy_consumed") or 0)) * 3_600_000,
                        "co2_g": (float(row.get("emissions") or 0)) * 1_000,
                        "cpu_power_w": float(row.get("cpu_power") or 0),
                        "ram_power_w": float(row.get("ram_power") or 0),
                        "pais": row.get("country_name") or "",
                        "cpu_model": row.get("cpu_model") or "",
                        "pue": row.get("pue") or "",
                        "timestamp": row.get("timestamp") or "",
                    }
                    break
    return fases


def carga_del_pais(iso: str, mezcla: dict):
    """Devuelve la intensidad de carbono (gCO2e/kWh) de un país del dataset."""
    return float(mezcla[iso]["carbon_intensity"])


def grafica_1(fases: dict) -> None:
    """Eficiencia de carbono (pág. 3 y 10): total Y por operación."""
    solo = [c for c in ("1A", "1B", "2A", "2B") if c in fases]
    if not solo:
        return
    max_j = max(fases[c]["energia_j"] for c in solo) or 1
    con_ops = [c for c in solo if OPERACIONES.get(c)]
    max_uj = max(
        (fases[c]["energia_j"] / OPERACIONES[c] * 1e6 for c in con_ops), default=0
    ) or 1

    n_paneles = 2 if con_ops else 1
    fig, ejes = plt.subplots(1, n_paneles, figsize=(12.2, 4.6), squeeze=False)
    ax = ejes[0][0]
    nombres = [fases[c]["etiqueta"] for c in solo]
    valores = [fases[c]["energia_j"] for c in solo]
    colores = [fases[c]["color"] for c in solo]
    barras = ax.barh(nombres, valores, color=colores, edgecolor="white")
    ax.set_xlabel("Energía TOTAL de la fase (joules)")
    ax.set_title("Eficiencia de carbono (pág. 3 y 10):\nla misma tarea, decisiones de diseño distintas")
    for barra, c in zip(barras, solo):
        f = fases[c]
        ax.text(
            barra.get_width() + max_j * 0.01,
            barra.get_y() + barra.get_height() / 2,
            f"{fmt(f['energia_j'])} J  ·  {f['duracion_s']:.2f} s",
            va="center",
            fontsize=9,
        )
    ax.set_xlim(0, max_j * 1.4)
    ax.invert_yaxis()
    ax.spines[["top", "right"]].set_visible(False)

    if n_paneles == 2:
        ax2 = ejes[0][1]
        nombres2 = [fases[c]["etiqueta"] for c in con_ops]
        # µJ por operación: micro-joules = J * 1e6 / operaciones
        valores2 = [fases[c]["energia_j"] / OPERACIONES[c] * 1e6 for c in con_ops]
        colores2 = [fases[c]["color"] for c in con_ops]
        barras2 = ax2.barh(nombres2, valores2, color=colores2, edgecolor="white")
        ax2.set_xlabel("Energía POR OPERACIÓN (micro-joules / operación)")
        ax2.set_title("Normalizado: energía para lograr\nCADA operación (aquí gana la variante verde)")
        for barra, c, v in zip(barras2, con_ops, valores2):
            ax2.text(
                barra.get_width() + max_uj * 0.01,
                barra.get_y() + barra.get_height() / 2,
                f"{v:,.2f} µJ/op".replace(",", "."),
                va="center",
                fontsize=9,
            )
        ax2.set_xlim(0, max_uj * 1.4)
        ax2.invert_yaxis()
        ax2.spines[["top", "right"]].set_visible(False)

    fig.tight_layout()
    fig.savefig("grafica_1_energia_por_fase.png", dpi=150)
    plt.close(fig)


def grafica_2(fases: dict, mezcla: dict) -> None:
    """Conciencia de carbono: el mismo trabajo en distintos países (pág. 7)."""
    kwh_total = sum(fases[c]["kwh"] for c in PRODUCTIVAS if c in fases)
    if kwh_total <= 0:
        return

    # Países mencionados o útiles para la presentación (pág. 7: Francia vs Polonia)
    paises = [
        ("NOR", "Noruega"),
        ("FRA", "Francia"),
        ("COL", "Colombia\n(tu PC)"),
        ("USA", "EE. UU."),
        ("POL", "Polonia"),
        ("IND", "India"),
    ]
    paises = [(iso, nombre) for iso, nombre in paises if iso in mezcla]
    nombres = []
    valores_mg = []  # miligramos de CO2e
    intensidades = []
    for iso, nombre in paises:
        intensidad = carga_del_pais(iso, mezcla)
        nombres.append(f"{nombre}\n{intensidad:,.0f} gCO₂e/kWh".replace(",", "."))
        valores_mg.append(kwh_total * intensidad * 1000)  # kWh × g/kWh → g → mg
        intensidades.append(intensidad)

    min_mg = min(valores_mg) or 1
    fig, ax = plt.subplots(figsize=(9.6, 5.0))
    colores = []
    for v in valores_mg:
        # verde = red más limpia; rojo = la más sucia; gris = intermedias
        if v <= min_mg * 1.01:
            colores.append(VERDE)
        elif v == max(valores_mg):
            colores.append(ROJO)
        else:
            colores.append(GRIS)
    barras = ax.bar(nombres, valores_mg, color=colores, edgecolor="white")
    ax.set_ylabel("CO₂e emitido por el MISMO trabajo (miligramos)")
    ax.set_title(
        "Conciencia de carbono (pág. 7): el código no cambia, el país sí\n"
        f"workload idéntico de {fmt(kwh_total * 1000, 4)} Wh — solo cambia la red eléctrica"
    )
    for barra, v, iso in zip(barras, valores_mg, [p[0] for p in paises]):
        factor_rel = v / min_mg
        etiqueta = (
            f"{v:,.1f} mg\nCO₂e".replace(",", ".")
            if v >= 10
            else f"{v:,.2f} mg\nCO₂e".replace(",", ".")
        )
        if factor_rel >= 1.2:
            etiqueta += f"\n({factor_rel:,.1f}× la más limpia)".replace(",", ".")
        ax.text(
            barra.get_x() + barra.get_width() / 2,
            barra.get_height() + max(valores_mg) * 0.015,
            etiqueta,
            ha="center",
            va="bottom",
            fontsize=9,
        )
    ax.set_ylim(0, max(valores_mg) * 1.3)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig("grafica_2_paises.png", dpi=150)
    plt.close(fig)


def grafica_3(fases: dict) -> None:
    """Proporcionalidad de energía: trabajo útil vs punto muerto (pág. 5 y 8)."""
    util = sum(fases[c]["energia_j"] for c in PRODUCTIVAS if c in fases)
    muerto = fases.get("3", {}).get("energia_j", 0)
    if util + muerto <= 0:
        return

    # Donut: energía útil vs energía "en vano" (servidor encendido sin trabajo)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(9.6, 4.4))

    ax1.pie(
        [util, muerto],
        labels=[f"trabajo útil\n{fmt(util)} J", f"punto muerto\n{fmt(muerto)} J"],
        colors=[VERDE, GRIS],
        autopct=lambda p: f"{p:.1f}%",
        wedgeprops={"width": 0.42, "edgecolor": "white"},
        startangle=90,
    )
    ax1.set_title("Proporcionalidad (pág. 5):\nuna parte se gasta sin hacer nada")

    # Barra: potencia media por fase (W) — el piso de consumo del modelo
    claves = [c for c in FASES if c in fases]
    potencias, nombres, colores = [], [], []
    for c in claves:
        f = fases[c]
        w = f["energia_j"] / f["duracion_s"] if f["duracion_s"] > 0 else 0
        nombres.append(f["etiqueta"])
        potencias.append(w)
        colores.append(f["color"])
    ax2.barh(nombres, potencias, color=colores, edgecolor="white")
    ax2.set_xlabel("Potencia media durante la fase (W) — CPU + RAM estimadas")
    ax2.set_title("¿Qué tan 'derecha' es la proporción?\n(la fase 3 consume potencia, no ejecuta lógica)")
    ax2.invert_yaxis()
    ax2.spines[["top", "right"]].set_visible(False)
    for i, (c, w) in enumerate(zip(claves, potencias)):
        ax2.text(w, i, f"  {w:,.2f} W".replace(",", "."), va="center", fontsize=9)

    fig.tight_layout()
    fig.savefig("grafica_3_proporcionalidad.png", dpi=150)
    plt.close(fig)


def grafica_4(fases: dict) -> None:
    """¿Qué arquitectura es más verde? Monolito vs microservicios (pág. 8)."""
    par = [c for c in ("4A", "4B") if c in fases and OPERACIONES.get(c)]
    if len(par) < 2:
        return
    max_j = max(fases[c]["energia_j"] for c in par) or 1
    max_uj = max(fases[c]["energia_j"] / OPERACIONES[c] * 1e6 for c in par) or 1
    ratio = (
        fases["4B"]["energia_j"] / OPERACIONES["4B"]
    ) / (
        fases["4A"]["energia_j"] / OPERACIONES["4A"]
    )

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12.2, 4.6))

    # Panel izquierdo: energía TOTAL (con cargas distintas por diseño)
    nombres1 = [fases[c]["etiqueta"] for c in par]
    valores1 = [fases[c]["energia_j"] for c in par]
    colores1 = [fases[c]["color"] for c in par]
    barras1 = ax1.barh(nombres1, valores1, color=colores1, edgecolor="white")
    ax1.set_xlabel("Energía TOTAL de la fase (joules)")
    ax1.set_title("Arquitecturas (pág. 8): la MISMA lógica de negocio,\n2 granularidades de servicio")
    for barra, c in zip(barras1, par):
        f = fases[c]
        ax1.text(
            barra.get_width() + max_j * 0.01,
            barra.get_y() + barra.get_height() / 2,
            f"{fmt(f['energia_j'])} J · {f['duracion_s']:.2f} s\n"
            f"{OPERACIONES[c]:,} registros".replace(",", "."),
            va="center",
            fontsize=8.5,
        )
    ax1.set_xlim(0, max_j * 1.45)
    ax1.invert_yaxis()
    ax1.spines[["top", "right"]].set_visible(False)

    # Panel derecho: energía POR REGISTRO (comparación justa)
    nombres2 = [fases[c]["etiqueta"] for c in par]
    valores2 = [fases[c]["energia_j"] / OPERACIONES[c] * 1e6 for c in par]
    barras2 = ax2.barh(nombres2, valores2, color=[fases[c]["color"] for c in par], edgecolor="white")
    ax2.set_xlabel("Energía POR REGISTRO procesado (micro-joules)")
    ax2.set_title(f"Normalizado: cada cruce entre servicios\ncobra peaje energético ({ratio:,.1f}× por registro)".replace(",", "."))
    for barra, v in zip(barras2, valores2):
        ax2.text(
            barra.get_width() + max_uj * 0.01,
            barra.get_y() + barra.get_height() / 2,
            f"{v:,.2f} µJ/registro".replace(",", "."),
            va="center",
            fontsize=9,
        )
    ax2.set_xlim(0, max_uj * 1.4)
    ax2.invert_yaxis()
    ax2.spines[["top", "right"]].set_visible(False)

    fig.tight_layout()
    fig.savefig("grafica_4_arquitecturas.png", dpi=150)
    plt.close(fig)


def resumen_consola(fases: dict, mezcla: dict) -> None:
    """Tabla + equivalencias (FinOps, pág. 10) impresas en el terminal."""
    primero = next(iter(fases.values()), None)
    print()
    print("=" * 76)
    print(" RESUMEN — Software Verde (pasa estas tablas al informe)")
    print("=" * 76)
    if primero:
        print(
            f" Corrida: {primero.get('timestamp', '?')}   CPU: {primero.get('cpu_model', '?')}"
        )
        print(
            f" País detectado: {primero.get('pais', '?')}   PUE: {primero.get('pue', '?')}"
        )
    print()
    print(
        f" {'fase':<26}{'duración':>10}{'energía (J)':>14}{'CO₂e (g)':>12}{'pot. media (W)':>16}"
    )
    print(" " + "-" * 76)
    total_kwh = 0.0
    for clave, f in fases.items():
        pot = f["energia_j"] / f["duracion_s"] if f["duracion_s"] > 0 else 0
        print(
            f" {f['etiqueta']:<26}{f['duracion_s']:>9.2f}s{f['energia_j']:>14,.2f}"
            f"{f['co2_g']:>12.4f}{pot:>16,.2f}".replace(",", ".")
        )
        total_kwh += f["kwh"]
    print(" " + "-" * 76)
    total_j = total_kwh * 3_600_000
    impacto = " (ojo: algunas fases son insuficientes, la comparación relativa es la válida)" if total_j < 1 else ""
    print(f" TOTAL energía del benchmark: {fmt(total_kwh * 1000, 4)} Wh = {fmt(total_j)} J{impacto}")
    print()

    # --- Conciencia de carbono por país (pág. 7) ---
    # Se usa SOLO la energía de las fases productivas (PRODUCTIVAS), igual que
    # en grafica_2: "el mismo trabajo" en distintas redes eléctricas.
    kwh_productivo = sum(fases[c]["kwh"] for c in PRODUCTIVAS if c in fases)
    print(" Si este mismo trabajo corriera en otras redes eléctricas (pág. 7):")
    for iso, nombre in [("NOR", "Noruega"), ("FRA", "Francia"), ("COL", "Colombia"), ("POL", "Polonia"), ("IND", "India")]:
        if iso in mezcla:
            intensidad = float(mezcla[iso]["carbon_intensity"])
            mg = kwh_productivo * intensidad * 1000  # g -> mg
            print(
                f"   {nombre:<12}{intensidad:>9,.0f} gCO₂e/kWh   →  {mg:>9,.2f} mg CO₂e".replace(",", ".")
            )
    print()

    # --- FinOps (pág. 10): ¡costo real! ---
    # Precio residencial aproximado en Colombia: ~785 COP/kWh ≈ 0.19 USD
    # (usa el de tu contrato real; aquí es solo para dimensionar el orden de magnitud)
    PRECIO_USD_KWH = 0.19
    costo_1_run = total_kwh * PRECIO_USD_KWH
    duracion_total = sum(f["duracion_s"] for f in fases.values())
    # Extrapolación: si este proceso corriera continuo 24/7 durante un año
    if duracion_total > 0 and costo_1_run > 0:
        costo_anual = costo_1_run * (365 * 24 * 3600) / duracion_total
    else:
        costo_anual = 0.0
    print(f" FinOps / GreenOps (pág. 10) — precio supuesto {PRECIO_USD_KWH:.2f} USD/kWh:")
    print(f"   costo de ESTA corrida:            ≈ {costo_1_run:.6f} USD   ({fmt(costo_1_run * 4300, 3)} COP)")
    print(f"   si corriera 24/7 durante un año:  ≈ {costo_anual:.2f} USD/año")
    print()
    print(" Gráficas generadas (revisa las 4 imágenes PNG en la carpeta):")

    for nombre in (
        "grafica_1_energia_por_fase.png",
        "grafica_2_paises.png",
        "grafica_3_proporcionalidad.png",
        "grafica_4_arquitecturas.png",
    ):
        existe = "✓" if pathlib.Path(nombre).exists() else "✗"
        print(f"   [{existe}] {nombre}")
    print()
    print(" El punto muerto (fase 3) es la ilustración de: 'un servidor al 20 %")
    print(" sí consume cerca del 70 %' — aquí 6 s de sleep consumen energía real.")
    print("=" * 76)


def main() -> None:
    # Consolas Windows (cp1252) no saben imprimir ₂ ni →: fuerza UTF-8.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    if not CSV_PATH.exists():
        print("⚠️  No existe emissions.csv. Primero corre el benchmark (~25 s):")
        print("    .venv\\Scripts\\python.exe benchmark_estructuras.py")
        sys.exit(1)

    fases = cargar_fases()
    if not fases:
        print("⚠️  emissions.csv no tiene fases reconocidas (¿corriste --rapido?).")
        sys.exit(1)

    mezcla = {}
    try:
        with MEZCLA_PATH.open(encoding="utf-8") as f:
            mezcla = json.load(f)
    except OSError:
        print(f"⚠️  No encontré el dataset de países en {MEZCLA_PATH}: la gráfica 2 se omite.")

    grafica_1(fases)
    if mezcla:
        grafica_2(fases, mezcla)
    grafica_3(fases)
    grafica_4(fases)
    resumen_consola(fases, mezcla)


if __name__ == "__main__":
    main()
