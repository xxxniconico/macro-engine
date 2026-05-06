# Dalio 宏观周期定位引擎

基于 Ray Dalio 的三周期叠加框架（短期债务周期 + 长期债务周期 + 帝国兴衰周期），
构建实时宏观分析系统。

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 一键运行
bash run_daily.sh
```

## 项目结构

```
macro-engine/
├── run_daily.sh              # 每日一键运行
├── config.yaml               # 配置文件
├── requirements.txt
├── data/
│   ├── storage.py            # SQLite 数据库
│   ├── fetch_all.py          # 数据抓取入口
│   ├── fetchers/
│   │   ├── sina.py           # 新浪财经（美股/商品）
│   │   └── eastmoney.py      # 东方财富（A股/指数）
│   └── manual/               # 手动录入数据
├── engine/
│   └── cycle_locator.py      # 三周期定位引擎
└── dashboard/                # 看板（待建）
```

## 当前状态

- ✅ 数据抓取：东方财富（9个中国指标）
- ⚠️ 数据抓取：新浪财经（待修复网络问题）
- ✅ 周期引擎：短期周期定位（ETF 代理）
- ⏳ 长期/帝国周期：需手动录入宏观数据

## 需要手动录入的指标

参见 `data/manual/README.md`

## 协作方式

- **Hermes（微信）**：研究、设计、审查、调度 OpenCode
- **OpenCode**：AI 编码代理（DeepSeek API）
- **Cursor（可选）**：主人写代码
