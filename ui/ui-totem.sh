#!/bin/bash

source /usr/local/etc/.conteo.env
cd "$TOTEM_UI_DIR" || exit;

source "$CONTEO_PERSONAS_ENV/bin/activate";
python main.py "$@"