"""
绘制App冷启动分析结果图表
可视化：冷启动时长、功耗曲线、CPU频率曲线、GPU频率曲线
"""
import os
import sys
import matplotlib
# 设置非交互式后端（避免Tkinter依赖问题）
matplotlib.use('Agg')  # 必须在导入pyplot之前设置
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np

# 设置中文字体
matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS']
matplotlib.rcParams['axes.unicode_minus'] = False

# 添加项目根目录到路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))


def load_analysis_results(results_dir_or_dict):
    """
    加载分析结果
    
    Args:
        results_dir_or_dict: 结果目录路径或结果字典
    """
    if isinstance(results_dir_or_dict, dict):
        return results_dir_or_dict
    
    results = {}
    results_dir = results_dir_or_dict
    
    # 加载CSV文件
    cpu_freq_file = os.path.join(results_dir, 'cpu_frequency.csv')
    gpu_freq_file = os.path.join(results_dir, 'gpu_frequency.csv')
    power_file = os.path.join(results_dir, 'power.csv')
    cpu_sched_file = os.path.join(results_dir, 'cpu_scheduling.csv')
    cpu_util_file = os.path.join(results_dir, 'cpu_utilization.csv')
    if os.path.exists(cpu_freq_file):
        results['cpu_frequency'] = pd.read_csv(cpu_freq_file)
    if os.path.exists(gpu_freq_file):
        results['gpu_frequency'] = pd.read_csv(gpu_freq_file)
    if os.path.exists(power_file):
        results['power'] = pd.read_csv(power_file)
    if os.path.exists(cpu_sched_file):
        results['cpu_scheduling'] = pd.read_csv(cpu_sched_file)
    if os.path.exists(cpu_util_file):
        results['cpu_utilization'] = pd.read_csv(cpu_util_file)
    
    return results


def plot_cpu_frequency(results, output_path=None):
    """
    绘制8个CPU频率图（垂直堆叠，类似Perfetto风格）
    
    Args:
        results: 分析结果字典
        output_path: 输出图片路径
    """
    if 'cpu_frequency' not in results or results['cpu_frequency'].empty:
        print("⚠️  无CPU频率数据")
        return
    
    cpu_df = results['cpu_frequency']
    
    # 获取所有CPU编号并排序
    if 'cpu' in cpu_df.columns:
        cpu_list = sorted(cpu_df['cpu'].unique())
        cpu_list = cpu_list[:8]  # 最多8个CPU
    else:
        print("⚠️  CPU数据中没有cpu列")
        return
    
    # 创建垂直堆叠的子图（8行1列）
    fig, axes = plt.subplots(len(cpu_list), 1, figsize=(14, 2.5 * len(cpu_list)), sharex=True)
    
    # 如果只有一个CPU，axes不是数组
    if len(cpu_list) == 1:
        axes = [axes]
    
    # 为每个CPU绘制图表
    colors = plt.cm.tab10(np.linspace(0, 1, len(cpu_list)))
    for idx, cpu in enumerate(cpu_list):
        ax = axes[idx]
        cpu_data = cpu_df[cpu_df['cpu'] == cpu].sort_values('time_relative_s')
        
        if len(cpu_data) > 0:
            ax.plot(cpu_data['time_relative_s'], cpu_data['frequency'], 
                   linewidth=1.5, color=colors[idx], label=f'CPU {int(cpu)}')
            
            # 标记启动区间
            start_window_start = results.get('start_window_start_s', 0)
            start_window_end = results.get('start_window_end_s', 0)
            if start_window_end > 0:
                y_min = cpu_data['frequency'].min()
                y_max = cpu_data['frequency'].max()
                y_range = y_max - y_min if y_max > y_min else y_max
                # 添加半透明背景标记启动区间
                ax.axvspan(0, start_window_end, alpha=0.2, color='yellow', label='启动区间')
            
            # 设置Y轴范围：使用CPU支持的频率范围（直接使用原始值）
            cpu_available_freqs = results.get('cpu_available_frequencies', {})
            cpu_id_int = int(cpu)
            if cpu_id_int in cpu_available_freqs:
                # 使用可用频率的最小值和最大值（直接使用原始值，不转换）
                y_min = cpu_available_freqs[cpu_id_int]['min']
                y_max = cpu_available_freqs[cpu_id_int]['max']
                y_range = y_max - y_min
                if y_range > 0:
                    # 添加5%的边距以便查看
                    y_padding = y_range * 0.05
                    ax.set_ylim(y_min - y_padding, y_max + y_padding)
                else:
                    ax.set_ylim(y_min * 0.95, y_max * 1.05)
            else:
                # 如果没有可用频率信息，使用实际数据的频率范围
                y_min = cpu_data['frequency'].min()
                y_max = cpu_data['frequency'].max()
                y_range = y_max - y_min
                if y_range > 0:
                    y_padding = y_range * 0.1
                    ax.set_ylim(max(0, y_min - y_padding), y_max + y_padding)
                elif y_min == y_max and y_min > 0:
                    ax.set_ylim(max(0, y_min * 0.9), y_max * 1.1)
                else:
                    ax.set_ylim(0, max(100, y_max * 1.1) if y_max > 0 else 100)
        else:
            # 如果没有数据，设置默认范围
            ax.set_ylim(0, 3000)
        
        ax.set_ylabel(f'CPU {int(cpu)}\n频率', fontsize=10, fontweight='bold')
        ax.grid(True, alpha=0.3, linestyle='--')
        # 只在第一个CPU的子图显示完整的图例（包含启动区间）
        if idx == 0:
            ax.legend(loc='upper right', fontsize=9)
        else:
            # 其他CPU只显示CPU标签，不显示启动区间标签（避免重复）
            handles, labels = ax.get_legend_handles_labels()
            # 只保留CPU相关的图例项
            cpu_handles = [h for h, l in zip(handles, labels) if l.startswith('CPU')]
            cpu_labels = [l for l in labels if l.startswith('CPU')]
            if cpu_handles:
                ax.legend(cpu_handles, cpu_labels, loc='upper right', fontsize=9)
        # 确保Y轴刻度标签可见
        ax.tick_params(axis='y', labelsize=9, left=True, labelleft=True)
        ax.ticklabel_format(style='plain', axis='y', useOffset=False)  # 使用普通数字格式，不用科学计数法
        # 确保Y轴标签显示（特别是前几个CPU）
        ax.yaxis.set_visible(True)
        plt.setp(ax.get_yticklabels(), visible=True)  # 强制显示Y轴刻度标签
    
    # 只在最下面的子图显示X轴标签
    axes[-1].set_xlabel('时间 (秒)', fontsize=12, fontweight='bold')
    
    # 添加总标题
    duration_ms = results.get('cold_start_duration_ms', 0)
    duration_s = results.get('cold_start_duration_s', 0)
    fig.suptitle(f'CPU频率时间线 - 启动时长: {duration_ms:.2f} ms ({duration_s:.3f} 秒)', 
                fontsize=14, fontweight='bold', y=0.995)
    
    # 调整布局，确保Y轴标签有足够空间显示（特别是前几个CPU）
    plt.subplots_adjust(left=0.12, right=0.95, top=0.97, bottom=0.05, hspace=0.25)
    
    if output_path:
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"✅ CPU频率图表已保存到: {output_path}")
    
    plt.close()


def plot_gpu_frequency(results, output_path=None):
    """
    绘制GPU频率图
    
    Args:
        results: 分析结果字典
        output_path: 输出图片路径
    """
    fig, ax = plt.subplots(figsize=(12, 6))
    
    if 'gpu_frequency' in results and not results['gpu_frequency'].empty:
        gpu_df = results['gpu_frequency'].sort_values('time_relative_s')
        ax.plot(gpu_df['time_relative_s'], gpu_df['frequency'], 
               linewidth=2, color='red', label='GPU频率')
        
        # 标记启动区间
        start_window_start = results.get('start_window_start_s', 0)
        start_window_end = results.get('start_window_end_s', 0)
        if start_window_end > 0:
            # 添加半透明背景标记启动区间
            ax.axvspan(0, start_window_end, alpha=0.2, color='yellow', label='启动区间')
        
        # 设置X轴范围：显示所有数据，包括启动前的部分
        x_min_data = gpu_df['time_relative_s'].min()
        x_max_data = gpu_df['time_relative_s'].max()
        
        # 使用start_window_start_s作为X轴起始点（通常是负值，表示启动前的扩展范围）
        # 如果数据的最小值更小，则使用数据的最小值
        x_min = min(x_min_data, start_window_start) if start_window_start < 0 else x_min_data
        x_max = max(x_max_data, start_window_end)
        
        x_range = x_max - x_min
        if x_range > 0:
            # 添加5%的边距
            x_padding = x_range * 0.05
            ax.set_xlim(x_min - x_padding, x_max + x_padding)
        else:
            # 如果数据范围很小，至少显示一个合理的范围
            ax.set_xlim(x_min - 0.1, x_max + 0.1)
        
        # 设置Y轴范围：使用GPU支持的频率范围（直接使用原始值）
        gpu_available_freqs = results.get('gpu_available_frequencies')
        if gpu_available_freqs:
            # 使用可用频率的最小值和最大值（直接使用原始值，不转换）
            y_min = gpu_available_freqs['min']
            y_max = gpu_available_freqs['max']
            y_range = y_max - y_min
            if y_range > 0:
                # 添加5%的边距以便查看
                y_padding = y_range * 0.05
                ax.set_ylim(y_min - y_padding, y_max + y_padding)
            else:
                ax.set_ylim(y_min * 0.95, y_max * 1.05)
        else:
            # 如果没有可用频率信息，使用实际数据的频率范围
            y_min = gpu_df['frequency'].min()
            y_max = gpu_df['frequency'].max()
            y_range = y_max - y_min
            if y_range > 0:
                y_padding = y_range * 0.1
                ax.set_ylim(max(0, y_min - y_padding), y_max + y_padding)
            elif y_min == y_max and y_min > 0:
                ax.set_ylim(max(0, y_min * 0.9), y_max * 1.1)
            else:
                ax.set_ylim(0, max(100, y_max * 1.1) if y_max > 0 else 100)
        
        ax.set_xlabel('时间 (秒)', fontsize=12)
        ax.set_ylabel('频率', fontsize=12)
        ax.set_title('GPU频率变化', fontsize=14, fontweight='bold')
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=11)
    else:
        ax.text(0.5, 0.5, '无GPU频率数据', ha='center', va='center', 
               transform=ax.transAxes, fontsize=14)
        ax.set_title('GPU频率变化', fontsize=14, fontweight='bold')
    
    duration_ms = results.get('cold_start_duration_ms', 0)
    duration_s = results.get('cold_start_duration_s', 0)
    fig.suptitle(f'GPU频率时间线 - 启动时长: {duration_ms:.2f} ms ({duration_s:.3f} 秒)', 
                fontsize=14, fontweight='bold', y=0.98)
    
    plt.tight_layout()
    
    if output_path:
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"✅ GPU频率图表已保存到: {output_path}")
    
    plt.close()


def plot_voltage_current(results, output_path=None):
    """
    绘制电压和电流图（分开两张图）
    
    Args:
        results: 分析结果字典
        output_path: 输出图片路径（如果提供，会生成voltage.png和current.png）
    """
    if 'power' not in results or results['power'].empty:
        print("⚠️  无电压电流数据")
        return
    
    power_df = results['power'].sort_values('time_relative_s')
    
    # 分离电压和电流数据
    current_data = power_df[power_df['power_source'].str.contains('current_ua', case=False, na=False)].copy()
    voltage_data = power_df[power_df['power_source'].str.contains('voltage_uv', case=False, na=False)].copy()
    
    # 绘制电流图
    if not current_data.empty:
        fig, ax = plt.subplots(figsize=(12, 6))
        ax.plot(current_data['time_relative_s'], current_data['current_ma'], 
               linewidth=2, color='green', label='电流')
        
        # 标记启动区间
        start_window_end = results.get('start_window_end_s', 0)
        if start_window_end > 0:
            # 添加半透明背景标记启动区间
            ax.axvspan(0, start_window_end, alpha=0.2, color='yellow', label='启动区间')
        
        ax.set_xlabel('时间 (秒)', fontsize=12)
        ax.set_ylabel('电流 (mA)', fontsize=12)
        ax.set_title('电流变化', fontsize=14, fontweight='bold')
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=11)
        
        duration_ms = results.get('cold_start_duration_ms', 0)
        duration_s = results.get('cold_start_duration_s', 0)
        fig.suptitle(f'电流时间线 - 启动时长: {duration_ms:.2f} ms ({duration_s:.3f} 秒)', 
                    fontsize=14, fontweight='bold', y=0.98)
        
        plt.tight_layout()
        
        if output_path:
            current_path = output_path.replace('.png', '_current.png') if output_path.endswith('.png') else output_path + '_current.png'
            plt.savefig(current_path, dpi=300, bbox_inches='tight')
            print(f"✅ 电流图表已保存到: {current_path}")
        
        plt.close()
    
    # 绘制电压图
    if not voltage_data.empty:
        fig, ax = plt.subplots(figsize=(12, 6))
        ax.plot(voltage_data['time_relative_s'], voltage_data['current_ma'], 
               linewidth=2, color='orange', label='电压')
        
        # 标记启动区间
        start_window_end = results.get('start_window_end_s', 0)
        if start_window_end > 0:
            # 添加半透明背景标记启动区间
            ax.axvspan(0, start_window_end, alpha=0.2, color='yellow', label='启动区间')
        
        ax.set_xlabel('时间 (秒)', fontsize=12)
        ax.set_ylabel('电压 (V)', fontsize=12)
        ax.set_title('电压变化', fontsize=14, fontweight='bold')
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=11)
        
        duration_ms = results.get('cold_start_duration_ms', 0)
        duration_s = results.get('cold_start_duration_s', 0)
        fig.suptitle(f'电压时间线 - 启动时长: {duration_ms:.2f} ms ({duration_s:.3f} 秒)', 
                    fontsize=14, fontweight='bold', y=0.98)
        
        plt.tight_layout()
        
        if output_path:
            voltage_path = output_path.replace('.png', '_voltage.png') if output_path.endswith('.png') else output_path + '_voltage.png'
            plt.savefig(voltage_path, dpi=300, bbox_inches='tight')
            print(f"✅ 电压图表已保存到: {voltage_path}")
        
        plt.close()


def plot_power(results, output_path=None):
    """
    绘制功耗图
    
    Args:
        results: 分析结果字典
        output_path: 输出图片路径
    """
    fig, ax = plt.subplots(figsize=(12, 6))
    
    if 'power' in results and not results['power'].empty:
        power_df = results['power'].sort_values('time_relative_s')
        
        # 标记启动区间
        start_window_end = results.get('start_window_end_s', 0)
        if start_window_end > 0:
            # 添加半透明背景标记启动区间
            ax.axvspan(0, start_window_end, alpha=0.2, color='yellow', label='启动区间')
        
        # 查找功耗数据（power_mw）
        power_data = power_df[power_df['power_source'].str.contains('power_mw', case=False, na=False)]
        
        if not power_data.empty:
            ax.plot(power_data['time_relative_s'], power_data['current_ma'], 
                   linewidth=2, color='purple', label='功耗')
            ax.set_xlabel('时间 (秒)', fontsize=12)
            ax.set_ylabel('功耗 (mW)', fontsize=12)
            ax.set_title('功耗变化', fontsize=14, fontweight='bold')
            ax.grid(True, alpha=0.3)
            ax.legend(fontsize=11)
        else:
            # 如果没有power_mw，尝试使用current_ua
            current_data = power_df[power_df['power_source'].str.contains('current_ua', case=False, na=False)]
            if not current_data.empty:
                ax.plot(current_data['time_relative_s'], current_data['current_ma'], 
                       linewidth=2, color='green', label='功耗电流')
                ax.set_xlabel('时间 (秒)', fontsize=12)
                ax.set_ylabel('电流 (mA)', fontsize=12)
                ax.set_title('功耗变化 (电流)', fontsize=14, fontweight='bold')
                ax.grid(True, alpha=0.3)
                ax.legend(fontsize=11)
            else:
                ax.text(0.5, 0.5, '无功耗数据', ha='center', va='center', 
                       transform=ax.transAxes, fontsize=14)
                ax.set_title('功耗变化', fontsize=14, fontweight='bold')
    else:
        ax.text(0.5, 0.5, '无功耗数据', ha='center', va='center', 
               transform=ax.transAxes, fontsize=14)
        ax.set_title('功耗变化', fontsize=14, fontweight='bold')
    
    duration_ms = results.get('cold_start_duration_ms', 0)
    duration_s = results.get('cold_start_duration_s', 0)
    fig.suptitle(f'功耗时间线 - 启动时长: {duration_ms:.2f} ms ({duration_s:.3f} 秒)', 
                fontsize=14, fontweight='bold', y=0.98)
    
    plt.tight_layout()
    
    if output_path:
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"✅ 功耗图表已保存到: {output_path}")
    
    plt.close()


def plot_cpu_scheduling(results, output_path=None):
    """
    绘制应用进程在哪个CPU上运行的调度图（类似Perfetto的CPU调度视图）
    每个CPU一行，显示应用进程在该CPU上运行的时间段
    
    Args:
        results: 分析结果字典
        output_path: 输出图片路径
    """
    if 'cpu_scheduling' not in results or results['cpu_scheduling'].empty:
        print("⚠️  无CPU调度数据")
        return
    
    cpu_sched_df = results['cpu_scheduling'].copy()
    
    # 获取所有CPU编号并排序
    if 'cpu' in cpu_sched_df.columns:
        cpu_list = sorted(cpu_sched_df['cpu'].unique())
        cpu_list = cpu_list[:8]  # 最多8个CPU
    else:
        print("⚠️  CPU调度数据中没有cpu列")
        return
    
    # 如果没有数据，返回
    if len(cpu_list) == 0:
        print("⚠️  未找到CPU调度数据")
        return
    
    # 创建垂直堆叠的子图（每个CPU一行）
    fig, axes = plt.subplots(len(cpu_list), 1, figsize=(14, 1.8 * len(cpu_list)), sharex=True)
    
    # 如果只有一个CPU，axes不是数组
    if len(cpu_list) == 1:
        axes = [axes]
    
    # 为每个CPU绘制调度信息
    colors = plt.cm.tab20(np.linspace(0, 1, 20))  # 使用更多颜色以区分不同线程
    
    # 获取所有唯一的线程
    if 'utid' in cpu_sched_df.columns:
        unique_threads = sorted(cpu_sched_df['utid'].unique())
    else:
        unique_threads = [0]
    
    # 为每个线程分配颜色和Y位置
    thread_info = {}
    thread_count = len(unique_threads)
    if thread_count > 0:
        y_step = 0.8 / max(thread_count, 1)  # 在Y轴范围内均匀分布线程
        for i, utid in enumerate(unique_threads):
            thread_info[utid] = {
                'color': colors[i % len(colors)],
                'y_pos': -0.4 + i * y_step,
                'y_height': y_step * 0.8  # 线程条的高度
            }
    
    for idx, cpu in enumerate(cpu_list):
        ax = axes[idx]
        cpu_data = cpu_sched_df[cpu_sched_df['cpu'] == cpu].sort_values('time_relative_s')
        
        if len(cpu_data) > 0:
            # 检查是否有duration_ns字段
            has_duration = 'duration_ns' in cpu_data.columns and cpu_data['duration_ns'].notna().any()
            
            # 对每个线程，绘制该线程在该CPU上运行的时间段
            for i, utid in enumerate(cpu_data['utid'].unique()):
                thread_data = cpu_data[cpu_data['utid'] == utid].sort_values('time_relative_s')
                thread_name = thread_data['thread_name'].iloc[0] if 'thread_name' in thread_data.columns and len(thread_data) > 0 else f'TID-{utid}'
                thread_color = thread_info.get(utid, {}).get('color', 'blue')
                y_pos = thread_info.get(utid, {}).get('y_pos', 0)
                y_height = thread_info.get(utid, {}).get('y_height', 0.1)
                
                # 只在第一个CPU的子图中添加图例标签
                label = thread_name if idx == 0 else ""
                first_bar = True  # 标记是否为第一个时间段
                
                if has_duration:
                    # 如果有持续时间信息，绘制水平条（类似Gantt图）
                    for _, row in thread_data.iterrows():
                        start_time = row['time_relative_s']
                        duration_ns = row.get('duration_ns', 0)
                        if pd.isna(duration_ns):
                            duration_ns = 0
                        duration_s = duration_ns / 1e9 if duration_ns > 0 else 0
                        if duration_s > 0:
                            # 绘制水平条，只在第一个时间段添加标签
                            current_label = label if first_bar else ""
                            ax.barh(y_pos, duration_s, left=start_time, 
                                   height=y_height, color=thread_color, 
                                   alpha=0.7, edgecolor='black', linewidth=0.5,
                                   label=current_label)
                            first_bar = False  # 后续时间段不再添加标签
                else:
                    # 如果没有持续时间信息，使用散点图
                    ax.scatter(thread_data['time_relative_s'], 
                              [y_pos] * len(thread_data),
                              c=[thread_color], 
                              s=15, 
                              alpha=0.7,
                              label=label)
            
            # 标记启动区间
            start_window_end = results.get('start_window_end_s', 0)
            if start_window_end > 0:
                # 添加半透明背景标记启动区间
                ax.axvspan(0, start_window_end, alpha=0.1, color='yellow', zorder=0)
        
        ax.set_ylabel(f'CPU {int(cpu)}', fontsize=10, fontweight='bold')
        ax.set_ylim(-0.5, 0.5)  # 固定Y轴范围
        ax.set_yticks([])  # 不显示Y轴刻度
        ax.grid(True, alpha=0.3, linestyle='--', axis='x', zorder=1)
        ax.spines['left'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['top'].set_visible(False)
        
        # 只在第一个CPU的子图显示图例
        if idx == 0:
            # 简化图例：只显示前15个线程，避免图例过于拥挤
            handles, labels = ax.get_legend_handles_labels()
            # 去重图例
            seen_labels = set()
            unique_handles = []
            unique_labels = []
            for h, l in zip(handles, labels):
                if l not in seen_labels and l:  # 只添加非空标签
                    seen_labels.add(l)
                    unique_handles.append(h)
                    unique_labels.append(l)
            
            if len(unique_handles) > 15:
                ax.legend(unique_handles[:15], unique_labels[:15], 
                         loc='upper right', fontsize=7, ncol=2, 
                         framealpha=0.9)
            elif len(unique_handles) > 0:
                ax.legend(unique_handles, unique_labels, 
                         loc='upper right', fontsize=7, ncol=2,
                         framealpha=0.9)
    
    # 只在最下面的子图显示X轴标签
    axes[-1].set_xlabel('时间 (秒)', fontsize=12, fontweight='bold')
    
    # 添加总标题
    duration_ms = results.get('cold_start_duration_ms', 0)
    duration_s = results.get('cold_start_duration_s', 0)
    fig.suptitle(f'CPU调度时间线 - 启动时长: {duration_ms:.2f} ms ({duration_s:.3f} 秒)', 
                fontsize=14, fontweight='bold', y=0.995)
    
    # 调整布局
    plt.subplots_adjust(left=0.1, right=0.95, top=0.97, bottom=0.05, hspace=0.3)
    
    if output_path:
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"✅ CPU调度图表已保存到: {output_path}")
    
    plt.close()


def plot_cpu_utilization(results, output_path=None):
    """
    绘制8个CPU利用率图（垂直堆叠，类似Perfetto风格）
    每100毫秒时间窗口内每个CPU的利用率
    
    Args:
        results: 分析结果字典
        output_path: 输出图片路径
    """
    if 'cpu_utilization' not in results or results['cpu_utilization'].empty:
        print("⚠️  无CPU利用率数据")
        return
    
    cpu_util_df = results['cpu_utilization']
    
    # 获取所有CPU编号并排序
    if 'cpu' in cpu_util_df.columns:
        cpu_list = sorted(cpu_util_df['cpu'].unique())
        cpu_list = cpu_list[:8]  # 最多8个CPU
    else:
        print("⚠️  CPU利用率数据中没有cpu列")
        return
    
    # 创建垂直堆叠的子图（8行1列）
    fig, axes = plt.subplots(len(cpu_list), 1, figsize=(14, 2.5 * len(cpu_list)), sharex=True)
    
    # 如果只有一个CPU，axes不是数组
    if len(cpu_list) == 1:
        axes = [axes]
    
    # 为每个CPU绘制图表
    colors = plt.cm.tab10(np.linspace(0, 1, len(cpu_list)))
    for idx, cpu in enumerate(cpu_list):
        ax = axes[idx]
        cpu_data = cpu_util_df[cpu_util_df['cpu'] == cpu].sort_values('time_relative_s')
        
        if len(cpu_data) > 0:
            # 绘制利用率曲线（转换为百分比）
            ax.plot(cpu_data['time_relative_s'], cpu_data['cpu_util'] * 100, 
                   linewidth=1.5, color=colors[idx], label=f'CPU {int(cpu)}')
            
            # 标记启动区间
            start_window_start = results.get('start_window_start_s', 0)
            start_window_end = results.get('start_window_end_s', 0)
            if start_window_end > 0:
                # 添加半透明背景标记启动区间
                ax.axvspan(0, start_window_end, alpha=0.2, color='yellow', label='启动区间')
            
            # 设置Y轴范围：利用率在0-100%之间
            y_min = 0
            y_max = min(100, cpu_data['cpu_util'].max() * 100 * 1.1)  # 添加10%边距，但不超过100%
            if y_max < 10:
                y_max = 100  # 如果最大值很小，显示到100%
            ax.set_ylim(y_min, y_max)
        else:
            # 如果没有数据，设置默认范围
            ax.set_ylim(0, 100)
        
        ax.set_ylabel(f'CPU {int(cpu)}\n利用率 (%)', fontsize=10, fontweight='bold')
        ax.grid(True, alpha=0.3, linestyle='--')
        # 只在第一个CPU的子图显示完整的图例（包含启动区间）
        if idx == 0:
            ax.legend(loc='upper right', fontsize=9)
        else:
            # 其他CPU只显示CPU标签，不显示启动区间标签（避免重复）
            handles, labels = ax.get_legend_handles_labels()
            # 只保留CPU相关的图例项
            cpu_handles = [h for h, l in zip(handles, labels) if l.startswith('CPU')]
            cpu_labels = [l for l in labels if l.startswith('CPU')]
            if cpu_handles:
                ax.legend(cpu_handles, cpu_labels, loc='upper right', fontsize=9)
        # 确保Y轴刻度标签可见
        ax.tick_params(axis='y', labelsize=9, left=True, labelleft=True)
        ax.ticklabel_format(style='plain', axis='y', useOffset=False)  # 使用普通数字格式，不用科学计数法
        # 确保Y轴标签显示（特别是前几个CPU）
        ax.yaxis.set_visible(True)
        plt.setp(ax.get_yticklabels(), visible=True)  # 强制显示Y轴刻度标签
    
    # 只在最下面的子图显示X轴标签
    axes[-1].set_xlabel('时间 (秒)', fontsize=12, fontweight='bold')
    
    # 添加总标题
    duration_ms = results.get('cold_start_duration_ms', 0)
    duration_s = results.get('cold_start_duration_s', 0)
    fig.suptitle(f'CPU利用率时间线 - 启动时长: {duration_ms:.2f} ms ({duration_s:.3f} 秒)', 
                fontsize=14, fontweight='bold', y=0.995)
    
    # 调整布局，确保Y轴标签有足够空间显示（特别是前几个CPU）
    plt.subplots_adjust(left=0.12, right=0.95, top=0.97, bottom=0.05, hspace=0.25)
    
    if output_path:
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"✅ CPU利用率图表已保存到: {output_path}")
    
    plt.close()


def plot_cold_start_analysis(results, output_path=None, show_plot=True):
    """
    绘制冷启动分析图表（生成多张独立图片）
    
    Args:
        results: 分析结果字典
        output_path: 输出图片基础路径（会生成多个文件）
        show_plot: 是否显示图表（已废弃，使用Agg后端）
    """
    if output_path is None:
        output_path = 'cold_start_analysis'
    
    # 获取基础路径和目录
    base_dir = os.path.dirname(output_path) if os.path.dirname(output_path) else '.'
    base_name = os.path.basename(output_path)
    if base_name.endswith('.png'):
        base_name = base_name[:-4]
    
    # 生成各个独立的图表
    cpu_path = os.path.join(base_dir, f'{base_name}_cpu_frequency.png')
    gpu_path = os.path.join(base_dir, f'{base_name}_gpu_frequency.png')
    voltage_current_path = os.path.join(base_dir, f'{base_name}_voltage_current.png')
    power_path = os.path.join(base_dir, f'{base_name}_power.png')
    cpu_sched_path = os.path.join(base_dir, f'{base_name}_cpu_scheduling.png')
    cpu_util_path = os.path.join(base_dir, f'{base_name}_cpu_utilization.png')
    
    # 1. CPU频率图（8个CPU垂直堆叠）
    plot_cpu_frequency(results, cpu_path)
    
    # 2. GPU频率图
    plot_gpu_frequency(results, gpu_path)
    
    # 3. 电压和电流图（分开两张）
    plot_voltage_current(results, voltage_current_path)
    
    # 4. 功耗图
    plot_power(results, power_path)
    
    # 5. CPU调度图（显示app在哪个CPU上运行）
    plot_cpu_scheduling(results, cpu_sched_path)
    
    # 6. CPU利用率图（8个CPU垂直堆叠）
    plot_cpu_utilization(results, cpu_util_path)
    
    print(f"\n✅ 所有图表已生成完成！")
    print(f"   - CPU频率: {cpu_path}")
    print(f"   - GPU频率: {gpu_path}")
    print(f"   - 电压: {voltage_current_path.replace('.png', '_voltage.png')}")
    print(f"   - 电流: {voltage_current_path.replace('.png', '_current.png')}")
    print(f"   - 功耗: {power_path}")
    print(f"   - CPU调度: {cpu_sched_path}")
    print(f"   - CPU利用率: {cpu_util_path}")


def plot_summary_statistics(results, output_path=None, show_plot=True):
    """
    绘制统计摘要图表
    
    Args:
        results: 分析结果字典
        output_path: 输出图片路径
        show_plot: 是否显示图表
    """
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle('App冷启动统计摘要', fontsize=16, fontweight='bold')
    
    # 1. 冷启动时长
    ax1 = axes[0, 0]
    duration_ms = results.get('cold_start_duration_ms', 0)
    duration_s = results.get('cold_start_duration_s', 0)
    ax1.barh([0], [duration_ms], color='steelblue', height=0.5)
    ax1.set_xlabel('时长 (ms)', fontsize=11)
    ax1.set_title(f'冷启动时长: {duration_ms:.2f} ms', fontsize=12, fontweight='bold')
    ax1.set_yticks([])
    ax1.grid(True, alpha=0.3, axis='x')
    
    # 2. CPU频率统计
    ax2 = axes[0, 1]
    if 'cpu_frequency' in results and not results['cpu_frequency'].empty:
        cpu_df = results['cpu_frequency']
        avg_freq = cpu_df['frequency'].mean()
        max_freq = cpu_df['frequency'].max()
        min_freq = cpu_df['frequency'].min()
        stats = ['平均频率', '最大频率', '最小频率']
        values = [avg_freq, max_freq, min_freq]
        colors = ['skyblue', 'orange', 'lightgreen']
        bars = ax2.bar(stats, values, color=colors, alpha=0.7)
        ax2.set_ylabel('频率', fontsize=11)
        ax2.set_title('CPU频率统计', fontsize=12, fontweight='bold')
        ax2.grid(True, alpha=0.3, axis='y')
        # 添加数值标签
        for bar, val in zip(bars, values):
            height = bar.get_height()
            ax2.text(bar.get_x() + bar.get_width()/2., height,
                    f'{val:.0f}', ha='center', va='bottom', fontsize=9)
    else:
        ax2.text(0.5, 0.5, '无数据', ha='center', va='center', 
                transform=ax2.transAxes, fontsize=12)
        ax2.set_title('CPU频率统计', fontsize=12, fontweight='bold')
    
    # 3. GPU频率统计
    ax3 = axes[1, 0]
    if 'gpu_frequency' in results and not results['gpu_frequency'].empty:
        gpu_df = results['gpu_frequency']
        avg_freq = gpu_df['frequency'].mean()
        max_freq = gpu_df['frequency'].max()
        min_freq = gpu_df['frequency'].min()
        stats = ['平均频率', '最大频率', '最小频率']
        values = [avg_freq, max_freq, min_freq]
        colors = ['salmon', 'coral', 'mistyrose']
        bars = ax3.bar(stats, values, color=colors, alpha=0.7)
        ax3.set_ylabel('频率', fontsize=11)
        ax3.set_title('GPU频率统计', fontsize=12, fontweight='bold')
        ax3.grid(True, alpha=0.3, axis='y')
        # 添加数值标签
        for bar, val in zip(bars, values):
            height = bar.get_height()
            ax3.text(bar.get_x() + bar.get_width()/2., height,
                    f'{val:.0f}', ha='center', va='bottom', fontsize=9)
    else:
        ax3.text(0.5, 0.5, '无数据', ha='center', va='center', 
                transform=ax3.transAxes, fontsize=12)
        ax3.set_title('GPU频率统计', fontsize=12, fontweight='bold')
    
    # 4. 功耗统计
    ax4 = axes[1, 1]
    if 'power' in results and not results['power'].empty:
        power_df = results['power']
        avg_current = power_df['current_ma'].mean()
        max_current = power_df['current_ma'].max()
        min_current = power_df['current_ma'].min()
        stats = ['平均电流', '最大电流', '最小电流']
        values = [avg_current, max_current, min_current]
        colors = ['lightgreen', 'darkgreen', 'palegreen']
        bars = ax4.bar(stats, values, color=colors, alpha=0.7)
        ax4.set_ylabel('电流 (mA)', fontsize=11)
        ax4.set_title('功耗统计', fontsize=12, fontweight='bold')
        ax4.grid(True, alpha=0.3, axis='y')
        # 添加数值标签
        for bar, val in zip(bars, values):
            height = bar.get_height()
            ax4.text(bar.get_x() + bar.get_width()/2., height,
                    f'{val:.1f} mA', ha='center', va='bottom', fontsize=9)
    else:
        ax4.text(0.5, 0.5, '无数据', ha='center', va='center', 
                transform=ax4.transAxes, fontsize=12)
        ax4.set_title('功耗统计', fontsize=12, fontweight='bold')
    
    plt.tight_layout()
    
    if output_path:
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"✅ 统计图表已保存到: {output_path}")
    
    # 注意：使用Agg后端时不支持plt.show()，图表已保存到文件
    plt.close()


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='绘制App冷启动分析结果')
    parser.add_argument('results', help='分析结果目录或trace文件路径')
    parser.add_argument('--trace_file', help='如果results是trace文件，需要提供包名')
    parser.add_argument('--package_name', help='应用包名(当使用trace_file时)')
    parser.add_argument('--output', help='输出图片路径', default='cold_start_analysis.png')
    parser.add_argument('--summary', help='输出统计图表路径', default='cold_start_summary.png')
    parser.add_argument('--no-show', action='store_true', help='不显示图表，只保存')
    
    args = parser.parse_args()
    
    # 如果是trace文件，先进行分析
    if args.trace_file and args.package_name:
        from analyze_trace import analyze_cold_start_trace
        results_dir = os.path.dirname(args.output) if args.output else './'
        results = analyze_cold_start_trace(args.trace_file, args.package_name, results_dir)
    else:
        # 从目录加载结果
        if os.path.isdir(args.results):
            results = load_analysis_results(args.results)
        else:
            print("错误: 请提供结果目录或使用--trace_file和--package_name参数")
            return
    
    if not results:
        print("❌ 无法加载分析结果")
        return
    
    # 绘制详细分析图表
    plot_cold_start_analysis(results, args.output, not args.no_show)
    
    # 绘制统计摘要图表
    if args.summary:
        plot_summary_statistics(results, args.summary, not args.no_show)


if __name__ == "__main__":
    main()
