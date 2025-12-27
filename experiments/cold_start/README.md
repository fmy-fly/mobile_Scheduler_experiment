# App冷启动实验

本实验用于统计Android应用的冷启动时长、功耗以及启动期间的CPU、GPU频率，使用Perfetto进行追踪和分析，最后生成可视化图表。

**所有统计信息都通过查询Perfetto Trace获取，不依赖adb命令。**

## 功能特性

- ✅ **冷启动追踪**: 自动停止应用并重新启动，确保冷启动场景
- ✅ **Perfetto集成**: 使用Perfetto进行系统级性能追踪
- ✅ **数据分析**: 从trace中查询冷启动时长、功耗、CPU频率、GPU频率
- ✅ **可视化**: 生成详细的图表展示分析结果

## 文件说明

- `run_experiment.py` - 运行实验脚本（启动perfetto、启动app、停止追踪、拉取trace）
- `analyze_trace.py` - 分析trace脚本（从perfetto trace中查询数据）
- `plot_results.py` - 绘制图表脚本（可视化分析结果）
- `run_complete.py` - 完整流程脚本（整合实验、分析、绘图）

## 使用方法

### 方法1: 使用完整流程脚本（推荐）

```bash
python experiments/cold_start/run_complete.py <package_name> [选项]

# 示例
python experiments/cold_start/run_complete.py com.example.app

# 指定Activity
python experiments/cold_start/run_complete.py com.example.app --activity com.example.app.MainActivity

# 指定实验名称和输出目录
python experiments/cold_start/run_complete.py com.example.app \
    --experiment-name MyExperiment \
    --output-dir ./results \
    --duration 30
```

### 方法2: 分步骤执行

#### 步骤1: 运行实验

```bash
python experiments/cold_start/run_experiment.py <package_name> [选项]
```

#### 步骤2: 分析数据

```bash
python experiments/cold_start/analyze_trace.py <trace_file_path> <package_name> [--output-dir <dir>]
```

#### 步骤3: 绘制图表

```bash
python experiments/cold_start/plot_results.py <results_dir> --output analysis.png --summary summary.png
```

## 参数说明

### run_complete.py / run_experiment.py

- `package_name` (必需): 应用包名
- `--activity`: 主Activity名称(可选，不指定时使用monkey启动)
- `--experiment-name`: 实验名称(默认: ColdStart)
- `--duration`: 追踪时长，秒(默认: 30)
- `--config`: Perfetto配置文件路径(默认: /data/misc/perfetto-configs/HardwareInfo.pbtx)
- `--output-dir`: 输出目录(默认: Perfetto/trace/traceAnalysis/results/{experiment_name})
- `--no-show`: 不显示图表，只保存

## 输出说明

实验完成后，会在输出目录生成以下文件：

1. **Trace文件**: `Perfetto/trace/traceRecord/method{experiment_name}/{experiment_name}.perfetto-trace`
2. **数据CSV文件**:
   - `cpu_frequency.csv`: CPU频率数据
   - `gpu_frequency.csv`: GPU频率数据
   - `power.csv`: 功耗数据
3. **图表文件**:
   - `cold_start_analysis.png`: 详细分析图表
     - CPU频率变化曲线
     - GPU频率变化曲线
     - 功耗变化曲线
     - CPU与GPU频率对比
   - `cold_start_summary.png`: 统计摘要图表
     - 冷启动时长
     - CPU频率统计(平均/最大/最小)
     - GPU频率统计(平均/最大/最小)
     - 功耗统计(平均/最大/最小)

## 数据来源

所有数据都通过查询Perfetto Trace获取：

1. **冷启动时长**: 从trace中查询应用进程启动时间和Displayed事件时间
2. **CPU频率**: 从trace的counter表中查询`cpufreq`数据
3. **GPU频率**: 从trace的counter表中查询GPU频率数据
4. **功耗**: 从trace的counter表中查询电池电流或功耗数据

## 前置准备

### 1. 推送Perfetto配置文件到设备

```bash
adb push "Perfetto/configPerfetto/HardwareInfo.pbtx" /data/misc/perfetto-configs/HardwareInfo.pbtx
```

### 2. 确保设备已root或已授予相应权限

Perfetto需要系统级权限才能追踪CPU、GPU频率和功耗数据。

## 依赖安装

```bash
pip install perfetto pandas matplotlib numpy
```

## 注意事项

1. **设备权限**: 需要root权限或已授予Perfetto系统级追踪权限
2. **配置文件**: 确保Perfetto配置文件已正确推送到设备
3. **应用包名**: 确保提供正确的应用包名
4. **追踪时长**: 根据应用启动时间调整追踪时长，建议设置为应用启动时间的2-3倍
5. **数据可用性**: 不同设备和Android版本可能支持的数据源不同，某些数据可能无法获取

## 示例

完整示例：

```bash
# 1. 运行完整实验
python experiments/cold_start/run_complete.py com.example.myapp \
    --activity com.example.myapp.MainActivity \
    --experiment-name TestRun1 \
    --duration 30

# 2. 查看结果
# 结果保存在: Perfetto/trace/traceAnalysis/results/TestRun1/
```
