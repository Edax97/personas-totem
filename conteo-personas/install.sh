#!/bin/bash

# new virtual env
source .env
python -m venv "$CONTEO_PERSONAS_ENV"

# install dependencies
source "$CONTEO_PERSONAS_ENV/bin/activate";
pip install ultralytics
pip install boxmot

cp .env /usr/local/etc/.conteo.env
cp "conteo-personas.sh" /usr/local/bin/
chmod +x /usr/local/bin/*sh