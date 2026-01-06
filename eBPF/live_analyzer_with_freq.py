"""
eBPF实时分析器 - 支持本地频率设置
在设备本地运行，检测app启动事件并立即设置频率，避免WiFi延迟
"""
import sys
import json
import os
import time
import threading
import subprocess

# 导入频率配置
try:
    from freq_config import APPS, APP_FREQ_CONFIGS
except ImportError:
    # 如果导入失败，使用空配置
    APPS = {}
    APP_FREQ_CONFIGS = {}

# 音频超时 (1.5s)
AUDIO_TIMEOUT = 1.5

# GPU路径
GPU_PATH = "/sys/devices/genpd:0:1f000000.mali/consumer:platform:1f000000.mali/consumer"


def execute_shell(cmd, need_root=False):
    """
    在设备本地执行shell命令（不使用adb，直接执行）
    
    Args:
        cmd: shell命令
        need_root: 是否需要root权限
    
    Returns:
        命令输出（字符串）
    """
    try:
        if need_root:
            full_cmd = f"su -c \"{cmd}\""
        else:
            full_cmd = cmd
        
        result = subprocess.run(
            full_cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=2.0
        )
        out = result.stdout.decode("utf-8", "ignore").strip()
        if result.returncode != 0:
            err = result.stderr.decode("utf-8", "ignore").strip()
            print(f"[WARN] 命令执行失败: {full_cmd}\n错误: {err}", flush=True)
        return out
    except subprocess.TimeoutExpired:
        print(f"[WARN] 命令执行超时: {cmd}", flush=True)
        return ""
    except Exception as e:
        print(f"[WARN] 命令执行异常: {cmd}, 错误: {e}", flush=True)
        return ""


def set_cpu_frequencies_local(cpu_freq_settings):
    """
    在设备本地设置CPU频率（不使用adb）
    
    Args:
        cpu_freq_settings: dict，格式为 {policy_id: freq_khz} 或 {policy_id: {'min': min_khz, 'max': max_khz}}
    """
    if not cpu_freq_settings:
        return
    
    try:
        for policy_id, freq_setting in cpu_freq_settings.items():
            policy_path = f"/sys/devices/system/cpu/cpufreq/policy{policy_id}"
            
            # 解析频率设置
            if isinstance(freq_setting, dict):
                min_freq = freq_setting.get('min', freq_setting.get('min_freq'))
                max_freq = freq_setting.get('max', freq_setting.get('max_freq'))
            elif isinstance(freq_setting, (int, float)):
                min_freq = max_freq = int(freq_setting)
            else:
                continue
            
            # 设置频率
            min_path = f"{policy_path}/scaling_min_freq"
            max_path = f"{policy_path}/scaling_max_freq"
            
            # 直接执行shell命令，不使用adb
            execute_shell(f"sh -c 'echo {min_freq} > {min_path}'", need_root=True)
            execute_shell(f"sh -c 'echo {max_freq} > {max_path}'", need_root=True)
            
            print(f"[频率] policy{policy_id}: {min_freq} KHz ({min_freq/1000:.0f} MHz)", flush=True)
    except Exception as e:
        print(f"[WARN] 设置CPU频率失败: {e}", flush=True)


def set_gpu_frequency_local(gpu_freq_setting):
    """
    在设备本地设置GPU频率（不使用adb）
    
    Args:
        gpu_freq_setting: int/float (Hz) 或 dict {'min': min_hz, 'max': max_hz}
    """
    if not gpu_freq_setting:
        return
    
    try:
        # 解析频率设置
        if isinstance(gpu_freq_setting, dict):
            min_freq = int(gpu_freq_setting.get('min', gpu_freq_setting.get('min_freq', 0)))
            max_freq = int(gpu_freq_setting.get('max', gpu_freq_setting.get('max_freq', 0)))
        elif isinstance(gpu_freq_setting, (int, float)):
            min_freq = max_freq = int(gpu_freq_setting)
        else:
            return
        
        # 设置频率
        min_path = f"{GPU_PATH}/scaling_min_freq"
        max_path = f"{GPU_PATH}/scaling_max_freq"
        
        execute_shell(f"sh -c 'echo {min_freq} > {min_path}'", need_root=True)
        execute_shell(f"sh -c 'echo {max_freq} > {max_path}'", need_root=True)
        
        print(f"[频率] GPU: {min_freq} Hz ({min_freq/1e6:.0f} MHz)", flush=True)
    except Exception as e:
        print(f"[WARN] 设置GPU频率失败: {e}", flush=True)


def set_cpu_mode(mode):
    """
    设置CPU模式（兼容旧接口）
    
    Args:
        mode: "boost" 或 "normal"
    """
    if mode == "boost":
        # 设置为最大频率
        set_cpu_frequencies_local({
            "0": 1950000,
            "4": 2450000,
            "7": 3015000
        })
    elif mode == "normal":
        # 恢复默认（这里可以设置为中等频率）
        set_cpu_frequencies_local({
            "0": 1328000,
            "4": 1549000,
            "7": 2147000
        })


class FrequencyController:
    """频率控制器 - 管理时间段频率切换"""
    
    def __init__(self, app_package_name):
        """
        初始化频率控制器
        
        Args:
            app_package_name: 应用包名（例如 "com.tencent.mm"）
        """
        self.app_package_name = app_package_name
        self.app_name = None
        self.freq_config = None
        self.start_time = None
        self.monitor_thread = None
        self.is_running = False
        
        # 查找对应的app配置
        for name, package in APPS.items():
            if package == app_package_name:
                self.app_name = name
                break
        
        # 获取频率配置
        if self.app_name and self.app_name in APP_FREQ_CONFIGS:
            self.freq_config = APP_FREQ_CONFIGS[self.app_name]
            print(f"[频率控制] 找到配置: {self.app_name}", flush=True)
        else:
            print(f"[频率控制] 未找到配置: {app_package_name}", flush=True)
    
    def start(self):
        """开始频率控制"""
        if not self.freq_config:
            return
        
        cpu_cfg = self.freq_config.get("cpu_freq_settings")
        if not cpu_cfg or not cpu_cfg.get("time_based"):
            return
        
        periods = cpu_cfg.get("periods", [])
        if not periods:
            return
        
        # 设置初始频率（第一个时间段）
        first_period = periods[0]
        if first_period.get("cpu_freq"):
            set_cpu_frequencies_local(first_period["cpu_freq"])
        if first_period.get("gpu_freq"):
            set_gpu_frequency_local(first_period["gpu_freq"])
        
        # 记录启动时间
        self.start_time = time.time()
        self.is_running = True
        
        # 启动监控线程
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        
        print(f"[频率控制] 已启动，时间段数: {len(periods)}", flush=True)
    
    def _monitor_loop(self):
        """监控循环 - 根据时间段切换频率"""
        if not self.freq_config:
            return
        
        cpu_cfg = self.freq_config.get("cpu_freq_settings")
        periods = cpu_cfg.get("periods", [])
        last_period_index = 0
        
        while self.is_running:
            if not self.start_time:
                time.sleep(0.01)
                continue
            
            elapsed = time.time() - self.start_time
            
            # 检查是否需要切换到下一个时间段
            for idx, period in enumerate(periods):
                start_s = period.get("start", 0)
                end_s = period.get("end", float('inf'))
                
                if start_s <= elapsed < end_s and idx != last_period_index:
                    # 需要切换到这个时间段
                    print(f"[频率切换] 时间段 {idx+1}/{len(periods)}: {start_s:.2f}s - {end_s:.2f}s (当前: {elapsed:.3f}s)", flush=True)
                    
                    if period.get("cpu_freq"):
                        set_cpu_frequencies_local(period["cpu_freq"])
                    if period.get("gpu_freq"):
                        set_gpu_frequency_local(period["gpu_freq"])
                    
                    last_period_index = idx
                    break
            
            # 如果超过最后一个时间段，停止监控
            if elapsed >= periods[-1].get("end", 10.0):
                self.is_running = False
                break
            
            time.sleep(0.01)  # 每10ms检查一次
    
    def stop(self):
        """停止频率控制"""
        self.is_running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=1.0)


class StateMachine:
    def __init__(self):
        self.foreground_app = "System"
        self.pid_map = {}
        self.last_input_time = time.time()
        self.input_count = 0
        
        self.is_audio_active = False
        self.last_audio_signal_ts = 0
        
        # 频率控制器
        self.freq_controller = None
        
        threading.Thread(target=self._audio_watchdog, daemon=True).start()

    def _audio_watchdog(self):
        while True:
            time.sleep(0.5)
            if self.is_audio_active:
                if time.time() - self.last_audio_signal_ts > AUDIO_TIMEOUT:
                    print(f"\033[33m>>> [停止] 音频结束\033[0m", flush=True)
                    set_cpu_mode("normal")
                    self.is_audio_active = False

    def get_process_name(self, pid):
        if pid in self.pid_map:
            return self.pid_map[pid]
        try:
            path = f"/proc/{pid}/cmdline"
            if not os.path.exists(path):
                return None
            with open(path, "rb") as f:
                content = f.read().replace(b'\x00', b'').decode('utf-8').strip()
                if content:
                    name = content.split('.')[-1] if '.' in content else content
                    if name in ["zygote64", "zygote", "<pre-initialized>"]:
                        return name
                    self.pid_map[pid] = name
                    return name
        except:
            pass
        return None
    
    def get_package_name(self, pid):
        """获取完整的包名"""
        try:
            path = f"/proc/{pid}/cmdline"
            if not os.path.exists(path):
                return None
            with open(path, "rb") as f:
                content = f.read().replace(b'\x00', b'').decode('utf-8').strip()
                return content
        except:
            pass
        return None

    def handle_cold_start_async(self, pid, temp_name):
        def _wait_and_print():
            time.sleep(0.2)
            final_name = temp_name
            package_name = None
            try:
                path = f"/proc/{pid}/cmdline"
                if os.path.exists(path):
                    with open(path, "rb") as f:
                        c = f.read().replace(b'\x00', b'').decode('utf-8').strip()
                        if c:
                            final_name = c.split('.')[-1]
                            package_name = c
            except:
                pass
            self.pid_map[pid] = final_name
            print(f"[冷启动] 新进程创建: {final_name}", flush=True)
            
            # 启动频率控制
            if package_name:
                # 停止旧的频率控制器
                if self.freq_controller:
                    self.freq_controller.stop()
                
                # 创建新的频率控制器
                self.freq_controller = FrequencyController(package_name)
                self.freq_controller.start()
        
        threading.Thread(target=_wait_and_print).start()

    def process(self, line):
        try:
            line = line.strip()
            
            # 1. 音频信号 (来自 Module A)
            if line == "sys_event:AUDIO_ACTIVE":
                self.last_audio_signal_ts = time.time()
                if not self.is_audio_active:
                    print(f"\033[36m>>> [播放] 音频活跃\033[0m", flush=True)
                    set_cpu_mode("boost")
                    self.is_audio_active = True
                return

            # 2. UI 日志 (来自 Module B)
            if not line.startswith("{"):
                return
            
            try:
                entry = json.loads(line)
            except:
                return

            if "B|" not in entry['log']:
                return
            
            content = entry['log'].split('|', 2)[2]
            pid = entry['pid']
            
            # 输入法监测
            if "showSoftInput" in content:
                print(f"[输入法] 键盘弹出", flush=True)
                set_cpu_mode("boost")
                return

            if "hideSoftInput" in content:
                print(f"[输入法] 键盘收起", flush=True)
                return

            # 极速 UI 响应
            if "activityStart" in content:
                set_cpu_mode("boost")
                # 尝试从activityStart中提取包名
                # 格式: activityStart: cmp=com.tencent.mm/.ui.LauncherUI
                if "cmp=" in content:
                    try:
                        cmp_part = content.split("cmp=")[1].split()[0]
                        package_name = cmp_part.split("/")[0]
                        if package_name in APPS.values():
                            # 停止旧的频率控制器
                            if self.freq_controller:
                                self.freq_controller.stop()
                            
                            # 创建新的频率控制器
                            self.freq_controller = FrequencyController(package_name)
                            self.freq_controller.start()
                    except:
                        pass
            
            if "dispatchInputEvent" in content:
                if time.time() - self.last_input_time > 0.5:
                    set_cpu_mode("boost")
                self.last_input_time = time.time()

            # 获取进程名
            pid_name = self.get_process_name(pid)
            is_ui = pid_name and pid_name not in ["system_server", "surfaceflinger", "audioserver"]

            # 触摸与滑动
            if "dispatchInputEvent" in content and is_ui:
                self.foreground_app = pid_name
                if time.time() - self.last_input_time < 0.5:
                    self.input_count += 1
                else:
                    self.input_count = 1
                self.last_input_time = time.time()

                if self.input_count == 1:
                    print(f"[触摸] 在 {self.foreground_app} 点击", flush=True)
                elif self.input_count == 3:
                    print(f"[滑动] 正在 {self.foreground_app} (开始滑动)", flush=True)
                elif self.input_count > 3 and self.input_count % 10 == 0:
                    print(f"[滑动] 正在 {self.foreground_app} (持续滑动...)", flush=True)

            # 冷启动
            if "bindApplication" in content:
                if is_ui:
                    if pid_name in ["<pre-initialized>", "zygote64", "zygote"]:
                        self.handle_cold_start_async(pid, pid_name)
                    else:
                        print(f"[冷启动] 新进程创建: {pid_name}", flush=True)
                        # 获取完整包名并启动频率控制
                        package_name = self.get_package_name(pid)
                        if package_name:
                            if self.freq_controller:
                                self.freq_controller.stop()
                            self.freq_controller = FrequencyController(package_name)
                            self.freq_controller.start()
                    self.foreground_app = pid_name if pid_name not in ["<pre-initialized>"] else self.foreground_app
                return

            # 页面切换
            if any(k in content for k in ["activityStart", "activityResume"]):
                if is_ui and pid_name != self.foreground_app:
                    print(f"[页面切换] {self.foreground_app} -> {pid_name}", flush=True)
                    self.foreground_app = pid_name

        except Exception as e:
            pass  # 静默忽略错误


def main():
    print(f"Start - 频率控制模式", flush=True)
    sm = StateMachine()
    # 使用errors='replace'或'ignore'来处理非UTF-8字符
    # 这样可以避免UnicodeDecodeError，即使bpftrace输出包含特殊字符
    for line in sys.stdin.buffer:
        try:
            # 尝试UTF-8解码，失败时使用replace策略
            line_str = line.decode('utf-8', errors='replace').strip()
            sm.process(line_str)
        except Exception as e:
            # 静默忽略解码错误，继续处理下一行
            pass


if __name__ == "__main__":
    main()

