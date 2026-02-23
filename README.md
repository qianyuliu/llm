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

参考：`/Users/levent/leventProjects/llm/openclaw.example.json`

配置后可直接选：

- `corp-local-gateway/panzhi_qwen3_coder`
- `corp-local-gateway/neibu_qwen3_coder`

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

