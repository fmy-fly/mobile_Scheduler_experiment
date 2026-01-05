"""
频率配置对比测试脚本
比较三种频率配置方式：默认调度、最大频率、自定义频率
对比指标：启动时长、平均功耗
"""
import os
import sys
import json
import time
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
from experiments.cold_start.run_experiment import run_cold_start_experiment
from experiments.cold_start.analyze_trace import analyze_cold_start_trace
from experiments.cold_start.batch_test import APPS, APP_FREQ_CONFIGS


def compare_freq_configs_for_apps(apps=None,
                                   experiment_name="FreqCompare",
                                   trace_duration=30,
                                   config_file="/data/misc/perfetto-configs/HardwareInfo.pbtx",
                                   output_dir=None):
    """
    对比测试：比较三种频率配置的性能
    
    Args:
        apps: 要测试的App列表，格式为 {app_name: package_name}，如果为None则测试所有App
        experiment_name: 实验名称
        trace_duration: 追踪时长(秒)
        config_file: perfetto配置文件路径
        output_dir: 输出目录
    
    Returns:
        dict: 对比结果，包含每个App在三种配置下的性能指标
    """
    if apps is None:
        apps = APPS
    
    print("=" * 80)
    print("📊 频率配置对比测试")
    print("=" * 80)
    print(f"📋 测试App数量: {len(apps)}")
    print(f"🔬 测试配置: 默认调度、最大频率、自定义频率")
    print("=" * 80)
    
    # 设置默认输出目录
    if not output_dir:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(os.path.dirname(script_dir))
        output_dir = os.path.join(project_root, "Perfetto", "trace", "traceAnalysis", "results", experiment_name)
    os.makedirs(output_dir, exist_ok=True)
    
    # 三种配置模式
    config_modes = [
        {
            "name": "默认调度",
            "max_frequency": False,
            "cpu_freq_settings": None,
            "gpu_freq_setting": None
        },
        {
            "name": "最大频率",
            "max_frequency": True,
            "cpu_freq_settings": None,
            "gpu_freq_setting": None
        },
        {
            "name": "自定义频率",
            "max_frequency": False,
            "cpu_freq_settings": None,  # 从APP_FREQ_CONFIGS获取
            "gpu_freq_setting": None    # 从APP_FREQ_CONFIGS获取
        }
    ]
    
    # 存储所有结果
    all_results = {}
    
    # 对每个App进行测试
    for idx, (app_name, package_name) in enumerate(apps.items(), 1):
        print("\n" + "=" * 80)
        print(f"[{idx}/{len(apps)}] 测试App: {app_name} ({package_name})")
        print("=" * 80)
        
        app_results = {
            "package_name": package_name,
            "configs": {}
        }
        
        # 对每种配置进行测试
        for mode_idx, mode in enumerate(config_modes, 1):
            print(f"\n--- [{mode_idx}/3] 配置: {mode['name']} ---")
            
            # 获取配置参数
            if mode["name"] == "自定义频率":
                if app_name in APP_FREQ_CONFIGS:
                    app_config = APP_FREQ_CONFIGS[app_name]
                    cpu_settings = app_config.get("cpu_freq_settings")
                    gpu_setting = app_config.get("gpu_freq_setting")
                else:
                    print(f"⚠️  {app_name} 未配置自定义频率，跳过")
                    app_results["configs"][mode["name"]] = {
                        "status": "skipped",
                        "reason": "未配置自定义频率"
                    }
                    continue
            else:
                cpu_settings = mode["cpu_freq_settings"]
                gpu_setting = mode["gpu_freq_setting"]
            
            try:
                # 运行实验
                exp_name = f"{experiment_name}_{app_name}_{mode['name']}"
                trace_file = run_cold_start_experiment(
                    package_name=package_name,
                    experiment_name=exp_name,
                    trace_duration=trace_duration,
                    config_file=config_file,
                    max_frequency=mode["max_frequency"],
                    cpu_freq_settings=cpu_settings,
                    gpu_freq_setting=gpu_setting
                )
                
                if not trace_file:
                    print(f"❌ {mode['name']}: 实验失败（无法获取trace文件）")
                    app_results["configs"][mode["name"]] = {
                        "status": "failed",
                        "error": "无法获取trace文件"
                    }
                    continue
                
                # 分析trace文件
                print(f"📊 分析 {mode['name']} 的trace数据...")
                try:
                    app_output_dir = os.path.join(output_dir, app_name, mode["name"])
                    os.makedirs(app_output_dir, exist_ok=True)
                    
                    analysis_results = analyze_cold_start_trace(
                        trace_path=trace_file,
                        package_name=package_name,
                        output_dir=app_output_dir
                    )
                    
                    if analysis_results:
                        app_results["configs"][mode["name"]] = {
                            "status": "success",
                            "trace_file": str(trace_file),
                            "cold_start_duration_ms": analysis_results.get('cold_start_duration_ms'),
                            "cold_start_duration_s": analysis_results.get('cold_start_duration_s'),
                            "avg_power_mw": analysis_results.get('avg_power_mw'),
                            "max_power_mw": analysis_results.get('max_power_mw'),
                            "min_power_mw": analysis_results.get('min_power_mw'),
                            "total_power_consumption_j": analysis_results.get('total_power_consumption_j'),
                            "avg_current_ma": analysis_results.get('avg_current_ma'),
                            "avg_voltage_v": analysis_results.get('avg_voltage_v'),
                        }
                        
                        duration_ms = analysis_results.get('cold_start_duration_ms', 0)
                        avg_power = analysis_results.get('avg_power_mw', 0)
                        print(f"✅ {mode['name']}: 启动时长 = {duration_ms:.2f} ms, 平均功耗 = {avg_power:.1f} mW")
                    else:
                        app_results["configs"][mode["name"]] = {
                            "status": "failed",
                            "trace_file": str(trace_file),
                            "error": "分析失败"
                        }
                        print(f"⚠️  {mode['name']}: trace文件已生成，但分析失败")
                        
                except Exception as e:
                    print(f"⚠️  {mode['name']}: 分析trace时出错: {e}")
                    app_results["configs"][mode["name"]] = {
                        "status": "failed",
                        "trace_file": str(trace_file),
                        "error": f"分析出错: {str(e)}"
                    }
                
                # 测试间隔，避免设备过热
                if mode_idx < len(config_modes):
                    print(f"⏳ 等待3秒后测试下一个配置...")
                    time.sleep(3)
                    
            except Exception as e:
                print(f"❌ {mode['name']}: 测试失败 - {e}")
                app_results["configs"][mode["name"]] = {
                    "status": "failed",
                    "error": str(e)
                }
        
        all_results[app_name] = app_results
        
        # App间隔
        if idx < len(apps):
            print(f"\n⏳ 等待5秒后测试下一个App...")
            time.sleep(5)
    
    # 生成对比报告
    print("\n" + "=" * 80)
    print("📊 对比测试总结")
    print("=" * 80)
    
    generate_comparison_report(all_results, output_dir)
    
    # 保存结果到JSON文件
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_file = os.path.join(output_dir, f"freq_comparison_results_{timestamp}.json")
    
    with open(results_file, 'w', encoding='utf-8') as f:
        json.dump({
            'experiment_name': experiment_name,
            'timestamp': timestamp,
            'apps': apps,
            'results': all_results
        }, f, indent=2, ensure_ascii=False)
    
    print(f"\n💾 详细结果已保存到: {results_file}")
    
    return all_results


def generate_comparison_report(results, output_dir):
    """
    生成对比报告（控制台输出和文本文件）
    """
    report_lines = []
    report_lines.append("=" * 100)
    report_lines.append("频率配置对比测试报告")
    report_lines.append("=" * 100)
    report_lines.append("")
    
    # 存储对比数据
    comparison_summary = {}
    
    # 生成对比表格
    report_lines.append("【详细数据表】")
    report_lines.append("")
    
    # 表头
    header = f"{'App名称':<15} {'配置':<12} {'启动时长(ms)':<15} {'平均功耗(mW)':<15} {'总功耗(J)':<15} {'状态':<10}"
    report_lines.append(header)
    report_lines.append("-" * 100)
    
    # 按App分组显示
    for app_name, app_data in results.items():
        comparison_summary[app_name] = {}
        
        for config_name, config_data in app_data.get("configs", {}).items():
            if config_data.get("status") == "success":
                duration_ms = config_data.get("cold_start_duration_ms", 0)
                avg_power_mw = config_data.get("avg_power_mw", 0)
                total_power_j = config_data.get("total_power_consumption_j", 0)
                
                line = f"{app_name:<15} {config_name:<12} {duration_ms:>14.2f} {avg_power_mw:>14.1f} {total_power_j:>14.3f} {'✅':<10}"
                report_lines.append(line)
                
                comparison_summary[app_name][config_name] = {
                    "duration_ms": duration_ms,
                    "avg_power_mw": avg_power_mw,
                    "total_power_j": total_power_j
                }
            else:
                status = config_data.get("status", "unknown")
                error = config_data.get("error", "")
                line = f"{app_name:<15} {config_name:<12} {'N/A':>15} {'N/A':>15} {'N/A':>15} {status:<10}"
                report_lines.append(line)
                if error:
                    report_lines.append(f"  └─ 错误: {error}")
        
        report_lines.append("")
    
    # 生成简化对比表（每个App三种配置横向对比）
    report_lines.append("=" * 100)
    report_lines.append("【横向对比表】")
    report_lines.append("=" * 100)
    report_lines.append("")
    
    # 表头：每个App一行，三种配置的启动时长和功耗横向对比
    header_line = f"{'App名称':<15} "
    header_line += f"{'默认调度':>25} | {'最大频率':>25} | {'自定义频率':>25}"
    report_lines.append(header_line)
    sub_header = " " * 15 + f"{'时长(ms)':>10} {'功耗(mW)':>14} | {'时长(ms)':>10} {'功耗(mW)':>14} | {'时长(ms)':>10} {'功耗(mW)':>14}"
    report_lines.append(sub_header)
    report_lines.append("-" * 100)
    
    for app_name, app_data in results.items():
        if app_name not in comparison_summary:
            continue
        
        app_configs = comparison_summary[app_name]
        line = f"{app_name:<15} "
        
        # 默认调度
        if "默认调度" in app_configs:
            default = app_configs["默认调度"]
            line += f"{default['duration_ms']:>10.2f} {default['avg_power_mw']:>14.1f} | "
        else:
            line += f"{'N/A':>10} {'N/A':>14} | "
        
        # 最大频率
        if "最大频率" in app_configs:
            max_freq = app_configs["最大频率"]
            line += f"{max_freq['duration_ms']:>10.2f} {max_freq['avg_power_mw']:>14.1f} | "
        else:
            line += f"{'N/A':>10} {'N/A':>14} | "
        
        # 自定义频率
        if "自定义频率" in app_configs:
            custom = app_configs["自定义频率"]
            line += f"{custom['duration_ms']:>10.2f} {custom['avg_power_mw']:>14.1f}"
        else:
            line += f"{'N/A':>10} {'N/A':>14}"
        
        report_lines.append(line)
    
    # 计算改进百分比
    report_lines.append("=" * 100)
    report_lines.append("改进分析（相对于默认调度）")
    report_lines.append("=" * 100)
    report_lines.append("")
    
    for app_name, app_data in results.items():
        if app_name not in comparison_summary:
            continue
        
        app_configs = comparison_summary[app_name]
        
        if "默认调度" not in app_configs:
            continue
        
        default = app_configs["默认调度"]
        default_duration = default["duration_ms"]
        default_power = default["avg_power_mw"]
        
        report_lines.append(f"【{app_name}】")
        
        # 最大频率对比
        if "最大频率" in app_configs:
            max_freq = app_configs["最大频率"]
            duration_improve = ((default_duration - max_freq["duration_ms"]) / default_duration * 100) if default_duration > 0 else 0
            power_increase = ((max_freq["avg_power_mw"] - default_power) / default_power * 100) if default_power > 0 else 0
            
            report_lines.append(f"  最大频率 vs 默认调度:")
            report_lines.append(f"    启动时长: {max_freq['duration_ms']:.2f} ms ({duration_improve:+.1f}%)")
            report_lines.append(f"    平均功耗: {max_freq['avg_power_mw']:.1f} mW ({power_increase:+.1f}%)")
        
        # 自定义频率对比
        if "自定义频率" in app_configs:
            custom = app_configs["自定义频率"]
            duration_improve = ((default_duration - custom["duration_ms"]) / default_duration * 100) if default_duration > 0 else 0
            power_change = ((custom["avg_power_mw"] - default_power) / default_power * 100) if default_power > 0 else 0
            
            report_lines.append(f"  自定义频率 vs 默认调度:")
            report_lines.append(f"    启动时长: {custom['duration_ms']:.2f} ms ({duration_improve:+.1f}%)")
            report_lines.append(f"    平均功耗: {custom['avg_power_mw']:.1f} mW ({power_change:+.1f}%)")
        
        # 自定义 vs 最大频率
        if "自定义频率" in app_configs and "最大频率" in app_configs:
            custom = app_configs["自定义频率"]
            max_freq = app_configs["最大频率"]
            duration_diff = ((max_freq["duration_ms"] - custom["duration_ms"]) / max_freq["duration_ms"] * 100) if max_freq["duration_ms"] > 0 else 0
            power_save = ((max_freq["avg_power_mw"] - custom["avg_power_mw"]) / max_freq["avg_power_mw"] * 100) if max_freq["avg_power_mw"] > 0 else 0
            
            report_lines.append(f"  自定义频率 vs 最大频率:")
            report_lines.append(f"    启动时长差异: {duration_diff:+.1f}%")
            report_lines.append(f"    功耗节省: {power_save:+.1f}%")
        
        report_lines.append("")
    
    # 输出到控制台
    for line in report_lines:
        print(line)
    
    # 保存到文件
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = os.path.join(output_dir, f"comparison_report_{timestamp}.txt")
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(report_lines))
    
    print(f"\n📄 对比报告已保存到: {report_file}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description='频率配置对比测试：比较默认调度、最大频率、自定义频率三种配置的性能',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  # 测试所有App
  python experiments/cold_start/compare_freq_configs.py
  
  # 测试指定App
  python experiments/cold_start/compare_freq_configs.py --apps 微信 QQ
  
  # 指定输出目录
  python experiments/cold_start/compare_freq_configs.py --output-dir ./comparison_results
        """
    )
    parser.add_argument('--apps', nargs='+', help='要测试的App名称列表（空格分隔），例如: --apps 微信 QQ。如果不指定则测试所有App')
    parser.add_argument('--experiment-name', default='FreqCompare', help='实验名称（默认: FreqCompare）')
    parser.add_argument('--duration', type=int, default=30, help='追踪时长(秒)（默认: 30）')
    parser.add_argument('--config', default='/data/misc/perfetto-configs/HardwareInfo.pbtx',
                       help='Perfetto配置文件路径')
    parser.add_argument('--output-dir', help='输出目录（默认: Perfetto/trace/traceAnalysis/results/{experiment_name}）')
    
    args = parser.parse_args()
    
    # 解析要测试的App
    apps_to_test = None
    if args.apps:
        apps_to_test = {}
        for app_name in args.apps:
            if app_name in APPS:
                apps_to_test[app_name] = APPS[app_name]
            else:
                print(f"⚠️  警告: 未知App名称 '{app_name}'，跳过")
        if not apps_to_test:
            print("❌ 没有有效的App可测试")
            sys.exit(1)
    
    # 运行对比测试
    results = compare_freq_configs_for_apps(
        apps=apps_to_test,
        experiment_name=args.experiment_name,
        trace_duration=args.duration,
        config_file=args.config,
        output_dir=args.output_dir
    )
    
    print("\n✅ 对比测试完成!")

