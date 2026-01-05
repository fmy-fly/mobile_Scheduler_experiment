"""
频率管理模块
用于设置和恢复CPU、GPU频率
注意：现在使用experiments.cpu和experiments.gpu模块
"""
import os
import sys

# 添加项目根目录到路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

try:
    # 导入CPU模块
    from experiments.cpu.set_cpu_max_freq import (
        set_all_policies_to_max as cpu_set_all_policies_to_max,
        restore_all_policies_frequency as cpu_restore_all_policies_frequency,
        list_cpu_domains,
        adb_shell as cpu_adb_shell
    )
    _CPU_MODULE_AVAILABLE = True
    # 为了兼容，同时导出adb_shell
    adb_shell = cpu_adb_shell
except ImportError as e:
    print(f"⚠️  无法导入CPU频率管理模块: {e}")
    _CPU_MODULE_AVAILABLE = False
    adb_shell = None

try:
    # 导入GPU模块
    from experiments.gpu.set_gpu_max_freq import (
        set_gpu_to_max as gpu_set_gpu_to_max,
        restore_gpu_frequency as gpu_restore_gpu_frequency,
        get_gpu_info
    )
    _GPU_MODULE_AVAILABLE = True
except ImportError as e:
    print(f"⚠️  无法导入GPU频率管理模块: {e}")
    _GPU_MODULE_AVAILABLE = False


def set_all_frequencies_to_max():
    """
    设置所有CPU和GPU到最大频率
    
    Returns:
        dict: 包含原始频率设置，用于恢复
    """
    original_settings = {
        'cpu_freqs': None,  # CPU设置现在由experiments.cpu模块管理
        'gpu_freq': None
    }
    
    # 设置CPU（使用experiments.cpu模块）
    if _CPU_MODULE_AVAILABLE:
        try:
            original_settings['cpu_freqs'] = cpu_set_all_policies_to_max()
        except Exception as e:
            print(f"⚠️  设置CPU频率失败: {e}")
            original_settings['cpu_freqs'] = None
    else:
        print("⚠️  CPU频率管理模块不可用，跳过CPU频率设置")
    
    # 设置GPU（使用experiments.gpu模块）
    if _GPU_MODULE_AVAILABLE:
        try:
            original_settings['gpu_freq'] = gpu_set_gpu_to_max(save_original=True)
        except Exception as e:
            print(f"⚠️  设置GPU频率失败: {e}")
            original_settings['gpu_freq'] = None
    else:
        print("⚠️  GPU频率管理模块不可用，跳过GPU频率设置")
    
    print("\n✅ 所有频率已设置为最大")
    return original_settings


def restore_all_frequencies(original_settings=None):
    """
    恢复所有频率设置
    
    Args:
        original_settings: 保留参数以兼容旧代码，但不再使用（现在直接从设备读取可用频率）
    """
    # 恢复CPU频率（使用experiments.cpu模块）
    if _CPU_MODULE_AVAILABLE:
        try:
            cpu_restore_all_policies_frequency()
        except Exception as e:
            print(f"⚠️  恢复CPU频率失败: {e}")
    else:
        print("⚠️  CPU频率管理模块不可用，跳过CPU频率恢复")
    
    # 恢复GPU频率（使用experiments.gpu模块）
    if _GPU_MODULE_AVAILABLE:
        try:
            gpu_restore_gpu_frequency()
        except Exception as e:
            print(f"⚠️  恢复GPU频率失败: {e}")
    else:
        print("⚠️  GPU频率管理模块不可用，跳过GPU频率恢复")
    
    print("✅ 频率设置已恢复")


def get_available_cpu_frequencies(cpu_id):
    """
    获取指定CPU的可用频率列表（KHz）
    
    Args:
        cpu_id: CPU核心ID
        
    Returns:
        list: 可用频率列表（KHz），如果失败返回None
    """
    if not _CPU_MODULE_AVAILABLE:
        print(f"⚠️  CPU频率管理模块不可用")
        return None
    
    try:
        # 获取所有CPU policy域
        domains = list_cpu_domains()
        
        # 找到包含指定CPU的policy域
        for domain in domains:
            if domain.get("policy") == "N/A":
                continue
            
            # 获取该policy域关联的CPU列表
            cpus_str = domain.get("cpus", "")
            if cpus_str == "unknown":
                continue
            
            cpus = [int(c.strip()) for c in cpus_str.split() if c.strip().isdigit()]
            
            # 如果该policy域包含指定的CPU
            if cpu_id in cpus:
                policy_id = domain.get("policy")
                policy_path = domain.get("path")
                
                # 读取可用频率列表
                try:
                    freqs_str = adb_shell(f"cat {policy_path}/scaling_available_frequencies 2>/dev/null", need_root=True).strip()
                    if freqs_str:
                        freqs = [int(f) for f in freqs_str.split() if f.isdigit()]
                        if freqs:
                            return freqs
                except:
                    pass
                
                # 如果scaling_available_frequencies不可用，尝试使用cpuinfo_min_freq和cpuinfo_max_freq的范围
                try:
                    min_freq_str = domain.get("min_freq", "")
                    max_freq_str = domain.get("max_freq", "")
                    if min_freq_str.isdigit() and max_freq_str.isdigit():
                        # 返回最小和最大频率（虽然这不是完整的列表，但至少提供了范围）
                        return [int(min_freq_str), int(max_freq_str)]
                except:
                    pass
        
        print(f"⚠️  无法找到CPU {cpu_id}的频率信息")
        return None
    except Exception as e:
        print(f"⚠️  获取CPU {cpu_id}可用频率失败: {e}")
        return None


def get_available_gpu_frequencies():
    """
    获取GPU的可用频率列表（Hz）
    
    Returns:
        list: 可用频率列表（Hz），如果失败返回None
    """
    if not _GPU_MODULE_AVAILABLE:
        print("⚠️  GPU频率管理模块不可用")
        return None
    
    try:
        info = get_gpu_info()
        if info and 'available_freqs_hz' in info:
            return info['available_freqs_hz']
        else:
            print("⚠️  无法获取GPU可用频率列表")
            return None
    except Exception as e:
        print(f"⚠️  获取GPU可用频率失败: {e}")
        return None


def set_cpu_frequencies(cpu_freq_settings):
    """
    设置自定义CPU频率
    
    Args:
        cpu_freq_settings: dict，格式为 {policy_id: freq_khz} 或 {policy_id: {'min': min_khz, 'max': max_khz}}
                          例如: {'0': 1800000, '4': {'min': 1200000, 'max': 2300000}}
    
    Returns:
        dict: 原始频率设置，用于恢复
    """
    if not _CPU_MODULE_AVAILABLE or adb_shell is None:
        print("⚠️  CPU频率管理模块不可用")
        return None
    
    original_settings = {}
    
    try:
        for policy_id, freq_setting in cpu_freq_settings.items():
            policy_path = f"/sys/devices/system/cpu/cpufreq/policy{policy_id}"
            
            # 保存原始设置
            try:
                original_min = adb_shell(f"cat {policy_path}/scaling_min_freq", need_root=True).strip()
                original_max = adb_shell(f"cat {policy_path}/scaling_max_freq", need_root=True).strip()
                original_settings[policy_id] = {
                    'min_freq_khz': int(original_min),
                    'max_freq_khz': int(original_max)
                }
            except:
                pass
            
            # 解析频率设置
            if isinstance(freq_setting, dict):
                min_freq = freq_setting.get('min', freq_setting.get('min_freq'))
                max_freq = freq_setting.get('max', freq_setting.get('max_freq'))
            elif isinstance(freq_setting, (int, float)):
                # 单个值表示同时设置min和max
                min_freq = max_freq = int(freq_setting)
            else:
                print(f"⚠️  policy{policy_id}: 无效的频率设置格式")
                continue
            
            # 设置频率
            min_path = f"{policy_path}/scaling_min_freq"
            max_path = f"{policy_path}/scaling_max_freq"
            
            adb_shell(f"sh -c 'echo {min_freq} > {min_path}'", need_root=True)
            adb_shell(f"sh -c 'echo {max_freq} > {max_path}'", need_root=True)
            
            if min_freq == max_freq:
                print(f"✅ policy{policy_id}: {min_freq} KHz ({min_freq/1000:.0f} MHz)")
            else:
                print(f"✅ policy{policy_id}: {min_freq}-{max_freq} KHz ({min_freq/1000:.0f}-{max_freq/1000:.0f} MHz)")
        
        return original_settings if original_settings else None
    except Exception as e:
        print(f"⚠️  设置CPU频率失败: {e}")
        return original_settings if original_settings else None


def set_gpu_frequency(gpu_freq_setting):
    """
    设置自定义GPU频率
    
    Args:
        gpu_freq_setting: int/float (Hz) 或 dict {'min': min_hz, 'max': max_hz}
                         例如: 150000000 或 {'min': 100000000, 'max': 850000000}
    
    Returns:
        dict: 原始频率设置，用于恢复
    """
    if not _GPU_MODULE_AVAILABLE:
        print("⚠️  GPU频率管理模块不可用")
        return None
    
    try:
        # 从GPU模块导入adb_shell（如果CPU模块不可用）
        if adb_shell is None:
            from experiments.gpu.set_gpu_max_freq import adb_shell as gpu_adb_shell
            adb_shell_func = gpu_adb_shell
        else:
            adb_shell_func = adb_shell
        
        GPU_PATH = "/sys/devices/genpd:0:1f000000.mali/consumer:platform:1f000000.mali/consumer"
        
        # 保存原始设置
        try:
            original_min = adb_shell_func(f"cat {GPU_PATH}/scaling_min_freq", need_root=True).strip()
            original_max = adb_shell_func(f"cat {GPU_PATH}/scaling_max_freq", need_root=True).strip()
            original_settings = {
                'min_freq_hz': int(original_min),
                'max_freq_hz': int(original_max)
            }
        except:
            original_settings = None
        
        # 解析频率设置
        if isinstance(gpu_freq_setting, dict):
            min_freq = int(gpu_freq_setting.get('min', gpu_freq_setting.get('min_freq', 0)))
            max_freq = int(gpu_freq_setting.get('max', gpu_freq_setting.get('max_freq', 0)))
        elif isinstance(gpu_freq_setting, (int, float)):
            # 单个值表示同时设置min和max
            min_freq = max_freq = int(gpu_freq_setting)
        else:
            print(f"⚠️  GPU: 无效的频率设置格式")
            return None
        
        # 设置频率
        min_path = f"{GPU_PATH}/scaling_min_freq"
        max_path = f"{GPU_PATH}/scaling_max_freq"
        
        adb_shell_func(f"sh -c 'echo {min_freq} > {min_path}'", need_root=True)
        adb_shell_func(f"sh -c 'echo {max_freq} > {max_path}'", need_root=True)
        
        if min_freq == max_freq:
            print(f"✅ GPU: {min_freq} Hz ({min_freq/1e6:.0f} MHz)")
        else:
            print(f"✅ GPU: {min_freq}-{max_freq} Hz ({min_freq/1e6:.0f}-{max_freq/1e6:.0f} MHz)")
        
        return original_settings
    except Exception as e:
        print(f"⚠️  设置GPU频率失败: {e}")
        return None


def set_custom_frequencies(cpu_freq_settings=None, gpu_freq_setting=None):
    """
    设置自定义CPU和GPU频率
    
    Args:
        cpu_freq_settings: dict，格式为 {policy_id: freq_khz} 或 {policy_id: {'min': min_khz, 'max': max_khz}}
        gpu_freq_setting: int/float (Hz) 或 dict {'min': min_hz, 'max': max_hz}
    
    Returns:
        dict: 原始频率设置，用于恢复
    """
    original_settings = {
        'cpu_freqs': None,
        'gpu_freq': None
    }
    
    if cpu_freq_settings:
        # 检查是否是时间段配置
        if isinstance(cpu_freq_settings, dict) and cpu_freq_settings.get("time_based"):
            # 时间段配置在启动过程中动态设置，这里只保存原始设置
            original_settings['cpu_freqs'] = {}
            original_settings['gpu_freq'] = None
        else:
            original_settings['cpu_freqs'] = set_cpu_frequencies(cpu_freq_settings)
    
    if gpu_freq_setting and not (cpu_freq_settings and cpu_freq_settings.get("time_based")):
        original_settings['gpu_freq'] = set_gpu_frequency(gpu_freq_setting)
    
    print("\n✅ 自定义频率设置完成")
    return original_settings


def set_time_based_frequencies(periods, app_start_time_ns, current_time_ns):
    """
    根据时间段配置设置频率（在App启动过程中动态调用）
    
    Args:
        periods: 时间段配置列表，每个元素包含 start, end, cpu_freq, gpu_freq
        app_start_time_ns: App启动时间戳（纳秒）
        current_time_ns: 当前时间戳（纳秒）
    
    Returns:
        bool: 是否成功设置频率
    """
    if not periods:
        return False
    
    # 计算当前时间相对于App启动的秒数
    elapsed_s = (current_time_ns - app_start_time_ns) / 1e9
    
    # 找到当前应该使用的频率配置
    for period in periods:
        start_s = period.get('start', 0)
        end_s = period.get('end', float('inf'))
        
        if start_s <= elapsed_s < end_s:
            # 找到匹配的时间段，设置频率
            cpu_freq = period.get('cpu_freq')
            gpu_freq = period.get('gpu_freq')
            
            if cpu_freq:
                set_cpu_frequencies(cpu_freq)
            if gpu_freq:
                set_gpu_frequency(gpu_freq)
            
            return True
    
    return False
