"""Web shell over the matching engine.

This module owns only I/O and presentation: receive the three files, let the user
map columns (with data-driven suggestions), run the engine, and return a summary,
the rows needing attention, and a downloadable result. All identity logic lives
in the ``matcher`` package.
"""

from __future__ import annotations

import csv
import tempfile
import uuid
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

from matcher.models import Outcome
from matcher.pipeline import (
    ColumnMap,
    build_kommo_records,
    row_estado,
    run_matching,
    to_output_rows,
)
from matcher.reader import Table, read_table

app = FastAPI(title="Kommo Matcher")

_STATIC = Path(__file__).parent / "static"

# Candidate column names per field, best-known first. suggest_column() then picks
# whichever candidate actually holds the most data, so an empty "Teléfono celular"
# loses to a populated "Teléfono oficina".
_CANDIDATES: dict[str, list[str]] = {
    "id": ["ID", "Id", "id"],
    "dni": ["DNI (contacto)", "DNI", "Dni", "Documento", "DOCUMENTO", "Nro Documento"],
    "phone": [
        "Teléfono oficina",
        "Teléfono celular",
        "Teléfono celular (contacto)",
        "Teléfono oficina (contacto)",
        "TELEFONO",
        "Teléfono",
        "Telefono",
        "Celular",
        "CELULAR",
    ],
    "name": [
        "Nombre",
        "Nombre del lead",
        "Nombre completo",
        "PACIENTE",
        "Paciente",
        "Contacto principal",
        "NOMBRE",
    ],
    "birthdate": [
        "F. NACIMIENTO",
        "Fecha de nacimiento",
        "Cumpleaños (contacto)",
        "Cumpleaños",
        "FECHA NACIMIENTO",
    ],
}

# Which fields each role needs to map.
_ROLE_FIELDS = {
    "contactos": ["id", "dni", "phone", "name", "birthdate"],
    "leads": ["id", "dni", "phone", "name", "birthdate"],
    "importar": ["dni", "phone", "name", "birthdate"],
}

# session_id -> {"dir": Path, "files": {role: path}}
_SESSIONS: dict[str, dict] = {}


def _suggest(table: Table, fields: list[str]) -> dict[str, str | None]:
    return {field: table.suggest_column(_CANDIDATES[field]) for field in fields}


def _columns_info(table: Table) -> list[dict]:
    return [
        {"name": h, "filled": table.fill_rate(i)[0], "total": len(table.rows)}
        for i, h in enumerate(table.headers)
    ]


def _save_upload(directory: Path, role: str, upload: UploadFile) -> Path:
    suffix = Path(upload.filename or "").suffix.lower() or ".csv"
    path = directory / f"{role}{suffix}"
    path.write_bytes(upload.file.read())
    return path


def _column_map(mapping: dict, fields: list[str]) -> ColumnMap:
    # Empty string from the UI means "no column".
    clean = {f: (mapping.get(f) or None) for f in fields}
    return ColumnMap(**clean)


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    return HTMLResponse((_STATIC / "index.html").read_text(encoding="utf-8"))


@app.post("/analyze")
async def analyze(
    contactos: UploadFile,
    importar: UploadFile,
    leads: UploadFile | None = None,
) -> JSONResponse:
    session_id = uuid.uuid4().hex
    directory = Path(tempfile.mkdtemp(prefix="kommo_"))
    files: dict[str, Path] = {}
    response: dict[str, dict] = {}

    uploaded = {"contactos": contactos, "importar": importar}
    if leads is not None and leads.filename:
        uploaded["leads"] = leads

    for role, upload in uploaded.items():
        path = _save_upload(directory, role, upload)
        files[role] = path
        try:
            table = read_table(path)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"{role}: {exc}") from exc
        response[role] = {
            "filename": upload.filename,
            "rows": len(table.rows),
            "columns": _columns_info(table),
            "suggestions": _suggest(table, _ROLE_FIELDS[role]),
        }

    _SESSIONS[session_id] = {"dir": directory, "files": files}
    return JSONResponse({"session_id": session_id, "files": response})


@app.post("/match")
async def match(payload: dict) -> JSONResponse:
    session_id = payload.get("session_id")
    session = _SESSIONS.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Sesión no encontrada. Volvé a analizar.")

    mappings = payload.get("mappings", {})
    files = session["files"]

    contacts_table = read_table(files["contactos"])
    import_table = read_table(files["importar"])
    contacts = build_kommo_records(
        contacts_table, _column_map(mappings.get("contactos", {}), _ROLE_FIELDS["contactos"])
    )

    leads = []
    if "leads" in files:
        leads_table = read_table(files["leads"])
        leads = build_kommo_records(
            leads_table, _column_map(mappings.get("leads", {}), _ROLE_FIELDS["leads"])
        )

    import_map = _column_map(mappings.get("importar", {}), _ROLE_FIELDS["importar"])
    results = run_matching(import_table, import_map, contacts, leads)

    # Persist the output for download.
    headers, rows = to_output_rows(import_table, results)
    out_path = session["dir"] / "resultado.csv"
    with open(out_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)
    session["output"] = out_path

    name_values = import_table.values(import_map.name) if import_map.name else None
    summary = {"total": len(results), "ok": 0, "revisar_dato": 0, "revisar_identidad": 0, "nuevo": 0}
    review: list[dict] = []
    for result in results:
        estado = row_estado(result)
        summary[estado] += 1
        if estado in ("revisar_dato", "revisar_identidad"):
            review.append(
                {
                    "fila": result.row_index + 1,
                    "nombre": name_values[result.row_index] if name_values else "",
                    "estado": estado,
                    "motivo": result.motivo_match,
                    "id_contacto": result.id_contacto,
                    "candidatos": list(result.contacto_candidatos),
                    "detalle": result.contacto_review_cause or "",
                    "discrepancias": [
                        {"campo": d.field, "kommo": d.kommo_value, "nuevo": d.import_value}
                        for d in result.discrepancias
                    ],
                }
            )

    leads_existentes = sum(1 for r in results if r.ya_existe_como_lead)
    return JSONResponse(
        {
            "summary": summary,
            "leads_existentes": leads_existentes,
            "review": review,
            "download_url": f"/download/{session_id}",
        }
    )


@app.get("/download/{session_id}")
def download(session_id: str) -> FileResponse:
    session = _SESSIONS.get(session_id)
    if not session or "output" not in session:
        raise HTTPException(status_code=404, detail="No hay resultado para descargar.")
    return FileResponse(
        session["output"], filename="Resultado_con_IDs.csv", media_type="text/csv"
    )
