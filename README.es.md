# MatchLens Pocket Stadium

<p align="center">
  <a href="README.md">English</a> ·
  <a href="README.zh-CN.md">简体中文</a> ·
  <a href="README.fr.md">Français</a> ·
  <strong>Español</strong> ·
  <a href="README.ar.md">العربية</a>
</p>

**Ver MatchLens — el vídeo muestra la experiencia sin conexión; los agentes
conectados a una API utilizan la misma interfaz.**

https://github.com/user-attachments/assets/7c19dc86-b2b1-4d1c-8126-0246e06f65e4

<h3 align="center">
  <a href="https://yuxuanfuture.github.io/MatchLens/">▶ Abrir la demo interactiva</a>
</h3>

<p align="center">Funciona en el navegador con escenarios sintéticos, sin servidor ni clave de API.</p>

[![CI](https://github.com/yuxuanfuture/MatchLens/actions/workflows/ci.yml/badge.svg)](https://github.com/yuxuanfuture/MatchLens/actions/workflows/ci.yml)

MatchLens convierte los eventos de fútbol observados en explicaciones vinculadas a evidencias y en un estadio en miniatura personalizado. Los mismos hechos se transforman en una narración concisa para aficionados, contexto cuantificado para analistas y señales sincronizadas para superposiciones de retransmisión.

## Dos formas de ejecución

MatchLens es un framework ejecutable de evidencias y agentes, no solo un vídeo de demostración prerenderizado.

| Modo | Qué se ejecuta |
| --- | --- |
| **Sin conexión** | Procesamiento determinista de eventos, analítica, evidencias, repetición, localización e interfaz. No requiere modelo ni clave de API. |
| **Multiagente con API** | DeepSeek u Ollama local controla el Coordinator y los roles especialistas opcionales; las herramientas deterministas siguen siendo la fuente de los hechos numéricos y un Verifier independiente revisa cada propuesta. |

Ambos modos comparten la misma ventana de observación congelada, el contrato de evidencias, Pocket Stadium y las comprobaciones de resultados obsoletos. Un modelo puede investigar y explicar el partido, pero no puede inventar registros, adelantar el reloj de repetición ni eludir el presupuesto de solicitudes.

## Por qué MatchLens

Los datos de fútbol son fáciles de contar, pero difíciles de explicar. MatchLens vincula cada afirmación con los eventos o registros de seguimiento que la respaldan, respeta lo que era observable en ese momento y muestra la incertidumbre en lugar de rellenar los huecos con hechos inventados.

La interfaz adapta un mismo flujo de evidencias a los modos Fan y Analyst. El idioma predeterminado es el inglés y también se admiten chino simplificado, francés, español y árabe, además del seguimiento de equipos o jugadores, Pocket Stadium reproducible y una superposición transparente para retransmisión.

## Funciones destacadas

- **Evidencia primero:** las explicaciones enlazan con los registros recibidos y las métricas deterministas; los datos ausentes siguen ausentes en vez de convertirse en cero.
- **Consciente de la repetición:** el tiempo del evento y el tiempo de llegada se mantienen separados, por lo que una repetición no puede revelar un gol o una decisión del VAR futuros.
- **Adaptado a la audiencia:** los modos Fan y Analyst comparten hechos, pero difieren en lenguaje, densidad, enfoque y presentación.
- **Preparado para multiagente:** un sistema acotado opcional puede delegar la investigación, verificar afirmaciones de forma independiente y descartar resultados obsoletos.
- **Demostración portátil:** la experiencia principal funciona localmente con Python y un navegador moderno, sin proceso de compilación del frontend.

## Inicio rápido: sin conexión

Requisitos: Python 3.13 y un navegador moderno. Node.js 22 solo es necesario para las pruebas del navegador.

### macOS o Linux

```bash
python3 -m backend.server --port 43128
```

### Windows

```powershell
powershell -ExecutionPolicy Bypass -File .\start-matchlens-windows.ps1
```

Abre <http://127.0.0.1:43128/?lang=es>. El servicio local debe permanecer activo porque proporciona el flujo de eventos, las API de evidencias y los controles de repetición.

## Conectar un proveedor de modelos

El repositorio incluye adaptadores para la API oficial de DeepSeek y un servicio Ollama en la interfaz de bucle local. La política incluida falla de forma cerrada, por lo que añadir una clave no genera ninguna solicitud. Para activar investigaciones multiagente con API:

1. Configura el proveedor localmente: guarda la clave de DeepSeek en `.env.local`, ignorado por Git, o inicia un modelo Ollama en `127.0.0.1`.
2. Crea una autorización explícita y acotada en `config/model-policy.json`.
3. Inicia el servidor para investigaciones continuas agrupadas por eventos o ejecuta `scripts/run_harness.py` contra una instantánea congelada del flujo.

Consulta **[Configuración de la API del modelo (en inglés)](docs/MODEL_API_SETUP.md)** para ver los comandos de DeepSeek y Ollama, los campos de la política, el comportamiento del presupuesto y los pasos de desactivación. Los secretos nunca entran en el navegador, los prompts, las trazas ni los archivos confirmados.

## Demostración

El escenario principal es una secuencia de 120 segundos en el tiempo añadido: una entrada limpia inicia un contraataque, un mano a mano se señala como fuera de juego, el VAR pasa a una revisión en el campo y el gol solo se concede cuando la decisión final se vuelve observable.

Prueba a cambiar entre los modos Fan y Analyst, cambiar el idioma, seguir a un jugador, abrir **See the evidence**, generar un resumen y retroceder en la línea temporal para confirmar que los resultados futuros desaparecen.

## Sistema multiagente

El producto no necesita un modelo para funcionar. Cuando se activa explícitamente la política fail-closed, las mismas herramientas de evidencia congelada pueden usarse en un sistema de investigación multiagente acotado:

![Arquitectura del sistema multiagente de MatchLens](docs/architecture/multi-agent-system-v3.svg)

Solo el Coordinator puede delegar. Cada propuesta no vacía recibe una revisión independiente, todas las afirmaciones numéricas deben proceder de herramientas deterministas y se descartan los resultados de una posición de reproducción, unas preferencias o una ventana de evidencias anteriores. Los adaptadores de DeepSeek y Ollama local son opcionales; la política incluida desactiva las llamadas al modelo de forma predeterminada.

## Verificación

Ejecuta la suite completa de aceptación sin conexión:

```bash
python3 scripts/offline_acceptance.py
```

Valida los datos sintéticos, ejecuta las pruebas de Python y las pruebas de Node del navegador sin realizar solicitudes a una API de modelos. GitHub Actions ejecuta la misma ruta en cada push y pull request.

## Estructura del proyecto

| Ruta | Propósito |
| --- | --- |
| `backend/` | Servicio de eventos, analítica determinista, herramientas de evidencias, harness de agentes opcional y procesos de vídeo locales |
| `dist/` | Pocket Stadium, renderizador, localización, herramientas de datos y superposición de retransmisión |
| `data/` | Flujos sintéticos reproducibles, manifiestos y planes de señales de audio |
| `evals/` | Expectativas de fixtures y ejecuciones históricas de evaluación claramente etiquetadas |
| `scripts/` | Generación de datos, validación, configuración del entorno y comandos de aceptación |
| `tests/` | Pruebas de regresión de Python y del navegador |
| `docs/` y `case-design/` | Contratos de ingeniería, guías de configuración, limitaciones y justificación de escenarios |

## Documentación

- [Diseño multiagente](docs/HARNESS_PLAN.zh-CN.md)
- [Configuración de la API del modelo (inglés)](docs/MODEL_API_SETUP.md)
- [Flujo de eventos y superposición](docs/STREAM_AND_OVERLAY.md)
- [Contrato de datos sintéticos](data/README.md)
- [Guía de aceptación sin conexión](docs/OFFLINE_ACCEPTANCE.zh-CN.md)
- [Inferencia de vídeo local opcional](docs/WINDOWS_VIDEO.zh-CN.md)
- [Límites de ingeniería](docs/ENGINEERING_ACCEPTANCE.zh-CN.md)
- [Resumen de la entrega](SUBMISSION.md)
- [Avisos de terceros](THIRD_PARTY_NOTICES.md)

## Límites y licencia

- Todos los clubes, jugadores, eventos, posiciones y marcadores son datos sintéticos ficticios.
- No se incluye ni se reivindica material de la Premier League, una fuente oficial de datos, escudos de clubes o una colaboración de producción.
- La ruta de vídeo opcional es preprocesamiento sin conexión, no una demostración de inferencia de retransmisión en tiempo real; las pistas anónimas requieren una asociación explícita con la plantilla.
- El repositorio público excluye pesos de modelos, grabaciones fuente de terceros, la pista de público generada y entornos virtuales específicos de cada equipo.

El código original de MatchLens está disponible para inspección, evaluación y pruebas del hackathon bajo la [LICENSE](LICENSE) source-available del repositorio. Los componentes de terceros conservan sus propias licencias.
