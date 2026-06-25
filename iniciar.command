#!/bin/bash
# Lanzador de Kommo Matcher para macOS.
# Doble clic en este archivo y listo: instala lo necesario (solo la primera vez)
# y abre la app en el navegador. Los datos nunca salen de esta computadora.

cd "$(dirname "$0")" || exit 1

echo "================================"
echo "   Kommo Matcher"
echo "================================"

if ! command -v python3 >/dev/null 2>&1; then
  echo ""
  echo "No encontré Python 3. Instalalo con:  brew install python"
  echo "(o desde https://www.python.org/downloads/ )"
  echo ""
  echo "Apretá Enter para cerrar."
  read -r
  exit 1
fi

if [ ! -d ".venv" ]; then
  echo "Preparando el entorno (solo la primera vez, puede tardar un minuto)..."
  python3 -m venv .venv || {
    echo "No se pudo crear el entorno. Apretá Enter para cerrar."
    read -r
    exit 1
  }
fi

echo "Instalando/actualizando dependencias..."
./.venv/bin/python -m pip install -q --upgrade pip
./.venv/bin/python -m pip install -q -r requirements.txt

echo ""
echo "Abriendo http://localhost:8000 en el navegador..."
( sleep 3 && open "http://localhost:8000" ) &

echo "App corriendo. Para cerrarla: cerrá esta ventana o apretá Ctrl+C."
echo ""
./.venv/bin/python -m uvicorn app.main:app --port 8000
