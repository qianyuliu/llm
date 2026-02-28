# OpenClaw Corp LLM Gateway

本项目把公司内的 `panzhi`（盘智）和 `juzhi`（聚智）大模型统一暴露成 OpenAI 兼容接口，供 OpenClaw 直接使用。

## 架构

```
Client → Gateway → ModelRouter → Provider (panzhi / juzhi)
                                     ↓
                              AuthStrategy → Upstream API
```

- `provider_type=panzhi` → 盘智平台（Qwen 签名认证）
- `provider_type=juzhi` → 聚智平台（HMAC-SHA256 认证）

入口代码：`app/providers/factory.py`

## 配置结构

模型注册：`config/model_registry.json`

### provider_defaults

聚智模型共享配置通过 `provider_defaults.juzhi` 统一管理，每个 provider 只需写差异字段（如 `auth.model_id_env`），其余自动继承。

### 关键字段

- `provider_type`: `panzhi` / `juzhi`
- `models[].alias`: 对 OpenClaw 暴露的模型名
- `models[].upstream_model`: 上游模型名（fallback）
- `models[].upstream_model_env`: 上游模型名环境变量（优先）

### 当前模型

| alias | 平台 | upstream_model |
|-------|------|---------------|
| `panzhi_qwen3_coder` | panzhi | qwen3_coder |
| `juzhi_qwen3_coder` | juzhi | (env) |
| `juzhi_minimax25` | juzhi | minimax25_sort... |
| `juzhi_kimi2.5` | juzhi | kimi_sort... |
| `juzhi_glm5` | juzhi | glm-5_sort... |

## 环境变量

样例：`.env.example`

### panzhi

- `PANZHI_APPID` / `PANZHI_APPKEY` / `PANZHI_MODEL_NAME` / `PANZHI_BASE_URL`

### juzhi（所有聚智模型共享）

- `OPENAI_API_BASE` / `OPENAI_API_ID` / `OPENAI_API_SECRET`
- `MODELSOURCE` / `TRACE_ID` / `MODEL_ID` / `INTERNAL_DEFAULT_MODEL`

### 聚智模型 modelId（HMAC 签名用）

- `MINIMAX25_MODEL_ID` / `KIMI25_MODEL_ID` / `GLM5_MODEL_ID`

`custom_resolvers.get_api_key` 实现 HMAC 签名逻辑：`custom_resolvers.py`

## 启动

```bash
cd /Users/levent/leventProjects/llm
pip install -e ".[dev]"

cp .env.example .env
cp config/model_registry.example.json config/model_registry.json

python -m app.main
```

## Docker 启动

```bash
cp .env.example .env                    # 编辑填入真实密钥
cp config/model_registry.example.json config/model_registry.json
docker compose up -d --build
docker compose logs -f                  # 查看日志
docker compose down                     # 停止
```

> **提示**：`docker-compose.yml` 中已自动将 `HOST` 覆盖为 `0.0.0.0`。

## 调用示例

### curl

```bash
# 聚智 minimax25
curl -s http://127.0.0.1:18080/v1/chat/completions \
  -H "Authorization: Bearer local-proxy-key" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "juzhi_minimax25",
    "messages": [{"role":"user","content":"你好"}],
    "temperature": 0.2
  }'

# 盘智 qwen3_coder
curl -s http://127.0.0.1:18080/v1/chat/completions \
  -H "Authorization: Bearer local-proxy-key" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "panzhi_qwen3_coder",
    "messages": [{"role":"user","content":"写一段100字内总结"}],
    "temperature": 0.7
  }'
```

### Python（OpenAI SDK）

```python
from openai import OpenAI

client = OpenAI(
    api_key="local-proxy-key",
    base_url="http://127.0.0.1:18080/v1",
)

resp = client.chat.completions.create(
    model="juzhi_kimi2.5",
    messages=[{"role": "user", "content": "给我三点建议"}],
)
print(resp.choices[0].message.content)
```

## OpenClaw 配置

参考模板：`openclaw.example.json`

把下面片段合并到 OpenClaw 配置的 `models.providers`：

```json
"corp-local-gateway": {
  "api": "openai-completions",
  "baseUrl": "http://127.0.0.1:18080/v1",
  "apiKey": "local-proxy-key",
  "authHeader": true,
  "models": [
    {"id": "panzhi_qwen3_coder", "name": "Qwen3 Coder (Panzhi)", "contextWindow": 200000, "maxTokens": 8192},
    {"id": "juzhi_qwen3_coder", "name": "Qwen3 Coder (Juzhi)", "contextWindow": 200000, "maxTokens": 8192},
    {"id": "juzhi_minimax25", "name": "MiniMax 2.5 (Juzhi)", "contextWindow": 200000, "maxTokens": 8192},
    {"id": "juzhi_kimi2.5", "name": "Kimi 2.5 (Juzhi)", "contextWindow": 200000, "maxTokens": 8192},
    {"id": "juzhi_glm5", "name": "GLM-5 (Juzhi)", "contextWindow": 200000, "maxTokens": 8192}
  ]
}
```

## 扩展新模型

1. 同类模型：仅改 `model_registry.json` 的 `providers`。
2. 新鉴权类型：在 `app/auth/strategies.py` 新增 `AuthStrategy`，并在 `build_auth_strategy` 注册。
3. 新 Provider 语义：在 `app/providers/factory.py` 新增 `_create_xxx_provider`，并在 `create_provider` 分派。

## 接口

- `GET /health`
- `GET /v1/models`
- `POST /v1/chat/completions`
- `POST /v1/completions`
- `POST /v1/responses`
