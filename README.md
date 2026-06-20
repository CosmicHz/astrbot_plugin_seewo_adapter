# astrbot_plugin_seewo_adapter

> [!WARNING]
> 此项目仍在早期开发阶段，请勿用于生产环境！

将 [AstrBot](https://github.com/Soulter/AstrBot) 接入希沃云班亲情留言，让 AI 与班牌上的学生实时对话。

## 功能

- 接收学生从班牌发送的文本、图片、语音消息
- AI 回复自动发送到班牌（支持文本、图片、语音）
- 微信扫码登录，Token 自动续期
- 轮询模式，无需额外启动 HTTP 服务器
- 错误退避与自动重连

## 安装

手动克隆到 `data/plugins/` 目录（暂不支持在 AstrBot 插件市场安装）：

```bash
cd data/plugins/
git clone https://github.com/CosmicHz/astrbot_plugin_seewo_adapter.git
```

重启 AstrBot 后自动加载。

## 使用

1. 在 AstrBot 管理面板的 **平台配置** 中添加 `seewo` 适配器
2. 首次启动时查看 AstrBot 日志，使用微信扫描二维码登录希沃账号
3. 登录成功后适配器自动开始轮询学生消息
4. 学生在班牌上发消息，AstrBot 即可接收并回复

## 配置项

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `poll_interval` | 5 | 轮询间隔（秒） |

## 数据存储

插件数据存放在 `data/seewo/` 目录下：

- `tokens.json` — 登录凭证
- `uploads.json` — 上传文件记录
- `chat_history.json` — 聊天记录缓存

## 依赖

- requests
- requests-toolbelt
- numpy
- Pillow

## 致谢

希沃客户端核心逻辑来自 [cmy2008/seewo_robot](https://github.com/cmy2008/seewo_robot)。
