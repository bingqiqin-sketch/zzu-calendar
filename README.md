# 郑州大学通知截止时间 · 云端订阅日历

把抓取程序放到 GitHub 云端，每天自动抓取学生处「通知公告」的截止时间并生成 `calendar.ics`，由 GitHub Pages 托管。**iPhone 订阅一次后永久自动更新**，无需 Mac、无需双击、无需日常操作。

## 工作原理

```
GitHub Actions（每天 08:15 北京时间）
   └─ 抓取官网 → deadlines.json → calendar.ics → 提交回仓库
GitHub Pages 托管 calendar.ics
   └─ iPhone「订阅日历」定期拉取，自动更新
```

## 文件说明

| 文件 | 作用 |
|---|---|
| `zzu_calendar.py` | 抓取 + 生成 .ics（仅 Python 标准库） |
| `.github/workflows/update.yml` | 每天自动运行 + 手动触发 |
| `deadlines.json` | 抓取结果（自动维护） |
| `calendar.ics` | 日历文件（自动维护，iPhone 订阅的就是它） |

## 首次部署（一次性，约 15 分钟）

### 1. 建 GitHub 仓库

1. 打开 https://github.com/new
2. Repository name 填 `zzu-calendar`，选 **Public**（公开，免费；内容只是公开通知的截止时间）
3. 不要勾选 README/gitignore（本目录已含），点 **Create repository**

### 2. 推送代码

在本目录执行（把 `你的用户名` 换成你的 GitHub 用户名）：

```bash
cd 日程管理/云端版
git remote add origin https://github.com/你的用户名/zzu-calendar.git
git branch -M main
git push -u origin main
```

> 第一次 push 会弹出浏览器让你登录 GitHub 授权，点授权即可。

### 3. 开启 GitHub Pages

1. 仓库页 → **Settings** → 左侧 **Pages**
2. **Source** 选 **Deploy from a branch**
3. Branch 选 **main**、文件夹选 **/ (root)**，点 **Save**
4. 等约 1 分钟，页面上会显示网址 `https://你的用户名.github.io/zzu-calendar/`

### 4. iPhone 订阅日历

1. iPhone → **设置 → 日历 → 账户 → 添加账户 → 其他 → 添加订阅日历**
2. 粘贴订阅地址（二选一，推荐第一个）：
   - `https://你的用户名.github.io/zzu-calendar/calendar.ics`
   - 或 `webcal://你的用户名.github.io/zzu-calendar/calendar.ics`
3. 点「下一步」→「存储」，完成。手机日历里会立即出现这些截止时间。

### 5. 立即测试一次

首次手动触发一次，验证整条链路：仓库页 → **Actions** 标签 → 左侧 **Update calendar** → **Run workflow** → 绿色按钮 **Run workflow**。约 1 分钟后刷新，看到绿色 ✓ 即成功。以后每天自动跑。

## 说明与限制

- **截止时间由正则自动提取**，官网排版偶有拆字/缺年份等情况，可能漏提或错提个别条目，属正常。如发现漏提，可手动编辑 `deadlines.json` 后提交，或告诉我来改抓取规则。
- **无「截止/前完成」等字样的纯活动通知**（如讲座、沙龙、训练营）不会被抓取；这类活动如需提醒，请手动补进 `deadlines.json`。
- **事件 UID 由「名称+截止时间」哈希生成**，跨天稳定，订阅端据此判重，不会重复；但若某条**改动了截止日期**，会产生一条新事件（旧的保留），需在手机日历手动删除旧的。
- **订阅日历的「提前 1 天」通知在 iOS 上是否弹出**因系统而异，事件本身一定能看到；上线后请实测，若不弹通知，可退回本机 Mac 方案（原生通知更可靠）。

## 抓取范围调整

`zzu_calendar.py` 顶部 `PAGES = 2` 控制抓取最新几页（默认 2 页 ≈ 20 条最新通知）。改大后可抓更多历史页，但历史通知大多已过期。
