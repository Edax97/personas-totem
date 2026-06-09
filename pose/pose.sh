#!/bin/bash

source /usr/local/etc/.conteo.env
source "$CONTEO_PERSONAS_ENV/bin/activate";

cd "$POSE_DIR" || exit;
python app.py "$@"