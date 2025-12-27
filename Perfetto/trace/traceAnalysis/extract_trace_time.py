from datetime import datetime, timedelta, timezone
from perfetto.trace_processor import TraceProcessor, TraceProcessorConfig
import os


def ns_to_cst(timestamp_val, is_ns=True):
    """
    将时间戳转换为东八区（UTC+8）字符串
    修复了 DeprecationWarning
    """
    if timestamp_val is None:
        return "Unknown"
    # 转换为秒
    ts_seconds = timestamp_val / 1e9 if is_ns else timestamp_val
    # 1. 使用 timezone-aware 的 UTC 时间对象
    utc_time = datetime.fromtimestamp(ts_seconds, timezone.utc)
    # 2. 转换为东八区 (UTC+8)
    # astimezone 会自动处理时区转换
    cst_tz = timezone(timedelta(hours=8))
    cst_time = utc_time.astimezone(cst_tz)
    return cst_time.strftime("%Y-%m-%d %H:%M:%S.%f CST")





def analyseTrace_final():
    print("✅ 开始 Trace 时间分析...")

    # 路径配置
    bin_path = r"E:\mobicom26\code\Experiment\Perfetto\configPerfetto\trace_processor_shell.exe"
    trace_path = r"E:\mobicom26\code\Experiment\Perfetto\trace\traceRecord\methodHardWareInfo\HardWareInfo.perfetto-trace"

    if not os.path.exists(trace_path):
        print(f"❌ 文件不存在: {trace_path}")
        return

    config = TraceProcessorConfig(bin_path=bin_path)
    tp = TraceProcessor(trace=trace_path, config=config)

    try:
        # 1️⃣ 获取基础信息
        bounds = tp.query("SELECT start_ts, end_ts FROM trace_bounds;")
        row = next(iter(bounds), None)

        if not row:
            print("❌ Trace 数据为空")
            return

        start_ts = row.start_ts
        end_ts = row.end_ts
        duration_ns = end_ts - start_ts

        real_start_ns = None
        source_type = "Unknown"

        # 2️⃣ 首选策略: 使用 Perfetto 内置转换函数 (最准确)
        try:
            # TO_REALTIME 是 Perfetto SQL 的内置函数，会自动查找最佳的时钟同步源
            time_check = tp.query(f"SELECT TO_REALTIME({start_ts}) as rt_start")
            rt_row = next(iter(time_check), None)

            # 校验转换结果是否有效 (大于 2020年)
            if rt_row and rt_row.rt_start and rt_row.rt_start > 1577836800000000000:
                real_start_ns = rt_row.rt_start
                source_type = "Internal Clock Sync (High Precision)"
        except Exception as e:
            pass


        # 计算结束时间
        real_end_ns = real_start_ns + duration_ns

        # ---------------- 打印结果 ----------------
        print("\n" + "=" * 50)
        print(f"📊 分析报告")
        print("=" * 50)
        print(f"⏱️  持续时长: {duration_ns / 1e9:.3f} s")
        print(f"📅 开始时间: {ns_to_cst(real_start_ns)}")
        print(f"📅 结束时间: {ns_to_cst(real_end_ns)}")
        print(f"ℹ️  时间来源: {source_type}")
        print("=" * 50)

    finally:
        tp.close()


if __name__ == "__main__":
    analyseTrace_final()