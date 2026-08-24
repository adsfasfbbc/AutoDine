import serial
import random
import time
import crcmod


class ModbusMultiEnvSensor:
    def __init__(self, port, port_backup, baudrate, slave_id, mock_sensor=False):
        self.port = port
        self.port_backup = port_backup
        self.baudrate = baudrate
        self.slave_id = slave_id
        self.mock_sensor = mock_sensor
        self.ser = None

        if not self.mock_sensor:
            try:
                self.ser = serial.Serial(port, baudrate=self.baudrate, timeout=0.5)
            except Exception:
                self.ser = serial.Serial(port_backup, baudrate=self.baudrate, timeout=0.5)

    def _send_read_reg_cmd(self, reg_addr: int):
        func_code = 0x03
        reg_count = 0x0001
        payload = bytes([self.slave_id, func_code]) + reg_addr.to_bytes(2, byteorder='big') + reg_count.to_bytes(2, byteorder='big')
        crc16 = crcmod.Crc(0x18005, initCrc=0xFFFF, rev=True)
        crc16.update(payload)
        crc_val = crc16.crcValue
        tx_frame = payload + crc_val.to_bytes(2, byteorder='little')

        self.ser.flushInput()
        self.ser.flushOutput()
        self.ser.write(tx_frame)
        resp = self.ser.read(7)
        if len(resp) != 7:
            return None
        reg_val = int.from_bytes(resp[3:5], byteorder='big')
        return reg_val

    def read_all(self):
        if self.mock_sensor:
            return {
                "tvoc_ppb": random.randint(10, 800),
                "temperature": round(random.uniform(22.0, 28.0), 1),
                "humidity": round(random.uniform(40, 65), 1),
                "pm25": random.randint(5, 40),
                "atm_pressure": round(random.uniform(980.0, 1030.0), 1),
                "fire": random.randint(0, 1),
                "co2_ppm": random.randint(420, 1200),
                "sensor_model": "Multi‑Modbus‑Env"
            }
        try:
            tvoc = self._send_read_reg_cmd(0x0001)
            temp = self._send_read_reg_cmd(0x0002)
            hum = self._send_read_reg_cmd(0x0003)
            pm25 = self._send_read_reg_cmd(0x0005)
            atm_raw = self._send_read_reg_cmd(0x0006)
            fire = self._send_read_reg_cmd(0x0007)
            co2 = self._send_read_reg_cmd(0x0009)

            if None in [tvoc, temp, hum, pm25, atm_raw, fire, co2]:
                return None

            atm_pressure = atm_raw / 10.0
            return {
                "tvoc_ppb": tvoc,
                "temperature": float(temp),
                "humidity": float(hum),
                "pm25": pm25,
                "atm_pressure": atm_pressure,
                "fire": fire,
                "co2_ppm": co2,
                "sensor_model": "Multi‑Modbus‑Env"
            }
        except Exception:
            return None

    def close(self):
        if self.ser is not None:
            self.ser.close()
