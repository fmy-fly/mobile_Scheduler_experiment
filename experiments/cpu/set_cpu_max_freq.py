from os import name
import subprocess
import re
import sys
import time

def adb_shell(cmd: str, need_root: bool = False) -> str:
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


def restore_governor_ranges(cluster):
    # cluster 是 "0"、"1"、"2"…这样的字符串
    base = f"/sys/devices/system/cpu/cpu{cluster}/cpufreq"
    info_min_path = f"{base}/cpuinfo_min_freq"
    info_max_path = f"{base}/cpuinfo_max_freq"
    min_path      = f"{base}/scaling_min_freq"
    max_path      = f"{base}/scaling_max_freq"

    # 1. 先读默认上下限
    default_min = adb_shell(f"cat {info_min_path}", need_root=True).strip()
    default_max = adb_shell(f"cat {info_max_path}", need_root=True).strip()

    # 2. 写回 scaling_min_freq 和 scaling_max_freq
    adb_shell(f"echo {default_min} > {min_path}", need_root=True)
    adb_shell(f"echo {default_max} > {max_path}", need_root=True)

def set_cluster_frequency(cluster: str, freq: int):
    min_path = "/sys/devices/system/cpu/cpu" + cluster + "/cpufreq/scaling_min_freq"
    max_path = "/sys/devices/system/cpu/cpu" + cluster + "/cpufreq/scaling_max_freq"
    adb_shell(f"echo {freq} > {min_path}", need_root=True)
    adb_shell(f"echo {freq} > {max_path}", need_root=True)
def list_cpu_domains() -> list[dict]:
    """
    返回 CPU 频率域（cpufreq policy）列表：
    [
      {
        "policy": "0",
        "path": "/sys/devices/system/cpu/cpufreq/policy0",
        "cpus": "0 1 2 3",
        "governor": "schedutil",
        "cur_freq": "1286400",
        "min_freq": "300000",
        "max_freq": "2016000",
      },
      ...
    ]
    """
    # 优先走 policy（最标准）
    out = adb_shell("ls -d /sys/devices/system/cpu/cpufreq/policy* 2>/dev/null")
    policies = [p.strip() for p in out.splitlines() if p.strip()]
    domains = []

    if policies:
        for p in policies:
            m = re.search(r"policy(\d+)$", p)
            if not m:
                continue
            policy_id = m.group(1)

            cpus = adb_shell(
                f"cat {p}/related_cpus 2>/dev/null || cat {p}/affected_cpus 2>/dev/null || echo unknown"
            ).strip()
            governor = adb_shell(f"cat {p}/scaling_governor 2>/dev/null || echo unknown").strip()
            cur_freq = adb_shell(f"cat {p}/scaling_cur_freq 2>/dev/null || echo unknown").strip()
            min_freq = adb_shell(f"cat {p}/cpuinfo_min_freq 2>/dev/null || echo unknown").strip()
            max_freq = adb_shell(f"cat {p}/cpuinfo_max_freq 2>/dev/null || echo unknown").strip()

            domains.append({
                "policy": policy_id,
                "path": p,
                "cpus": cpus,
                "governor": governor,
                "cur_freq": cur_freq,
                "min_freq": min_freq,
                "max_freq": max_freq,
            })
        return domains

    # 兜底：老式路径（cpuX/cpufreq）存在时，按 related_cpus 进行归组
    cpu_list = adb_shell("ls -d /sys/devices/system/cpu/cpu[0-9]* 2>/dev/null | sed 's#.*/cpu##' | sort -n")
    cpus = [c.strip() for c in cpu_list.splitlines() if c.strip()]
    groups = {}

    for cpu in cpus:
        base = f"/sys/devices/system/cpu/cpu{cpu}/cpufreq"
        exists = adb_shell(f"if [ -d {base} ]; then echo 1; fi").strip()
        if exists != "1":
            continue
        rel = adb_shell(f"cat {base}/related_cpus 2>/dev/null || echo {cpu}").strip()
        groups.setdefault(rel, set()).add(cpu)

    # 输出成“域”列表（没有 policy id，就用 related_cpus 字符串当 key）
    for rel_cpus, members in groups.items():
        domains.append({
            "policy": "N/A",
            "path": "cpu*/cpufreq",
            "cpus": rel_cpus,
            "members": " ".join(str(x) for x in sorted(int(i) for i in members)),
        })

    return domains


def print_cpu_domains():
    domains = list_cpu_domains()
    if not domains:
        print("未发现 cpufreq 域（policy* 或 cpu*/cpufreq 都没有）。")
        return

    print("=== CPU 频率域（cpufreq domains）===")
    for d in domains:
        if d.get("policy") != "N/A":
            print(
                f"- policy{d['policy']}  cpus=[{d['cpus']}]  "
                f"gov={d['governor']}  cur={d['cur_freq']}  "
                f"min={d['min_freq']}  max={d['max_freq']}"
            )
        else:
            print(f"- domain cpus=[{d['cpus']}] members=[{d.get('members', '')}] (fallback)")


def get_policy_original_settings(policy_id: str):
    """
    获取policy的原始频率设置（从cpuinfo_min_freq和cpuinfo_max_freq读取默认范围）
    
    Args:
        policy_id: policy ID
    
    Returns:
        dict: 包含min_freq和max_freq的字典
    """
    policy_path = f"/sys/devices/system/cpu/cpufreq/policy{policy_id}"
    
    # 读取默认的最小和最大频率（硬件支持的范围）
    min_freq = adb_shell(f"cat {policy_path}/cpuinfo_min_freq", need_root=True).strip()
    max_freq = adb_shell(f"cat {policy_path}/cpuinfo_max_freq", need_root=True).strip()
    
    return {
        'policy_id': policy_id,
        'policy_path': policy_path,
        'min_freq_khz': min_freq,
        'max_freq_khz': max_freq
    }


def set_policy_to_max(policy_id: str, save_original=True):
    """
    设置指定policy到最大频率
    
    Args:
        policy_id: policy ID，例如 "0", "4", "7"
        save_original: 是否保存原始设置（用于恢复）
    
    Returns:
        dict: 原始频率设置，如果save_original=False则返回None
    """
    policy_path = f"/sys/devices/system/cpu/cpufreq/policy{policy_id}"
    
    # 保存原始设置
    original_settings = None
    if save_original:
        original_settings = get_policy_original_settings(policy_id)
    
    # 读取最大频率
    max_freq = adb_shell(f"cat {policy_path}/cpuinfo_max_freq", need_root=True).strip()
    
    # 设置最小和最大频率都为最大值
    min_path = f"{policy_path}/scaling_min_freq"
    max_path = f"{policy_path}/scaling_max_freq"
    
    # 使用sh -c来确保重定向正确执行
    # adb_shell在need_root时会用su -c "cmd"，所以这里用单引号避免嵌套
    adb_shell(f"sh -c 'echo {max_freq} > {min_path}'", need_root=True)
    adb_shell(f"sh -c 'echo {max_freq} > {max_path}'", need_root=True)
    
    print(f"✅ policy{policy_id}: {max_freq} KHz ({int(max_freq)/1000:.0f} MHz)")
    return original_settings


def restore_policy_frequency(policy_id: str):
    """
    恢复policy频率到默认范围（cpuinfo_min_freq 到 cpuinfo_max_freq）
    
    Args:
        policy_id: policy ID
    """
    original = get_policy_original_settings(policy_id)
    policy_path = original['policy_path']
    min_freq = original['min_freq_khz']
    max_freq = original['max_freq_khz']
    
    min_path = f"{policy_path}/scaling_min_freq"
    max_path = f"{policy_path}/scaling_max_freq"
    
    # 恢复最小频率到硬件支持的最小值
    adb_shell(f"sh -c 'echo {min_freq} > {min_path}'", need_root=True)
    # 恢复最大频率到硬件支持的最大值
    adb_shell(f"sh -c 'echo {max_freq} > {max_path}'", need_root=True)
    
    print(f"✅ policy{policy_id}: 已恢复 (min: {int(min_freq)/1000:.0f} MHz, max: {int(max_freq)/1000:.0f} MHz)")


def restore_all_policies_frequency():
    """恢复所有policy频率到默认范围"""
    domains = list_cpu_domains()
    if not domains:
        print("⚠️  未找到任何CPU policy域")
        return
    
    print(f"\n🔧 恢复所有CPU policy域频率设置（共{len(domains)}个policy）...\n")
    
    for d in domains:
        policy_id = d.get("policy")
        if policy_id and policy_id != "N/A":
            try:
                restore_policy_frequency(policy_id)
            except Exception as e:
                print(f"⚠️  policy{policy_id}: 恢复失败 - {e}")
    
    print("\n✅ 所有CPU policy频率已恢复")


def set_all_policies_to_max():
    """设置所有policy到最大频率"""
    domains = list_cpu_domains()
    if not domains:
        print("⚠️  未找到任何CPU policy域")
        return []
    
    print(f"\n🔧 设置所有CPU policy域到最大频率（共{len(domains)}个policy）...\n")
    
    original_settings_list = []
    for d in domains:
        policy_id = d.get("policy")
        if policy_id and policy_id != "N/A":
            try:
                original = set_policy_to_max(policy_id, save_original=True)
                if original:
                    original_settings_list.append(original)
            except Exception as e:
                print(f"⚠️  policy{policy_id}: 设置失败 - {e}")
    
    print("\n✅ 所有CPU policy频率已设置为最大")
    return original_settings_list


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='将CPU频率设置为最大值（基于policy域）')
    parser.add_argument('--list', action='store_true', help='列出所有CPU policy域及其信息')
    parser.add_argument('--policy', type=str, help='指定要设置的policy ID（例如 0, 4, 7），如果不指定则设置所有policy')
    parser.add_argument('--all', action='store_true', help='设置所有policy到最大频率')
    parser.add_argument('--restore', type=str, nargs='?', const='all', metavar='POLICY_ID', 
                       help='恢复频率到默认范围。使用 --restore 恢复所有，或 --restore POLICY_ID 恢复指定policy')
    
    args = parser.parse_args()
    
    # 如果指定了--list，只列出信息并退出
    if args.list:
        print_cpu_domains()
        return
    
    # 如果指定了--restore，恢复频率
    if args.restore:
        if args.restore == 'all':
            # 恢复所有policy
            restore_all_policies_frequency()
        else:
            # 恢复指定policy
            try:
                restore_policy_frequency(args.restore)
            except Exception as e:
                print(f"❌ 错误：{e}")
                sys.exit(1)
        return
    
    # 如果指定了--policy，只设置该policy
    if args.policy:
        try:
            set_policy_to_max(args.policy)
        except Exception as e:
            print(f"❌ 错误：{e}")
            sys.exit(1)
    elif args.all:
        # 设置所有policy到最大频率
        set_all_policies_to_max()
    else:
        # 默认设置所有policy
        set_all_policies_to_max()


if __name__ == "__main__":
    main()
