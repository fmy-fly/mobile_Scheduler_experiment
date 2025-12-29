"""
GPU频率管理模块
"""
from .set_gpu_max_freq import (
    get_gpu_info,
    print_gpu_info,
    get_gpu_original_settings,
    set_gpu_to_max,
    restore_gpu_frequency,
    GPU_PATH
)

__all__ = [
    'get_gpu_info',
    'print_gpu_info',
    'get_gpu_original_settings',
    'set_gpu_to_max',
    'restore_gpu_frequency',
    'GPU_PATH'
]

