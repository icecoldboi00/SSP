# Printing System Troubleshooting Guide

## Quick Diagnosis

Run the diagnostic script to identify issues:
```bash
python diagnose_printing.py
```

## Common Issues and Solutions

### 1. PyMuPDF Library Missing
**Error:** `PyMuPDF library is not installed`

**Solution:**
```bash
pip install PyMuPDF
```

### 2. CUPS Not Installed
**Error:** `'lp' command not found`

**Solution:**
```bash
sudo apt-get update
sudo apt-get install cups
sudo systemctl start cups
sudo systemctl enable cups
```

### 3. Printer Not Found
**Error:** `Printer 'HP_Smart_Tank_580_590_series_5E0E1D_USB' not found`

**Solutions:**
1. **Check available printers:**
   ```bash
   lpstat -p
   ```

2. **Update printer name in config.py:**
   ```python
   printer_name = "Your_Actual_Printer_Name"
   ```

3. **Add a printer:**
   ```bash
   sudo lpadmin -p HP_Printer -E -v usb://HP/Smart%20Tank%20580%20590%20series%205E0E1D%20USB -m everywhere
   ```

### 4. Printer Offline/Stopped
**Error:** `Printer is offline or stopped`

**Solutions:**
```bash
# Enable printer
sudo cupsenable HP_Printer

# Start printer
sudo cupsaccept HP_Printer

# Check status
lpstat -p HP_Printer
```

### 5. Paper Jam
**Error:** `Paper jam detected`

**Solution:**
1. Clear the paper jam physically
2. Reset printer status:
   ```bash
   sudo cupsenable HP_Printer
   ```

### 6. File Not Found
**Error:** `PDF file not found`

**Solutions:**
1. Check if USB drive is properly mounted
2. Verify file path in logs
3. Ensure file permissions are correct

### 7. Permission Issues
**Error:** `Permission denied`

**Solutions:**
```bash
# Add user to lpadmin group
sudo usermod -a -G lpadmin $USER

# Restart CUPS
sudo systemctl restart cups
```

## Testing Steps

### 1. Test Basic Printing
```bash
echo "Test print" | lp -d Your_Printer_Name
```

### 2. Test PDF Printing
```bash
lp -d Your_Printer_Name /path/to/test.pdf
```

### 3. Run System Test
```bash
python test_printing.py
```

## Debug Mode

Enable debug logging by adding this to your main application:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## File System Issues

### Check Temp Directory
```bash
ls -la /tmp/
df -h /tmp/
```

### Check USB Mount
```bash
lsblk
mount | grep usb
```

## Printer Configuration

### List All Printers
```bash
lpstat -p
```

### Get Printer Details
```bash
lpstat -l -p Your_Printer_Name
```

### Test Printer
```bash
lp -d Your_Printer_Name /usr/share/cups/data/testprint
```

## Common CUPS Commands

```bash
# List printers
lpstat -p

# Check printer status
lpstat -l -p Your_Printer_Name

# Enable printer
sudo cupsenable Your_Printer_Name

# Disable printer
sudo cupsdisable Your_Printer_Name

# Delete printer
sudo lpadmin -x Your_Printer_Name

# Add printer
sudo lpadmin -p Printer_Name -E -v device_uri -m driver

# Restart CUPS
sudo systemctl restart cups
```

## Log Files

Check these log files for errors:
- `/var/log/cups/error_log`
- `/var/log/cups/access_log`
- Application console output

## Still Having Issues?

1. Run the diagnostic script: `python diagnose_printing.py`
2. Check CUPS logs: `sudo tail -f /var/log/cups/error_log`
3. Test with a simple file: `echo "test" | lp`
4. Verify printer is physically connected and powered on
5. Check USB cable and connections
