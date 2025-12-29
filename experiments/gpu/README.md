# GPU频率管理

这个模块用于将GPU频率设置为最大值。

## 功能

- 查看GPU频率信息
- 将GPU频率设置为硬件支持的最大值
- 恢复GPU频率到默认范围

## 使用方法

### 1. 查看GPU频率信息

```bash
python experiments/gpu/set_gpu_max_freq.py --info
```

这会显示：
- 频率范围（最小-最大）
- 当前频率设置
- 可用频率列表

### 2. 设置GPU到最大频率

```bash
python experiments/gpu/set_gpu_max_freq.py
```

### 3. 恢复GPU频率到默认范围

```bash
python experiments/gpu/set_gpu_max_freq.py --restore
```

## 示例

```bash
# 查看GPU频率信息
python experiments/gpu/set_gpu_max_freq.py --info

# 设置GPU到最大频率
python experiments/gpu/set_gpu_max_freq.py

# 恢复GPU频率到默认范围
python experiments/gpu/set_gpu_max_freq.py --restore
```

## 函数说明

### `get_gpu_info()`
获取GPU频率信息

**返回**：
- `dict`: 包含GPU频率信息的字典

### `print_gpu_info()`
打印GPU频率信息到控制台

### `get_gpu_original_settings()`
获取GPU的原始频率设置（从available_frequencies读取）

**返回**：
- `dict`: 包含min_freq_hz和max_freq_hz的字典

### `set_gpu_to_max(save_original=True)`
设置GPU到最大频率

**参数**：
- `save_original` (bool): 是否保存原始设置

**返回**：
- `dict`: 原始频率设置，如果save_original=False则返回None

### `restore_gpu_frequency()`
恢复GPU频率到默认范围

## 注意事项

1. **需要root权限**：设置GPU频率需要root权限，确保设备已root且`su`命令可用
2. **固定路径**：GPU路径固定为 `/sys/devices/genpd:0:1f000000.mali/consumer:platform:1f000000.mali/consumer`
3. **重定向处理**：使用 `sh -c` 来确保重定向操作正确执行

