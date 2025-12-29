# start_perfetto_subprocess.py
import logging
import os
import shutil
import subprocess
from datetime import datetime
def start_perfetto(
    config_file="/data/misc/perfetto-configs/HardwareInfo.pbtx",
    outfile="/data/misc/perfetto-traces/trace.perfetto-trace"
):
    """
    在设备上启动一段系统级 Perfetto 跟踪，并拉取到本地后删掉设备端文件。
      config_file: 设备端 Perfetto 配置文件路径
      outfile:     设备端跟踪文件输出路径
    """
    # 1. 启动 trace（使用 -t 分配伪终端，以便之后能用 CTRL+C 优雅地停止）
    subprocess.run([
        "adb", "shell", "-t",
        "perfetto",
        "--txt",
        "-c", config_file,
        "--out", outfile
    ], check=True)
    print(f"✅ Perfetto 跟踪已完成，保存在设备：{outfile}")
def start_perfetto_for_AppStartup(
    config_file="/data/misc/perfetto-configs/HardwareInfo.pbtx",
    outfile="/data/misc/perfetto-traces/trace.perfetto-trace"
):
    """
    在设备上启动一段系统级 Perfetto 跟踪，并拉取到本地后删掉设备端文件。
      config_file: 设备端 Perfetto 配置文件路径
      outfile:     设备端跟踪文件输出路径
    """
    # 1. 启动 trace（使用 -t 分配伪终端，以便之后能用 CTRL+C 优雅地停止）
    subprocess.run([
        "adb", "shell", "-t",
        "perfetto",
        "--txt",
        "-c", config_file,
        "--out", outfile
    ], check=True)
    print(f"✅ Perfetto 跟踪已完成，保存在设备：{outfile}")



def get_perfetto(method):
    # 获取当前脚本所在目录（项目根目录）
    script_dir = os.path.dirname(os.path.abspath(__file__))
    # 构建绝对路径：项目根目录/Perfetto/trace/traceRecord/method{method}
    package_folder = os.path.join(script_dir, "Perfetto", "trace", "traceRecord", f"method{method}")
    outfile = "/data/misc/perfetto-traces/trace.perfetto-trace"

    # 1. 确保文件夹存在
    if not os.path.exists(package_folder):
        os.makedirs(package_folder)
        print(f"✅ 创建文件夹：{package_folder}")

    # 2. 生成带时间戳的文件名
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dst_file = os.path.join(package_folder, f"{method}_{timestamp}.perfetto-trace")
    
    subprocess.run([
        "adb", "pull", outfile, dst_file
    ], check=True)
    print(f"✅ 跟踪文件已拉取并保存为：{dst_file}")

    # 3. 删除设备端文件
    subprocess.run([
        "adb", "shell", "rm", "-f", outfile
    ], check=True)
    print(f"✅ 已删除设备端文件：{outfile}")
    
    # 返回生成的文件名（不含路径）
    return os.path.basename(dst_file)

def stop_perfetto():
    logging.info("结束 Perfetto 采集")
    subprocess.run(["adb", "shell", "pkill", "-2", "perfetto"], check=False)

if __name__ == "__main__":
    start_perfetto()
    # get_perfetto()