"""
频率管理模块
用于设置和恢复CPU、GPU频率
"""
import subprocess
import os
import time


def get_cpu_count():
    """获取CPU核心数量"""
    try:
        result = subprocess.run(
            ["adb", "shell", "su", "-c", "cat /proc/cpuinfo"],
            capture_output=True,
            text=True,
            check=True
        )
        # 简单统计processor数量
        cpu_count = result.stdout.count("processor")
        return max(cpu_count, 4)  # 至少返回4，如果没有检测到
    except Exception as e:
        print(f"⚠️  获取CPU数量失败，使用默认值8: {e}")
        return 8


def get_max_cpu_frequency(cpu_id):
    """获取指定CPU的最大频率（KHz）"""
    try:
        result = subprocess.run(
            ["adb", "shell", "su", "-c", f"cat /sys/devices/system/cpu/cpu{cpu_id}/cpufreq/cpuinfo_max_freq"],
            capture_output=True,
            text=True,
            check=True
        )
        return int(result.stdout.strip())
    except Exception as e:
        print(f"⚠️  获取CPU {cpu_id}最大频率失败: {e}")
        return None


def get_current_cpu_frequencies(cpu_id):
    """
    获取指定CPU的当前scaling_min_freq和scaling_max_freq（KHz）
    
    Returns:
        tuple: (min_freq_khz, max_freq_khz) 或 (None, None) 如果失败
    """
    try:
        min_result = subprocess.run(
            ["adb", "shell", "su", "-c", f"cat /sys/devices/system/cpu/cpu{cpu_id}/cpufreq/scaling_min_freq"],
            capture_output=True,
            text=True,
            check=True
        )
        max_result = subprocess.run(
            ["adb", "shell", "su", "-c", f"cat /sys/devices/system/cpu/cpu{cpu_id}/cpufreq/scaling_max_freq"],
            capture_output=True,
            text=True,
            check=True
        )
        min_freq = int(min_result.stdout.strip())
        max_freq = int(max_result.stdout.strip())
        return (min_freq, max_freq)
    except Exception as e:
        print(f"⚠️  获取CPU {cpu_id}当前频率失败: {e}")
        return (None, None)


def set_cpu_frequency(cpu_id, max_freq_khz):
    """
    设置CPU频率（将最小和最大频率都设置为最大值，锁定到最高频率）
    
    Args:
        cpu_id: CPU核心ID
        max_freq_khz: 最大频率(KHz)，将min和max都设置为这个值
    """
    try:
        # 将最小频率设置为最大值
        subprocess.run(
            ["adb", "shell", "su", "-c", f"echo {max_freq_khz} > /sys/devices/system/cpu/cpu{cpu_id}/cpufreq/scaling_min_freq"],
            check=False,
            capture_output=True
        )
        # 将最大频率设置为最大值
        subprocess.run(
            ["adb", "shell", "su", "-c", f"echo {max_freq_khz} > /sys/devices/system/cpu/cpu{cpu_id}/cpufreq/scaling_max_freq"],
            check=False,
            capture_output=True
        )
        return True
    except Exception as e:
        print(f"⚠️  设置CPU {cpu_id}频率失败: {e}")
        return False


def set_all_cpu_to_max():
    """
    设置所有CPU核心到最大频率
    
    Returns:
        dict: 每个CPU的原始频率(min, max)，格式为 {cpu_id: (min_freq, max_freq)}，用于恢复
    """
    cpu_count = get_cpu_count()
    original_freqs = {}
    
    print(f"\n🔧 设置所有CPU核心到最大频率（共{cpu_count}个核心）...")
    
    for cpu_id in range(cpu_count):
        # 获取原始最大频率（硬件支持的最大值）
        original_max = get_max_cpu_frequency(cpu_id)
        if original_max:
            # 保存当前设置的min和max频率（用于恢复）
            original_min, original_max_current = get_current_cpu_frequencies(cpu_id)
            if original_min is not None and original_max_current is not None:
                original_freqs[cpu_id] = (original_min, original_max_current)
            else:
                # 如果获取失败，使用硬件最大值作为备份
                original_freqs[cpu_id] = (original_max, original_max)
            
            # 将最小和最大频率都设置为最大值（锁定到最高频率）
            if set_cpu_frequency(cpu_id, original_max):
                print(f"  ✅ CPU {cpu_id}: {original_max} KHz ({original_max/1000:.0f} MHz)")
            else:
                print(f"  ⚠️  CPU {cpu_id}: 设置失败")
        else:
            print(f"  ⚠️  CPU {cpu_id}: 无法获取最大频率")
    
    time.sleep(1)  # 等待频率设置生效
    return original_freqs


def restore_cpu_frequency(cpu_id, original_freqs):
    """
    恢复CPU频率设置（将min和max恢复到原始值）
    
    Args:
        cpu_id: CPU核心ID
        original_freqs: 原始频率元组 (min_freq_khz, max_freq_khz)
    
    Returns:
        bool: 是否恢复成功
    """
    if original_freqs is None or len(original_freqs) != 2:
        return False
    
    original_min, original_max = original_freqs
    if original_min is None or original_max is None:
        return False
    
    try:
        # 恢复最小频率
        subprocess.run(
            ["adb", "shell", "su", "-c", f"echo {original_min} > /sys/devices/system/cpu/cpu{cpu_id}/cpufreq/scaling_min_freq"],
            check=False,
            capture_output=True
        )
        # 恢复最大频率
        subprocess.run(
            ["adb", "shell", "su", "-c", f"echo {original_max} > /sys/devices/system/cpu/cpu{cpu_id}/cpufreq/scaling_max_freq"],
            check=False,
            capture_output=True
        )
        return True
    except Exception as e:
        print(f"⚠️  恢复CPU {cpu_id}频率失败: {e}")
        return False


def restore_all_cpu_frequency(original_freqs):
    """
    恢复所有CPU频率设置
    
    Args:
        original_freqs: dict，格式为 {cpu_id: (min_freq, max_freq)}
    """
    if not original_freqs:
        return
    
    cpu_count = get_cpu_count()
    print(f"\n🔧 恢复所有CPU核心频率设置（共{cpu_count}个核心）...")
    
    for cpu_id in range(cpu_count):
        if cpu_id in original_freqs:
            if restore_cpu_frequency(cpu_id, original_freqs[cpu_id]):
                min_freq, max_freq = original_freqs[cpu_id]
                print(f"  ✅ CPU {cpu_id}: 已恢复 (min: {min_freq/1000:.0f} MHz, max: {max_freq/1000:.0f} MHz)")
            else:
                print(f"  ⚠️  CPU {cpu_id}: 恢复失败")
        else:
            print(f"  ⚠️  CPU {cpu_id}: 没有原始频率数据")


def find_gpu_devfreq_path():
    """查找GPU devfreq设备路径"""
    # 方法1: 直接尝试已知的常见路径（最快）
    known_paths = [
        "/sys/devices/genpd:0:1f000000.mali/consumer:platform:1f000000.mali/consumer",
    ]
    
    for gpu_path in known_paths:
        try:
            check_result = subprocess.run(
                ["adb", "shell", "su", "-c", f"test -f {gpu_path}/available_frequencies"],
                check=False
            )
            if check_result.returncode == 0:
                return gpu_path
        except:
            continue
    
    

    
    return None


def get_gpu_max_frequency():
    """获取GPU最大频率（Hz）"""
    gpu_path = find_gpu_devfreq_path()
    
    if gpu_path is None:
        return None
    
    # 读取available_frequencies，取最大值
    try:
        result = subprocess.run(
            ["adb", "shell", "su", "-c", f"cat {gpu_path}/available_frequencies"],
            capture_output=True,
            text=True,
            check=True
        )
        freqs = result.stdout.strip().split()
        if freqs:
            # 转换为整数并返回最大值
            freq_ints = [int(f) for f in freqs if f.isdigit()]
            if freq_ints:
                return max(freq_ints)
    except:
        pass
    
    return None


def get_current_gpu_frequencies():
    """
    获取GPU的当前scaling_min_freq和scaling_max_freq（Hz）
    
    Returns:
        tuple: (min_freq_hz, max_freq_hz, gpu_path) 或 (None, None, None) 如果失败
    """
    gpu_path = find_gpu_devfreq_path()
    if gpu_path is None:
        return (None, None, None)
    
    try:
        min_result = subprocess.run(
            ["adb", "shell", "su", "-c", f"cat {gpu_path}/scaling_min_freq"],
            capture_output=True,
            text=True,
            check=True
        )
        max_result = subprocess.run(
            ["adb", "shell", "su", "-c", f"cat {gpu_path}/scaling_max_freq"],
            capture_output=True,
            text=True,
            check=True
        )
        min_freq = int(min_result.stdout.strip())
        max_freq = int(max_result.stdout.strip())
        return (min_freq, max_freq, gpu_path)
    except Exception as e:
        print(f"⚠️  获取GPU当前频率失败: {e}")
        return (None, None, None)


def set_gpu_to_max():
    """
    设置GPU到最大频率（将最小和最大频率都设置为最大值，锁定到最高频率）
    
    Returns:
        dict: 包含原始频率和GPU路径，格式为 {'min_freq': int, 'max_freq': int, 'gpu_path': str}，用于恢复
    """
    print("\n🔧 设置GPU到最大频率...")
    
    gpu_path = find_gpu_devfreq_path()
    if gpu_path is None:
        print("  ⚠️  无法找到GPU devfreq设备路径")
        print("  💡 调试信息：尝试手动查找GPU路径")
        print("     运行命令: adb shell find /sys/devices -name available_frequencies -path '*consumer*'")
        print("     或者: adb shell find /sys/devices -path '*consumer:platform:*mali*consumer' -type d")
        return None
    
    max_freq = get_gpu_max_frequency()
    if max_freq is None:
        print("  ⚠️  无法获取GPU最大频率")
        return None
    
    # 保存当前设置的min和max频率（用于恢复）
    original_min, original_max, _ = get_current_gpu_frequencies()
    if original_min is None or original_max is None:
        print(f"  ⚠️  无法读取GPU当前频率，将使用max_freq作为恢复值")
        print(f"     max_freq = {max_freq} Hz ({max_freq/1e6:.1f} MHz)")
        original_min = max_freq
        original_max = max_freq
    else:
        print(f"  📝 保存GPU原始频率: min={original_min} Hz ({original_min/1e6:.1f} MHz), max={original_max} Hz ({original_max/1e6:.1f} MHz)")
    original_settings = {
        'min_freq': original_min,
        'max_freq': original_max,
        'gpu_path': gpu_path
    }
    
    # 将最小和最大频率都设置为最大值（锁定到最高频率）
    try:
        # 使用完整路径（与CPU命令保持一致，用引号包围路径避免特殊字符问题）
        # 设置最小频率
        subprocess.run(
            ["adb", "shell", "su", "-c", f"echo {max_freq} > '{gpu_path}/scaling_min_freq'"],
            check=False,
            capture_output=True
        )
        # 设置最大频率
        subprocess.run(
            ["adb", "shell", "su", "-c", f"echo {max_freq} > '{gpu_path}/scaling_max_freq'"],
            check=False,
            capture_output=True
        )
        print(f"  ✅ GPU: {max_freq} Hz ({max_freq/1e6:.0f} MHz)")
        time.sleep(0.5)
        return original_settings
    except Exception as e:
        print(f"  ⚠️  设置GPU频率失败: {e}")
        return None


def set_all_frequencies_to_max():
    """
    设置所有CPU和GPU到最大频率
    
    Returns:
        dict: 包含原始频率设置，用于恢复
    """
    original_settings = {
        'cpu_freqs': {},
        'gpu_freq': None
    }
    
    # 设置CPU
    original_settings['cpu_freqs'] = set_all_cpu_to_max()
    
    # 设置GPU
    original_settings['gpu_freq'] = set_gpu_to_max()
    
    print("\n✅ 所有频率已设置为最大")
    return original_settings


def restore_gpu_frequency(original_settings):
    """
    恢复GPU频率设置（将min和max恢复到原始值）
    
    Args:
        original_settings: dict，格式为 {'min_freq': int, 'max_freq': int, 'gpu_path': str}
    """
    if not original_settings:
        return
    
    gpu_path = original_settings.get('gpu_path')
    original_min = original_settings.get('min_freq')
    original_max = original_settings.get('max_freq')
    
    if gpu_path is None or original_min is None or original_max is None:
        print("  ⚠️  GPU: 无法恢复，缺少原始频率数据")
        return
    
    try:
        # 使用完整路径（与CPU命令保持一致，用引号包围路径避免特殊字符问题）
        # 恢复最小频率
        subprocess.run(
            ["adb", "shell", "su", "-c", f"echo {original_min} > '{gpu_path}/scaling_min_freq'"],
            check=False,
            capture_output=True
        )
        # 恢复最大频率
        subprocess.run(
            ["adb", "shell", "su", "-c", f"echo {original_max} > '{gpu_path}/scaling_max_freq'"],
            check=False,
            capture_output=True
        )
        # GPU频率单位是Hz，直接显示原始值（Hz），不转换为MHz
        # 因为GPU频率文件的单位就是Hz，比如150000表示150MHz
        print(f"  ✅ GPU: 已恢复 (min: {original_min} Hz, max: {original_max} Hz)")
   
    except Exception as e:
        print(f"  ⚠️  GPU: 恢复失败: {e}")


def restore_all_frequencies(original_settings):
    """恢复所有频率设置"""
    if not original_settings:
        return
    
    restore_all_cpu_frequency(original_settings.get('cpu_freqs', {}))
    
    # 恢复GPU频率
    gpu_settings = original_settings.get('gpu_freq')
    if gpu_settings:
        print("\n🔧 恢复GPU频率设置...")
        restore_gpu_frequency(gpu_settings)
    
    print("✅ 频率设置已恢复")

