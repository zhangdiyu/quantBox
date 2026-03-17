# QuantBox Streamlit Web 版本

这是 QuantBox 的 Web 版本，基于 Streamlit 构建，可以在手机浏览器上方便查看。

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements_streamlit.txt
```

### 2. 运行应用

```bash
streamlit run app.py
```

### 3. 访问应用

浏览器会自动打开 `http://localhost:8501`

## 功能特性

- 🏠 **首页** - 快速概览
- 📈 **数据浏览** - 查看股票K线和技术指标
- 🎯 **策略回测** - 测试均线交叉策略

## 手机访问

在同一局域网内，手机可以通过以下方式访问：

1. 查看电脑的 IP 地址
2. 在手机浏览器访问 `http://<电脑IP>:8501`

## 部署到云端

可以部署到以下平台：
- Streamlit Community Cloud (免费)
- Heroku
- Vercel
- 其他支持 Python 的云平台

## 代码复用

这个版本复用了原项目的核心逻辑：
- `src/data_reader.py` - 数据读取和技术指标
- `src/backtest_engine.py` - 回测引擎
- `src/visualization.py` - 可视化模块
