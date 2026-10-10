# 果初部署与交接说明

本文供负责上线的成员使用。部署不依赖任何成员电脑上的绝对路径；服务器只需要取得
GitHub 仓库代码，并在仓库根目录执行通用命令。

## 一、部署内容

果初代码包含两部分：

1. **后端接口**：本仓库中的 `api/`、`algo/` 和 `data/`，由 Python 和 FastAPI 运行。
2. **家庭网页**：本仓库中的 `web/`，由同一个 FastAPI 服务在网站根路径 `/` 提供。

目前接口和六个家庭页面已经接通。部署同一个 Python 服务即可同时提供网页和 API，
不需要把成员电脑上的绝对路径写入部署命令。

## 二、从 GitHub 获取代码

在服务器或部署平台中连接仓库：

```text
https://github.com/pingli-ppt/scheduler
```

手动部署时可使用：

```bash
git clone https://github.com/pingli-ppt/scheduler.git
cd scheduler
python -m pip install -r requirements.txt
```

部署平台如果直接连接 GitHub，安装命令填写为：

```text
python -m pip install -r requirements.txt
```

## 三、后端接口的正式配置

在部署平台的“环境变量”页面设置以下内容：

| 环境变量 | 示例 | 作用 |
| --- | --- | --- |
| `GUOCHU_DB_PATH` | `/data/guochu.sqlite3` | 正式 SQLite 数据库在服务器上的位置 |
| `GUOCHU_EXPERIMENT_PHASE` | `baseline` 或 `active` | 基线期或正式实验期 |
| `GUOCHU_CORS_ORIGINS` | `https://网页实际域名` | 允许哪个家庭网页调用接口；多个域名用英文逗号分隔 |
| `GUOCHU_AUTH_ENABLED` | `true` | 内部测试环境启用网页登录保护；本地开发可不设置 |
| `GUOCHU_HTPASSWD_PATH` | `/etc/nginx/.htpasswd` | 服务器密码文件路径，不要放进仓库 |
| `GUOCHU_AUTH_USERNAME` | `guochu` | 密码文件中用于校验的平台用户名 |
| `GUOCHU_SESSION_SECRET_PATH` | `/etc/guochu/session-secret` | 会话签名密钥文件路径，不要放进仓库 |
| `GUOCHU_SESSION_MAX_AGE_SECONDS` | `604800` | 登录有效期，默认示例为 7 天 |
| `PORT` | 通常由平台自动提供 | 后端监听端口；没有提供时默认使用 8000 |

注意：

- 不要把 `tmp/guochu-test.sqlite3` 部署为正式数据库，它只包含测试假数据。
- 不要把密码、平台令牌或真实家庭信息写进仓库或本文档。
- 微信内置浏览器不可靠地支持 HTTP Basic Auth 弹窗；内部测试环境应使用
  `GUOCHU_AUTH_ENABLED=true` 提供的中文登录页和安全 Cookie。
- `GUOCHU_CORS_ORIGINS` 必须填写网页真正使用的 `https://` 域名，结尾不要写路径。

## 四、正式数据库和 100 种食物

SQLite 数据库必须放在平台的**持久化磁盘或持久化卷**中。如果数据库只放在普通临时
目录，平台重启或重新部署后，家庭填写的数据可能丢失。

将持久化目录挂载为 `/data` 后，设置：

```text
GUOCHU_DB_PATH=/data/guochu.sqlite3
```

仓库中的 `data/foods.csv` 已包含通过程序校验的100种正式食物。首次部署时在服务器上
运行一次：

```bash
python -m data.import_foods data/foods.csv --database /data/guochu.sqlite3
```

以后修正食物数据时可以再次运行同一命令；导入工具会按食物编号新增或更新，不会清空
儿童档案和家庭记录。

## 五、启动后端

部署平台的启动命令统一填写为：

```text
python -m api.run_server
```

这个入口会读取平台提供的 `PORT`，并监听所有网络地址。正式服务器不要使用本地开发命令
中的 `--reload`。

如果平台要求填写健康检查路径，填写：

```text
/health
```

## 六、部署后的检查

假设平台给出的接口域名是 `https://api.example.com`，依次检查：

1. 打开 `https://api.example.com/health`，应看到 `{"status":"ok"}`。
2. 打开 `https://api.example.com/docs`，应能看到中文为主的接口文档。
3. 调用 `GET /foods`，确认正式食物数量和内容正确。
4. 建立一个匿名测试儿童，走通生成推荐、采纳、摄入和结果上报。
5. 上报一次测试用不良反应，确认后续旧计划取消且生成新计划。
6. 删除测试记录或重新准备干净的正式数据库，再交给家庭使用。

## 七、检查家庭网页

后端启动后，直接打开部署平台提供的根网址即可进入家庭网页，例如
`https://app.example.com/`。上线前需要：

1. 用手机在微信内打开网页，完整走一遍建档、查看安排、每日膳食、结果上报、已吃清单和分享。
2. 分别建立实验组与对照组测试档案，确认对照组看不到自动推荐页面。
3. 确认“查看依据”能打开公开来源。
4. 确认网页全程使用 HTTPS；手机系统分享功能在普通 HTTP 地址上可能不可用。
5. 确认页面说明以中文为主，并检查手机窄屏下没有遮挡或横向溢出。

如果以后决定把网页与 API 分开部署，才需要给网页配置正式 API 地址，并把网页域名写入
`GUOCHU_CORS_ORIGINS`；当前同域部署不需要这一步。

## 八、上线后的维护

- 每次部署前运行：`python -m unittest discover -s tests -p "test_*.py"`。
- 定期备份持久化目录中的 `guochu.sqlite3`。
- 切换基线期和正式实验期时，只修改 `GUOCHU_EXPERIMENT_PHASE`，然后重启服务。
- 更换网页域名时，同步修改 `GUOCHU_CORS_ORIGINS`。
- 出现问题时记录部署版本对应的 Git 提交编号，便于回退和排查。

## 九、自建 Ubuntu 服务器配置模板

仓库的 [`deploy/`](../deploy/) 目录提供不含秘密的可复用模板，包括：

- Nginx 首次 HTTP 配置和最终 HTTPS 配置；
- systemd 应用服务、备份服务和每日定时器；
- SQLite 一致性备份及完整性检查脚本；
- 环境变量示例和安装验证步骤。

模板可以提交 Git，但实际的密码文件、会话签名密钥、Let's Encrypt 私钥、数据库和备份
绝不能提交。安装或更新前先阅读 [`deploy/README.md`](../deploy/README.md)，并确认服务器
路径、域名、数据库环境和模板一致。
