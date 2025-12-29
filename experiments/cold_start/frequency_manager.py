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
        adb_shell
    )
    _CPU_MODULE_AVAILABLE = True
except ImportError as e:
    print(f"⚠️  无法导入CPU频率管理模块: {e}")
    _CPU_MODULE_AVAILABLE = False

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
