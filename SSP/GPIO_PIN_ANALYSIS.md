# GPIO Pin Conflict Analysis for SSP System

## Current GPIO Pin Usage

### 1. **Payment System** (`screens/payment_dialog.py`)
- **Coin Acceptor Pin**: GPIO 17 (INPUT)
- **Bill Acceptor Pin**: GPIO 18 (INPUT) 
- **Bill Inhibit Pin**: GPIO 23 (OUTPUT)

### 2. **Change Dispenser/Hopper System** (`screens/hopper_manager.py`)
- **1-Peso Hopper Signal Pin**: GPIO 21 (INPUT)
- **1-Peso Hopper Enable Pin**: GPIO 16 (OUTPUT)
- **5-Peso Hopper Signal Pin**: GPIO 6 (INPUT)
- **5-Peso Hopper Enable Pin**: GPIO 26 (OUTPUT)

### 3. **SMS System** (`sms_manager.py`)
- **Serial Communication**: `/dev/serial0` (UART pins)
  - **TX Pin**: GPIO 14 (Physical pin 8)
  - **RX Pin**: GPIO 15 (Physical pin 10)

## Pin Conflict Analysis

### ✅ **NO CONFLICTS DETECTED**

All GPIO pins are used for different purposes and there are **no conflicts**:

| Pin | Usage | Type | Function |
|-----|-------|------|----------|
| GPIO 6 | 5P Hopper Signal | INPUT | Coin sensor |
| GPIO 14 | SMS TX | UART | Serial transmission |
| GPIO 15 | SMS RX | UART | Serial reception |
| GPIO 16 | 1P Hopper Enable | OUTPUT | Motor control |
| GPIO 17 | Coin Acceptor | INPUT | Coin detection |
| GPIO 18 | Bill Acceptor | INPUT | Bill detection |
| GPIO 21 | 1P Hopper Signal | INPUT | Coin sensor |
| GPIO 23 | Bill Inhibit | OUTPUT | Bill acceptor control |
| GPIO 26 | 5P Hopper Enable | OUTPUT | Motor control |

## Physical Pin Mapping (Raspberry Pi 3B/4B)

| GPIO | Physical Pin | Function |
|------|--------------|----------|
| 6 | Pin 31 | 5P Hopper Signal |
| 14 | Pin 8 | SMS TX (UART) |
| 15 | Pin 10 | SMS RX (UART) |
| 16 | Pin 36 | 1P Hopper Enable |
| 17 | Pin 11 | Coin Acceptor |
| 18 | Pin 12 | Bill Acceptor |
| 21 | Pin 40 | 1P Hopper Signal |
| 23 | Pin 16 | Bill Inhibit |
| 26 | Pin 37 | 5P Hopper Enable |

## System Compatibility

### ✅ **All Systems Can Run Simultaneously**

1. **Payment System**: Uses GPIO 17, 18, 23
2. **Change Dispenser**: Uses GPIO 6, 16, 21, 26  
3. **SMS System**: Uses GPIO 14, 15 (UART)

### **No Interference Between Systems**

- **Different Pin Numbers**: All systems use completely different GPIO pins
- **Different Functions**: Input vs Output pins are properly separated
- **UART Isolation**: SMS system uses dedicated UART pins (14, 15)
- **Motor Control**: Hopper enable pins (16, 26) are separate from sensor pins

## Recommendations

### ✅ **Current Setup is Optimal**

1. **No Changes Needed**: Your current pin assignment is conflict-free
2. **All Systems Compatible**: Payment, hopper, and SMS can all run together
3. **Proper Separation**: Input and output functions are well-separated
4. **UART Usage**: SMS system correctly uses dedicated UART pins

### **Wiring Checklist**

Make sure your wiring follows this pinout:

```
Payment System:
- Coin Acceptor → GPIO 17 (Pin 11)
- Bill Acceptor → GPIO 18 (Pin 12)  
- Bill Inhibit → GPIO 23 (Pin 16)

Hopper System:
- 1P Signal → GPIO 21 (Pin 40)
- 1P Enable → GPIO 16 (Pin 36)
- 5P Signal → GPIO 6 (Pin 31)
- 5P Enable → GPIO 26 (Pin 37)

SMS System:
- GSM TX → GPIO 14 (Pin 8)
- GSM RX → GPIO 15 (Pin 10)
```

## Conclusion

**✅ NO CONFLICTS - Your system is properly configured!**

All GPIO pins are used for different purposes with no overlap. You can safely run all three systems (payment, hopper, SMS) simultaneously without any pin conflicts.
