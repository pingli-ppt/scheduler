# 果初部署与交接说明

本文供负责上线的成员使用。部署不依赖任何成员电脑上的绝对路径；服务器只需要取得
GitHub 仓库代码，并在仓库根目录执行通用命令。

## 一、部署内容

果初上线时分为两部分：

1. **后端接口**：本仓库中的 `api/`、`algo/` 和 `data/`，由 Python 和 FastAPI 运行。
2. **家庭网页**：本仓库中的 `web/`，完成后作为手机网页发布，再调用后端接口。

目前后端接口已经可运行；家庭网页尚未完成。网页做好后，应在本文件补上所选托管平台
和最终网址。

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
| `PORT` | 通常由平台自动提供 | 后端监听端口；没有提供时默认使用 8000 |

注意：

- 不要把 `tmp/guochu-test.sqlite3` 部署为正式数据库，它只包含测试假数据。
- 不要把密码、平台令牌或真实家庭信息写进仓库或本文档。
- `GUOCHU_CORS_ORIGINS` 必须填写网页真正使用的 `https://` 域名，结尾不要写路径。

## 四、正式数据库和 100 种食物

SQLite 数据库必须放在平台的**持久化磁盘或持久化卷**中。如果数据库只放在普通临时
目录，平台重启或重新部署后，家庭填写的数据可能丢失。

将持久化目录挂载为 `/data` 后，设置：

```text
GUOCHU_DB_PATH=/data/guochu.sqlite3
```

100 种正式食物通过校验后，在服务器上运行一次：

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

## 七、部署家庭网页

家庭网页完成后，可以放到支持 HTTPS 的静态网页托管服务。部署时需要：

1. 把网页中的接口基础地址设置为已经上线的后端地址，例如
   `https://api.example.com`，不能使用 `127.0.0.1` 或 `localhost`。
2. 把网页正式域名写入后端环境变量 `GUOCHU_CORS_ORIGINS`。
3. 用手机在微信内打开网页，完整走一遍建档、查看安排、每日膳食和结果上报。
4. 确认网页全程使用 HTTPS，且页面说明以中文为主。

家庭网页和后端可以使用不同平台，只要网页能通过 HTTPS 访问后端即可。

## 八、上线后的维护

- 每次部署前运行：`python -m unittest discover -s tests -p "test_*.py"`。
- 定期备份持久化目录中的 `guochu.sqlite3`。
- 切换基线期和正式实验期时，只修改 `GUOCHU_EXPERIMENT_PHASE`，然后重启服务。
- 更换网页域名时，同步修改 `GUOCHU_CORS_ORIGINS`。
- 出现问题时记录部署版本对应的 Git 提交编号，便于回退和排查。
