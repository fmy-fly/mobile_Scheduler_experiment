# CPU频率管理（基于Policy域）

这个模块用于将所有CPU频率设置为最大值，基于CPU的policy域进行管理。

## 使用方法

### 1. 查看所有CPU policy域

```bash
python experiments/cpu/set_cpu_max_freq.py --list
```

这会列出所有policy域，包括：
- policy名称和ID
- 关联的CPU核心
- 当前频率设置
- 频率范围（最小-最大）

### 2. 设置所有policy到最大频率

```bash
python experiments/cpu/set_cpu_max_freq.py
```

或者：

```bash
python experiments/cpu/set_cpu_max_freq.py --all
```

### 3. 设置单个policy到最大频率

```bash
# 设置policy0到最大频率
python experiments/cpu/set_cpu_max_freq.py --policy 0

# 设置policy4到最大频率
python experiments/cpu/set_cpu_max_freq.py --policy 4
```

### 4. 恢复频率到默认范围

```bash
# 恢复所有policy频率到默认范围
python experiments/cpu/set_cpu_max_freq.py --restore

# 恢复指定policy频率到默认范围
python experiments/cpu/set_cpu_max_freq.py --restore 0
```

## 示例

```bash
# 首先查看有哪些policy域
python experiments/cpu/set_cpu_max_freq.py --list

# 设置所有policy到最大频率
python experiments/cpu/set_cpu_max_freq.py --all

# 设置单个policy到最大频率
python experiments/cpu/set_cpu_max_freq.py --policy 0

# 恢复所有policy频率到默认范围
python experiments/cpu/set_cpu_max_freq.py --restore

# 恢复指定policy频率到默认范围
python experiments/cpu/set_cpu_max_freq.py --restore 0
```

## 函数说明

### `list_cpu_domains()`
列出所有CPU policy域

**返回**：
- `list[dict]`: policy域信息列表

### `print_cpu_domains()`
打印所有CPU policy域信息到控制台

### `set_policy_to_max(policy_id)`
设置指定policy到最大频率

**参数**：
- `policy_id` (str): policy ID，例如 "0", "4", "7"

### `set_all_policies_to_max()`
设置所有policy到最大频率

**返回**：
- `list`: 原始频率设置列表

### `restore_policy_frequency(policy_id)`
恢复指定policy频率到默认范围（cpuinfo_min_freq 到 cpuinfo_max_freq）

**参数**：
- `policy_id` (str): policy ID

### `restore_all_policies_frequency()`
恢复所有policy频率到默认范围

## 注意事项

1. **需要root权限**：设置CPU频率需要root权限，确保设备已root且`su`命令可用
2. **基于policy域**：代码直接操作 `/sys/devices/system/cpu/cpufreq/policy*` 路径
3. **重定向处理**：使用 `sh -c` 来确保重定向操作正确执行

