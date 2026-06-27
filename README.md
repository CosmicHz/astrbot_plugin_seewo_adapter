# astrbot_plugin_seewo_adapter

> [!WARNING]
> 此项目仍在早期开发阶段，请勿用于生产环境！

将 [AstrBot](https://github.com/Soulter/AstrBot) 接入希沃云班亲情留言，让 AI 与班牌上的学生实时对话。

## 功能

- 接收学生从班牌发送的文本、图片、语音消息
- AI 回复自动发送到班牌（支持文本、图片、语音）
- 通过本地 API 服务器（seewo_robot）收发消息，无需内嵌客户端代码
- 微信扫码登录
- 错误退避与自动重连

## 架构

```
AstrBot ←→ 本插件(适配器) ←→ seewo_robot API 服务器 ←→ 希沃云班
```

本插件通过 HTTP 调用 [seewo_robot](https://github.com/cmy2008/seewo_robot) 的 API 服务器收发消息，自身仅负责消息轮询与 AstrBot 协议转换。

## 前置条件

需要先启动 seewo_robot 的 API 服务器：

```bash
# 真实环境
python api_server.py

# 本地调试（Mock 服务器）
python mock_server.py
```

详见 [seewo_robot 文档](https://github.com/cmy2008/seewo_robot)。

## 安装

手动克隆到 `data/plugins/` 目录（暂不支持在 AstrBot 插件市场安装）：

```bash
cd data/plugins/
git clone https://github.com/CosmicHz/astrbot_plugin_seewo_adapter.git
```

重启 AstrBot 后自动加载。

## 使用

1. 启动 seewo_robot 的 API 服务器
2. 在 AstrBot 管理面板的 **平台配置** 中添加 `seewo` 适配器
3. 填写 API 服务器地址和 API Key
4. 首次启动时使用 `/seewo_login` 指令触发扫码登录
5. 登录成功后适配器自动开始轮询学生消息
6. 学生在班牌上发消息，AstrBot 即可接收并回复

## 指令

| 指令 | 说明 |
|------|------|
| `/seewo_status` | 查看适配器运行状态 |
| `/seewo_login` | 触发扫码登录 |

## 配置项

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `api_url` | `http://localhost:5001` | seewo_robot API 服务器地址 |
| `api_key` | `your-secret-key` | API 密钥 |
| `poll_interval` | 5 | 轮询间隔（秒） |

## 依赖

- aiohttp

## 致谢

希沃客户端核心逻辑来自 [cmy2008/seewo_robot](https://github.com/cmy2008/seewo_robot)。
