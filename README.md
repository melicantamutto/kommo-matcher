# Kommo Matcher

Asigna el **ID de Kommo** a una base nueva antes de importarla, para que los leads
nuevos queden atados a los contactos que ya existen — y Kommo **no duplique**.

El problema que resuelve: cuando importás una base a Kommo, no deduplica solo. Si
subís un contacto que ya existe (y cambió algún dato), Kommo crea uno nuevo. La
única forma de evitarlo es darle a cada fila el **ID del contacto existente**. Esta
herramienta encuentra ese ID por vos, de forma segura.

## Cómo funciona el match (cascada)

Para cada fila de la base a importar, busca a la persona en los Contactos de Kommo,
de la señal más fuerte a la más débil:

| Señal | Qué hace |
|---|---|
| **DNI coincide** | Ata automático. El DNI es único. |
| **Teléfono coincide + nombre parecido** | Ata automático. |
| **Teléfono coincide pero nombre distinto** | A revisión (un teléfono lo comparten madre e hijos). |
| **Solo coincide el nombre** | A revisión. Un nombre solo nunca confirma. |
| **La fila coincide con 2+ contactos** | A revisión. |
| **No coincide nada** | Queda sin ID → Kommo lo crea nuevo. |

**Regla de oro:** un nombre solo NUNCA ata automático. Hace falta una clave fuerte
(DNI o teléfono) para confiar. Así nunca se cruza el ID de una persona con otra.

### Discrepancias de datos

Si la identidad es segura (matchea por DNI) pero un dato difiere — teléfono, nombre
o fecha de nacimiento — **igual ata el ID** (evita el duplicado) y **marca** el campo
distinto para que decidas qué valor es el correcto.

## Salida

El archivo original + estas columnas:

- `id_contacto` — el ID a usar para atar el lead al contacto existente.
- `id_lead` / `ya_existe_como_lead` — aviso de que el lead ya existe.
- `motivo_match` — por qué matcheó (dni / telefono / nombre). Para auditar.
- `estado` — `ok`, `revisar_dato`, `revisar_identidad`, `nuevo`.
- `discrepancias` / `candidatos` / `detalle_revision` — contexto para revisar.

## Cómo correrlo

### Mac (fácil, doble clic)

1. Descargá el proyecto (botón verde **Code → Download ZIP**) y descomprimilo.
2. Doble clic en **`iniciar.command`**.

La primera vez prepara todo solo (puede pedir permiso de macOS para abrir el
archivo: clic derecho → Abrir). Después abre la app en el navegador. Los datos
nunca salen de tu computadora.

### Manual (cualquier sistema)

Necesitás Python 3.11+.

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Abrí <http://localhost:8000> en el navegador:

1. Cargá los 3 archivos (Contactos y Base a importar son obligatorios; Leads es opcional).
2. Confirmá las columnas (te pre-selecciona la que tiene más datos).
3. Ejecutá el match, revisá los casos dudosos y descargá el CSV con los IDs.

Hay archivos de prueba en `examples/` (datos inventados) para probarlo sin tu base real.

## Probar rápido

```bash
# Datos de ejemplo, sin datos reales
ls examples/
```

## Tests

Toda la lógica de matching vive en el paquete `matcher/` (sin nada de UI) y está
cubierta por tests:

```bash
pytest
```

## Arquitectura

- `matcher/` — el motor puro: normalización, cascada, discrepancias. Sin UI.
  - `normalize.py` — teléfono (AR), DNI, nombre, fecha, similitud de nombres.
  - `matching.py` — la cascada y la política de revisión.
  - `reader.py` — lee xlsx/csv, maneja headers duplicados, sugiere columnas.
  - `pipeline.py` — orquesta archivos + mapeo → filas de salida.
- `app/` — la cáscara web (FastAPI + una página HTML). Solo entrada/salida.

> ⚠️ Este repo **no contiene ninguna base con datos personales**. Las bases reales
> están excluidas en `.gitignore`.
