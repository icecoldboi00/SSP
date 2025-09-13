# Raspberry Pi Setup Guide for SSP Printing System

## Prerequisites

### 1. Install Required Python Packages
```bash
sudo apt update
sudo apt install python3-pip python3-pyqt5
pip3 install PyMuPDF
```

### 2. Install and Configure CUPS (Printing System)
```bash
# Install CUPS
sudo apt install cups cups-client

# Add your user to the lpadmin group
sudo usermod -a -G lpadmin pi

# Start and enable CUPS service
sudo systemctl start cups
sudo systemctl enable cups
```

### 3. Configure Your Printer

#### Option A: USB Printer
1. Connect your printer via USB
2. Check if it's detected:
   ```bash
   lsusb
   ```
3. Add the printer to CUPS:
   ```bash
   sudo lpadmin -p "HP_Smart_Tank_580_590_series" -E -v usb://HP/Smart%20Tank%20580%20590%20series -m everywhere
   ```

#### Option B: Network Printer
1. Find your printer on the network:
   ```bash
   lpinfo -v
   ```
2. Add the printer:
   ```bash
   sudo lpadmin -p "HP_Smart_Tank_580_590_series" -E -v ipp://PRINTER_IP_ADDRESS -m everywhere
   ```

### 4. Verify Printer Setup
```bash
# List available printers
lpstat -p

# Test printing
echo "Test print" | lp -d "HP_Smart_Tank_580_590_series"
```

### 5. Update Printer Name in Code
Edit `printing/printer_manager.py` and update the `PRINTER_NAME` variable with your actual printer name from `lpstat -p`.

## Running the Application

### 1. Install Additional Dependencies
```bash
# For GPIO support (if using physical payment system)
sudo apt install python3-rpi.gpio

# For USB monitoring
sudo apt install python3-pyudev
```

### 2. Run the Application
```bash
cd /path/to/your/SSP/project
python3 main_app.py
```

## Troubleshooting

### Printer Not Found
- Check printer connection: `lsusb` or `lpinfo -v`
- Verify printer name: `lpstat -p`
- Check CUPS web interface: http://localhost:631

### Permission Issues
- Ensure user is in lpadmin group: `groups $USER`
- Check CUPS permissions: `sudo nano /etc/cups/cupsd.conf`

### PDF Processing Issues
- Verify PyMuPDF installation: `python3 -c "import fitz; print('PyMuPDF OK')"`
- Check file permissions on PDF files

## Hardware Setup (Optional)

### GPIO Configuration for Payment System
If using physical coin/bill acceptors:
1. Enable GPIO: `sudo raspi-config` → Interface Options → GPIO
2. Install pigpio: `sudo apt install pigpio`
3. Start pigpio service: `sudo systemctl start pigpio`

### USB File Access
For USB file reading:
1. Ensure USB devices are mounted: `lsblk`
2. Check permissions: `ls -la /media/pi/`
