#!/bin/bash

cp .env /usr/local/etc/.conteo.env
cp "conteo-personas/conteo-personas.sh" /usr/local/bin/
cp "ui/ui-totem.sh" /usr/local/bin/
cp ui/ui-totem.desktop "$HOME/.config/autostart/"
sudo chmod +x "$HOME/.config/autostart/*.desktop"
chmod +x /usr/local/bin/*sh