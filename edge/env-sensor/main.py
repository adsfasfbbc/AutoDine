import serial
import csv
from datetime import datetime
import time
# --------------------------配置区--------------------------
SERIAL_PORT = "/dev/ttyUSB0"
BAUD_RATE = 9600
SLAVE_ADDR = 0x02
csv_filename = "sensor_data.csv"

# =========【新增：智能家居阈值，只在这里修改】=========
TEMP_HIGH = 28.0    # 高于该温度建议制冷
TEMP_LOW  = 18.0    # 低于该温度建议制热
TVOC_LIMIT = 400    # TVOC大于该值建议开风扇
HUMI_HIGH = 65.0    # 湿度大于该值建议空调除湿
FLAME_ALARM = 1     # 火焰信号非0代表检测到起火
# =====================================================

# REG_CONFIG: name显示名称，unit单位，reg寄存器地址，div缩放除数
REG_CONFIG = [
    {"name": "TVOC", "unit": "ppb", "reg": 0x0001, "div": 1},
    {"name": "温度", "unit": "℃", "reg": 0x0002, "div": 1},
    {"name": "湿度", "unit": "%RH", "reg": 0x0003, "div": 1},
    {"name": "PM2.5", "unit": "μg/m³", "reg": 0x0005, "div": 1},
    {"name": "大气压", "unit": "hPa", "reg": 0x0006, "div": 10.0},
    {"name": "火焰", "unit": "", "reg": 0x0007, "div": 1},
    {"name": "CO2", "unit": "ppm", "reg": 0x0009, "div": 1},
]
# -----------------------------------------------------------
def calc_crc(data):
    """Modbus CRC16校验计算"""
    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            if crc & 0x01:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return crc

def read_single_reg(ser, addr, reg):
    """读取单个寄存器，返回【有符号16位整数】，通信失败返回None"""
    send_buf = [addr, 0x03, (reg >> 8) & 0xFF, reg & 0xFF, 0x00, 0x01]
    crc16 = calc_crc(bytes(send_buf))
    send_buf.append(crc16 & 0xFF)
    send_buf.append((crc16 >> 8) & 0xFF)
    ser.reset_input_buffer()
    ser.write(bytes(send_buf))
    resp = ser.read(7)
    if len(resp) != 7:
        return None
    payload = resp[:-2]
    recv_crc = resp[-2] + (resp[-1] << 8)
    calc_crc_val = calc_crc(payload)
    if recv_crc != calc_crc_val:
        return None
    raw_val = (resp[3] << 8) + resp[4]
    # 关键：转为有符号16位int，支持负温度
    if raw_val >= 0x8000:
        raw_val = raw_val - 0x10000
    return raw_val

def init_csv_file():
    """初始化CSV文件，没有文件就写入表头"""
    try:
        with open(csv_filename, "r", encoding="utf-8") as f:
            pass
    except FileNotFoundError:
        with open(csv_filename, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            header = ["时间"] + [f"{cfg['name']}({cfg['unit']})" for cfg in REG_CONFIG]
            writer.writerow(header)

def main():
    init_csv_file()
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.8)
    print("=== 多环境传感器采集程序启动 ===")
    print("采集项：", [f"{cfg['name']}({cfg['unit']})" for cfg in REG_CONFIG])
    print("Ctrl+C 停止采集\n")
    try:
        while True:
            result = {}
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            result["时间"] = now_str
            for cfg in REG_CONFIG:
                raw = read_single_reg(ser, SLAVE_ADDR, cfg["reg"])
                if raw is not None:
                    val = raw / cfg["div"]
                    result[f"{cfg['name']}({cfg['unit']})"] = round(val, 1)
                    print(f"{cfg['name']}:{val}{cfg['unit']} ", end="")
                else:
                    result[f"{cfg['name']}({cfg['unit']})"] = None
                    print(f"{cfg['name']}:通信失败 ", end="")
                time.sleep(0.2)
            print("")

            # =====================【新增：数据比较，输出家电控制建议，原有代码完全不动】=====================
            temp_val  = result.get("温度(℃)")
            tvoc_val  = result.get("TVOC(ppb)")
            humi_val  = result.get("湿度(%RH)")
            flame_val = result.get("火焰()")
            suggest_list = []

            if temp_val is not None:
                if temp_val > TEMP_HIGH:
                    suggest_list.append("[建议]温度过高，请开启空调制冷")
                elif temp_val < TEMP_LOW:
                    suggest_list.append("[建议]温度过低，请开启空调制热")

            if humi_val is not None:
                if humi_val > HUMI_HIGH:
                    suggest_list.append("[建议]湿度过高，请开启空调除湿")

            # 仅空气质量异常时输出风扇提示，正常不输出风扇相关
            if tvoc_val is not None:
                if tvoc_val > TVOC_LIMIT:
                    suggest_list.append("[建议]空气质量差，请打开风扇")

            # 火焰检测，检测到起火输出逃离提示
            if flame_val is not None:
                if flame_val >= FLAME_ALARM:
                    suggest_list.append("[警告！]检测到火焰，请立即撤离现场！")

            # 全部条件正常，输出当前环境适宜
            if len(suggest_list) > 0:
                for s in suggest_list:
                    print(s)
            else:
                # 没有任何告警建议，代表环境正常
                print("[提示] 当前环境适宜")
            # ==========================================================================================

            row_data = [result[key] for key in result.keys()]
            with open(csv_filename, "a", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(row_data)
            time.sleep(1.0)
    except KeyboardInterrupt:
        print("\n程序结束，数据保存至", csv_filename)
    finally:
        ser.close()

if __name__ == "__main__":
    main()
