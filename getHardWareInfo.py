import subprocess
import threading
import time

from startPrefetto import stop_perfetto, get_perfetto, start_perfetto





def getHardWareInfo():

    perfetto_thread = threading.Thread(target=start_perfetto)

    # 启动两个线程
    perfetto_thread.start()

    time.sleep(10)


    # 停止 Perfetto 并拉取、分析
    stop_perfetto()
    # 等待perfetto停止
    perfetto_thread.join()
    time.sleep(3)
    # 拉取perfetto
    get_perfetto("HardWareInfo")

      



if __name__ == "__main__":
    getHardWareInfo()  # 启动应用



