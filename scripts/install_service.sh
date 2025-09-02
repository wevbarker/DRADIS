#!/bin/bash
# Install DRADIS as a system service

# Copy service file
sudo cp dradis.service /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload

# Enable service
sudo systemctl enable dradis

echo "DRADIS service installed successfully!"
echo "To start: sudo systemctl start dradis"
echo "To check status: sudo systemctl status dradis"
echo "To view logs: journalctl -u dradis -f"