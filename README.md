# Meetup Event Announcer

Automatically announces upcoming Meetup events for your group.

## Prerequisites

- Python 3.8 or higher
- AlmaLinux 8 or higher
- Meetup account with admin access to your group

## Installation

1. Install system dependencies:
```bash
# Install EPEL repository
sudo dnf install -y epel-release

# Install required packages
sudo dnf install -y chromium chromium-headless chromedriver xorg-x11-server-Xvfb python3-pip python3-devel

sudo dnf install -y xorg-x11-server-Xephyr
sudo dnf install -y tigervnc-server
```

2. Create and activate a virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate
```

3. Install Python dependencies:
```bash
pip install -r requirements.txt
```

## Usage

1. First-time setup (manual login required):
ssh into your server with -Y for x11 forwarding
```
source venv/bin/activate
```

```bash
python meetup_announcer.py --manual-login --group-url "https://www.meetup.com/your-group-name/"
```

2. Subsequent runs (automated):
```bash
python meetup_announcer.py --group-url "https://www.meetup.com/your-group-name/"
```

## Installation

```bash
sudo ./install_service.sh
sudo systemctl daemon-reload
sudo systemctl restart meetup-announcer.timer
```

## Troubleshooting

1. If you encounter Chrome/Chromium issues:
   - Verify Chrome is installed: `which chromium`
   - Check Chrome version: `chromium --version`
   - Ensure chromedriver matches Chrome version: `chromedriver --version`

2. For display issues:
   - Verify Xvfb is running: `ps aux | grep Xvfb`
   - Check DISPLAY environment variable: `echo $DISPLAY`

## Logging

All actions are logged to `meetup_announcer.log` in the current directory. Check this file for detailed information about the script's operation and any errors that occur.

## Security Notes

- The script stores Chrome profile data in the `chrome_profile` directory
- Never share your Meetup credentials or Chrome profile data
