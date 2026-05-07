# CC DeepSeek Proxy

一个轻量的本地 Claude Code 兼容代理。它接收 Claude/Anthropic 风格的
`/v1/messages` 请求，根据配置把模型名映射到目标服务商模型，并把响应以流式方式返回给客户端。

## 功能

- 兼容 Claude Code 常用的 Anthropic 消息接口：
  - `POST /v1/messages`
  - `POST /v1/messages/count_tokens`
  - `GET /v1/models`
- 支持流式转发目标服务商响应，保留上游返回的 `Content-Type`。
- 支持按配置把 Claude Code 请求模型映射到目标服务商模型。
- 未命中模型映射时，会优先使用配置中的第一个目标模型作为兜底。
- 转发请求时会清洗顶层 `user_id` 和 `metadata.user_id`，避免部分服务商因用户标识格式拒绝请求。
- 支持自定义服务商名称、Base URL、消息接口路径、Anthropic Version、超时时间和监听端口。
- 转发时会同时发送 Anthropic 兼容的 `x-api-key` 和常见网关使用的 `Authorization: Bearer`。
- 上游超时、网络异常或非 200 响应会返回结构化 JSON，便于客户端和日志定位问题。
- 支持 GUI 模式和无窗口模式：
  - GUI 模式用于编辑配置、维护模型映射、启动或停止代理、查看运行日志。
  - 无窗口模式适合脚本、终端或自启动场景。
- 配置保存在独立的 `config.json` 中，源码和 exe 不会内置用户配置。
- `config.json` 中未填写 `api_key` 时，可以通过环境变量 `DEEPSEEK_API_KEY` 提供密钥。
- 配置文件损坏时会自动备份为 `config.json.broken`，并重新生成默认配置。
- 提供 `/health` 健康检查接口，方便确认本地服务是否启动。

## 快速使用

1. 解压发布包，例如 `cc-deepseek-proxy-windows-onedir.zip`。
2. 双击 `cc-deepseek-proxy.exe`。
3. 在窗口里填入 API Key，确认 Base URL、转发接口和模型映射。
4. 点击顶部的“启动”。
5. 将 Claude Code 的代理地址配置为：

```text
http://127.0.0.1:8085
```

浏览器打开下面地址可以检查服务是否运行：

```text
http://127.0.0.1:8085/health
```

## 配置说明

`config.json` 示例：

```json
{
  "host": "127.0.0.1",
  "port": 8085,
  "provider_name": "DeepSeek",
  "base_url": "https://api.deepseek.com",
  "messages_path": "/anthropic/v1/messages",
  "api_key": "",
  "anthropic_version": "2023-06-01",
  "request_timeout_seconds": 120,
  "model_mapping": {
    "claude-4.6-opus": "deepseek-v4-pro",
    "claude-4.6-sonnet": "deepseek-v4-flash"
  }
}
```

字段说明：

- `host`：本地监听地址，默认只监听本机 `127.0.0.1`。
- `port`：本地监听端口。
- `provider_name`：运行日志中显示的目标服务商名称。
- `base_url`：目标服务商基础地址，不要以 `/` 结尾。
- `messages_path`：目标服务商消息接口路径，会和 `base_url` 拼成完整转发地址。
- `api_key`：目标服务商 API Key。不要提交到代码仓库。
- `anthropic_version`：转发时使用的 `anthropic-version` 请求头。
- `request_timeout_seconds`：读取目标服务商响应的超时时间，单位为秒。
- `model_mapping`：Claude Code 请求模型到目标服务商模型的映射。

Base URL、转发接口、API Key、超时时间和模型映射保存后会影响新的请求。`host` 和 `port`
保存后需要停止并重新启动代理才会换到新的监听地址。

## API Key 配置

推荐在 GUI 中填写 API Key，配置会保存到本地 `config.json`。如果不想把密钥写入配置文件，也可以保持
`api_key` 为空，并在启动前设置环境变量：

```powershell
$env:DEEPSEEK_API_KEY = "your-api-key"
python main.py --headless
```

## 开发运行

安装依赖：

```powershell
python -m pip install -r requirements.txt
```

打开 GUI：

```powershell
python main.py
```

无窗口模式：

```powershell
python main.py --headless
```

指定配置文件：

```powershell
python main.py --config D:\path\to\config.json
```

兼容旧入口：

```powershell
python claudeProxy.py
```

## 打包

打包脚本使用 PyInstaller，产物是标准 zip 压缩包，Windows 自带解压、7-Zip、WinRAR 等工具都可以解压。

推荐打包方式：

```powershell
python build_package.py --install-missing --mode onedir
```

产物位置：

```text
release/cc-deepseek-proxy-windows-onedir.zip
```

如果需要单文件 exe：

```powershell
python build_package.py --install-missing --mode onefile
```

`onedir` 启动更快，适合日常分发。`onefile` 只有一个 exe，但首次启动时需要先解压内部运行文件。

## 安全注意

- 不要把真实 API Key 写进源码或提交到仓库。
- 默认 `.gitignore` 已排除本地 `config.json`、虚拟环境、构建目录和发布产物。
- 发布包里的 `config.json` 默认不包含 API Key，需要用户自己填写。
- 窗口日志不会保存到文件，也不会打印完整请求体和 API Key。
- 如果真实 API Key 曾经泄露，建议立即到服务商后台轮换该 Key。
