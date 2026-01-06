"""
频率配置文件
从 batch_test.py 中提取的APP频率配置
"""

# App包名映射
APPS = {
    "play商店": "com.android.vending",
    "Gmail": "com.google.android.gm",
    "youtube": "com.google.android.youtube",
    "抖音": "com.ss.android.ugc.aweme",
    "小红书": "com.xingin.xhs",
    "微信": "com.tencent.mm",
    "QQ": "com.tencent.mobileqq",
}

# 每个App的个性化频率配置
APP_FREQ_CONFIGS = {
    "Gmail": {
        "cpu_freq_settings": {
            "time_based": True,
            "periods": [
                {
                    "start": 0.0,
                    "end": 0.25,
                    "cpu_freq": {
                        "0": 1696000,
                        "4": 2130000,
                        "7": 2687000
                    },
                    "gpu_freq": 649000
                },
                {
                    "start": 0.25,
                    "end": 10.0,
                    "cpu_freq": {
                        "0": 1328000,
                        "4": 1549000,
                        "7": 2147000
                    },
                    "gpu_freq": 419000
                }
            ]
        },
        "gpu_freq_setting": None
    },
    
    "play商店": {
        "cpu_freq_settings": {
            "time_based": True,
            "periods": [
                {
                    "start": 0.0,
                    "end": 0.3,
                    "cpu_freq": {
                        "0": 1849000,
                        "4": 2367000,
                        "7": 2914000
                    },
                    "gpu_freq": 723000
                },
                {
                    "start": 0.3,
                    "end": 10.0,
                    "cpu_freq": {
                        "0": 1548000,
                        "4": 1945000,
                        "7": 2499000
                    },
                    "gpu_freq": 467000
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
                    "end": 0.3,
                    "cpu_freq": {
                        "0": 1849000,
                        "4": 2245000,
                        "7": 2914000
                    },
                    "gpu_freq": 723000
                },
                {
                    "start": 0.3,
                    "end": 10.0,
                    "cpu_freq": {
                        "0": 1548000,
                        "4": 1795000,
                        "7": 2363000
                    },
                    "gpu_freq": 467000
                }
            ]
        },
        "gpu_freq_setting": None
    },
    
    "抖音": {
        "cpu_freq_settings": {
            "time_based": True,
            "periods": [
                {
                    "start": 0.0,
                    "end": 0.1,
                    "cpu_freq": {
                        "0": 1950000,
                        "4": 2450000,
                        "7": 3015000
                    },
                    "gpu_freq": 850000
                },
                {
                    "start": 0.1,
                    "end": 10.0,
                    "cpu_freq": {
                        "0": 1696000,
                        "4": 2130000,
                        "7": 2687000
                    },
                    "gpu_freq": 521000
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
                    "end": 0.4,
                    "cpu_freq": {
                        "0": 1950000,
                        "4": 2450000,
                        "7": 3015000
                    },
                    "gpu_freq": 850000
                },
                {
                    "start": 0.4,
                    "end": 10.0,
                    "cpu_freq": {
                        "0": 1696000,
                        "4": 2130000,
                        "7": 2687000
                    },
                    "gpu_freq": 521000
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
                    "end": 0.35,
                    "cpu_freq": {
                        "0": 1950000,
                        "4": 2367000,
                        "7": 2970000
                    },
                    "gpu_freq": 807000
                },
                {
                    "start": 0.35,
                    "end": 10.0,
                    "cpu_freq": {
                        "0": 1696000,
                        "4": 1945000,
                        "7": 2687000
                    },
                    "gpu_freq": 467000
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
                    "end": 0.35,
                    "cpu_freq": {
                        "0": 1950000,
                        "4": 2367000,
                        "7": 2970000
                    },
                    "gpu_freq": 807000
                },
                {
                    "start": 0.35,
                    "end": 10.0,
                    "cpu_freq": {
                        "0": 1696000,
                        "4": 1945000,
                        "7": 2687000
                    },
                    "gpu_freq": 467000
                }
            ]
        },
        "gpu_freq_setting": None
    }
}

