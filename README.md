# GLaDOS 自动签到 (新版 glados.cloud)

> 适配 2026 年新版 GLaDOS 网站 (glados.cloud)，支持自动签到 + 积分自动兑换天数

## 功能特性

- 每日自动签到
- 自动查询积分
- 积分达标自动兑换天数（支持三档配置）
- 微信推送通知（可选）
- 支持多账号

## 食用方式

### 1. 注册 GLaDOS 账号

[注册地址](https://glados.space/landing/0A58E-NV28S-6U3QV-33VMG)

邀请码：`B1AW6-4NBAX-VYRZM-5HEJ0`

### 2. Fork 本仓库

![图片加载失败](imgs/1.png)

### 3. 添加 Secrets

跳转至自己的仓库的 `Settings` -> `Secrets and variables` -> `Action`

#### 必填：COOKIES

添加 `repository secret`，命名为 `COOKIES`

**获取方式：**

1. 打开 GLaDOS 签到页面：https://glados.cloud/console/checkin
2. 按 `F12` 打开开发者工具
3. 切换到 `Network` 页面，刷新

![图片加载失败](imgs/2.png)

4. 点击发往 `glados.cloud` 的请求，在 `Request Headers` 下找到 `Cookie`，复制完整值（包括存在的 `gld:sess`、`gld:sess.sig`，不要只复制 `koa:sess`）。

> 参考格式：`koa:sess=eyJ1c2xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxAwMH0=; koa:sess.sig=xJkOxxxxxxxxxxxxxxxtnM;`

![图片加载失败](imgs/3.png)

**多账号**：在 `COOKIES` 中用 `&` 连接多个 cookie（例如：`cookie1&cookie2&cookie3`）

#### 可选：USER_AGENT（登录设备一致性）

从获取 Cookie 的同一个浏览器请求中复制 `User-Agent`，保存为 `USER_AGENT` Secret。
未配置时使用 macOS Chrome；如果在 Windows、Android 或其他设备登录，请务必配置。
多账号共用此配置，请在同一设备类型的独立浏览器/个人资料中分别登录并获取 Cookie。

如果签到返回 `reason: device-mismatch`，表示登录设备与请求设备不一致。
关闭开发者工具中的手机模拟，使用真实登录设备的 User-Agent；必要时重新登录并更新完整 Cookie。
脚本会输出登录设备和请求设备，不再打印完整账号状态或 Cookie 片段。

`code: 1` 且提示 `Today's observation logged. Return tomorrow for more points.` 表示今日已签到。
签到或账号状态查询失败时，脚本会在处理完账号后以非零状态退出，使 Actions 显示失败。

#### 可选：PUSHPLUS（微信推送）

添加 `repository secret`，命名为 `PUSHPLUS`，值为 pushplus 秘钥

[获取地址](http://www.pushplus.plus)

#### 可选：EXCHANGE_PLAN（积分兑换策略）

添加 `repository secret`，命名为 `EXCHANGE_PLAN`，配置自动兑换策略：

| 值 | 积分要求 | 兑换天数 |
|---|---------|---------|
| `plan100` | 100 积分 | 10 天 |
| `plan200` | 200 积分 | 30 天 |
| `plan500` | 500 积分 | 100 天 (默认) |

> 不配置时默认为 `plan500`，即积分达到 500 时自动兑换 100 天

### 4. Star 自己的仓库

![图片加载失败](imgs/4.png)

## 文件结构

```shell
│  checkin.py           # 签到脚本
│
├─.github
│  └─workflows
│          gladosCheck.yml  # Actions 配置文件
```

## 更新日志

- **2026-01**: 适配新版 glados.cloud，新增积分自动兑换功能

## 声明

本项目不保证稳定运行与更新，因 GitHub 相关规定可能会删库，请注意备份
