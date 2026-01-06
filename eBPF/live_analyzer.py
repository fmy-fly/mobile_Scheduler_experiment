import sys
import json
import os
import time
import threading

# 音频超时 (1.5s)
AUDIO_TIMEOUT = 1.5 

def set_cpu_mode(mode):
    def _run():
        # pass # 填写真实 echo 命令
        # print(f"Execute: {mode}") 
        pass 
    threading.Thread(target=_run).start()

class StateMachine:
    def __init__(self):
        self.foreground_app = "System"
        self.pid_map = {} 
        self.last_input_time = time.time()
        self.input_count = 0
        
        self.is_audio_active = False 
        self.last_audio_signal_ts = 0
        
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
        if pid in self.pid_map: return self.pid_map[pid]
        try:
            path = f"/proc/{pid}/cmdline"
            if not os.path.exists(path): return None
            with open(path, "rb") as f:
                content = f.read().replace(b'\x00', b'').decode('utf-8').strip()
                if content:
                    name = content.split('.')[-1] if '.' in content else content
                    if name in ["zygote64", "zygote", "<pre-initialized>"]: return name
                    self.pid_map[pid] = name
                    return name
        except: pass
        return None

    def handle_cold_start_async(self, pid, temp_name):
        def _wait_and_print():
            time.sleep(0.2)
            final_name = temp_name
            try:
                path = f"/proc/{pid}/cmdline"
                if os.path.exists(path):
                    with open(path, "rb") as f:
                        c = f.read().replace(b'\x00', b'').decode('utf-8').strip()
                        if c: final_name = c.split('.')[-1]
            except: pass
            self.pid_map[pid] = final_name
            print(f"[冷启动] 新进程创建: {final_name}", flush=True)
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
            if not line.startswith("{"): return
            
            try:
                entry = json.loads(line)
            except: return 

            if "B|" not in entry['log']: return
            
            content = entry['log'].split('|', 2)[2]
            pid = entry['pid']
            
            # ==========================================
            # 🔥 新增：输入法监测逻辑
            # ==========================================
            # showSoftInput: 键盘弹出
            # hideSoftInput: 键盘收起
            if "showSoftInput" in content:
                print(f"[输入法] 键盘弹出", flush=True)
                set_cpu_mode("boost") # 键盘弹出是重负载，拉频！
                return # 既然是键盘事件，就不用走下面的触摸逻辑了

            if "hideSoftInput" in content:
                print(f"[输入法] 键盘收起", flush=True)
                return

            # ==========================================
            # 原有逻辑
            # ==========================================

            # --- 极速 UI 响应 ---
            if "activityStart" in content: set_cpu_mode("boost")
            if "dispatchInputEvent" in content:
                if time.time() - self.last_input_time > 0.5: set_cpu_mode("boost")
                self.last_input_time = time.time()

            # --- 获取进程名 ---
            pid_name = self.get_process_name(pid)
            is_ui = pid_name and pid_name not in ["system_server", "surfaceflinger", "audioserver"]

            # --- 触摸与滑动 ---
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

            # --- 冷启动 ---
            if "bindApplication" in content:
                if is_ui:
                    if pid_name in ["<pre-initialized>", "zygote64", "zygote"]:
                        self.handle_cold_start_async(pid, pid_name)
                    else:
                        print(f"[冷启动] 新进程创建: {pid_name}", flush=True)
                    self.foreground_app = pid_name if pid_name not in ["<pre-initialized>"] else self.foreground_app
                return

            # --- 页面切换 ---
            if any(k in content for k in ["activityStart", "activityResume"]):
                if is_ui and pid_name != self.foreground_app:
                    print(f"[页面切换] {self.foreground_app} -> {pid_name}", flush=True)
                    self.foreground_app = pid_name

        except Exception: pass

def main():
    print(f"Start", flush=True)
    sm = StateMachine()
    for line in sys.stdin:
        sm.process(line.strip())

if __name__ == "__main__":
    main()