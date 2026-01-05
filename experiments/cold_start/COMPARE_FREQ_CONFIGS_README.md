# 频率配置对比测试使用说明

## 功能说明

`compare_freq_configs.py` 脚本用于对比测试三种频率配置方式的性能表现：

1. **默认调度**：使用系统默认的频率调度策略
2. **最大频率**：将所有CPU和GPU设置为最大频率
3. **自定义频率**：使用在 `batch_test.py` 中配置的个性化频率方案

## 对比指标

对每个App，脚本会收集以下指标：
- **启动时长**（毫秒）：App冷启动完成所需时间
- **平均功耗**（毫瓦）：启动期间的平均功率消耗
- **总功耗**（焦耳）：启动期间的总能耗

## 使用方法

### 1. 测试所有App

```bash
python experiments/cold_start/compare_freq_configs.py
```

### 2. 测试指定App

```bash
python experiments/cold_start/compare_freq_configs.py --apps 微信 QQ
```

### 3. 指定输出目录

```bash
python experiments/cold_start/compare_freq_configs.py --output-dir ./comparison_results
```

### 4. 自定义实验名称

```bash
python experiments/cold_start/compare_freq_configs.py --experiment-name MyCompare
```

## 参数说明

- `--apps`: 要测试的App名称列表（空格分隔），例如: `--apps 微信 QQ play商店`
- `--experiment-name`: 实验名称（默认: FreqCompare）
- `--duration`: 追踪时长(秒)（默认: 30）
- `--config`: Perfetto配置文件路径（默认: /data/misc/perfetto-configs/HardwareInfo.pbtx）
- `--output-dir`: 输出目录（默认: Perfetto/trace/traceAnalysis/results/{experiment_name}）

## 输出结果

### 1. 控制台输出

脚本会在控制台实时显示：
- 每个App的三种配置测试进度
- 每个配置的启动时长和平均功耗
- 最终的对比报告

### 2. 输出文件

#### JSON结果文件
- 文件名：`freq_comparison_results_{timestamp}.json`
- 位置：输出目录根目录
- 内容：所有测试的详细数据（JSON格式）

#### 对比报告文件
- 文件名：`comparison_report_{timestamp}.txt`
- 位置：输出目录根目录
- 内容：包含：
  - **详细数据表**：每个App的三种配置的详细指标
  - **横向对比表**：每个App的三种配置横向对比
  - **改进分析**：相对于默认调度的改进百分比

#### Trace文件和分析结果
- 每个App的每个配置都会生成独立的trace文件和分析结果
- 位置：`{输出目录}/{app_name}/{配置名称}/`

## 报告示例

### 横向对比表

```
App名称           默认调度              最大频率              自定义频率
                   时长(ms) 功耗(mW) |   时长(ms) 功耗(mW) |   时长(ms) 功耗(mW)
微信              2345.67    1250.5  |   1890.23    2150.8  |   1980.45    1680.3
QQ                2456.78    1320.2  |   1950.12    2280.5  |   2056.34    1750.6
```

### 改进分析

```
【微信】
  最大频率 vs 默认调度:
    启动时长: 1890.23 ms (-19.4%)
    平均功耗: 2150.8 mW (+72.1%)
  自定义频率 vs 默认调度:
    启动时长: 1980.45 ms (-15.6%)
    平均功耗: 1680.3 mW (+34.4%)
  自定义频率 vs 最大频率:
    启动时长差异: +4.8%
    功耗节省: -21.9%
```

## 测试流程

对每个App，脚本会按以下顺序测试：

1. **默认调度**：测试一次（3秒间隔）
2. **最大频率**：测试一次（3秒间隔）
3. **自定义频率**：测试一次（如果已配置）

每个App测试完成后，等待5秒再测试下一个App（避免设备过热）。

## 注意事项

1. **测试时间**：每个App需要测试3种配置，每种配置需要约1-2分钟，请预留足够时间
2. **设备温度**：脚本已包含测试间隔，但如设备过热可手动延长间隔
3. **自定义配置**：如果App未在 `APP_FREQ_CONFIGS` 中配置，该App的自定义频率测试会被跳过
4. **数据完整性**：建议在网络稳定、设备温度正常时运行测试，以获得准确结果

## 结果解读

### 启动时长
- **负值改进**：启动时间缩短（更好）
- **正值改进**：启动时间增加（更差）

### 功耗
- **负值变化**：功耗降低（更好）
- **正值变化**：功耗增加（更差）

### 优化建议

根据对比结果，可以：
1. **如果自定义频率启动时间较长**：适当提高启动阶段的频率
2. **如果自定义频率功耗较高**：降低稳定阶段的频率
3. **如果启动时间改善不明显**：可能需要延长启动阶段的时间窗口

## 示例完整命令

```bash
# 测试微信和QQ，使用自定义输出目录
python experiments/cold_start/compare_freq_configs.py \
  --apps 微信 QQ \
  --experiment-name WeChatQQ_Compare \
  --output-dir ./my_comparison_results \
  --duration 30
```

