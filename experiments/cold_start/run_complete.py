"""
App冷启动实验完整流程脚本
整合：实验运行 -> 数据分析 -> 结果可视化
"""
import os
import sys

# 添加项目根目录到路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from experiments.cold_start.run_experiment import run_cold_start_experiment
from experiments.cold_start.analyze_trace import analyze_cold_start_trace
from experiments.cold_start.plot_results import (
    plot_cold_start_analysis, 
    plot_summary_statistics
)


def run_complete_experiment(package_name, activity_name=None, 
                           experiment_name="ColdStart",
                           trace_duration=30,
                           config_file="/data/misc/perfetto-configs/HardwareInfo.pbtx",
                           output_dir=None,
                           show_plots=True,
                           max_frequency=False):
    """
    运行完整的冷启动实验流程
    
    Args:
        package_name: 应用包名
        activity_name: 主Activity名称(可选)
        experiment_name: 实验名称
        trace_duration: 追踪时长(秒)
        config_file: perfetto配置文件路径
        output_dir: 输出目录
        show_plots: 是否显示图表
        max_frequency: 是否设置CPU/GPU到最大频率（默认False，使用系统默认调度）
    
    Returns:
        包含所有结果的字典
    """
    print("=" * 80)
    print("🚀 App冷启动完整实验流程")
    print("=" * 80)
    
    # 1. 运行实验
    print("\n[阶段 1/3] 运行冷启动实验...")
    trace_file = run_cold_start_experiment(
        package_name=package_name,
        activity_name=activity_name,
        experiment_name=experiment_name,
        trace_duration=trace_duration,
        config_file=config_file,
        max_frequency=max_frequency
    )
    
    if not trace_file or not os.path.exists(trace_file):
        print("❌ Trace文件不存在，实验失败")
        return None
    
    print(f"✅ Trace文件: {trace_file}")
    
    # 2. 分析数据
    print("\n[阶段 2/3] 分析Trace数据...")
    if output_dir is None:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(os.path.dirname(script_dir))  # experiments/cold_start -> experiments -> 项目根目录
        output_dir = os.path.join(project_root, "Perfetto", "trace", "traceAnalysis", 
                                 "results", experiment_name)
    
    os.makedirs(output_dir, exist_ok=True)
    results = analyze_cold_start_trace(trace_file, package_name, output_dir)
    
    if not results:
        print("❌ 数据分析失败")
        return None
    
    print(f"✅ 分析结果已保存到: {output_dir}")
    
    # 3. 绘制图表
    print("\n[阶段 3/3] 绘制分析图表...")
    analysis_plot_path = os.path.join(output_dir, "cold_start_analysis.png")
    summary_plot_path = os.path.join(output_dir, "cold_start_summary.png")
    
    plot_cold_start_analysis(results, analysis_plot_path, show_plots)
    plot_summary_statistics(results, summary_plot_path, show_plots)
    
    print("\n" + "=" * 80)
    print("✅ 完整实验流程已完成!")
    print("=" * 80)
    print(f"📁 结果目录: {output_dir}")
    print(f"📊 详细分析图表: {analysis_plot_path}")
    print(f"📈 统计摘要图表: {summary_plot_path}")
    print(f"⏱️  冷启动时长: {results['cold_start_duration_ms']:.2f} ms")
    print("=" * 80)
    
    return {
        'trace_file': trace_file,
        'results': results,
        'output_dir': output_dir,
        'analysis_plot': analysis_plot_path,
        'summary_plot': summary_plot_path
    }


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='App冷启动完整实验')
    parser.add_argument('package_name', help='应用包名')
    parser.add_argument('--activity', help='主Activity名称(可选)')
    parser.add_argument('--experiment-name', default='ColdStart', help='实验名称')
    parser.add_argument('--duration', type=int, default=30, help='追踪时长(秒)')
    parser.add_argument('--config', default='/data/misc/perfetto-configs/HardwareInfo.pbtx',
                       help='Perfetto配置文件路径')
    parser.add_argument('--output-dir', help='输出目录')
    parser.add_argument('--no-show', action='store_true', help='不显示图表')
    parser.add_argument('--max-frequency', action='store_true',
                       help='设置CPU/GPU到最大频率（默认使用系统调度）')
    
    args = parser.parse_args()
    
    run_complete_experiment(
        package_name=args.package_name,
        activity_name=args.activity,
        experiment_name=args.experiment_name,
        trace_duration=args.duration,
        config_file=args.config,
        output_dir=args.output_dir,
        show_plots=not args.no_show,
        max_frequency=args.max_frequency
    )
