# CC DeepSeek Proxy

一个轻量的本地 Claude Code 兼容代理。它接收 Claude/Anthropic 风格的
`/v1/messages` 请求，把模型名按配置映射后转发到目标服务商接口，并把响应流式返回。

## 功能

- 双击 exe 打开 Tkinter 窗口，不依赖 Electron、PyQt 等重型 GUI 框架。
- 可在窗口里修改监听地址、端口、服务商、Base URL、转发接口、API Key 和模型映射。
- 配置保存到 exe 同目录的 `config.json`，不会写入程序内部。
- 窗口使用 Anthropic/Claude 风格的暖米白、深色文字和橙色强调色，保留轻量圆角面板、圆角按钮和圆角输入框。
- 英文标题优先使用 Poppins，英文正文和数字优先使用 Lora；中文界面文字优先使用 Microsoft YaHei/微软雅黑，找不到时使用 Microsoft YaHei UI、Segoe UI 或 Tk 系统默认字体。目标电脑没有对应字体时会自动 fallback，不额外打包字体文件。
- GUI 采用左配置、右日志的工作台布局：顶部集中保存/启动/停止操作；左侧代理配置按短字段双列、长字段整行排列，模型映射竖向编辑；右侧独立运行日志占满剩余空间。布局会随窗口拖动自动伸缩。
- 运行日志使用白色背景和 emoji 等级标记。
- 运行日志只显示在窗口里，不保存到日志文件。
- 保留原脚本主功能：
  - `POST /v1/messages`
  - `POST /v1/messages/count_tokens`
  - 流式转发
  - `user_id` 清洗

## 快速使用

1. 解压发布包，例如 `cc-deepseek-proxy-windows-onedir.zip`。
2. 双击 `cc-deepseek-proxy.exe`。
3. 在窗口里填入 API Key，确认 Base URL 和转发接口。
4. 点击顶部的“启动”。
5. Claude Code 的代理地址配置为：

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
- `provider_name`：日志里显示的服务商名称。
- `base_url`：服务商基础地址，不要以 `/` 结尾。
- `messages_path`：消息接口路径，会和 `base_url` 拼成完整转发地址。
- `api_key`：服务商 API Key，不要提交到代码仓库。
- `anthropic_version`：转发时使用的 `anthropic-version` 请求头。
- `model_mapping`：Claude Code 请求模型到目标模型的映射。

Base URL、转发接口、API Key、模型映射保存后会影响新的请求。`host` 和 `port`
保存后需要停止并重新启动代理才会换到新的监听地址。

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

兼容旧入口：

```powershell
python claudeProxy.py
```

## 打包

打包脚本使用 Python 编写，产物是标准 zip 压缩包，Windows 自带解压、7-Zip、
WinRAR 等主流工具都可以解压。

推荐打包方式：

```powershell
python build_package.py --install-missing --mode onedir
```

产物位置：

```text
release/cc-deepseek-proxy-windows-onedir.zip
```

如果想要单文件 exe：

```powershell
python build_package.py --install-missing --mode onefile
```

单文件模式启动时会先解压内部运行文件，首次启动会比 `onedir` 慢一些。日常分发建议使用
`onedir` zip，解压后双击 exe 即可运行。

## 安全注意

- 不要把真实 API Key 写进源码。
- 发布包里的 `config.json` 默认不包含 API Key，需要用户自己填写。
- 窗口日志不会保存到文件，也不会打印完整请求体和 API Key。
- 如果曾经把真实 API Key 写进代码或发给别人，建议到服务商后台轮换该 Key。
