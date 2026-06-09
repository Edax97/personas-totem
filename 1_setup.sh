#!/bin/bash

sudo cp .env /usr/local/etc/.conteo.env
sudo cp "conteo-personas/conteo-personas.sh" /usr/local/bin/
sudo cp "ui/ui-totem.sh" /usr/local/bin/
sudo cp pose/pose.sh /usr/local/bin/
cp ui/ui-totem.desktop "$HOME/.config/autostart/"
sudo chmod +x "$HOME/.config/autostart/ui-totem.desktop"
sudo chmod +x /usr/local/bin/*sh