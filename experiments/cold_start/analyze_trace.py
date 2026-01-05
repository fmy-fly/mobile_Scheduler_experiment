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
from experiments.cold_start.frequency_manager import get_available_cpu_frequencies, get_available_gpu_frequencies


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
        try:
            # 先列出所有CPU频率相关的track，用于调试
            try:
                debug_query = """
                SELECT DISTINCT t.name as track_name
                FROM track t
                WHERE (t.name LIKE '%cpu%freq%' OR t.name LIKE '%cpufreq%' OR t.name LIKE '%cpu_freq%')
                ORDER BY t.name
                """
                debug_result = self.tp.query(debug_query)
                cpu_tracks = [row.track_name for row in debug_result]
                if cpu_tracks:
                    print(f"   🔍 找到CPU频率相关track: {', '.join(cpu_tracks[:15])}")
            except:
                pass
            
            # 尝试通过cpu_counter_track查询（标准方法）
            preferred_track_names = ['cpu_freq', 'cpufreq']
            for track_name in preferred_track_names:
                try:
                    query = f"""
                    SELECT 
                        c.ts,
                        c.value as frequency,
                        cct.cpu
                    FROM counter c
                    JOIN cpu_counter_track cct ON c.track_id = cct.id
                    JOIN track t ON c.track_id = t.id
                    WHERE t.name = '{track_name}'
                    AND c.ts >= {start_time_ns}
                    AND c.ts <= {end_time_ns}
                    ORDER BY c.ts ASC, cct.cpu ASC
                    """
                    result = self.tp.query(query)
                    data = []
                    for row in result:
                        freq = row.frequency if row.frequency else 0
                        cpu_id = getattr(row, 'cpu', 0)
                        data.append({
                            'timestamp_ns': row.ts,
                            'frequency': freq,
                            'cpu': cpu_id
                        })
                    if len(data) > 0:
                        print(f"   ✅ 使用track: {track_name}, {len(data)}条CPU频率数据")
                        return pd.DataFrame(data)
                except Exception as e:
                    continue
            
            print("   ⚠️  未找到CPU频率数据")
            return pd.DataFrame()
            
        except Exception as e:
            print(f"⚠️  获取CPU频率数据时出错: {e}")
            import traceback
            traceback.print_exc()
            return pd.DataFrame()
    
    def get_gpu_frequency_data(self, start_time_ns, end_time_ns):
        """从trace中查询GPU频率数据"""
        try:
            # 优先选择最准确的track（gpufreq是最常见的GPU频率track）
            preferred_tracks = ['gpufreq']
            # , 'gpu_frequency', 'gpu_freq', 'GPU Frequency'
            for preferred in preferred_tracks:
                try:
                    query = f"""
                    SELECT 
                        c.ts,
                        c.value as frequency
                    FROM counter c
                    JOIN track t ON c.track_id = t.id
                    WHERE t.name = '{preferred}'
                    AND c.ts >= {start_time_ns}
                    AND c.ts <= {end_time_ns}
                    ORDER BY c.ts ASC
                    """
                    result = self.tp.query(query)
                    data = []
                    for row in result:
                        freq = row.frequency if row.frequency else 0
                        data.append({
                            'timestamp_ns': row.ts,
                            'frequency': freq
                        })
                    if len(data) > 0:
                        print(f"   ✅ 使用track: {preferred}, {len(data)}条")
                        return pd.DataFrame(data)
                except Exception as e:
                    continue
            
            print("   ⚠️  未找到GPU频率数据")
            return pd.DataFrame()
            
        except Exception as e:
            print(f"⚠️  获取GPU频率数据时出错: {e}")
            import traceback
            traceback.print_exc()
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
    
    def get_cpu_scheduling_data(self, package_name, start_time_ns, end_time_ns):
        """从trace中查询应用进程在哪个CPU上运行的数据"""
        data = []
        try:
            # 首先找到应用的进程
            process_query = f"""
            SELECT DISTINCT pid, name
            FROM process
            WHERE name LIKE '%{package_name}%'
            ORDER BY pid
            """
            process_result = self.tp.query(process_query)
            process_pids = []
            for row in process_result:
                process_pids.append(row.pid)
                print(f"   🔍 找到进程: {row.name} (PID: {row.pid})")
            
            if not process_pids:
                print(f"   ⚠️  未找到包名包含 '{package_name}' 的进程")
                # 尝试通过线程名称查找
                thread_query = f"""
                SELECT DISTINCT t.tid, t.name
                FROM thread t
                WHERE t.name LIKE '%{package_name}%'
                ORDER BY t.tid
                LIMIT 20
                """
                thread_result = self.tp.query(thread_query)
                thread_tids = []
                for row in thread_result:
                    thread_tids.append(row.tid)
                    print(f"   🔍 找到线程: {row.name} (TID: {row.tid})")
                
                if not thread_tids:
                    print("   ⚠️  未找到相关进程或线程")
                    return pd.DataFrame()
                
                # 使用线程ID查询调度信息
                query = f"""
                SELECT 
                    s.ts,
                    s.dur,
                    s.cpu,
                    s.utid,
                    t.name as thread_name,
                    t.tid
                FROM sched s
                JOIN thread t ON s.utid = t.utid
                WHERE t.tid IN ({','.join(map(str, thread_tids))})
                AND s.ts >= {start_time_ns}
                AND s.ts <= {end_time_ns}
                ORDER BY s.ts ASC, s.cpu ASC
                """
            else:
                # 使用进程ID查询该进程的所有线程
                query = f"""
                SELECT 
                    s.ts,
                    s.dur,
                    s.cpu,
                    s.utid,
                    t.name as thread_name,
                    t.tid
                FROM sched s
                JOIN thread t ON s.utid = t.utid
                JOIN process p ON t.upid = p.upid
                WHERE p.pid IN ({','.join(map(str, process_pids))})
                AND s.ts >= {start_time_ns}
                AND s.ts <= {end_time_ns}
                ORDER BY s.ts ASC, s.cpu ASC
                """
            
            result = self.tp.query(query)
            for row in result:
                duration_ns = getattr(row, 'dur', 0) if hasattr(row, 'dur') else 0
                data.append({
                    'timestamp_ns': row.ts,
                    'duration_ns': duration_ns,
                    'cpu': row.cpu,
                    'utid': row.utid,
                    'thread_name': getattr(row, 'thread_name', 'unknown'),
                    'tid': getattr(row, 'tid', 0)
                })
            
            if len(data) > 0:
                print(f"   ✅ 获取到 {len(data)} 条CPU调度数据")
                return pd.DataFrame(data)
            else:
                print("   ⚠️  未获取到CPU调度数据")
                return pd.DataFrame()
            
        except Exception as e:
            print(f"⚠️  获取CPU调度数据时出错: {e}")
            import traceback
            traceback.print_exc()
            return pd.DataFrame()
    
    def get_cpu_utilization_data(self, package_name, start_time_ns, end_time_ns):
        """
        从trace中查询CPU利用率数据
        每100毫秒时间窗口内每个CPU的利用率
        查询整个系统在该时间段的CPU利用率（不限制特定进程）
        
        Args:
            package_name: 应用包名（保留参数以兼容，但实际查询所有进程）
            start_time_ns: 开始时间（纳秒）
            end_time_ns: 结束时间（纳秒）
        
        Returns:
            DataFrame: 包含 time_100ms, cpu, cpu_util 列
        """
        data = []
        try:
            query = f"""
            SELECT
              -- 1. 时间分桶：10^8 纳秒 = 100毫秒
              CAST(ts / 1e8 AS INT) AS time_100ms,
              
              cpu,

              -- 2. 计算利用率：分母改成 1e8 (100ms)
              -- 查询所有进程在该时间段的CPU利用率，不限制特定应用
              SUM(dur) * 1.0 / 1e8 AS cpu_util

            FROM sched s
            WHERE
              s.utid != 0
              AND s.ts >= {start_time_ns}
              AND s.ts <= {end_time_ns}
            GROUP BY time_100ms, cpu
            ORDER BY time_100ms, cpu
            """
            
            result = self.tp.query(query)
            for row in result:
                data.append({
                    'time_100ms': row.time_100ms,
                    'cpu': row.cpu,
                    'cpu_util': row.cpu_util
                })
            
            if len(data) > 0:
                print(f"   ✅ 获取到 {len(data)} 条CPU利用率数据")
                return pd.DataFrame(data)
            else:
                print("   ⚠️  未获取到CPU利用率数据")
                return pd.DataFrame()
            
        except Exception as e:
            print(f"⚠️  获取CPU利用率数据时出错: {e}")
            import traceback
            traceback.print_exc()
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
        
        # 4. 获取CPU频率数据（扩展查询范围：前后各30%的启动时长）
        print("\n📈 提取CPU频率数据...")
        duration_extend_ns = cold_start_duration_ns * 0.3  # 30%的启动时长
        cpu_query_start = app_start_ns_orig - duration_extend_ns
        cpu_query_end = app_drawn_ns_orig + duration_extend_ns
        cpu_freq_df = self.get_cpu_frequency_data(cpu_query_start, cpu_query_end)
        if not cpu_freq_df.empty:
            # 使用app_start_ns_orig作为基准，这样启动区间从0开始
            cpu_freq_df['time_relative_s'] = (cpu_freq_df['timestamp_ns'] - app_start_ns_orig) / 1e9
            print(f"✅ 获取到 {len(cpu_freq_df)} 条CPU频率数据 (查询范围: {duration_extend_ns/1e9:.3f}s前 ~ {duration_extend_ns/1e9:.3f}s后)")
        else:
            print("⚠️  未获取到CPU频率数据")
        
        # 5. 获取GPU频率数据（扩展查询范围：前后各30%的启动时长）
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
        
        # 6. 获取功耗数据（扩展查询范围：前后各30%的启动时长）
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
        
        # 7. 获取CPU调度数据（扩展查询范围：前后各30%的启动时长）
        print("📈 提取CPU调度数据...")
        cpu_sched_query_start = app_start_ns_orig - duration_extend_ns
        cpu_sched_query_end = app_drawn_ns_orig + duration_extend_ns
        cpu_sched_df = self.get_cpu_scheduling_data(package_name, cpu_sched_query_start, cpu_sched_query_end)
        if not cpu_sched_df.empty:
            # 使用app_start_ns_orig作为基准，这样启动区间从0开始
            cpu_sched_df['time_relative_s'] = (cpu_sched_df['timestamp_ns'] - app_start_ns_orig) / 1e9
            print(f"✅ 获取到 {len(cpu_sched_df)} 条CPU调度数据 (查询范围: {duration_extend_ns/1e9:.3f}s前 ~ {duration_extend_ns/1e9:.3f}s后)")
        else:
            print("⚠️  未获取到CPU调度数据")
        
        # 8. 获取CPU利用率数据（扩展查询范围：前后各100%的启动时长，即前后各延伸一个完整的启动时长）
        print("📈 提取CPU利用率数据...")
        cpu_util_extend_ns = cold_start_duration_ns * 1.0 # 100%的启动时长
        cpu_util_query_start = app_start_ns_orig - cpu_util_extend_ns
        cpu_util_query_end = app_drawn_ns_orig + cpu_util_extend_ns
        cpu_util_df = self.get_cpu_utilization_data(package_name, cpu_util_query_start, cpu_util_query_end)
        if not cpu_util_df.empty:
            # 将time_100ms转换为相对时间（秒）
            # time_100ms是基于trace开始时间的100ms桶，需要转换为相对于app_start_ns_orig的时间
            cpu_util_df['time_relative_s'] = (cpu_util_df['time_100ms'] * 1e8 - app_start_ns_orig) / 1e9
            print(f"✅ 获取到 {len(cpu_util_df)} 条CPU利用率数据 (查询范围: {cpu_util_query_start/1e9:.3f}s前 ~ {cpu_util_query_end/1e9:.3f}s后)")
        else:
            print("⚠️  未获取到CPU利用率数据")
        
        # 获取CPU和GPU的可用频率范围（保持原始单位，不进行转换）
        cpu_available_freqs = {}  # {cpu_id: {'min': min_freq, 'max': max_freq}}
        if not cpu_freq_df.empty and 'cpu' in cpu_freq_df.columns:
            for cpu_id in cpu_freq_df['cpu'].unique():
                freqs = get_available_cpu_frequencies(int(cpu_id))
                if freqs:
                    # 保持原始单位，不转换
                    cpu_available_freqs[int(cpu_id)] = {
                        'min': min(freqs),
                        'max': max(freqs)
                    }
        
        gpu_available_freqs = None  # {'min': min_freq, 'max': max_freq}
        gpu_freqs = get_available_gpu_frequencies()
        if gpu_freqs:
            # 保持原始单位，不转换
            gpu_available_freqs = {
                'min': min(gpu_freqs),
                'max': max(gpu_freqs)
            }
        
        # 计算启动区间内的功耗统计（平均、最大、最小、总功耗）
        start_window_end_s = cold_start_duration_ns / 1e9  # 启动时长（秒）
        
        # 筛选启动区间内的功耗数据（time_relative_s在0到启动时长之间）
        startup_power_df = power_df[
            (power_df['time_relative_s'] >= 0) & 
            (power_df['time_relative_s'] <= start_window_end_s)
        ].copy() if not power_df.empty else pd.DataFrame()
        
        total_power_consumption_mj = None  # 总功耗（毫焦耳）
        total_power_consumption_j = None  # 总功耗（焦耳）
        avg_power_mw = None  # 平均功率（毫瓦）
        max_power_mw = None  # 最大功率（毫瓦）
        min_power_mw = None  # 最小功率（毫瓦）
        avg_current_ma = None  # 平均电流（毫安）
        max_current_ma = None  # 最大电流（毫安）
        min_current_ma = None  # 最小电流（毫安）
        avg_voltage_v = None  # 平均电压（伏特）
        max_voltage_v = None  # 最大电压（伏特）
        min_voltage_v = None  # 最小电压（伏特）
        
        if not startup_power_df.empty:
            try:
                # 计算功率统计（power_mw数据）
                power_mw_data = startup_power_df[startup_power_df['power_source'].str.contains('power_mw', case=False, na=False)]
                if not power_mw_data.empty:
                    avg_power_mw = power_mw_data['current_ma'].mean()  # 实际是mW值
                    max_power_mw = power_mw_data['current_ma'].max()
                    min_power_mw = power_mw_data['current_ma'].min()
                    
                    # 计算总功耗（对功耗曲线积分）
                    power_mw_data_sorted = power_mw_data.sort_values('timestamp_ns')
                    power_values = power_mw_data_sorted['current_ma'].values
                    time_values = power_mw_data_sorted['time_relative_s'].values
                    
                    # 使用梯形积分法计算总功耗
                    # 手动实现梯形积分（兼容性更好）
                    if len(power_values) > 1 and len(time_values) > 1:
                        # 计算相邻时间点的平均值乘以时间间隔
                        total_power_consumption_mj = 0.0
                        for i in range(len(time_values) - 1):
                            dt = time_values[i + 1] - time_values[i]  # 时间间隔（秒）
                            avg_power = (power_values[i] + power_values[i + 1]) / 2.0  # 平均功率（mW）
                            total_power_consumption_mj += avg_power * dt  # 能量（毫焦耳）
                    else:
                        total_power_consumption_mj = 0.0
                    
                    total_power_consumption_j = total_power_consumption_mj / 1000.0  # 转换为焦耳
                    
                    print(f"✅ 计算启动区间功耗统计:")
                    print(f"   平均功率: {avg_power_mw:.1f} mW, 最大: {max_power_mw:.1f} mW, 最小: {min_power_mw:.1f} mW")
                    print(f"   总功耗: {total_power_consumption_j:.3f} J (时间范围: 0 ~ {start_window_end_s:.3f}s)")
                
                # 计算电流统计（current_ua数据）
                current_data = startup_power_df[startup_power_df['power_source'].str.contains('current_ua', case=False, na=False)]
                if not current_data.empty:
                    avg_current_ma = current_data['current_ma'].mean()
                    max_current_ma = current_data['current_ma'].max()
                    min_current_ma = current_data['current_ma'].min()
                    print(f"✅ 启动区间电流统计: 平均: {avg_current_ma:.1f} mA, 最大: {max_current_ma:.1f} mA, 最小: {min_current_ma:.1f} mA")
                
                # 计算电压统计（voltage_uv数据）
                voltage_data = startup_power_df[startup_power_df['power_source'].str.contains('voltage_uv', case=False, na=False)]
                if not voltage_data.empty:
                    # voltage_data['current_ma'] 实际存储的是电压值（伏特），因为在get_power_data中已经转换了
                    avg_voltage_v = voltage_data['current_ma'].mean()
                    max_voltage_v = voltage_data['current_ma'].max()
                    min_voltage_v = voltage_data['current_ma'].min()
                    print(f"✅ 启动区间电压统计: 平均: {avg_voltage_v:.3f} V, 最大: {max_voltage_v:.3f} V, 最小: {min_voltage_v:.3f} V")
                    
            except Exception as e:
                print(f"⚠️  计算启动区间功耗统计时出错: {e}")
                import traceback
                traceback.print_exc()
        
        # 计算启动区间内的CPU和GPU频率统计
        start_window_end_s = cold_start_duration_ns / 1e9
        cpu_freq_startup_stats = {}  # {cpu_id: {'avg': ..., 'max': ..., 'min': ...}}
        gpu_freq_startup_stats = None  # {'avg': ..., 'max': ..., 'min': ...}
        
        if not cpu_freq_df.empty:
            # 筛选启动区间内的CPU频率数据
            startup_cpu_freq_df = cpu_freq_df[
                (cpu_freq_df['time_relative_s'] >= 0) & 
                (cpu_freq_df['time_relative_s'] <= start_window_end_s)
            ]
            if not startup_cpu_freq_df.empty and 'cpu' in startup_cpu_freq_df.columns:
                for cpu_id in startup_cpu_freq_df['cpu'].unique():
                    cpu_data = startup_cpu_freq_df[startup_cpu_freq_df['cpu'] == cpu_id]
                    cpu_freq_startup_stats[int(cpu_id)] = {
                        'avg': cpu_data['frequency'].mean(),
                        'max': cpu_data['frequency'].max(),
                        'min': cpu_data['frequency'].min()
                    }
        
        if not gpu_freq_df.empty:
            # 筛选启动区间内的GPU频率数据
            startup_gpu_freq_df = gpu_freq_df[
                (gpu_freq_df['time_relative_s'] >= 0) & 
                (gpu_freq_df['time_relative_s'] <= start_window_end_s)
            ]
            if not startup_gpu_freq_df.empty:
                gpu_freq_startup_stats = {
                    'avg': startup_gpu_freq_df['frequency'].mean(),
                    'max': startup_gpu_freq_df['frequency'].max(),
                    'min': startup_gpu_freq_df['frequency'].min()
                }
        
        # 汇总结果（使用转换后的真实时间戳）
        results = {
            'cold_start_duration_ms': cold_start_duration_ms,
            'cold_start_duration_s': cold_start_duration_ns / 1e9,
            'app_start_time_ns': app_start_ns_real,
            'app_drawn_time_ns': app_drawn_ns_real,
            'cpu_frequency': cpu_freq_df,
            'gpu_frequency': gpu_freq_df,
            'power': power_df,
            'cpu_scheduling': cpu_sched_df,
            'cpu_utilization': cpu_util_df,
            # 启动区间内的功耗统计
            'total_power_consumption_mj': total_power_consumption_mj,  # 总功耗（毫焦耳）
            'total_power_consumption_j': total_power_consumption_j,  # 总功耗（焦耳）
            'avg_power_mw': avg_power_mw,  # 平均功率（毫瓦）
            'max_power_mw': max_power_mw,  # 最大功率（毫瓦）
            'min_power_mw': min_power_mw,  # 最小功率（毫瓦）
            'avg_current_ma': avg_current_ma,  # 平均电流（毫安）
            'max_current_ma': max_current_ma,  # 最大电流（毫安）
            'min_current_ma': min_current_ma,  # 最小电流（毫安）
            'avg_voltage_v': avg_voltage_v,  # 平均电压（伏特）
            'max_voltage_v': max_voltage_v,  # 最大电压（伏特）
            'min_voltage_v': min_voltage_v,  # 最小电压（伏特）
            # 启动区间内的频率统计
            'cpu_freq_startup_stats': cpu_freq_startup_stats,  # CPU频率统计（启动区间内）
            'gpu_freq_startup_stats': gpu_freq_startup_stats,  # GPU频率统计（启动区间内）
            'start_window_start_s': -duration_extend_ns / 1e9,  # 启动区间开始（相对时间）
            'start_window_end_s': cold_start_duration_ns / 1e9,  # 启动区间结束（相对时间，即启动时长）
            'cpu_available_frequencies': cpu_available_freqs,  # CPU可用频率范围
            'gpu_available_frequencies': gpu_available_freqs   # GPU可用频率范围
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
                if not results['cpu_scheduling'].empty:
                    results['cpu_scheduling'].to_csv(
                        os.path.join(output_dir, 'cpu_scheduling.csv'), 
                        index=False
                    )
                if not results['cpu_utilization'].empty:
                    results['cpu_utilization'].to_csv(
                        os.path.join(output_dir, 'cpu_utilization.csv'), 
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
