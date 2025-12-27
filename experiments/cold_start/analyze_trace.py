"""
分析Perfetto Trace数据
从trace中查询：冷启动时长、功耗、CPU频率、GPU频率
所有数据都通过查询perfetto trace获取
"""
import os
import sys
from perfetto.trace_processor import TraceProcessor, TraceProcessorConfig
import pandas as pd

# 添加项目根目录到路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
from Perfetto.trace.traceAnalysis.extract_trace_time import ns_to_cst


class ColdStartAnalyzer:
    def __init__(self, trace_path, tp_bin_path=None):
        """
        初始化分析器
        
        Args:
            trace_path: trace文件路径
            tp_bin_path: trace_processor可执行文件路径
        """
        self.trace_path = trace_path
        if not os.path.exists(trace_path):
            raise FileNotFoundError(f"Trace文件不存在: {trace_path}")
        
        # 默认trace_processor路径
        if tp_bin_path is None:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(os.path.dirname(script_dir))  # experiments/cold_start -> experiments -> 项目根目录
            tp_bin_path = os.path.join(project_root, "Perfetto", "configPerfetto", 
                                      "trace_processor_shell.exe")
            tp_bin_path = os.path.normpath(tp_bin_path)
        
        if not os.path.exists(tp_bin_path):
            raise FileNotFoundError(f"Trace processor不存在: {tp_bin_path}")
        
        config = TraceProcessorConfig(bin_path=tp_bin_path)
        self.tp = TraceProcessor(trace=trace_path, config=config)
        self.start_time_ns = None
        self.end_time_ns = None
        
    def get_trace_bounds(self):
        """
        获取trace的时间边界
        使用 TO_REALTIME 函数获取真实时间戳（更准确）
        """
        bounds = self.tp.query("SELECT start_ts, end_ts FROM trace_bounds;")
        row = next(iter(bounds), None)
        if not row:
            return None, None
        
        start_ts = row.start_ts
        end_ts = row.end_ts
        duration_ns = end_ts - start_ts
        
        # 使用 TO_REALTIME 函数转换时间戳（Perfetto内置函数，自动查找最佳时钟同步源）
        real_start_ns = None
        try:
            time_check = self.tp.query(f"SELECT TO_REALTIME({start_ts}) as rt_start")
            rt_row = next(iter(time_check), None)
            
            # 校验转换结果是否有效 (大于 2020年，即 1577836800000000000 纳秒)
            if rt_row and rt_row.rt_start and rt_row.rt_start > 1577836800000000000:
                real_start_ns = rt_row.rt_start
        except Exception:
            # 如果转换失败，使用原始时间戳
            pass
        
        # 如果转换成功，使用真实时间戳；否则使用原始时间戳
        if real_start_ns:
            self.start_time_ns = real_start_ns
            self.end_time_ns = real_start_ns + duration_ns
        else:
            self.start_time_ns = start_ts
            self.end_time_ns = end_ts
        
        return self.start_time_ns, self.end_time_ns
    
    def get_cold_start_duration_from_startups(self, package_name):
        """
        使用 Perfetto 的 android.startup.startups 模块查询冷启动时长（最准确的方法）
        使用 TO_REALTIME 函数转换时间戳为真实时间（用于显示）
        同时返回原始时间戳（用于后续数据查询）
        
        Returns:
            tuple: (duration_ms, start_ts_real, end_ts_real, start_ts_orig, end_ts_orig) 
                   或 (None, None, None, None, None) 如果查询失败
                   start_ts_real/end_ts_real: 转换后的真实时间戳（用于显示）
                   start_ts_orig/end_ts_orig: 原始相对时间戳（用于查询数据）
        """
        try:
            # 首先查询原始时间戳和时长
            query = f"""
            INCLUDE PERFETTO MODULE android.startup.startups;
            SELECT
                dur/1e6 AS duration_ms,
                ts AS start_ts,
                ts + dur AS end_ts
            FROM android_startups
            WHERE package = '{package_name}' AND startup_type = 'cold'
            ORDER BY ts DESC
            LIMIT 1
            """
            result = self.tp.query(query)
            row = next(iter(result), None)
            if row and row.duration_ms:
                start_ts_orig = row.start_ts
                end_ts_orig = row.end_ts
                
                # 使用 TO_REALTIME 函数转换时间戳为真实时间（用于显示）
                real_start_ns = None
                real_end_ns = None
                try:
                    time_check = self.tp.query(f"SELECT TO_REALTIME({start_ts_orig}) as rt_start")
                    rt_row = next(iter(time_check), None)
                    # 校验转换结果是否有效 (大于 2020年，即 1577836800000000000 纳秒)
                    if rt_row and rt_row.rt_start and rt_row.rt_start > 1577836800000000000:
                        real_start_ns = rt_row.rt_start
                        real_end_ns = real_start_ns + (end_ts_orig - start_ts_orig)
                except Exception:
                    pass
                
                # 如果转换失败，使用原始时间戳
                if real_start_ns is None:
                    real_start_ns = start_ts_orig
                    real_end_ns = end_ts_orig
                
                return row.duration_ms, real_start_ns, real_end_ns, start_ts_orig, end_ts_orig
        except Exception as e:
            print(f"   ⚠️  使用 android.startup.startups 查询失败: {e}")
        return None, None, None, None, None
    
    def get_cpu_frequency_data(self, start_time_ns, end_time_ns):
        """从trace中查询CPU频率数据"""
        data = []
        
        # 通过cpu_counter_track查询，可以获取正确的CPU编号
        try:
            query = f"""
            SELECT 
                c.ts,
                c.value as frequency_khz,
                cct.cpu
            FROM counter c
            JOIN cpu_counter_track cct ON c.track_id = cct.id
            JOIN track t ON c.track_id = t.id
            WHERE (t.name LIKE '%cpu_freq%' OR t.name LIKE '%cpufreq%')
            AND c.ts >= {start_time_ns}
            AND c.ts <= {end_time_ns}
            ORDER BY c.ts ASC, cct.cpu ASC
            """
            result = self.tp.query(query)
            for row in result:
                freq_khz = row.frequency_khz if row.frequency_khz else 0
                freq_mhz = freq_khz / 1000.0 if freq_khz > 1000 else freq_khz
                cpu_id = getattr(row, 'cpu', 0)
                data.append({
                    'timestamp_ns': row.ts,
                    'frequency_mhz': freq_mhz,
                    'cpu': cpu_id
                })
        except Exception as e:
            print(f"⚠️  查询CPU频率数据失败: {e}")
    
        return pd.DataFrame(data)
    
    def get_gpu_frequency_data(self, start_time_ns, end_time_ns):
        """从trace中查询GPU频率数据"""
        try:
            # 方法1: 从counter表查询
            query = f"""
            SELECT 
                ts,
                value as frequency_mhz
            FROM counter c
            JOIN track t ON c.track_id = t.id
            WHERE (t.name LIKE '%gpu%frequency%' OR t.name LIKE '%gpu_freq%')
            AND ts >= {start_time_ns - start_time_ns % 1000000}
            AND ts <= {end_time_ns + 1000000 - end_time_ns % 1000000}
            ORDER BY ts ASC
            """
            result = self.tp.query(query)
            data = []
            for row in result:
                freq = row.frequency_mhz / 1000000.0 if row.frequency_mhz > 1000 else row.frequency_mhz
                data.append({
                    'timestamp_ns': row.ts,
                    'frequency_mhz': freq
                })
            
            if len(data) == 0:
                # 方法2: 从ftrace事件查询
                query2 = f"""
                SELECT 
                    ts,
                    CAST(value AS REAL) as frequency_mhz
                FROM counter c
                JOIN track t ON c.track_id = t.id
                WHERE t.name LIKE '%gpu_freq%'
                AND ts >= {start_time_ns}
                AND ts <= {end_time_ns}
                ORDER BY ts ASC
                """
                result2 = self.tp.query(query2)
                for row in result2:
                    freq = row.frequency_mhz / 1000000.0 if row.frequency_mhz > 1000 else row.frequency_mhz
                    data.append({
                        'timestamp_ns': row.ts,
                        'frequency_mhz': freq
                    })
            
            return pd.DataFrame(data)
        except Exception as e:
            print(f"⚠️  获取GPU频率数据时出错: {e}")
            return pd.DataFrame()
    
    def get_power_data(self, start_time_ns, end_time_ns):
        """从trace中查询功耗数据"""
        data = []
        
        # 查询电池相关的功耗数据（根据实际track名称）
        try:
            query = f"""
            SELECT 
                c.ts,
                c.value,
                t.name as track_name
            FROM counter c
            JOIN track t ON c.track_id = t.id
            WHERE (t.name LIKE 'batt.current_ua%' 
                   OR t.name LIKE 'batt.power_mw%'
                   OR t.name LIKE 'batt.voltage_uv%'
                   OR t.name LIKE 'batt.%'
                   OR t.name LIKE '%battery%current%'
                   OR t.name LIKE '%power%current%'
                   OR t.name LIKE '%rail%power%')
            AND c.ts >= {start_time_ns}
            AND c.ts <= {end_time_ns}
            ORDER BY c.ts ASC
            """
            result = self.tp.query(query)
            for row in result:
                value = row.value if row.value else 0
                track_name = getattr(row, 'track_name', 'unknown')
                
                # 根据track名称处理单位转换
                current_ma = 0
                if 'current_ua' in track_name:
                    # 微安转换为毫安 (除以1000)
                    current_ma = value / 1000.0
                elif 'power_mw' in track_name:
                    # 功率(毫瓦)，可以近似转换为电流，或者直接使用功率值
                    # 这里我们存储功率值，单位是毫瓦
                    current_ma = value  # 存储功率值，但字段名仍为current_ma
                elif 'voltage_uv' in track_name:
                    # 电压(微伏)，可以用于计算功率，这里暂时存储电压值
                    current_ma = value / 1000000.0  # 转换为伏特，但存储在current_ma字段
                else:
                    # 其他情况，直接使用原值
                    current_ma = value
                
                data.append({
                    'timestamp_ns': row.ts,
                    'current_ma': current_ma,
                    'power_source': track_name
                })
            
            return pd.DataFrame(data)
        except Exception as e:
            print(f"⚠️  获取功耗数据时出错: {e}")
            return pd.DataFrame()
    
    def analyze(self, package_name):
        """
        执行完整分析
        
        Returns:
            dict: 包含所有分析结果的字典
        """
        print("=" * 60)
        print("📊 开始分析Trace数据...")
        print("=" * 60)
        
        # 1. 获取trace边界
        start_ts, end_ts = self.get_trace_bounds()
        if not start_ts or not end_ts:
            print("❌ 无法获取trace边界")
            return None
        
        print(f"📅 Trace时间范围: {ns_to_cst(start_ts)} ~ {ns_to_cst(end_ts)}")
        print(f"⏱️  Trace总时长: {(end_ts - start_ts) / 1e9:.3f} 秒")
        
        # 2. 使用 android.startup.startups 模块查询冷启动时长
        print("\n🔍 查询冷启动时长...")
        cold_start_duration_ms, app_start_ns_real, app_drawn_ns_real, app_start_ns_orig, app_drawn_ns_orig = self.get_cold_start_duration_from_startups(package_name)
        
        if cold_start_duration_ms is None or app_start_ns_real is None or app_drawn_ns_real is None:
            print("❌ 无法从 android.startup.startups 获取冷启动数据")
            return None
        
        print(f"✅ 使用 android.startup.startups 模块查询成功")
        print(f"🚀 应用启动时间: {ns_to_cst(app_start_ns_real)}")
        print(f"✅ 应用完全绘制时间: {ns_to_cst(app_drawn_ns_real)}")
        print(f"⏱️  冷启动时长: {cold_start_duration_ms:.2f} ms ({cold_start_duration_ms / 1000:.3f} 秒)")
        cold_start_duration_ns = cold_start_duration_ms * 1e6
        
        # 4. 获取CPU频率数据（扩展查询范围：前后各20%的启动时长）
        print("\n📈 提取CPU频率数据...")
        duration_extend_ns = cold_start_duration_ns * 0.2  # 20%的启动时长
        cpu_query_start = app_start_ns_orig - duration_extend_ns
        cpu_query_end = app_drawn_ns_orig + duration_extend_ns
        cpu_freq_df = self.get_cpu_frequency_data(cpu_query_start, cpu_query_end)
        if not cpu_freq_df.empty:
            # 使用app_start_ns_orig作为基准，这样启动区间从0开始
            cpu_freq_df['time_relative_s'] = (cpu_freq_df['timestamp_ns'] - app_start_ns_orig) / 1e9
            print(f"✅ 获取到 {len(cpu_freq_df)} 条CPU频率数据 (查询范围: {duration_extend_ns/1e9:.3f}s前 ~ {duration_extend_ns/1e9:.3f}s后)")
        else:
            print("⚠️  未获取到CPU频率数据")
        
        # 5. 获取GPU频率数据（扩展查询范围：前后各20%的启动时长）
        print("📈 提取GPU频率数据...")
        gpu_query_start = app_start_ns_orig - duration_extend_ns
        gpu_query_end = app_drawn_ns_orig + duration_extend_ns
        gpu_freq_df = self.get_gpu_frequency_data(gpu_query_start, gpu_query_end)
        if not gpu_freq_df.empty:
            # 使用app_start_ns_orig作为基准，这样启动区间从0开始
            gpu_freq_df['time_relative_s'] = (gpu_freq_df['timestamp_ns'] - app_start_ns_orig) / 1e9
            print(f"✅ 获取到 {len(gpu_freq_df)} 条GPU频率数据 (查询范围: {duration_extend_ns/1e9:.3f}s前 ~ {duration_extend_ns/1e9:.3f}s后)")
        else:
            print("⚠️  未获取到GPU频率数据")
        
        # 6. 获取功耗数据（扩展查询范围：前后各20%的启动时长）
        print("📈 提取功耗数据...")
        power_query_start = app_start_ns_orig - duration_extend_ns
        power_query_end = app_drawn_ns_orig + duration_extend_ns
        power_df = self.get_power_data(power_query_start, power_query_end)
        if not power_df.empty:
            # 使用app_start_ns_orig作为基准，这样启动区间从0开始
            power_df['time_relative_s'] = (power_df['timestamp_ns'] - app_start_ns_orig) / 1e9
            print(f"✅ 获取到 {len(power_df)} 条功耗数据 (查询范围: {duration_extend_ns/1e9:.3f}s前 ~ {duration_extend_ns/1e9:.3f}s后)")
        else:
            print("⚠️  未获取到功耗数据")
        
        # 汇总结果（使用转换后的真实时间戳）
        results = {
            'cold_start_duration_ms': cold_start_duration_ms,
            'cold_start_duration_s': cold_start_duration_ns / 1e9,
            'app_start_time_ns': app_start_ns_real,
            'app_drawn_time_ns': app_drawn_ns_real,
            'cpu_frequency': cpu_freq_df,
            'gpu_frequency': gpu_freq_df,
            'power': power_df,
            'start_window_start_s': -duration_extend_ns / 1e9,  # 启动区间开始（相对时间）
            'start_window_end_s': cold_start_duration_ns / 1e9   # 启动区间结束（相对时间，即启动时长）
        }
        
        return results
    
    def close(self):
        """关闭trace processor"""
        self.tp.close()


def analyze_cold_start_trace(trace_path, package_name, output_dir=None):
    """
    分析冷启动trace的主函数
    
    Args:
        trace_path: trace文件路径
        package_name: 应用包名
        output_dir: 输出目录(可选)
    
    Returns:
        分析结果字典
    """
    analyzer = ColdStartAnalyzer(trace_path)
    try:
        results = analyzer.analyze(package_name)
        if results:
            # 保存结果到CSV(如果指定了输出目录)
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)
                if not results['cpu_frequency'].empty:
                    results['cpu_frequency'].to_csv(
                        os.path.join(output_dir, 'cpu_frequency.csv'), 
                        index=False
                    )
                if not results['gpu_frequency'].empty:
                    results['gpu_frequency'].to_csv(
                        os.path.join(output_dir, 'gpu_frequency.csv'), 
                        index=False
                    )
                if not results['power'].empty:
                    results['power'].to_csv(
                        os.path.join(output_dir, 'power.csv'), 
                        index=False
                    )
            return results
        return None
    finally:
        analyzer.close()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='分析App冷启动Trace数据')
    parser.add_argument('trace_path', help='Trace文件路径')
    parser.add_argument('package_name', help='应用包名')
    parser.add_argument('--output-dir', help='输出目录')
    
    args = parser.parse_args()
    
    results = analyze_cold_start_trace(args.trace_path, args.package_name, args.output_dir)
    
    if results:
        print("\n" + "=" * 60)
        print("✅ 分析完成!")
        print("=" * 60)
        print(f"冷启动时长: {results['cold_start_duration_ms']:.2f} ms")
        print(f"CPU频率数据点: {len(results['cpu_frequency'])}")
        print(f"GPU频率数据点: {len(results['gpu_frequency'])}")
        print(f"功耗数据点: {len(results['power'])}")
