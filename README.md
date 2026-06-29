# gscore-login

gscore 外置登录服务。让 bot 端不用对外暴露端口也能跑登录。


## 公共地址

- [gscore-login](https://login.xiamoshi.icu/)

## 启动

```sh
uv sync && uv run python main.py       # 本地
```

默认监听 `0.0.0.0:7861`。

## 配置（环境变量 / `.env`）

```sh
cp .env.example .env             # 拷一份再按需改
```

| 变量            | 默认   | 说明                                        |
| --------------- | ------ | -------------------------------------------|
| `PORT`          | `7861` | 监听端口                                    |
| `login_list`    | `["ww", "dna", "nte"]` | 启用的登录列表，ww、dna、nte |
| `SHARED_SECRET` | 空     | 启用 HMAC 签名校验；                         |
| `SESSION_TTL_S` | `600`  | 会话存活秒数                                 |
| `LOG_LEVEL`     | `INFO` | 日志级别                                    |



# 来源

- [NTEUID](https://github.com/tyql688/NTEUID)
- [DNAUID](https://github.com/tyql688/DNAUID)
- [XutheringWavesUID](https://github.com/Loping151/XutheringWavesUID)
