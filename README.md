# 反走私动态情报网站

每日自动聚合全国及国际反走私相关新闻，每天 09:00 自动更新。

## 功能

- 📰 聚合海关总署、新华社、央视、公安部、Interpol、WCO 等多源新闻
- 🔍 关键词自动过滤，只保留反走私相关内容
- 🏷️ 自动分类：国内要闻 / 国际动态 / 海关执法 / 公安行动 / 司法判决 / 政策法规
- ⏰ 每天北京时间 09:00 由 GitHub Actions 自动抓取更新
- 🆓 完全免费，部署在 Vercel

## 部署步骤

### 1. 上传到 GitHub

```bash
# 在此目录下
git init
git add .
git commit -m "初始化反走私新闻网站"
git remote add origin https://github.com/你的用户名/anti-smuggling-news.git
git push -u origin main
```

### 2. 部署到 Vercel

1. 打开 https://vercel.com，用 GitHub 账号登录
2. 点击 "New Project" → 选择刚才的仓库
3. 框架选 "Other"，根目录保持默认
4. 点击 "Deploy"，等待部署完成
5. 获得免费域名，如 `anti-smuggling-news.vercel.app`

### 3. 启用 GitHub Actions

仓库上传后，GitHub Actions 会自动按计划运行。
也可以在 Actions 页面手动触发第一次抓取。

## 目录结构

```
anti-smuggling-news/
├── index.html              # 前端页面
├── data/
│   └── news.json           # 新闻数据（自动生成）
├── scripts/
│   ├── fetch_news.py       # 抓取脚本
│   └── requirements.txt    # Python 依赖
└── .github/
    └── workflows/
        └── daily-update.yml  # 自动更新配置
```

## 数据来源

| 来源 | 类型 | 说明 |
|------|------|------|
| 海关总署 | 官方 | customs.gov.cn |
| 新华社 | 官媒 | xinhuanet.com |
| 央视新闻 | 官媒 | news.cctv.com |
| 人民日报 | 官媒 | people.com.cn |
| 公安部 | 官方 | mps.gov.cn |
| 最高检 | 官方 | spp.gov.cn |
| Interpol | 国际 | interpol.int |
| WCO | 国际 | wcoomd.org |
