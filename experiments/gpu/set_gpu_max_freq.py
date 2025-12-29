"""
将GPU频率设置为最大值
"""
import subprocess
import sys
import os
import time


def adb_shell(cmd: str, need_root: bool = False) -> str:
    """执行adb shell命令"""
    if need_root:
        full_cmd = f"su -c \"{cmd}\""
    else:
        full_cmd = cmd
    result = subprocess.run(
        ["adb", "shell", full_cmd],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    out = result.stdout.decode("utf-8", "ignore").strip()
    err = result.stderr.decode("utf-8", "ignore").strip()
    if result.returncode != 0:
        print(f"[ERROR] ADB 命令失败: {full_cmd}\n{err}", file=sys.stderr)
        sys.exit(1)
    return out


# GPU路径（固定）
GPU_PATH = "/sys/devices/genpd:0:1f000000.mali/consumer:platform:1f000000.mali/consumer"


def get_gpu_info():
    """
    获取GPU频率信息
    
    Returns:
        dict: 包含GPU频率信息的字典，如果失败返回None
    """
    try:
        info = {}
        
        # 读取cpuinfo_max_freq（如果存在）
        try:
            max_freq = adb_shell(f"cat {GPU_PATH}/cpuinfo_max_freq 2>/dev/null || echo ''", need_root=True).strip()
            if max_freq:
                info['max_freq_hz'] = int(max_freq)
        except:
            pass
        
        # 读取available_frequencies
        try:
            freqs_str = adb_shell(f"cat {GPU_PATH}/available_frequencies", need_root=True).strip()
            if freqs_str:
                freqs = [int(f) for f in freqs_str.split() if f.isdigit()]
                if freqs:
                    info['available_freqs_hz'] = freqs
                    info['min_freq_hz'] = min(freqs)
                    info['max_freq_hz'] = max(freqs)
        except:
            pass
        
        # 读取当前设置的频率
        try:
            current_min = adb_shell(f"cat {GPU_PATH}/scaling_min_freq", need_root=True).strip()
            if current_min:
                info['current_min_freq_hz'] = int(current_min)
        except:
            pass
        
        try:
            current_max = adb_shell(f"cat {GPU_PATH}/scaling_max_freq", need_root=True).strip()
            if current_max:
                info['current_max_freq_hz'] = int(current_max)
        except:
            pass
        
        return info if info else None
    except Exception as e:
        print(f"⚠️  获取GPU信息失败: {e}")
        return None


def print_gpu_info():
    """打印GPU频率信息"""
    info = get_gpu_info()
    if not info:
        print("⚠️  无法获取GPU频率信息")
        return
    
    print("=== GPU 频率信息 ===")
    if 'min_freq_hz' in info and 'max_freq_hz' in info:
        print(f"频率范围: {info['min_freq_hz']} - {info['max_freq_hz']} Hz "
              f"({info['min_freq_hz']/1e6:.1f} - {info['max_freq_hz']/1e6:.1f} MHz)")
    if 'current_min_freq_hz' in info and 'current_max_freq_hz' in info:
        print(f"当前设置: {info['current_min_freq_hz']} - {info['current_max_freq_hz']} Hz "
              f"({info['current_min_freq_hz']/1e6:.1f} - {info['current_max_freq_hz']/1e6:.1f} MHz)")
    if 'available_freqs_hz' in info:
        print(f"可用频率数量: {len(info['available_freqs_hz'])}")
    print()


def get_gpu_original_settings():
    """
    获取GPU的原始频率设置（从available_frequencies读取默认范围）
    
    Returns:
        dict: 包含min_freq和max_freq的字典
    """
    info = get_gpu_info()
    if not info or 'min_freq_hz' not in info or 'max_freq_hz' not in info:
        print("⚠️  无法获取GPU原始频率设置")
        return None
    
    return {
        'gpu_path': GPU_PATH,
        'min_freq_hz': info['min_freq_hz'],
        'max_freq_hz': info['max_freq_hz']
    }


def set_gpu_to_max(save_original=True):
    """
    设置GPU到最大频率
    
    Args:
        save_original: 是否保存原始设置（用于恢复）
    
    Returns:
        dict: 原始频率设置，如果save_original=False则返回None
    """
    info = get_gpu_info()
    if not info or 'max_freq_hz' not in info:
        print("⚠️  无法获取GPU最大频率")
        return None
    
    max_freq = info['max_freq_hz']
    
    # 保存原始设置
    original_settings = None
    if save_original:
        original_settings = get_gpu_original_settings()
    
    # 设置最小和最大频率都为最大值
    min_path = f"{GPU_PATH}/scaling_min_freq"
    max_path = f"{GPU_PATH}/scaling_max_freq"
    
    # 使用sh -c来确保重定向正确执行
    adb_shell(f"sh -c 'echo {max_freq} > {min_path}'", need_root=True)
    adb_shell(f"sh -c 'echo {max_freq} > {max_path}'", need_root=True)
    
    print(f"✅ GPU: {max_freq} Hz ({max_freq/1e6:.0f} MHz)")
    return original_settings


def restore_gpu_frequency():
    """
    恢复GPU频率到默认范围（从available_frequencies读取最小值和最大值）
    """
    original = get_gpu_original_settings()
    if not original:
        print("⚠️  无法获取GPU原始频率设置，无法恢复")
        return
    
    min_freq = original['min_freq_hz']
    max_freq = original['max_freq_hz']
    
    min_path = f"{GPU_PATH}/scaling_min_freq"
    max_path = f"{GPU_PATH}/scaling_max_freq"
    
    # 使用sh -c来确保重定向正确执行
    # 恢复最小频率到硬件支持的最小值
    adb_shell(f"sh -c 'echo {min_freq} > {min_path}'", need_root=True)
    # 恢复最大频率到硬件支持的最大值
    adb_shell(f"sh -c 'echo {max_freq} > {max_path}'", need_root=True)
    
    print(f"✅ GPU: 已恢复 (min: {min_freq/1e6:.1f} MHz, max: {max_freq/1e6:.1f} MHz)")


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='将GPU频率设置为最大值')
    parser.add_argument('--info', action='store_true', help='查看GPU频率信息')
    parser.add_argument('--restore', action='store_true', help='恢复GPU频率到默认范围')
    
    args = parser.parse_args()
    
    # 如果指定了--info，只查看信息并退出
    if args.info:
        print_gpu_info()
        return
    
    # 如果指定了--restore，恢复频率
    if args.restore:
        restore_gpu_frequency()
        return
    
    # 默认设置GPU到最大频率
    set_gpu_to_max()


if __name__ == "__main__":
    main()

