#!/bin/bash

# Copy service and timer files to systemd directory
sudo cp meetup-announcer.service /etc/systemd/system/
sudo cp meetup-announcer.timer /etc/systemd/system/

# Reload systemd to recognize new files
sudo systemctl daemon-reload

# Enable and start the timer
sudo systemctl enable meetup-announcer.timer
sudo systemctl start meetup-announcer.timer

# Check status
echo "Service status:"
sudo systemctl status meetup-announcer.timer
echo -e "\nTimer status:"
sudo systemctl status meetup-announcer.timer