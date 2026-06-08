#!/bin/bash

source /usr/local/etc/.conteo.env
cd "$CONTEO_PERSONAS_DIR" || exit;

source "$CONTEO_PERSONAS_ENV/bin/activate";
python app.py
