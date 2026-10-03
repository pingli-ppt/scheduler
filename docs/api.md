# 果初 API

API 使用 FastAPI，默认读取 `data/guochu.sqlite3`；测试和部署时可通过
`GUOCHU_DB_PATH` 指定其他数据库。

## 第一次准备测试环境

以下命令需要在 `scheduler` 项目根目录运行。每个人的项目路径可以不同；只要当前目录
中能看到 `README.md`、`api/` 和 `data/` 即可。

```powershell
python -m pip install -r requirements.txt
python -m data.seed_test_data
```

这一步负责安装依赖，并根据杨紫玥的 0930 测试数据生成独立测试库。通常只需要执行
一次；测试数据有更新时可以重新执行 `seed_test_data`。

## 以后每次打开接口文档

关闭终端、停止服务或重新开机后，都需要重新运行下面三条命令：

```powershell
$env:GUOCHU_DB_PATH = "tmp/guochu-test.sqlite3"
python -m uvicorn api.main:app --reload
```

看到终端显示服务已启动后，保持终端窗口开启，再用浏览器访问：

- 接口文档：`http://127.0.0.1:8000/docs`
- 健康检查：`http://127.0.0.1:8000/health`

这些命令的作用和顺序是：

1. 先在自己电脑的 `scheduler` 项目根目录打开终端，让 Python 能找到项目代码。
2. `GUOCHU_DB_PATH` 告诉接口使用测试库，而不是正式库。
3. `uvicorn` 启动本机接口服务；命令运行期间终端必须保持打开。
4. 服务启动后，浏览器才能访问本机地址 `http://127.0.0.1:8000/docs`。

测试库与正式库分开，且 `tmp/` 已被 Git 忽略。测试库不需要每次重新生成，但接口
服务每次使用前都必须启动。`/docs` 中由本项目编写的标题、接口用途和字段说明以中文
为主；Swagger 自带的 `Try it out`、`Execute`、`Responses` 等按钮仍会显示英文。

需要在本机查看已经接入的100种正式食物时，先清除测试库环境变量，再启动服务：

```powershell
Remove-Item Env:GUOCHU_DB_PATH -ErrorAction SilentlyContinue
python -m uvicorn api.main:app --reload
```

此时接口默认读取 `data/guochu.sqlite3`。测试库和正式库不要混用。

这里是开发人员在自己电脑上的测试方法，不是服务器部署命令。交给其他成员的正式
部署步骤见 [`docs/deploy.md`](deploy.md)。

## 主要接口

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| `PUT` | `/children/{child_id}` | 新增或更新儿童档案 |
| `GET` | `/children/{child_id}` | 查询儿童档案 |
| `GET` | `/foods` | 查询食物库 |
| `POST` | `/children/{child_id}/schedule` | 生成推荐，并在展示时保存推荐编号 |
| `GET` | `/children/{child_id}/recommendations` | 查询推荐及采纳、摄入、结果、重排状态 |
| `PATCH` | `/recommendations/{id}/engagement` | 记录是否采纳、是否实际摄入 |
| `POST` | `/recommendations/{id}/outcome` | 上报通过、拒绝或不良反应；反应会自动重排 |
| `GET` | `/children/{child_id}/history` | 查询辅食记录 |
| `GET/PUT` | `/children/{child_id}/daily-intake` | 查询或保存每日膳食记录 |

推荐只有在真正展示给家庭时才由 `POST /schedule` 保存，因此未采纳的推荐也会留在
实验统计分母中。对照组不生成个性化推荐。若设置环境变量
`GUOCHU_EXPERIMENT_PHASE=baseline`，实验组在基线期也不会生成推荐。

杨紫玥提供的 `foods_test.csv` 是测试专用假数据，只用于接口和规则联调，不导入正式
食物库。吴琦提供的100种食物保存在 `data/foods.csv`，其中 `auto_recommend=0` 的食物
可以查询，但不会进入自动推荐结果。
