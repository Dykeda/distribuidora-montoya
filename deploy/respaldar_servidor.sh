#!/bin/bash
# Respaldo diario de la base de datos en el VPS. Pensado para correr por cron
# (ver DEPLOY.md). Guarda una copia con fecha y conserva solo los últimos 30 días.
set -e

ORIGEN="/home/montoya/distribuidora-montoya/instance/distribuidora.db"
DESTINO_DIR="/home/montoya/respaldos"

if [ ! -f "$ORIGEN" ]; then
    echo "No se encontró la base de datos en $ORIGEN"
    exit 1
fi

mkdir -p "$DESTINO_DIR"
MARCA=$(date +%Y-%m-%d)
cp "$ORIGEN" "$DESTINO_DIR/distribuidora_$MARCA.db"

# Borra respaldos de más de 30 días
find "$DESTINO_DIR" -name "distribuidora_*.db" -mtime +30 -delete

echo "Respaldo guardado en $DESTINO_DIR/distribuidora_$MARCA.db"
