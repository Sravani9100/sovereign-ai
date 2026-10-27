# MW-400 Hydraulic Press Troubleshooting Manual

Synthetic demonstration document for the fictional Musterwerk GmbH. Internal engineering use only.

## 1 Safety First

Before any troubleshooting, switch the press to maintenance mode, lock out the main switch, and depressurize the hydraulic system. Never bypass the light curtain.

## 2 Error Codes

### E101 Light Curtain Interrupted

The safety light curtain detected an object in the work area. Remove the object and acknowledge the error on the HMI. If the error persists, clean the light curtain lenses.

### E102 Emergency Stop Active

An emergency stop button is pressed. Release all emergency stop buttons and reset the safety controller.

### E103 Oil Temperature High

The hydraulic oil is above 65 °C. Check the cooler fan and the oil level. Let the press cool down before restarting.

### E104 Pressure Sensor Fault

The main pressure sensor (B201) reports a value outside 0 to 350 bar or no signal.

1. Check the sensor cable and the M12 connector at B201 for damage or loose contacts.
2. Measure the sensor output at terminal X4.12: it must be between 4 and 20 mA.
3. If the signal is outside this range with the system depressurized, replace sensor B201 (spare part 40-2210).
4. After replacement, run the pressure calibration routine in the HMI service menu.

If E104 occurs together with E103, check the oil temperature first: overheated oil can damage the sensor.

### E105 Valve Feedback Missing

The main valve Y1 did not report its position within 200 ms. Check the valve plug and the 24 V supply.

### E110 Communication Timeout

The PLC lost contact with the HMI. Restart the HMI. If the error repeats, check the Ethernet cable between PLC and HMI.

## 3 Escalation

If an error cannot be resolved with this manual within one hour, contact the on-call service engineer via the service hotline.
