# OpenClaw Corp LLM Gateway

本项目把公司内的 `panzhi` 和 `neibu` 大模型统一暴露成 OpenAI 兼容接口，供 OpenClaw 直接使用。

## 重构目标

参照你的 `llm_factory.py` 风格，网关侧也采用工厂化创建 Provider：

- `provider_type=panzhi` -> `ProviderFactory._create_panzhi_provider`
- `provider_type=neibu` -> `ProviderFactory._create_neibu_provider`
- 其它 -> `ProviderFactory._create_generic_provider`

入口代码：`/Users/levent/leventProjects/llm/app/providers/factory.py`

## 配置结构

模型注册：`/Users/levent/leventProjects/llm/config/model_registry.json`

关键字段：

- `provider_type`: `panzhi` / `neibu` / `generic`
- `models[].alias`: 对 OpenClaw 暴露的模型名
- `models[].upstream`: 上游默认模型名（fallback）
- `models[].upstream_env`: 上游模型名环境变量（优先）

默认已经配置两个模型：

- `panzhi_qwen3_coder`（盘智）
- `neibu_qwen3_coder`（内部网关）

## 环境变量

样例在：`/Users/levent/leventProjects/llm/.env.example`

### panzhi

- `PANZHI_APPID`
- `PANZHI_APPKEY`
- `PANZHI_MODEL_NAME`
- `PANZHI_BASE_URL`

### neibu

- `OPENAI_API_BASE`
- `OPENAI_API_ID`
- `OPENAI_API_SECRET`
- `MODELSOURCE`
- `TRACE_ID`
- `MODEL_ID`
- `INTERNAL_DEFAULT_MODEL`

`custom_resolvers.get_api_key` 已改为你工厂里的 HMAC 签名逻辑：
`/Users/levent/leventProjects/llm/custom_resolvers.py`

## 启动

```bash
cd /Users/levent/leventProjects/llm
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

cp .env.example .env
cp config/model_registry.example.json config/model_registry.json

set -a
source .env
set +a

python -m app.main
```

说明：应用启动时会自动尝试加载项目根目录 `.env`。即使未手动 `source .env`，常见场景下也可读取到环境变量。

## Docker 启动

### 1) 准备配置

```bash
cp .env.example .env                                          # 编辑填入真实密钥
cp config/model_registry.example.json config/model_registry.json
```

### 2) 构建并启动

```bash
docker compose up -d --build
```

### 3) 查看日志

```bash
docker compose logs -f
```

### 4) 停止

```bash
docker compose down
```

> **提示**：`docker-compose.yml` 中已自动将 `HOST` 覆盖为 `0.0.0.0`，无需手动修改 `.env`。

## 调用示例（直连本地网关）

### 1) 调用 neibu 模型

```bash
curl -s http://127.0.0.1:18080/v1/chat/completions \
  -H "Authorization: Bearer local-proxy-key" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "neibu_qwen3_coder",
    "messages": [{"role":"user","content":"你好，简要介绍你自己"}],
    "temperature": 0.2
  }'
```

### 2) 调用 panzhi 模型

```bash
curl -s http://127.0.0.1:18080/v1/chat/completions \
  -H "Authorization: Bearer local-proxy-key" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "panzhi_qwen3_coder",
    "messages": [{"role":"user","content":"写一段100字内总结"}],
    "temperature": 0.7
  }'
```

### 3) Python（OpenAI SDK）

```python
from openai import OpenAI

client = OpenAI(
    api_key="local-proxy-key",
    base_url="http://127.0.0.1:18080/v1",
)

resp = client.chat.completions.create(
    model="neibu_qwen3_coder",  # or panzhi_qwen3_coder
    messages=[{"role": "user", "content": "给我三点建议"}],
)
print(resp.choices[0].message.content)
```

## OpenClaw 配置

参考模板：`/Users/levent/leventProjects/llm/openclaw.example.json`

### 1) 合并 provider 到 OpenClaw 配置

OpenClaw 配置文件通常在：

- `/Users/levent/.openclaw/openclaw.json`

把下面片段合并到 `models.providers`（不要覆盖你现有 provider）：

```json
"corp-local-gateway": {
  "api": "openai-completions",
  "baseUrl": "http://127.0.0.1:18080/v1",
  "apiKey": "local-proxy-key",
  "authHeader": true,
  "models": [
    {
      "id": "panzhi_qwen3_coder",
      "name": "Qwen3 Coder (Panzhi)",
      "contextWindow": 200000,
      "maxTokens": 8192
    },
    {
      "id": "neibu_qwen3_coder",
      "name": "Qwen3 Coder (Neibu)",
      "contextWindow": 200000,
      "maxTokens": 8192
    }
  ]
}
```

### 2) 设置默认模型

可在 `openclaw.json` 中设置：

```json
"agents": {
  "defaults": {
    "model": {
      "primary": "corp-local-gateway/neibu_qwen3_coder"
    }
  }
}
```

也可用 CLI：

```bash
openclaw models set corp-local-gateway/neibu_qwen3_coder
```

### 3) 验证配置是否生效

```bash
openclaw models status --plain
openclaw models status --probe --probe-provider corp-local-gateway
openclaw status
```

### 4) 常见问题

`openclaw status` 会显示当前会话实际模型，不一定等于默认模型。默认模型失败时会自动走 fallback。

如果看到类似 `Model context window too small (4096). Minimum is 16000`，说明该模型被阻断了。把模型元信息调大：

```bash
openclaw config set models.providers.corp-local-gateway.models[0].contextWindow 200000 --strict-json
openclaw config set models.providers.corp-local-gateway.models[0].maxTokens 8192 --strict-json
openclaw config set models.providers.corp-local-gateway.models[1].contextWindow 200000 --strict-json
openclaw config set models.providers.corp-local-gateway.models[1].maxTokens 8192 --strict-json
openclaw gateway restart
```

若仍然看到旧模型，开一个新会话再观察 `status`。

## 扩展新模型

1. 同类模型：仅改 `model_registry.json` 的 `models`。
2. 新鉴权类型：在 `app/auth/strategies.py` 新增 `AuthStrategy`，并在 `build_auth_strategy` 注册。
3. 新 Provider 语义：在 `app/providers/factory.py` 新增 `_create_xxx_provider`，并在 `create_provider` 分派。

## 接口

- `GET /health`
- `GET /v1/models`
- `POST /v1/chat/completions`
- `POST /v1/completions`
- `POST /v1/responses`
