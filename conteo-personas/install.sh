#!/bin/bash

# new virtual env
source .env
python -m venv "$CONTEO_PERSONAS_ENV"

# install dependencies
source "$CONTEO_PERSONAS_ENV/bin/activate";
pip install ultralytics
pip install boxmot
