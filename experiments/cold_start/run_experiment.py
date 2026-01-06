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
from experiments.cold_start.frequency_manager import (
    set_all_frequencies_to_max, 
    restore_all_frequencies,
    set_custom_frequencies,
    set_cpu_frequencies,
    set_gpu_frequency
)


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
                              config_file="/data/misc/perfetto-configs/HardwareInfo.pbtx",
                              max_frequency=False,
                              cpu_freq_settings=None,
                              gpu_freq_setting=None):
    """
    运行冷启动实验
    
    Args:
        package_name: 应用包名
        activity_name: 主Activity名称(可选)
        experiment_name: 实验名称
        trace_duration: 追踪时长(秒)
        config_file: perfetto配置文件路径
        max_frequency: 是否设置CPU/GPU到最大频率（默认False，使用系统默认调度）
        cpu_freq_settings: 自定义CPU频率设置，dict格式 {policy_id: freq_khz} 或 {policy_id: {'min': min_khz, 'max': max_khz}}
        gpu_freq_setting: 自定义GPU频率设置，int/float (Hz) 或 dict {'min': min_hz, 'max': max_hz}
    
    Returns:
        trace文件路径，如果失败返回None
    """
    print("=" * 60)
    print(f"🚀 开始冷启动实验: {experiment_name}")
    print(f"📦 应用包名: {package_name}")
    
    # 检查是否是时间段频率配置
    is_time_based_freq = False
    freq_periods = None
    if cpu_freq_settings and isinstance(cpu_freq_settings, dict) and cpu_freq_settings.get("time_based"):
        is_time_based_freq = True
        freq_periods = cpu_freq_settings.get("periods", [])
    
    # 确定频率模式
    if is_time_based_freq:
        freq_mode = "时间段频率"
    elif cpu_freq_settings or gpu_freq_setting:
        freq_mode = "自定义频率"
    elif max_frequency:
        freq_mode = "最大频率"
    else:
        freq_mode = "默认调度"
    print(f"⚙️  频率模式: {freq_mode}")
    print("=" * 60)
    
    original_freq_settings = None
    
    # 0. 设置频率
    if is_time_based_freq:
        # 时间段配置，设置初始频率（第一个时间段的频率）
        if freq_periods and len(freq_periods) > 0:
            first_period = freq_periods[0]
            initial_cpu_freq = first_period.get('cpu_freq')
            initial_gpu_freq = first_period.get('gpu_freq')
            print(f"\n[0/6] 设置初始频率（时间段0-{first_period.get('end', 0)}s）...")
            try:
                original_freq_settings = set_custom_frequencies(
                    cpu_freq_settings=initial_cpu_freq,
                    gpu_freq_setting=initial_gpu_freq
                )
                time.sleep(2)  # 等待频率设置生效
            except Exception as e:
                print(f"⚠️  设置初始频率失败: {e}")
                original_freq_settings = None
    elif cpu_freq_settings or gpu_freq_setting:
        print("\n[0/6] 设置自定义频率...")
        try:
            original_freq_settings = set_custom_frequencies(
                cpu_freq_settings=cpu_freq_settings,
                gpu_freq_setting=gpu_freq_setting
            )
            time.sleep(2)  # 等待频率设置生效
        except Exception as e:
            print(f"⚠️  设置频率失败: {e}，继续使用默认频率")
            original_freq_settings = None
    elif max_frequency:
        print("\n[0/6] 设置CPU/GPU到最大频率...")
        try:
            original_freq_settings = set_all_frequencies_to_max()
            time.sleep(2)  # 等待频率设置生效
        except Exception as e:
            print(f"⚠️  设置频率失败: {e}，继续使用默认频率")
            original_freq_settings = None
    
    try:
        # 1. 强制停止应用(确保冷启动)
        print("\n[1/7] 停止应用(确保冷启动)...")
        force_stop_app(package_name)
        time.sleep(2)
    
        # 2. 启动perfetto追踪(在后台线程)
        print("\n[2/7] 启动Perfetto追踪...")
        
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
        print("\n[3/7] 启动应用...")
        
        # 如果是时间段频率配置，记录启动时间
        app_start_time_ns = None
        if is_time_based_freq:
            import time as time_module
            app_start_time_ns = int(time_module.time() * 1e9)  # 转换为纳秒
        
        if not launch_app(package_name, activity_name):
            stop_perfetto()
            return None
        
        # 4. 等待应用启动完成（如果使用时间段频率配置，在此过程中动态调整频率）
        print(f"\n[4/7] 等待应用启动完成（5秒）...")
        
        if is_time_based_freq and freq_periods:
            # 时间段频率配置：在启动过程中监控时间并动态调整频率
            import time as time_module
            check_interval = 0.05  # 每50ms检查一次
            total_wait_time = 5.0  # 总等待时间5秒
            elapsed_time = 0.0
            last_period_index = -1
            
            while elapsed_time < total_wait_time:
                current_time_ns = int(time_module.time() * 1e9)
                elapsed_s = (current_time_ns - app_start_time_ns) / 1e9
                
                # 检查是否需要切换到下一个时间段
                for idx, period in enumerate(freq_periods):
                    start_s = period.get('start', 0)
                    end_s = period.get('end', float('inf'))
                    
                    if start_s <= elapsed_s < end_s and idx != last_period_index:
                        # 需要切换到这个时间段
                        print(f"   切换到时间段 {idx+1}/{len(freq_periods)}: {start_s:.2f}s - {end_s:.2f}s")
                        try:
                            cpu_freq = period.get('cpu_freq')
                            gpu_freq = period.get('gpu_freq')
                            if cpu_freq:
                                set_cpu_frequencies(cpu_freq)
                            if gpu_freq:
                                set_gpu_frequency(gpu_freq)
                            last_period_index = idx
                        except Exception as e:
                            print(f"   ⚠️  切换频率失败: {e}")
                        break
                
                time.sleep(check_interval)
                elapsed_time += check_interval
        else:
            time.sleep(5)
        
        # 5. 停止perfetto追踪
        print("\n[5/7] 停止Perfetto追踪...")
        stop_perfetto()
        perfetto_thread.join(timeout=5)
        time.sleep(3)  # 等待perfetto完全停止
        
        # 6. 拉取trace文件
        print("\n[6/7] 拉取Trace文件...")
        trace_filename = get_perfetto(experiment_name)  # 获取实际生成的文件名（带时间戳）
        
        # 7. 关闭应用（测试完成后自动关闭）
        print("\n[7/7] 关闭应用...")
        force_stop_app(package_name)
        
        print("\n" + "=" * 60)
        print("✅ 实验完成!")
        print("=" * 60)
    
        # 返回trace文件路径（使用实际生成的文件名）
        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(os.path.dirname(script_dir))  # experiments/cold_start -> experiments -> 项目根目录
        trace_path = os.path.join(project_root, "Perfetto", "trace", "traceRecord", 
                                 f"method{experiment_name}", trace_filename)
        return trace_path if os.path.exists(trace_path) else None
    finally:
        # 恢复频率设置
        # 注意：只有最大频率模式（通过ADB设置）才需要恢复
        # 自定义频率模式（通过eBPF设置）不需要恢复，eBPF程序会自动停止
        if max_frequency and original_freq_settings:
            print("\n[恢复] 恢复CPU/GPU频率设置（ADB方式）...")
            try:
                restore_all_frequencies(original_freq_settings)
            except Exception as e:
                print(f"⚠️  恢复频率设置失败: {e}")
        elif cpu_freq_settings or gpu_freq_setting:
            print("\n[恢复] 使用eBPF方式，频率由eBPF程序自动管理，无需手动恢复")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='运行App冷启动实验')
    parser.add_argument('package_name', help='应用包名')
    parser.add_argument('--activity', help='主Activity名称(可选)')
    parser.add_argument('--experiment-name', default='ColdStart', help='实验名称')
    parser.add_argument('--duration', type=int, default=30, help='追踪时长(秒)')
    parser.add_argument('--config', default='/data/misc/perfetto-configs/HardwareInfo.pbtx',
                       help='Perfetto配置文件路径')
    parser.add_argument('--max-frequency', action='store_true',
                       help='设置CPU/GPU到最大频率（默认使用系统调度）')
    
    args = parser.parse_args()
    
    trace_file = run_cold_start_experiment(
        package_name=args.package_name,
        activity_name=args.activity,
        experiment_name=args.experiment_name,
        trace_duration=args.duration,
        config_file=args.config,
        max_frequency=args.max_frequency
    )
    
    if trace_file:
        print(f"\n📁 Trace文件路径: {trace_file}")
        print("\n💡 下一步: 运行分析脚本分析数据")
        print(f"   python experiments/cold_start/analyze_trace.py {trace_file} {args.package_name}")
