#!/usr/bin/env bash
set -e

# Directorio para la cache de pip
PIP_CACHE_DIR="$HOME/.cache/pip"
mkdir -p "$PIP_CACHE_DIR"

# Crear y activar el entorno virtual
python3 -m venv .venv
source .venv/bin/activate

# Exportar PYTHONPATH para que los módulos del proyecto se encuentren
SANDY_PATH="$PWD/Sandy bot"
if [ -z "$PYTHONPATH" ]; then
    export PYTHONPATH="$SANDY_PATH"
else
    export PYTHONPATH="$PYTHONPATH:$SANDY_PATH"
fi

# Actualizar pip e instalar dependencias
pip install --upgrade pip
pip install --cache-dir "$PIP_CACHE_DIR" -r "Sandy bot/requirements.txt"

# Herramientas de pruebas
pip install pytest pytest-cov
