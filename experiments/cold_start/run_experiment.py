"""
运行App冷启动实验
功能：启动perfetto追踪 -> 冷启动app -> 停止追踪 -> 拉取trace文件
"""
import os
import sys
import subprocess
import threading
import time

# 添加项目根目录到路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
from startPrefetto import start_perfetto, stop_perfetto, get_perfetto


def force_stop_app(package_name):
    """强制停止应用，确保冷启动"""
    try:
        subprocess.run(["adb", "shell", "am", "force-stop", package_name], 
                      check=False, capture_output=True)
        time.sleep(1)
        print(f"✅ 已强制停止应用: {package_name}")
    except Exception as e:
        print(f"⚠️  停止应用时出错: {e}")


def launch_app(package_name, activity_name=None):
    """启动应用"""
    try:
        if activity_name:
            cmd = ["adb", "shell", "am", "start", "-n", f"{package_name}/{activity_name}"]
        else:
            cmd = ["adb", "shell", "monkey", "-p", package_name, "-c", 
                   "android.intent.category.LAUNCHER", "1"]
        subprocess.run(cmd, check=True, capture_output=True)
        print(f"✅ 已启动应用: {package_name}")
        return True
    except Exception as e:
        print(f"❌ 启动应用失败: {e}")
        return False


def run_cold_start_experiment(package_name, activity_name=None, 
                              experiment_name="ColdStart", 
                              trace_duration=30,
                              config_file="/data/misc/perfetto-configs/HardwareInfo.pbtx"):
    """
    运行冷启动实验
    
    Args:
        package_name: 应用包名
        activity_name: 主Activity名称(可选)
        experiment_name: 实验名称
        trace_duration: 追踪时长(秒)
        config_file: perfetto配置文件路径
    
    Returns:
        trace文件路径，如果失败返回None
    """
    print("=" * 60)
    print(f"🚀 开始冷启动实验: {experiment_name}")
    print(f"📦 应用包名: {package_name}")
    print("=" * 60)
    
    # 1. 强制停止应用(确保冷启动)
    print("\n[1/5] 停止应用(确保冷启动)...")
    force_stop_app(package_name)
    time.sleep(2)
    
    # 2. 启动perfetto追踪(在后台线程)
    print("\n[2/5] 启动Perfetto追踪...")
    
    def run_perfetto():
        try:
            start_perfetto(config_file=config_file, 
                          outfile="/data/misc/perfetto-traces/trace.perfetto-trace")
        except Exception as e:
            print(f"⚠️  Perfetto进程异常: {e}")
    
    perfetto_thread = threading.Thread(target=run_perfetto, daemon=True)
    perfetto_thread.start()
    time.sleep(2)  # 等待perfetto启动
    
    # 3. 启动应用
    print("\n[3/5] 启动应用...")
    if not launch_app(package_name, activity_name):
        stop_perfetto()
        return None
    
    # 4. 等待应用启动完成
    print(f"\n[4/5] 等待应用启动完成（5秒）...")
    time.sleep(5)
    
    # 5. 停止perfetto追踪
    print("\n[5/5] 停止Perfetto追踪...")
    stop_perfetto()
    perfetto_thread.join(timeout=5)
    time.sleep(3)  # 等待perfetto完全停止
    
    # 6. 拉取trace文件
    print("\n[6/5] 拉取Trace文件...")
    get_perfetto(experiment_name)
    
    print("\n" + "=" * 60)
    print("✅ 实验完成!")
    print("=" * 60)
    
    # 返回trace文件路径
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(script_dir))  # experiments/cold_start -> experiments -> 项目根目录
    trace_path = os.path.join(project_root, "Perfetto", "trace", "traceRecord", 
                             f"method{experiment_name}", f"{experiment_name}.perfetto-trace")
    return trace_path if os.path.exists(trace_path) else None


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='运行App冷启动实验')
    parser.add_argument('package_name', help='应用包名')
    parser.add_argument('--activity', help='主Activity名称(可选)')
    parser.add_argument('--experiment-name', default='ColdStart', help='实验名称')
    parser.add_argument('--duration', type=int, default=30, help='追踪时长(秒)')
    parser.add_argument('--config', default='/data/misc/perfetto-configs/HardwareInfo.pbtx',
                       help='Perfetto配置文件路径')
    
    args = parser.parse_args()
    
    trace_file = run_cold_start_experiment(
        package_name=args.package_name,
        activity_name=args.activity,
        experiment_name=args.experiment_name,
        trace_duration=args.duration,
        config_file=args.config
    )
    
    if trace_file:
        print(f"\n📁 Trace文件路径: {trace_file}")
        print("\n💡 下一步: 运行分析脚本分析数据")
        print(f"   python experiments/cold_start/analyze_trace.py {trace_file} {args.package_name}")
