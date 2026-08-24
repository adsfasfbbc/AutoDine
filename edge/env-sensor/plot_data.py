import pandas as pd
import matplotlib.pyplot as plt

def draw():
    df = pd.read_csv("sensor_data.csv")
    df["时间"] = pd.to_datetime(df["时间"])

    plt.rcParams["font.sans-serif"] = ["SimHei"]
    plt.rcParams["axes.unicode_minus"] = False

    fig, axes = plt.subplots(3, 1, figsize=(14, 7), sharex=True)

    axes[0].plot(df["时间"], df["TVOC(ppb)"], color="#d62728", marker=".", label="TVOC(ppb)")
    axes[0].set_ylabel("TVOC ppb")
    axes[0].legend()
    axes[0].grid(alpha=0.3)

    axes[1].plot(df["时间"], df["温度(℃)"], color="#ff7f0e", marker=".", label="温度(℃)")
    axes[1].set_ylabel("温度 ℃")
    axes[1].legend()
    axes[1].grid(alpha=0.3)

    axes[2].plot(df["时间"], df["湿度(%RH)"], color="#2ca02c", marker=".", label="湿度(%RH)")
    axes[2].set_ylabel("湿度 %RH")
    axes[2].legend()
    axes[2].grid(alpha=0.3)

    plt.tight_layout()
    plt.savefig("sensor_plot.png", dpi=150)
    plt.show()
    print(">>> 图片已保存为 sensor_plot.png")

if __name__ == "__main__":
    draw()
