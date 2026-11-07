# Ejercicio: Software Verde con Python y CodeCarbon 🌱

**Curso:** Arquitectura de Software
**Tema:** Medición y optimización del consumo energético y de CO₂ de decisiones de diseño

---

## 1. Contexto teórico (leer antes de empezar)

**CodeCarbon** es una librería de Python que mide la energía consumida por tu programa
durante la ejecución y la convierte a **kg de CO₂ equivalente**, multiplicando la energía
por el factor de emisión de la red eléctrica de tu país (detectado por geolocalización)
y por una constante de recuperación de infraestructura del centro de datos (**PUE**).

Cómo obtiene la potencia:

| Plataforma | Fuente de potencia |
|---|---|
| Linux bare metal (Intel/AMD Sandy Bridge+) | **RAPL**: sensores de energía reales del CPU |
| **Windows** (caso de este ejercicio) | **Modelo de estimación**: TDP del CPU × utilización real (no requiere drivers ✅) |
| GPU | NVML/rocm-smi si hay GPU dedicada |

> Comparación con JoularJX (Java): JoularJX reporta vatios **por método** (instrumenta
> la JVM como agente) pero necesita drivers de RAPL en Windows. CodeCarbon mide el
> **proceso completo** en kWh y CO₂, y funciona en Windows sin instalar nada. Ahí está
> el trade-off granular/plataforma que discutiremos en clase.

## 2. El experimento — alineado página a página con la presentación

El benchmark ejecuta **5 fases**; cada una demuestra en vivo un concepto de
la presentación:

| Fase | ¿Qué compara? | Concepto de la presentación | Página |
|---|---|---|---|
| **1A vs 1B** | buscar duplicados con `x in lista` (O(n²)) vs `x in set` (O(n)) | **Eficiencia de carbono**: menos energía por unidad de trabajo; "verde = rápido" | pág. 3 y 10 |
| **2A vs 2B** | construir cadena con `s = f"{s}{frag}"` en ciclo (O(n²)) vs acúmulo + `"".join` (O(n)) | **Eficiencia de carbono** vía memoria/GC: strings intermedios = trabajo desperdiciado | pág. 3 y 10 |
| **3 (punto muerto)** | proceso "encendido" 6 s sin hacer NADA (sleep) | **Proporcionalidad de energía** (al 20% de carga NO consumes 20%) y **arquitecturas not-always-on** | pág. 5 y 8 |
| **4A vs 4B** | **la MISMA lógica de negocio** en un monolito (todo en un proceso) vs en una cadena de 3 microservicios (2 cruces con serialización JSON + validación) | **Arquitecturas verdes**: la granularidad de servicios cobra un peaje energético por cada cruce; el trade-off con escalabilidad/autonomía | pág. 8 |
| **Análisis por país** | el MISMO trabajo en Colombia, Francia, Polonia, India, Noruega… (dataset de 213 países incluido en CodeCarbon) | **Conciencia de carbono**: el código no cambia, el país sí; demand-shifting | pág. 7 |
| **FinOps en el resumen** | costo en COP/USD de la energía de la corrida, extrapolado a un año 24/7 | **FinOps = GreenOps**: cada kWh desperdiciado es también dinero | pág. 10 |

Además, la **fase 3** y el modelo de CodeCarbon evidencian el **carbono
embebido / eficiencia de hardware** (pág. 4 y 6): CodeCarbon asigna la potencia
del CPU con un *piso* del 10% de carga (el hardware nunca baja a 0 W), que es
exactamente el "+70% de consumo al 20% de carga" de la página 5.

Ambas variantes de cada fase producen el **mismo resultado** (el benchmark lo
verifica con checksums). En la fase 4, "mismo resultado" significa la MISMA
transformación de negocio por registro: lo único que cambia es cuántos
servicios atraviesa el dato.

📌 Sobre la fase 4 y el diseño: en la vida real los microservicios compran
autonomía de equipos, despliegues independientes y escalado selectivo — a
cambio de un peaje de energía por cada cruce (red + serialización + validación
en cada extremo). El ejercicio mide ese peaje con `json.dumps/loads` como
representación del borde (en producción con HTTP/TLS el costo REAL es mayor:
aquí no simulamos latencia de red ni buffers de socket).

📌 Nota de diseño: `s += t` con una variable **local** de CPython 3.13 puede
optimizarse (realloc in-place) y enmascarar el costo cuadrático; por eso el antipatrón
usa f-string (`s = f"{s}{frag}"`), que en Python garantiza un string nuevo por vuelta.
Lo comprobarás en la medición: 2A es mucho más costoso que 2B.

## 3. Paso a paso

### Paso 0 — Requisitos
- Python 3.10 o superior, con el launcher `py` (en Windows) o `python3` (Linux/Mac).
- **El entorno virtual NO viene en el repo** (es específico de cada máquina y pesa
  cientos de MB). La primera vez —y en cada PC nuevo— créalo así:

```powershell
py -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

> En Linux/Mac el ejecutable se llama `.venv/bin/python` en vez de
> `.venv\Scripts\python.exe`; en el resto de comandos cambia solo esa parte.

### Paso 1 — Prueba rápida

```powershell
.venv\Scripts\python.exe benchmark_estructuras.py --rapido
```

Debes ver las 5 fases (1A, 1B, 2A, 2B y punto muerto) con sus checksums. ⚠️ En `--rapido` los tiempos son muy cortos
(≈0.00 s) para ser medidos por CodeCarbon (intervalo de muestreo = 2 s): es solo
una prueba de que todo corre.

### Paso 2 — Corrida completa (~50 s)

```powershell
.venv\Scripts\python.exe benchmark_estructuras.py
```

Son 7 fases: 1A, 1B, 2A, 2B, el punto muerto, 4A y 4B. Cada una imprime
**duración, CO₂ (g)** y checksum. Se crea **emissions.csv**.

### Paso 3 — Análisis con gráficas (`analisis.py`)

```powershell
.venv\Scripts\python.exe analisis.py
```

Imprime una tabla resumen en el terminal y genera **4 gráficas PNG** con
matplotlib (todo local, nada web). Los PNG **no se incluyen en el repo**: cada
quien los genera al correr `analisis.py`. Lo que muestra cada uno:

| Gráfica | Qué muestra | Slide |
|---|---|---|
| `grafica_1_energia_por_fase.png` | Energía total y **energía por operación** de las 4 variantes de código | pág. 3 y 10 |
| `grafica_2_paises.png` | El mismo trabajo en Noruega, Francia, Colombia, EE. UU., Polonia e India (mg CO₂e) | pág. 7 |
| `grafica_3_proporcionalidad.png` | Donut trabajo útil vs punto muerto + potencia media por fase | pág. 5 y 8 |
| `grafica_4_arquitecturas.png` | **Monolito vs microservicios**: energía total y **por registro** (el peaje de cada cruce) | pág. 8 |

Además el resumen incluye las equivalencias de costo (FinOps, pág. 10).

### Paso 4 — Leer `emissions.csv` (detalle crudo)

Cada fila = una fase (identificada por `project_name`). Columnas clave:

| Columna | Contenido |
|---|---|
| `duration` | Duración de la fase (s) |
| `energy_consumed` | **Energía consumida (kWh)** — la métrica central |
| `emissions` | kg CO₂-eq por fase |
| `cpu_power` / `cpu_energy` | Potencia instantánea (W) / energía del CPU |
| `ram_power` / `ram_energy` | Igual, para la memoria RAM |
| `cpu_model`, `cpu_count` | CPU detectada (y el TDP usado por el modelo) |
| `country_name`, `region` | País y región usados para el factor de emisión |
| `pue` | PUE asumido (energía extra de la infraestructura del centro de datos) |
| `tracking_mode` | `machine` (todo el costo del equipo se le atribuye a tu proceso) |

> En tu máquina detectó: Ryzen 3 3200U (4 cores), Colombia (COL), PUE=1.0.

### Paso 5 — Plantilla de tabla (lo que se entrega)

| Fase | Variante | Estructura | Complejidad | Tiempo (s) | Energía (kWh) | CO₂ (g) | Energía por operación |
|------|----------|-----------|-------------|------------|---------------|---------|----------------------|
| 1A | ineficiente | lista `in` | O(n²) | … | … | … | … |
| 1B | eficiente | set `in` | O(n) | … | … | … | … |
| 2A | ineficiente | f-string en ciclo | O(n²) | … | … | … | … |
| 2B | eficiente | `"".join` | O(n) | … | … | … | … |
| 4A | monolito | pipeline directo | — | … | … | … | µJ/registro |
| 4B | microservicios | 3 servicios / 2 cruces | — | … | … | … | µJ/registro |

**Energía por operación** = `energy_consumed × 3 600 000` (kWh → julios) ÷ número de
operaciones de la fase (`PASADA_BUSQUEDA × vueltas`, o `APPENDS_STRING`/`APPENDS_PASADA_JOIN`).
Esta normalización ES el corazón del análisis: corrige el hecho de que las fases
corren cargas distintas por diseño (en fase 2, 2B ejecuta 80 000 000 appends frente
a 60 000 de 2A; en fase 1, cada variante corre su propio número de pasadas).

---

## 4. Preguntas del informe (cada una apunta a una página de la presentación)

1. **(pág. 3 y 10)** ¿Cuánta energía por operación ahorró pasar de lista a set (fase 1)?
   ¿Y de f-string a join (fase 2)? Usa el panel derecho de `grafica_1`.
   ¿Cuál ahorro es mayor en porcentaje y cuál en impacto total?
2. **(pág. 3 y 10)** Relaciona cada ahorro con su complejidad algorítmica. ¿Es lineal
   la relación entre "veces más rápido" y "veces menos energía", o hay un piso?
   (Pista: el costo base del intérprete y de la RAM son constantes.)
3. **(pág. 5 y 8)** En el punto muerto (fase 3), el proceso no hizo NINGÚN trabajo y
   aun así consumió energía real (usa los datos del donut de `grafica_3`). Relaciona
   ese resultado con "al 20% de carga no consumes 20%" y con el antipatrón
   always-on. ¿Cómo lo resolverías a nivel arquitectura (scale-to-zero, cron,
   lotes nocturnos…)?
4. **(pág. 7)** La gráfica de países usa el dataset REAL que CodeCarbon trae
   (213 países): el mismo benchmark en India emitió ~24× más CO₂ que en Noruega.
   Relaciona con tu slide "Francia vs Polonia". ¿Qué estrategia de arquitectura
   aprovecha esto (demand-shifting / demand-shaping)? ¿En qué horas conviene
   ejecutar batch jobs en Colombia?
5. **(pág. 4 y 6)** CodeCarbon asigna potencia al CPU con un piso del 10%
   (hardware que nunca baja a 0 W): eso conecta con "82% del impacto de un iPhone
   está embebido". ¿Cómo se relaciona "alargar la vida del hardware" con la
   eficiencia del software que corre en él?
6. **(pág. 10)** El resumen FinOps estima el costo de la corrida y de correrlo
   24/7 todo un año. ¿Por qué "verde = barato = fiable = rápido"? ¿Que implica
   para un equipo que ya mide costos cloud (FinOps) adoptar también métricas de carbono?
7. `emissions.csv` detecta tu país y su factor de emisión. Convierte la energía de
   cada fase de kWh a julios (× 3 600 000) y, con el factor de tu país, de energía
   a kgCO₂. ¿Coincide tu cálculo con la columna `emissions`? ¿Qué otros ajustes
   aplica CodeCarbon (PUE)?
8. CodeCarbon en Windows usa el modelo "TDP × utilización" (con piso del 10%);
   JoularJX (Java) usa RAPL real en Linux. Discute las implicaciones: exactitud vs
   portabilidad. ¿En qué situación preferirías cada una?
9. Reproducibilidad: corre el benchmark 2 veces más. ¿Varían los resultados?
   ¿Puede influir el boost del CPU (el Ryzen 3 3200U es un chip móvil) y las demás
   aplicaciones abiertas?
10. **Perspectiva de arquitectura**: si el antipatrón 2A corre en un backend con
    10 000 requests/s, ¿cuántos kWh y kgCO₂ al año (usa el FinOps del resumen como
    base de extrapolación)? Propón 3 reglas de "software verde" para code review.
11. **(pág. 8) Arquitecturas**: con la gráfica 4, compara monolito y microservicios.
    ¿Por qué 4B gasta ~17× más energía POR REGISTRO si hace la misma lógica de
    negocio? ¿Significa que los microservicios son "malos"? Discute el trade-off
    (autonomía de equipos, escalado independiente, resiliencia) y propone en qué
    escenarios elegirías cada arquitectura pensando también en el carbono. ¿Qué
    patrones reducen el peaje (batching en el borde, gRPC/protobuf en vez de JSON,
    consolidar servicios chatty)?

---

## 5. Entregable

1. Tabla del paso 5 completa con sus 3 corridas (anexe emissions.csv de cada corrida, renombrados).
2. Las **4 gráficas PNG** generadas por `analisis.py` (o capturas adicionales si prefieres otra herramienta).
3. Respuestas a las 11 preguntas (máximo 3–4 páginas).
4. Guía de 3 reglas de diseño energético-eficiente (entregable de arquitectura).

---

## 6. Glosario rápido

- **TDP** (*Thermal Design Power*): disipación de calor máxima del CPU (W). CodeCarbon en
  Windows lo usa como cota superior de consumo con la utilización real.
- **RAPL**: interfaz de Intel/AMD con la energía real consumida del CPU (julios), medida
  físicamente en el silicio. Disponible en CodeCarbon sólo en Linux bare metal.
- **PUE** (*Power Usage Effectiveness*): relación entre energía total del centro de datos
  y energía útil de cómputo (TIC) — usado por CodeCarbon para atribuir el costo de la sala.
- **kWh**: 1 kWh = 3 600 000 julios = 3600 s × 1 kW.
- **Checksum**: valor devuelto que evita que el intérprete descarte cálculos (dead code).
- **EmissionsTracker**: cuantificador de CodeCarbon; el contexto con `.start()` / `.stop()`
  envuelve el bloque de código a medir.

---

## 7. Plan B (si CodeCarbon no mide bien en tu equipo)

1. CodeCarbon marca un cálculo de energía de 1.7 W (casi-idle) aunque tu CPU esté al
   100%: es un bug/limitación de la versión de psutil en Windows con ese chip.
   Aún así el *ranking* de energía por fase se mantiene (proporcional a la duración,
   que CodeCarbon sí mide bien) — la comparación RELATIVA es válida para el ejercicio.
2. Para mediciones directas, instala CodeCarbon en Linux bare-metal (RAPL real) o
   discute en clase las alternativas (JoularJX + Scaphandre en Java, pyRAPL, CodeGreen).

## 8. Nota histórica (opcional): la versión Java del lab

Si te interesa usar mediciones RAPL reales (por método de ejecución, más precisas
pero con más setup), en la primera versión del lab usamos **JoularJX** (agente de JVM)
+ el driver RAPL de Hubblo para Windows. Los enlaces están en la sección 9. Discute
con el profesor si algún día hay que hacer esa versión.

## 9. Referencias

- CodeCarbon (la herramienta de este lab): https://github.com/mlco2/codecarbon
- Documentación de su API (EmissionsTracker, CSV): https://mlco2.github.io/codecarbon/
- CodeGreen (plataforma multi-lenguaje, más reciente): https://arxiv.org/html/2603.17924
- JoularJX (equivalente Java, con atribución por método): https://github.com/joular/joularjx
- Driver RAPL para Windows de Hubblo (usado por la versión Java): https://github.com/joular/WinPowerMonitor

---
*Herramientas usadas: Python 3.13, CodeCarbon (licencia MIT). Está todo instalado en
un entorno virtual (`.venv/`) para no tocar tu instalación global de Python.*

## 10. Limpieza opcional del sistema

Si ya instalaste Scaphandre y el driver RAPL de Hubblo para el lab previo en Java y
ya no los necesitas:
- Agregar/Quitar programas: desinstalar **Scaphandre**.
- `sc delete ScaphandreDrv` en un CMD como Administrador.
