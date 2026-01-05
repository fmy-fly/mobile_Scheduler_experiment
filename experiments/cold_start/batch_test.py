"""
批量测试多个App的冷启动时长
支持自定义频率设置
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


# ============================================================================
# 配置区域 - 在这里手动设置频率参数
# ============================================================================

# ====== CPU和GPU可用频率参考表 ======
# 注意：以下频率表是从设备查询得到的实际可用频率值
# CPU频率单位：KHz（千赫兹），例如 1800000 = 1800 MHz = 1.8 GHz
# GPU频率单位：Hz（赫兹），例如 150000000 = 150 MHz

# CPU可用频率表（KHz单位）
# 格式: {policy_id: [可用频率列表(KHz)]}
CPU_AVAILABLE_FREQUENCIES = {
    '0': [820000, 955000, 1098000, 1197000, 1328000, 1425000, 1548000, 1696000, 1849000, 1950000],  # CPUs: 0 1 2 3, 范围: 820000-1950000 KHz
    '4': [357000, 578000, 648000, 787000, 910000, 1065000, 1221000, 1328000, 1418000, 1549000, 1795000, 1945000, 2130000, 2245000, 2367000, 2450000, 2600000],  # CPUs: 4 5 6, 范围: 357000-2600000 KHz
    '7': [700000, 1164000, 1396000, 1557000, 1745000, 1885000, 1999000, 2147000, 2294000, 2363000, 2499000, 2687000, 2802000, 2914000, 2943000, 2970000, 3015000, 3105000],  # CPUs: 7, 范围: 700000-3105000 KHz
}

# GPU可用频率表（Hz单位）
GPU_AVAILABLE_FREQUENCIES = {
    'freqs': [940000, 890000, 850000, 807000, 723000, 649000, 580000, 521000, 467000, 419000, 376000, 337000, 302000, 150000],  # 频率列表（Hz）
    'min': 150000,  # 最小频率（Hz） = 150 MHz
    'max': 940000,  # 最大频率（Hz） = 940 MHz
}

# 频率表使用说明：
# 1. CPU频率配置时，请从 CPU_AVAILABLE_FREQUENCIES 中选择值（KHz单位）
#    例如: {"0": 1849000, "4": 2600000}  # policy0使用1849000 KHz (1.849 GHz), policy4使用2600000 KHz (2.6 GHz)
# 2. GPU频率配置时，请从 GPU_AVAILABLE_FREQUENCIES['freqs'] 中选择值（Hz单位）
#    例如: 850000  # 使用850 MHz（注意：这是Hz单位，850000 Hz = 850 MHz）
# 3. 如果需要更新频率表，运行: python experiments/cold_start/query_freq_list.py

# ====== App列表 ======
APPS = {
    "play商店": "com.android.vending",
    "Gmail": "com.google.android.gm",
    "youtube": "com.google.android.youtube",
    "抖音": "com.ss.android.ugc.aweme",
    "小红书": "com.xingin.xhs",
    "微信": "com.tencent.mm",
    "QQ": "com.tencent.mobileqq",
}

# ====== 每个App的个性化频率配置 ======
# 格式: {app_name: {"cpu_freq_settings": {...}, "gpu_freq_setting": ...}}
# 
# CPU频率设置（KHz单位）：
#   - 格式1（固定频率）: {policy_id: freq_khz} 
#     例如: {"0": 1800000, "4": 2300000}
#   - 格式2（频率范围）: {policy_id: {"min": min_khz, "max": max_khz}}
#     例如: {"0": {"min": 1200000, "max": 2300000}}
#   - 格式3（时间段频率）: {"time_based": True, "periods": [...]}
#     例如: {"time_based": True, "periods": [
#         {"start": 0.0, "end": 0.2, "cpu_freq": {"0": 1800000, "4": 2300000}, "gpu_freq": 150000000},
#         {"start": 0.2, "end": 0.4, "cpu_freq": {"0": 1500000, "4": 2000000}, "gpu_freq": 100000000}
#     ]}
#     说明: start/end是相对于App启动时间的秒数
#
# GPU频率设置（Hz单位）：
#   - 单个数值（固定频率）: 150000000
#   - 范围设置（dict）: {"min": 100000000, "max": 850000000}
#   - 如果使用时间段频率配置，GPU频率在periods中指定
#
# 如果某个App的配置为None，表示使用默认频率（系统调度）
# 如果某个App不在这个字典中，也会使用默认频率
#
# ====== 频率配置策略说明 ======
# 设计原则：平衡启动速度和能耗
# 1. 启动阶段（0-0.3秒）：使用较高频率快速完成关键初始化
# 2. 稳定阶段（0.3秒后）：降低频率节省能耗
# 3. 根据App复杂度调整：轻量级App使用保守配置，重度App使用积极配置
#
APP_FREQ_CONFIGS = {
    # ====== 轻量级App：Gmail ======
    # 策略：启动阶段适中频率，快速降低以节省能耗
    "Gmail": {
        "cpu_freq_settings": {
            "time_based": True,
            "periods": [
                {
                    "start": 0.0, 
                    "end": 0.25,  # 启动阶段：前250ms
                    "cpu_freq": {
                        "0": 1696000,  # 小核：1.696 GHz（中等偏高）
                        "4": 2130000,  # 中核：2.13 GHz（较高）
                        "7": 2687000   # 大核：2.687 GHz（较高）
                    },
                    "gpu_freq": 649000  # GPU: 649 MHz（中等）
                },
                {
                    "start": 0.25,
                    "end": 10.0,  # 稳定阶段：降低频率节省能耗
                    "cpu_freq": {
                        "0": 1328000,  # 小核：1.328 GHz（中等）
                        "4": 1549000,  # 中核：1.549 GHz（中等偏低）
                        "7": 2147000   # 大核：2.147 GHz（中等）
                    },
                    "gpu_freq": 419000  # GPU: 419 MHz（较低）
                }
            ]
        },
        "gpu_freq_setting": None
    },
    
    # ====== 中等复杂度App：Play商店、YouTube ======
    # 策略：启动阶段较高频率，稳定后适度降低
    "play商店": {
        "cpu_freq_settings": {
            "time_based": True,
            "periods": [
                {
                    "start": 0.0,
                    "end": 0.3,  # 启动阶段：前300ms
                    "cpu_freq": {
                        "0": 1849000,  # 小核：1.849 GHz（高）
                        "4": 2367000,  # 中核：2.367 GHz（高）
                        "7": 2914000   # 大核：2.914 GHz（高）
                    },
                    "gpu_freq": 723000  # GPU: 723 MHz（中高）
                },
                {
                    "start": 0.3,
                    "end": 10.0,  # 稳定阶段
                    "cpu_freq": {
                        "0": 1548000,  # 小核：1.548 GHz（中等）
                        "4": 1945000,  # 中核：1.945 GHz（中等）
                        "7": 2499000   # 大核：2.499 GHz（中等偏高）
                    },
                    "gpu_freq": 467000  # GPU: 467 MHz（中等）
                }
            ]
        },
        "gpu_freq_setting": None
    },
    
    "youtube": {
        "cpu_freq_settings": {
            "time_based": True,
            "periods": [
                {
                    "start": 0.0,
                    "end": 0.3,  # 启动阶段
                    "cpu_freq": {
                        "0": 1849000,  # 小核：1.849 GHz
                        "4": 2245000,  # 中核：2.245 GHz
                        "7": 2914000   # 大核：2.914 GHz
                    },
                    "gpu_freq": 723000  # GPU: 723 MHz
                },
                {
                    "start": 0.3,
                    "end": 10.0,  # 稳定阶段
                    "cpu_freq": {
                        "0": 1548000,  # 小核：1.548 GHz
                        "4": 1795000,  # 中核：1.795 GHz
                        "7": 2363000   # 大核：2.363 GHz
                    },
                    "gpu_freq": 467000  # GPU: 467 MHz
                }
            ]
        },
        "gpu_freq_setting": None
    },
    
    # ====== 重度App：抖音、小红书、微信、QQ ======
    # 策略：启动阶段最高频率快速完成，稳定后适度降低
    "抖音": {
        "cpu_freq_settings": {
            "time_based": True,
            "periods": [
                {
                    "start": 0.0,
                    "end": 0.4,  # 启动阶段：前400ms（重度App需要更长启动时间）
                    "cpu_freq": {
                        "0": 1950000,  # 小核：1.95 GHz（最高）
                        "4": 2450000,  # 中核：2.45 GHz（高）
                        "7": 3015000   # 大核：3.015 GHz（很高）
                    },
                    "gpu_freq": 850000  # GPU: 850 MHz（高）
                },
                {
                    "start": 0.4,
                    "end": 10.0,  # 稳定阶段
                    "cpu_freq": {
                        "0": 1696000,  # 小核：1.696 GHz（中等偏高）
                        "4": 2130000,  # 中核：2.13 GHz（中等偏高）
                        "7": 2687000   # 大核：2.687 GHz（中等偏高）
                    },
                    "gpu_freq": 521000  # GPU: 521 MHz（中等）
                }
            ]
        },
        "gpu_freq_setting": None
    },
    
    "小红书": {
        "cpu_freq_settings": {
            "time_based": True,
            "periods": [
                {
                    "start": 0.0,
                    "end": 0.4,  # 启动阶段
                    "cpu_freq": {
                        "0": 1950000,  # 小核：1.95 GHz
                        "4": 2450000,  # 中核：2.45 GHz
                        "7": 3015000   # 大核：3.015 GHz
                    },
                    "gpu_freq": 850000  # GPU: 850 MHz
                },
                {
                    "start": 0.4,
                    "end": 10.0,  # 稳定阶段
                    "cpu_freq": {
                        "0": 1696000,  # 小核：1.696 GHz
                        "4": 2130000,  # 中核：2.13 GHz
                        "7": 2687000   # 大核：2.687 GHz
                    },
                    "gpu_freq": 521000  # GPU: 521 MHz
                }
            ]
        },
        "gpu_freq_setting": None
    },
    
    "微信": {
        "cpu_freq_settings": {
            "time_based": True,
            "periods": [
                {
                    "start": 0.0,
                    "end": 0.35,  # 启动阶段
                    "cpu_freq": {
                        "0": 1950000,  # 小核：1.95 GHz
                        "4": 2367000,  # 中核：2.367 GHz
                        "7": 2970000   # 大核：2.97 GHz
                    },
                    "gpu_freq": 807000  # GPU: 807 MHz（中高）
                },
                {
                    "start": 0.35,
                    "end": 10.0,  # 稳定阶段
                    "cpu_freq": {
                        "0": 1696000,  # 小核：1.696 GHz
                        "4": 1945000,  # 中核：1.945 GHz
                        "7": 2687000   # 大核：2.687 GHz
                    },
                    "gpu_freq": 467000  # GPU: 467 MHz
                }
            ]
        },
        "gpu_freq_setting": None
    },
    
    "QQ": {
        "cpu_freq_settings": {
            "time_based": True,
            "periods": [
                {
                    "start": 0.0,
                    "end": 0.35,  # 启动阶段
                    "cpu_freq": {
                        "0": 1950000,  # 小核：1.95 GHz
                        "4": 2367000,  # 中核：2.367 GHz
                        "7": 2970000   # 大核：2.97 GHz
                    },
                    "gpu_freq": 807000  # GPU: 807 MHz
                },
                {
                    "start": 0.35,
                    "end": 10.0,  # 稳定阶段
                    "cpu_freq": {
                        "0": 1696000,  # 小核：1.696 GHz
                        "4": 1945000,  # 中核：1.945 GHz
                        "7": 2687000   # 大核：2.687 GHz
                    },
                    "gpu_freq": 467000  # GPU: 467 MHz
                }
            ]
        },
        "gpu_freq_setting": None
    }
}

# ============================================================================
# 以下为脚本代码，无需修改
# ============================================================================


def batch_test_apps(apps=None, 
                   experiment_name="BatchTest",
                   trace_duration=30,
                   config_file="/data/misc/perfetto-configs/HardwareInfo.pbtx",
                   max_frequency=False,  # 是否使用最大频率模式（覆盖所有App的个性化配置）
                   analyze=True,
                   output_dir=None):
    """
    批量测试多个App的冷启动时长
    
    Args:
        apps: 要测试的App列表，格式为 {app_name: package_name}，如果为None则测试所有App
        experiment_name: 实验名称
        trace_duration: 追踪时长(秒)
        config_file: perfetto配置文件路径
        max_frequency: 是否设置CPU/GPU到最大频率（True时会覆盖所有App的个性化配置）
        analyze: 是否自动分析trace文件
        output_dir: 输出目录
    
    Returns:
        dict: 测试结果，包含每个App的启动时长等信息
    """
    if apps is None:
        apps = APPS
    
    print("=" * 80)
    print("📱 批量测试App冷启动时长")
    print("=" * 80)
    print(f"📋 测试App数量: {len(apps)}")
    
    if max_frequency:
        print(f"⚙️  频率模式: 最大频率（覆盖所有App的个性化配置）")
    else:
        print(f"⚙️  频率模式: 每个App使用个性化配置")
        # 显示每个App的配置
        for app_name in apps.keys():
            if app_name in APP_FREQ_CONFIGS:
                config = APP_FREQ_CONFIGS[app_name]
                cpu_cfg = config.get("cpu_freq_settings")
                gpu_cfg = config.get("gpu_freq_setting")
                if cpu_cfg or gpu_cfg:
                    print(f"   {app_name}: ", end="")
                    if cpu_cfg:
                        print(f"CPU={cpu_cfg} ", end="")
                    if gpu_cfg:
                        print(f"GPU={gpu_cfg}", end="")
                    print()
                else:
                    print(f"   {app_name}: 默认频率")
            else:
                print(f"   {app_name}: 默认频率（未配置）")
    
    print(f"📊 是否自动分析: {'是' if analyze else '否'}")
    print("=" * 80)
    
    results = {}
    failed_apps = []
    
    for idx, (app_name, package_name) in enumerate(apps.items(), 1):
        print("\n" + "=" * 80)
        print(f"[{idx}/{len(apps)}] 测试: {app_name} ({package_name})")
        print("=" * 80)
        
        try:
            # 确定当前App的频率配置
            if max_frequency:
                # 使用最大频率模式（覆盖所有个性化配置）
                app_max_freq = True
                app_cpu_settings = None
                app_gpu_setting = None
            elif app_name in APP_FREQ_CONFIGS:
                # 使用该App的个性化配置
                app_config = APP_FREQ_CONFIGS[app_name]
                app_max_freq = False
                app_cpu_settings = app_config.get("cpu_freq_settings")
                app_gpu_setting = app_config.get("gpu_freq_setting")
            else:
                # App未配置，使用默认频率
                app_max_freq = False
                app_cpu_settings = None
                app_gpu_setting = None
            
            # 运行实验
            trace_file = run_cold_start_experiment(
                package_name=package_name,
                experiment_name=f"{experiment_name}_{app_name}",
                trace_duration=trace_duration,
                config_file=config_file,
                max_frequency=app_max_freq,
                cpu_freq_settings=app_cpu_settings,
                gpu_freq_setting=app_gpu_setting
            )
            
            if not trace_file:
                print(f"❌ {app_name}: 实验失败（无法获取trace文件）")
                failed_apps.append(app_name)
                results[app_name] = {
                    'package_name': package_name,
                    'status': 'failed',
                    'error': '无法获取trace文件'
                }
                continue
            
            # 分析trace文件（如果需要）
            if analyze:
                print(f"\n📊 分析 {app_name} 的trace数据...")
                try:
                    app_output_dir = None
                    if output_dir:
                        app_output_dir = os.path.join(output_dir, app_name)
                    
                    analysis_results = analyze_cold_start_trace(
                        trace_path=trace_file,
                        package_name=package_name,
                        output_dir=app_output_dir
                    )
                    
                    if analysis_results:
                        results[app_name] = {
                            'package_name': package_name,
                            'status': 'success',
                            'trace_file': trace_file,
                            'cold_start_duration_ms': analysis_results.get('cold_start_duration_ms'),
                            'cold_start_duration_s': analysis_results.get('cold_start_duration_s'),
                            'app_start_time_ns': analysis_results.get('app_start_time_ns'),
                            'app_drawn_time_ns': analysis_results.get('app_drawn_time_ns'),
                            # 启动区间内的功耗统计
                            'total_power_consumption_j': analysis_results.get('total_power_consumption_j'),
                            'total_power_consumption_mj': analysis_results.get('total_power_consumption_mj'),
                            'avg_power_mw': analysis_results.get('avg_power_mw'),
                            'max_power_mw': analysis_results.get('max_power_mw'),
                            'min_power_mw': analysis_results.get('min_power_mw'),
                            'avg_current_ma': analysis_results.get('avg_current_ma'),
                            'max_current_ma': analysis_results.get('max_current_ma'),
                            'min_current_ma': analysis_results.get('min_current_ma'),
                            'avg_voltage_v': analysis_results.get('avg_voltage_v'),
                            'max_voltage_v': analysis_results.get('max_voltage_v'),
                            'min_voltage_v': analysis_results.get('min_voltage_v'),
                        }
                        print(f"✅ {app_name}: 启动时长 = {analysis_results.get('cold_start_duration_ms', 0):.2f} ms")
                    else:
                        results[app_name] = {
                            'package_name': package_name,
                            'status': 'failed',
                            'trace_file': trace_file,
                            'error': '分析失败'
                        }
                        print(f"⚠️  {app_name}: trace文件已生成，但分析失败")
                except Exception as e:
                    print(f"⚠️  {app_name}: 分析trace时出错: {e}")
                    results[app_name] = {
                        'package_name': package_name,
                        'status': 'failed',
                        'trace_file': trace_file,
                        'error': f'分析出错: {str(e)}'
                    }
            else:
                results[app_name] = {
                    'package_name': package_name,
                    'status': 'success',
                    'trace_file': trace_file
                }
            
            # 测试间隔，避免设备过热
            if idx < len(apps):
                print(f"\n⏳ 等待5秒后继续下一个测试...")
                time.sleep(5)
                
        except Exception as e:
            print(f"❌ {app_name}: 测试失败 - {e}")
            failed_apps.append(app_name)
            results[app_name] = {
                'package_name': package_name,
                'status': 'failed',
                'error': str(e)
            }
    
    # 打印总结
    print("\n" + "=" * 80)
    print("📊 测试总结")
    print("=" * 80)
    
    successful_apps = [name for name, result in results.items() if result.get('status') == 'success']
    print(f"✅ 成功: {len(successful_apps)}/{len(apps)}")
    if failed_apps:
        print(f"❌ 失败: {len(failed_apps)}/{len(apps)}")
        print(f"   失败App: {', '.join(failed_apps)}")
    
    if analyze:
        print("\n📈 启动时长统计:")
        for app_name in successful_apps:
            duration_ms = results[app_name].get('cold_start_duration_ms')
            if duration_ms:
                print(f"   {app_name}: {duration_ms:.2f} ms")
        
        print("\n⚡ 功耗统计（启动区间）:")
        for app_name in successful_apps:
            total_power_j = results[app_name].get('total_power_consumption_j')
            avg_power_mw = results[app_name].get('avg_power_mw')
            avg_current_ma = results[app_name].get('avg_current_ma')
            
            info_parts = []
            if total_power_j is not None:
                info_parts.append(f"总功耗: {total_power_j:.3f} J")
            if avg_power_mw is not None:
                info_parts.append(f"平均功率: {avg_power_mw:.1f} mW")
            if avg_current_ma is not None:
                info_parts.append(f"平均电流: {avg_current_ma:.1f} mA")
            
            if info_parts:
                print(f"   {app_name}: {', '.join(info_parts)}")
            else:
                print(f"   {app_name}: 无功耗数据")
    
    # 保存结果到JSON文件
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results_file = os.path.join(output_dir, f"batch_test_results_{timestamp}.json")
        
        # 准备保存的数据（移除不能序列化的字段）
        save_results = {}
        for app_name, result in results.items():
            save_result = result.copy()
            # 移除可能无法序列化的字段
            if 'trace_file' in save_result:
                save_result['trace_file'] = str(save_result['trace_file'])
            save_results[app_name] = save_result
        
        with open(results_file, 'w', encoding='utf-8') as f:
            json.dump({
                'experiment_name': experiment_name,
                'timestamp': timestamp,
                'frequency_mode': '最大频率' if max_frequency else '个性化配置',
                'max_frequency': max_frequency,
                'results': save_results
            }, f, indent=2, ensure_ascii=False)
        
        print(f"\n💾 结果已保存到: {results_file}")
    
    return results


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description='批量测试多个App的冷启动时长',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
频率配置说明：
  1. 默认情况: 每个App使用代码中配置的个性化频率（APP_FREQ_CONFIGS）
  2. 使用 --max-frequency: 所有App都使用最大频率（覆盖个性化配置）
  
  个性化配置方法：
  在 batch_test.py 文件的 APP_FREQ_CONFIGS 字典中为每个App配置频率
        """
    )
    parser.add_argument('--apps', nargs='+', help='要测试的App名称列表（空格分隔），例如: --apps play商店 微信 QQ。如果不指定则测试所有App')
    parser.add_argument('--experiment-name', default='BatchTest', help='实验名称（默认: BatchTest）')
    parser.add_argument('--duration', type=int, default=30, help='追踪时长(秒)（默认: 30）')
    parser.add_argument('--config', default='/data/misc/perfetto-configs/HardwareInfo.pbtx',
                       help='Perfetto配置文件路径')
    parser.add_argument('--max-frequency', action='store_true',
                       help='设置所有App的CPU/GPU到最大频率（会覆盖个性化配置）')
    parser.add_argument('--no-analyze', action='store_true', help='不自动分析trace文件，只生成trace文件')
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
    
    # 设置默认输出目录
    if not args.output_dir:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(os.path.dirname(script_dir))
        args.output_dir = os.path.join(project_root, "Perfetto", "trace", "traceAnalysis", "results", args.experiment_name)
    
    # 确定频率设置
    max_freq = args.max_frequency  # 是否使用最大频率模式
    
    # 运行批量测试
    results = batch_test_apps(
        apps=apps_to_test,
        experiment_name=args.experiment_name,
        trace_duration=args.duration,
        config_file=args.config,
        max_frequency=max_freq,
        analyze=not args.no_analyze,
        output_dir=args.output_dir
    )
    
    print("\n✅ 批量测试完成!")

