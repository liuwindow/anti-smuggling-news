#!/bin/bash
# GitHub 初始化脚本

# 1. 设置用户信息
echo "设置 Git 配置..."
git config --global user.name "liu言"
git config --global user.email "example@example.com"

# 2. 初始化仓库
echo "初始化仓库..."
git init
git add .
git commit -m "初始化反走私新闻网站"

# 3. 提示用户去 GitHub 创建仓库
echo ""
echo "===== 下一步需要你手动操作 ====="
echo "1. 打开 https://github.com"
echo "2. 注册账号（如果没注册过）"
echo "3. 登录后点击右上角 '+' -> New Repository"
echo "4. 仓库名: anti-smuggling-news"
echo "5. 不要勾选 'Add .gitignore' 和 'Add README'"
echo "6. 创建成功后，复制仓库的 URL"
echo ""
echo "7. 回到此窗口，执行:"
echo "   git remote add origin https://github.com/你的用户名/anti-smuggling-news.git"
echo "   git push -u origin main"
echo ""
echo "8. 完成后浏览器访问 https://vercel.com"
echo "9. 登录 GitHub 账号，部署项目"