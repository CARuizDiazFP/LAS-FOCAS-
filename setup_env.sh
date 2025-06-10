#!/usr/bin/env bash
set -e

# Directorio para la cache de pip
PIP_CACHE_DIR="$HOME/.cache/pip"
mkdir -p "$PIP_CACHE_DIR"

# Crear y activar el entorno virtual
python -m venv .venv
source .venv/bin/activate

# Actualizar pip e instalar dependencias
pip install --upgrade pip
pip install --cache-dir "$PIP_CACHE_DIR" -r "Sandy bot/requirements.txt"

# Herramientas de pruebas
pip install pytest pytest-cov
