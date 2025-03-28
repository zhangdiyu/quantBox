import requests
import pandas as pd
import time

# 获取当前时间戳（秒级，浮点数）
timestamp_seconds = time.time()  # 示例输出：1711621234.567

# 转换为毫秒级（整数）
# 计算500天前的毫秒时间戳
initial_et = int(time.time() * 1000)
days_to_fetch = 500
milliseconds_per_day = 86400000

hstech_constituents = [
    #'700',  # 腾讯控股
    '9988', # 阿里巴巴
    '3690', # 美团
    '1810', # 小米
    '9618', # 京东
    '1024', # 快手
    '981', # 中芯国际
    '2015',  # 理想汽车
    '9868'  # 小鹏汽车
]

base_url = "https://api.itick.org/stock/kline"
headers = {
    "accept": "application/json",
    "token": "d90630449e754c7abb8f7123b182409dadc193a4376b4cf2a5fe7521247bd44e"
}

for stock_code in hstech_constituents:
    all_data = []
    current_et = initial_et
    fetched_days = 0

    while fetched_days < days_to_fetch:
        params = {
            "region": "HK",
            "code": stock_code,
            "kType": 8,
           # "limit": 1000,
            "et": current_et
        }

        try:
            response = requests.get(base_url, headers=headers, params=params)
            response.raise_for_status()
            
            data = response.json()
            if not data['data']:
                break
                
            # 计算本次获取的天数
            first_timestamp = data['data'][0]['t']
            last_timestamp = data['data'][-1]['t']
            days_diff = len(data['data'])
            fetched_days += int(days_diff)
            
            all_data.extend(data['data'])
            print(f"{stock_code} 已获取 {len(data['data'])} 条数据，累计天数: {min(fetched_days, days_to_fetch)}/{days_to_fetch}")
            
            # 更新et为最旧数据的时间戳减1天
            current_et = last_timestamp - milliseconds_per_day
            
            # 防止请求过于频繁
            time.sleep(5)
            
        except requests.exceptions.RequestException as e:
            print(f"请求错误 {stock_code}: {e}")
            break
        except KeyError:
            print(f"{stock_code} 数据格式异常")
            break
        except Exception as e:
            print(f"处理 {stock_code} 时发生未知错误: {str(e)}")
            break

    if all_data:
        df = pd.DataFrame(all_data)
        # 字段重命名和时间戳转换
        df = df.rename(columns={
            'c': 'close',
            'o': 'open',
            'h': 'high',
            'l': 'low',
            'v': 'volume',
            't': 'timestamp'
        })
        df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
        
        df.to_csv(f"{stock_code}_kline.csv", index=False)
        print(f"成功保存 {stock_code} 的K线数据")