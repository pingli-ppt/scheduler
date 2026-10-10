# 果初服务器配置模板

本目录保存果初内部测试环境的可复用部署配置。模板不包含密码、会话密钥、
Let's Encrypt 私钥、数据库或真实家庭数据，可以提交到 Git。

当前推荐架构：

```text
互联网 -> Nginx 80/443 -> Uvicorn 127.0.0.1:8000 -> SQLite 持久化数据库
```

## 文件说明

```text
deploy/
├── guochu.env.example                 应用和备份任务的非敏感环境变量模板
├── nginx/
│   ├── guochu-http.conf.example       首次申请证书前的 HTTP 配置
│   └── guochu-https.conf.example      取得证书后的 HTTPS 最终配置
├── scripts/
│   └── guochu-backup                  SQLite 一致性备份脚本
└── systemd/
    ├── guochu.service                 应用常驻与开机启动
    ├── guochu-backup.service          单次备份任务
    └── guochu-backup.timer            每日备份定时器
```

模板默认假设：

- 代码位于 `/opt/guochu`；
- Python 虚拟环境位于 `/opt/guochu/.venv`；
- 服务用户和组均为 `guochu`；
- 数据库位于 `/data/guochu-test.sqlite3`；
- 备份位于 `/var/backups/guochu`；
- 应用只监听 `127.0.0.1:8000`；
- Nginx 是唯一公网 Web 入口；
- 只运行一个 Uvicorn worker，避免 SQLite 多实例写入风险。

如果服务器路径不同，应统一修改模板，不能只修改其中一个文件。

## 一、准备目录和权限

```bash
sudo useradd --system --home /opt/guochu --shell /usr/sbin/nologin guochu
sudo install -d -o guochu -g guochu -m 0750 /opt/guochu
sudo install -d -o guochu -g guochu -m 0750 /data
sudo install -d -o root -g guochu -m 0750 /etc/guochu
sudo install -d -o guochu -g guochu -m 0750 /var/backups/guochu
```

用户已经存在时，`useradd` 报错可以忽略；目录所有权必须核对。

## 二、安装应用环境

在 `/opt/guochu` 中取得仓库代码后：

```bash
sudo -u guochu python3 -m venv /opt/guochu/.venv
sudo -u guochu /opt/guochu/.venv/bin/python -m pip install --upgrade pip
sudo -u guochu /opt/guochu/.venv/bin/python -m pip install -r /opt/guochu/requirements.txt
```

## 三、安装环境变量模板

```bash
sudo install -o root -g guochu -m 0640 \
  deploy/guochu.env.example /etc/guochu/guochu.env
sudoedit /etc/guochu/guochu.env
```

必须按实际环境检查数据库路径和实验阶段。不要把密码或会话密钥的明文放入该文件。

创建访问密码哈希和会话签名密钥：

```bash
sudo htpasswd -c /etc/nginx/.htpasswd guochu
sudo chown root:guochu /etc/nginx/.htpasswd
sudo chmod 0640 /etc/nginx/.htpasswd

sudo sh -c 'umask 027; openssl rand -base64 48 > /etc/guochu/session-secret'
sudo chown root:guochu /etc/guochu/session-secret
sudo chmod 0640 /etc/guochu/session-secret
```

这些真实文件只保存在服务器，不得复制回仓库。

## 四、安装 systemd 应用服务

```bash
sudo install -o root -g root -m 0644 \
  deploy/systemd/guochu.service /etc/systemd/system/guochu.service
sudo systemctl daemon-reload
sudo systemctl enable --now guochu.service
sudo systemctl status guochu.service --no-pager
curl http://127.0.0.1:8000/health
```

如果本机健康检查失败，先看应用日志，不要继续配置公网入口：

```bash
sudo journalctl -u guochu.service -n 100 --no-pager
```

## 五、安装 Nginx 与 HTTPS

先把模板中的 `YOUR_DOMAIN` 替换为真实域名。首次申请证书前只启用 HTTP 模板：

```bash
sudo install -o root -g root -m 0644 \
  deploy/nginx/guochu-http.conf.example /etc/nginx/sites-available/guochu
sudoedit /etc/nginx/sites-available/guochu
sudo ln -s /etc/nginx/sites-available/guochu /etc/nginx/sites-enabled/guochu
sudo nginx -t
sudo systemctl reload nginx
```

确认域名已经解析到服务器、80 和 443 已放行后申请证书：

```bash
sudo certbot --nginx -d YOUR_DOMAIN
sudo certbot renew --dry-run
```

`guochu-https.conf.example` 是最终配置参考。证书路径必须与 Certbot 实际生成路径一致。
同一时间只能启用一份 `guochu` 站点配置，避免端口和限速区域重复定义。

## 六、安装每日备份

先确认 `/etc/guochu/guochu.env` 中的数据库路径、备份目录和保留天数正确：

```bash
sudo install -o root -g root -m 0755 \
  deploy/scripts/guochu-backup /usr/local/sbin/guochu-backup
sudo install -o root -g root -m 0644 \
  deploy/systemd/guochu-backup.service /etc/systemd/system/guochu-backup.service
sudo install -o root -g root -m 0644 \
  deploy/systemd/guochu-backup.timer /etc/systemd/system/guochu-backup.timer
sudo systemctl daemon-reload
sudo systemctl enable --now guochu-backup.timer
```

立即做一次测试备份：

```bash
sudo systemctl start guochu-backup.service
sudo systemctl status guochu-backup.service --no-pager
sudo -u guochu ls -lh /var/backups/guochu
```

脚本使用 SQLite `.backup`，完成后执行 `PRAGMA integrity_check`；只有结果为 `ok` 才会
保留最终文件。默认删除超过 14 天的本机备份。

本机备份不能抵御整台服务器或整块磁盘丢失。正式收集数据前，还要把备份加密同步到
独立对象存储或另一受控位置，并实际演练恢复。

## 七、更新配置后的验证

```bash
sudo systemctl daemon-reload
sudo nginx -t
sudo systemctl restart guochu.service
sudo systemctl reload nginx
curl http://127.0.0.1:8000/health
curl -I https://YOUR_DOMAIN/
systemctl list-timers --all --no-pager | grep guochu
```

还必须用手机和微信完成建档、排程、结果上报、reaction 重排，并验证服务和服务器重启后
数据仍然存在。

## 八、禁止提交的运行文件

- `/etc/nginx/.htpasswd`；
- `/etc/guochu/session-secret`；
- `/etc/letsencrypt/` 下的证书私钥；
- 实际 `.env` 或 `guochu.env`；
- `/data/*.sqlite3`；
- `/var/backups/guochu/*.sqlite3`；
- SSH 私钥、Token、Cookie 和真实家庭信息。

仓库中只保存 `.example` 模板、无秘密的 systemd 配置和通用脚本。
