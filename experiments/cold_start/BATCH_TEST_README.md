# 批量测试App冷启动时长

这个脚本可以批量测试多个App的冷启动时长，支持自定义频率设置。

## 功能

- ✅ 批量测试多个App的冷启动时长
- ✅ 支持自定义CPU和GPU频率设置
- ✅ 自动分析trace文件并生成结果
- ✅ 保存测试结果到JSON文件
- ✅ 支持测试特定App或所有预定义App

## 预定义App列表

脚本中已预定义以下App：

- **play商店**: `com.android.vending`
- **Gmail**: `com.google.android.gm`
- **youtube**: `com.google.android.youtube`
- **抖音**: `com.ss.android.ugc.aweme`
- **小红书**: `com.xingin.xhs`
- **微信**: `com.tencent.mm`
- **QQ**: `com.tencent.mobileqq`

## 使用方法

### 1. 测试所有预定义App（默认频率）

```bash
python experiments/cold_start/batch_test.py
```

### 2. 测试特定App

```bash
python experiments/cold_start/batch_test.py --apps play商店 微信 QQ
```

### 3. 使用最大频率模式测试

```bash
python experiments/cold_start/batch_test.py --apps play商店 微信 --max-frequency
```

### 4. 使用自定义CPU频率测试

```bash
# 设置policy0为1800MHz，policy4为1200-2300MHz
python experiments/cold_start/batch_test.py --apps play商店 --cpu-freq '{"0": 1800000, "4": {"min": 1200000, "max": 2300000}}'
```

### 5. 使用自定义GPU频率测试

```bash
# 设置GPU为固定频率150MHz
python experiments/cold_start/batch_test.py --apps play商店 --gpu-freq 150000000

# 设置GPU频率范围为100-850MHz
python experiments/cold_start/batch_test.py --apps play商店 --gpu-freq '{"min": 100000000, "max": 850000000}'
```

### 6. 同时设置CPU和GPU自定义频率

```bash
python experiments/cold_start/batch_test.py \
    --apps play商店 微信 \
    --cpu-freq '{"0": 1800000, "4": 2300000}' \
    --gpu-freq 150000000
```

### 7. 只生成trace文件，不自动分析

```bash
python experiments/cold_start/batch_test.py --apps play商店 --no-analyze
```

### 8. 指定输出目录

```bash
python experiments/cold_start/batch_test.py --apps play商店 --output-dir ./results
```

## 参数说明

- `--apps`: 要测试的App名称列表（空格分隔），如果不指定则测试所有预定义App
- `--experiment-name`: 实验名称（默认: BatchTest）
- `--duration`: 追踪时长，秒（默认: 30）
- `--config`: Perfetto配置文件路径（默认: /data/misc/perfetto-configs/HardwareInfo.pbtx）
- `--max-frequency`: 设置CPU/GPU到最大频率
- `--cpu-freq`: 自定义CPU频率设置（JSON格式）
  - 格式: `{"policy_id": freq_khz}` 或 `{"policy_id": {"min": min_khz, "max": max_khz}}`
  - 例如: `'{"0": 1800000, "4": {"min": 1200000, "max": 2300000}}'`
- `--gpu-freq`: 自定义GPU频率设置（Hz）
  - 可以是数字: `150000000`（设置固定频率150MHz）
  - 或JSON格式: `'{"min": 100000000, "max": 850000000}'`（设置频率范围）
- `--no-analyze`: 不自动分析trace文件，只生成trace文件
- `--output-dir`: 输出目录（默认: Perfetto/trace/traceAnalysis/results/{experiment_name}）

## 频率设置格式说明

### CPU频率设置

CPU频率基于policy域进行设置。首先查看可用的policy域：

```bash
python experiments/cpu/set_cpu_max_freq.py --list
```

然后根据policy ID设置频率：

- **固定频率**: `{"0": 1800000}` - 将policy0设置为1800MHz
- **频率范围**: `{"0": {"min": 1200000, "max": 2300000}}` - 将policy0设置为1200-2300MHz
- **多个policy**: `{"0": 1800000, "4": 2300000}` - 同时设置多个policy

### GPU频率设置

- **固定频率**: `150000000` - 设置GPU为150MHz（固定值）
- **频率范围**: `'{"min": 100000000, "max": 850000000}'` - 设置GPU频率范围为100-850MHz

## 输出结果

测试完成后，会在输出目录生成以下文件：

1. **Trace文件**: 每个App的trace文件保存在 `Perfetto/trace/traceRecord/method{experiment_name}_{app_name}/` 目录
2. **分析结果**: 如果启用自动分析，每个App的分析结果保存在 `{output_dir}/{app_name}/` 目录
3. **批量测试结果JSON**: `{output_dir}/batch_test_results_{timestamp}.json`

JSON结果文件包含：

```json
{
  "experiment_name": "BatchTest",
  "timestamp": "20240101_120000",
  "frequency_mode": "自定义频率",
  "cpu_freq_settings": {...},
  "gpu_freq_setting": {...},
  "results": {
    "play商店": {
      "package_name": "com.android.vending",
      "status": "success",
      "cold_start_duration_ms": 1234.56,
      ...
    },
    ...
  }
}
```

## 注意事项

1. **需要root权限**: 设置自定义频率需要root权限
2. **频率范围**: 设置频率时，确保频率值在硬件支持的范围内
3. **测试间隔**: 脚本会在每个App测试之间等待5秒，避免设备过热
4. **频率恢复**: 测试完成后会自动恢复频率设置（如果使用了自定义频率）

## 查看可用频率

在设置自定义频率之前，可以先查看设备支持的频率范围：

```bash
# 查看CPU频率信息
python experiments/cpu/set_cpu_max_freq.py --list

# 查看GPU频率信息
python experiments/gpu/set_gpu_max_freq.py --info
```

## 示例工作流

```bash
# 1. 查看可用的CPU policy域
python experiments/cpu/set_cpu_max_freq.py --list

# 2. 查看GPU频率信息
python experiments/gpu/set_gpu_max_freq.py --info

# 3. 批量测试所有App（默认频率）
python experiments/cold_start/batch_test.py

# 4. 批量测试特定App（自定义频率）
python experiments/cold_start/batch_test.py \
    --apps play商店 微信 QQ \
    --cpu-freq '{"0": 1800000, "4": 2300000}' \
    --gpu-freq 150000000 \
    --experiment-name CustomFreqTest

# 5. 查看结果
cat Perfetto/trace/traceAnalysis/results/CustomFreqTest/batch_test_results_*.json
```

