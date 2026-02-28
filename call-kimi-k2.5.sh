#!/bin/bash

# Kimi-K2.5-vip 模型 curl 调用脚本
# 使用 HMAC-SHA256 签名鉴权，兼容 OpenAI 协议

# ===== 配置参数 =====
REQUEST_URL="http://172.16.251.142:9060/openapi/flames/api/v1/openai/chat"
APP_ID="267E7EE677234E989425"
APP_SECRET="1AE49E6F7AE74672B3E7B27C809E3723"
MODEL_ID="b9dc3f41-c661-42f4-8301-e26bf2cdef2f"
MODEL_SOURCE="public"
TRACE_ID="b4ed2004-ac50-4592-910f-53a4df9de13b"

# ===== 用户输入内容（可修改）=====
CONTENT="${1:-你好}"

# ===== 从 URL 提取 host 和 path =====
HOST="172.16.251.142"
PATH_STR="/openapi/flames/api/v1/openai/chat"

# ===== 生成 GMT 日期 =====
DATE=$(LC_ALL=en_US.UTF-8 date -u '+%a, %d %b %Y %H:%M:%S GMT')

# ===== 构造 request-line =====
REQUEST_LINE="POST ${PATH_STR} HTTP/1.1"

# ===== 构造签名字符串 =====
SIGNING_STR="host: ${HOST}\ndate: ${DATE}\n${REQUEST_LINE}"

# ===== HMAC-SHA256 签名 =====
SIGNATURE=$(printf '%b' "$SIGNING_STR" | openssl dgst -sha256 -hmac "$APP_SECRET" -binary | base64 | tr -d '\n')

# ===== 构造 auth_string =====
AUTH_STRING="hmac api_key=\"${APP_ID}\", algorithm=\"hmac-sha256\", headers=\"host date request-line\", signature=\"${SIGNATURE}\", modelId=\"${MODEL_ID}\", modelSource=\"${MODEL_SOURCE}\", traceId=\"${TRACE_ID}\", host=\"${HOST}\", date=\"${DATE}\", request-line=\"${REQUEST_LINE}\""

# ===== Base64 编码 auth_string =====
AUTH_BASE64=$(printf '%s' "$AUTH_STRING" | base64 | tr -d '\n')

echo "===== 请求信息 ====="
echo "URL: ${REQUEST_URL}"
echo "Date: ${DATE}"
echo "Content: ${CONTENT}"
echo "==================="
echo ""

# ===== 调用 curl =====
curl -X POST "$REQUEST_URL" \
  -H "Authorization: Bearer ${AUTH_BASE64}" \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -d "{
    \"model\": \"Kimi-K2.5-vip_sort20260225101726\",
    \"messages\": [
      {
        \"role\": \"user\",
        \"content\": \"${CONTENT}\"
      }
    ]
  }"

echo ""
