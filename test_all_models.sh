#!/bin/bash
# LLM Gateway 全模型手动测试脚本
# 使用方式：连上 VPN 后，在项目根目录执行
#   conda activate levent
#   python -m app.main &
#   bash test_all_models.sh

BASE="http://127.0.0.1:18080"
KEY="local-proxy-key"
MODELS=("panzhi_qwen3_coder" "juzhi_qwen3_coder" "juzhi_minimax25" "juzhi_kimi2.5" "juzhi_glm5")

echo "============================================"
echo "  LLM Gateway 全模型测试"
echo "  $(date '+%Y-%m-%d %H:%M:%S')"
echo "============================================"
echo ""

# Step 1: 健康检查
echo "▶ [1/3] 健康检查"
STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/health")
if [ "$STATUS" = "200" ]; then
  echo "  ✅ /health → $STATUS"
else
  echo "  ❌ /health → $STATUS（网关未启动？）"
  exit 1
fi
echo ""

# Step 2: 模型列表
echo "▶ [2/3] 模型列表"
echo "  GET /v1/models"
MODELS_RESP=$(curl -s "$BASE/v1/models" -H "Authorization: Bearer $KEY")
echo "$MODELS_RESP" | python3 -m json.tool 2>/dev/null || echo "$MODELS_RESP"
echo ""

# 检查每个模型是否在列表中
for MODEL in "${MODELS[@]}"; do
  if echo "$MODELS_RESP" | grep -q "\"$MODEL\""; then
    echo "  ✅ $MODEL 已注册"
  else
    echo "  ❌ $MODEL 未找到！"
  fi
done
echo ""

# Step 3: 逐个调用
echo "▶ [3/3] 逐模型调用测试"
echo ""

PASS=0
FAIL=0

for MODEL in "${MODELS[@]}"; do
  echo "  ── $MODEL ──"
  START=$(date +%s)

  RESP=$(curl -s --max-time 60 "$BASE/v1/chat/completions" \
    -H "Authorization: Bearer $KEY" \
    -H "Content-Type: application/json" \
    -d "{
      \"model\": \"$MODEL\",
      \"messages\": [{\"role\":\"user\",\"content\":\"用一句话介绍你自己\"}],
      \"temperature\": 0.1,
      \"max_tokens\": 300
    }" 2>&1)

  END=$(date +%s)
  ELAPSED=$((END - START))

  # 检查是否有 choices
  if echo "$RESP" | grep -q '"choices"'; then
    CONTENT=$(echo "$RESP" | python3 -c "
import sys, json
d = json.load(sys.stdin)
msg = d['choices'][0]['message']
text = (msg.get('content', '') or '').strip()
reason = (msg.get('reasoning', '') or msg.get('reasoning_content', '') or '').strip()
if text:
    print(text[:120])
elif reason:
    print('[思考链] ' + reason[:120])
else:
    print('[空回复]')
" 2>/dev/null)
    echo "  ✅ 成功 (${ELAPSED}s)"
    echo "  回复: $CONTENT"
    PASS=$((PASS + 1))
  else
    echo "  ❌ 失败 (${ELAPSED}s)"
    echo "  原始响应:"
    echo "$RESP" | python3 -m json.tool 2>/dev/null || echo "  $RESP"
    FAIL=$((FAIL + 1))
  fi
  echo ""
done

# 汇总
echo "============================================"
echo "  测试结果: $PASS 通过 / $FAIL 失败 / ${#MODELS[@]} 总计"
echo "============================================"
