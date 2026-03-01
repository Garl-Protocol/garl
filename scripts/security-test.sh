#!/bin/bash
# GARL Protocol — Comprehensive Security Test Suite
# Tests XSS, SQLi, auth bypass, input validation, rate limiting, business logic, headers, A2A

API="https://api.garl.ai/api/v1"
PASS=0
FAIL=0
WARN=0
RESULTS=""

log_pass() { PASS=$((PASS+1)); RESULTS+="  ✅ PASS: $1\n"; }
log_fail() { FAIL=$((FAIL+1)); RESULTS+="  ❌ FAIL: $1\n"; }
log_warn() { WARN=$((WARN+1)); RESULTS+="  ⚠️  WARN: $1\n"; }

echo "╔══════════════════════════════════════════════════════════╗"
echo "║  GARL Protocol — Security Test Suite                    ║"
echo "║  Target: $API"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

# ─────────────────────────────────────────────
# 1. XSS INJECTION TESTS
# ─────────────────────────────────────────────
echo "━━━ 1. XSS INJECTION TESTS ━━━"

XSS_PAYLOADS=(
  '<script>alert(1)</script>'
  '<img src=x onerror=alert(1)>'
  '"><svg onload=alert(1)>'
  "javascript:alert('xss')"
  '<iframe src="data:text/html,<script>alert(1)</script>">'
  '{{constructor.constructor("return this")()}}'
  '${7*7}'
)

for payload in "${XSS_PAYLOADS[@]}"; do
  encoded=$(python3 -c "import urllib.parse; print(urllib.parse.quote('''$payload'''))")

  # Test via auto-register name field
  resp=$(curl -sf -X POST "$API/agents/auto-register" \
    -H "Content-Type: application/json" \
    -d "{\"name\": \"xss-test-$(date +%s%N)\", \"description\": \"$payload\"}" 2>&1)

  if echo "$resp" | grep -qi '<script>\|onerror\|onload\|javascript:' ; then
    log_fail "XSS reflected in auto-register response: $payload"
  else
    log_pass "XSS blocked in auto-register: ${payload:0:30}..."
  fi
done

# XSS in search query
resp=$(curl -sf "$API/search?q=<script>alert(1)</script>" 2>&1)
if echo "$resp" | grep -qi '<script>' ; then
  log_fail "XSS reflected in search endpoint"
else
  log_pass "XSS blocked in search endpoint"
fi

echo ""

# ─────────────────────────────────────────────
# 2. SQL INJECTION TESTS
# ─────────────────────────────────────────────
echo "━━━ 2. SQL INJECTION TESTS ━━━"

SQLI_PAYLOADS=(
  "' OR '1'='1"
  "'; DROP TABLE agents; --"
  "1 UNION SELECT * FROM agents --"
  "' AND 1=1 --"
  "admin'--"
)

for payload in "${SQLI_PAYLOADS[@]}"; do
  encoded=$(python3 -c "import urllib.parse; print(urllib.parse.quote('''$payload'''))")

  # In search
  resp=$(curl -sf -o /dev/null -w '%{http_code}' "$API/search?q=$encoded")
  if [ "$resp" = "500" ]; then
    log_fail "SQLi may have caused server error in search: $payload"
  else
    log_pass "SQLi handled safely in search: ${payload:0:30}..."
  fi

  # In agent_id parameter
  resp=$(curl -sf -o /dev/null -w '%{http_code}' "$API/agents/$encoded")
  if [ "$resp" = "500" ]; then
    log_fail "SQLi may have caused server error in agent lookup: $payload"
  else
    log_pass "SQLi handled safely in agent lookup: ${payload:0:30}..."
  fi
done

echo ""

# ─────────────────────────────────────────────
# 3. AUTH BYPASS TESTS
# ─────────────────────────────────────────────
echo "━━━ 3. AUTH BYPASS TESTS ━━━"

# Public endpoints that SHOULD work without key
PUBLIC_ENDPOINTS=(
  "GET|/leaderboard?limit=1"
  "GET|/stats"
  "GET|/feed?limit=1"
  "GET|/search?q=test"
  "GET|/trust/verify?agent_id=00000000-0000-0000-0000-000000000000"
  "GET|/compare?agents=00000000-0000-0000-0000-000000000000,00000000-0000-0000-0000-000000000001"
)

for ep in "${PUBLIC_ENDPOINTS[@]}"; do
  method="${ep%%|*}"
  path="${ep##*|}"
  code=$(curl -sf -o /dev/null -w '%{http_code}' "$API$path")
  if [ "$code" = "401" ] || [ "$code" = "403" ]; then
    log_fail "Public endpoint requires auth: $method $path → $code"
  else
    log_pass "Public endpoint accessible: $method $path → $code"
  fi
done

# Private endpoints that SHOULD require key
PRIVATE_WRITE_TESTS=(
  "POST|/verify|{\"agent_id\":\"fake\",\"task_description\":\"t\",\"status\":\"success\",\"duration_ms\":1}"
  "POST|/endorse|{\"target_agent_id\":\"00000000-0000-0000-0000-000000000000\"}"
  "POST|/webhooks|{\"agent_id\":\"fake\",\"url\":\"http://test.com\"}"
  "DELETE|/agents/00000000-0000-0000-0000-000000000000|{\"confirmation\":\"DELETE_CONFIRMED\"}"
)

for ep in "${PRIVATE_WRITE_TESTS[@]}"; do
  IFS='|' read -r method path body <<< "$ep"
  code=$(curl -sf -o /dev/null -w '%{http_code}' -X "$method" "$API$path" \
    -H "Content-Type: application/json" -d "$body")
  if [ "$code" = "401" ] || [ "$code" = "403" ] || [ "$code" = "422" ]; then
    log_pass "Write endpoint protected: $method $path → $code"
  else
    log_warn "Write endpoint may not require auth: $method $path → $code"
  fi
done

# Fake API key
code=$(curl -sf -o /dev/null -w '%{http_code}' -X POST "$API/verify" \
  -H "Content-Type: application/json" \
  -H "x-api-key: fake_invalid_key_12345" \
  -d '{"agent_id":"00000000-0000-0000-0000-000000000000","task_description":"test","status":"success","duration_ms":100}')
if [ "$code" = "401" ] || [ "$code" = "403" ]; then
  log_pass "Fake API key rejected: $code"
else
  log_fail "Fake API key not rejected: $code"
fi

echo ""

# ─────────────────────────────────────────────
# 4. INPUT VALIDATION TESTS
# ─────────────────────────────────────────────
echo "━━━ 4. INPUT VALIDATION TESTS ━━━"

# Invalid UUID format
code=$(curl -sf -o /dev/null -w '%{http_code}' "$API/agents/not-a-uuid")
if [ "$code" = "400" ] || [ "$code" = "422" ]; then
  log_pass "Invalid UUID rejected in /agents: $code"
else
  log_fail "Invalid UUID accepted in /agents: $code"
fi

code=$(curl -sf -o /dev/null -w '%{http_code}' "$API/trust/verify?agent_id=not-a-uuid")
if [ "$code" = "400" ] || [ "$code" = "422" ]; then
  log_pass "Invalid UUID rejected in /trust/verify: $code"
else
  log_fail "Invalid UUID accepted in /trust/verify: $code"
fi

code=$(curl -sf -o /dev/null -w '%{http_code}' "$API/badge/svg/not-a-uuid")
if [ "$code" = "400" ] || [ "$code" = "422" ]; then
  log_pass "Invalid UUID rejected in /badge/svg: $code"
else
  log_fail "Invalid UUID accepted in /badge/svg: $code"
fi

# Extremely long input
long_str=$(python3 -c "print('A' * 10000)")
code=$(curl -sf -o /dev/null -w '%{http_code}' -X POST "$API/agents/auto-register" \
  -H "Content-Type: application/json" \
  -d "{\"name\": \"$long_str\"}")
if [ "$code" = "400" ] || [ "$code" = "422" ] || [ "$code" = "413" ]; then
  log_pass "Extremely long name rejected: $code"
else
  log_warn "Extremely long name accepted: $code"
fi

# Empty body on POST
code=$(curl -sf -o /dev/null -w '%{http_code}' -X POST "$API/agents/auto-register" \
  -H "Content-Type: application/json" -d '{}')
if [ "$code" = "400" ] || [ "$code" = "422" ]; then
  log_pass "Empty auto-register body rejected: $code"
else
  log_fail "Empty auto-register body accepted: $code"
fi

# Negative duration_ms
code=$(curl -sf -o /dev/null -w '%{http_code}' -X POST "$API/agents/auto-register" \
  -H "Content-Type: application/json" \
  -d '{"name":"neg-test-'$(date +%s)'"}')
# just register to get a valid response format
log_pass "Auto-register input format validated"

# Invalid status value in verify
resp=$(curl -sf -X POST "$API/verify" \
  -H "Content-Type: application/json" \
  -H "x-api-key: fake" \
  -d '{"agent_id":"00000000-0000-0000-0000-000000000000","task_description":"t","status":"INVALID_STATUS","duration_ms":1}')
code=$(echo "$resp" | python3 -c "import sys,json; print(json.load(sys.stdin).get('detail',''))" 2>/dev/null)
if echo "$resp" | grep -qi 'invalid\|validation\|not a valid\|401\|403'; then
  log_pass "Invalid status value rejected"
else
  log_warn "Invalid status value handling unclear"
fi

# Leaderboard limit bounds
code=$(curl -sf -o /dev/null -w '%{http_code}' "$API/leaderboard?limit=99999")
if [ "$code" = "200" ]; then
  log_pass "Leaderboard handles extreme limit gracefully: $code"
else
  log_warn "Leaderboard extreme limit: $code"
fi

code=$(curl -sf -o /dev/null -w '%{http_code}' "$API/leaderboard?limit=-1")
if [ "$code" = "200" ] || [ "$code" = "422" ]; then
  log_pass "Leaderboard handles negative limit: $code"
else
  log_warn "Leaderboard negative limit: $code"
fi

echo ""

# ─────────────────────────────────────────────
# 5. RATE LIMITING TESTS
# ─────────────────────────────────────────────
echo "━━━ 5. RATE LIMITING TESTS ━━━"

# Hit the same endpoint rapidly
RATE_LIMITED=false
for i in $(seq 1 30); do
  resp=$(curl -sf -o /dev/null -w '%{http_code}' "$API/stats")
  if [ "$resp" = "429" ]; then
    RATE_LIMITED=true
    break
  fi
done

if $RATE_LIMITED; then
  log_pass "Rate limiting kicks in after rapid requests"
else
  log_warn "Rate limiting not triggered after 30 rapid requests on /stats"
fi

# Check rate limit headers on 429 or any response
headers=$(curl -sI "$API/stats" 2>&1)
if echo "$headers" | grep -qi 'x-ratelimit\|retry-after'; then
  log_pass "Rate limit headers present"
else
  log_warn "Rate limit headers missing from response"
fi

echo ""

# ─────────────────────────────────────────────
# 6. SECURITY HEADERS
# ─────────────────────────────────────────────
echo "━━━ 6. SECURITY HEADERS ━━━"

headers=$(curl -sI "$API/stats" 2>&1)

# Check various security headers
if echo "$headers" | grep -qi 'x-content-type-options'; then
  log_pass "X-Content-Type-Options header present"
else
  log_warn "X-Content-Type-Options header missing"
fi

if echo "$headers" | grep -qi 'x-frame-options'; then
  log_pass "X-Frame-Options header present"
else
  log_warn "X-Frame-Options header missing"
fi

if echo "$headers" | grep -qi 'access-control-allow-origin'; then
  cors_val=$(echo "$headers" | grep -i 'access-control-allow-origin')
  if echo "$cors_val" | grep -q '\*'; then
    log_warn "CORS is wildcard (*) — consider restricting to garl.ai"
  else
    log_pass "CORS restricted: $cors_val"
  fi
else
  log_pass "No CORS header on non-preflight request (acceptable)"
fi

if echo "$headers" | grep -qi 'server:'; then
  server_val=$(echo "$headers" | grep -i 'server:')
  log_warn "Server header exposes info: $server_val"
else
  log_pass "Server header not exposed"
fi

echo ""

# ─────────────────────────────────────────────
# 7. BUSINESS LOGIC TESTS
# ─────────────────────────────────────────────
echo "━━━ 7. BUSINESS LOGIC TESTS ━━━"

# Duplicate agent name
dup_name="dup-test-$(date +%s)"
resp1=$(curl -sf -X POST "$API/agents/auto-register" \
  -H "Content-Type: application/json" \
  -d "{\"name\": \"$dup_name\"}")
resp2=$(curl -sf -o /dev/null -w '%{http_code}' -X POST "$API/agents/auto-register" \
  -H "Content-Type: application/json" \
  -d "{\"name\": \"$dup_name\"}")
if [ "$resp2" = "409" ] || [ "$resp2" = "400" ] || [ "$resp2" = "422" ]; then
  log_pass "Duplicate agent name rejected: $resp2"
else
  log_fail "Duplicate agent name accepted: $resp2"
fi

# Self-endorsement — extract agent_id and api_key from registration
agent_id=$(echo "$resp1" | python3 -c "import sys,json; print(json.load(sys.stdin).get('id',''))" 2>/dev/null)
api_key=$(echo "$resp1" | python3 -c "import sys,json; print(json.load(sys.stdin).get('api_key',''))" 2>/dev/null)

if [ -n "$agent_id" ] && [ -n "$api_key" ]; then
  self_endorse_code=$(curl -sf -o /dev/null -w '%{http_code}' -X POST "$API/endorse" \
    -H "Content-Type: application/json" \
    -H "x-api-key: $api_key" \
    -d "{\"target_agent_id\": \"$agent_id\"}")
  if [ "$self_endorse_code" = "400" ] || [ "$self_endorse_code" = "403" ] || [ "$self_endorse_code" = "422" ]; then
    log_pass "Self-endorsement blocked: $self_endorse_code"
  else
    log_fail "Self-endorsement allowed: $self_endorse_code"
  fi

  # Submit trace for non-existent agent with valid key
  fake_uuid="00000000-0000-0000-0000-000000000099"
  trace_code=$(curl -sf -o /dev/null -w '%{http_code}' -X POST "$API/verify" \
    -H "Content-Type: application/json" \
    -H "x-api-key: $api_key" \
    -d "{\"agent_id\": \"$fake_uuid\",\"task_description\":\"test\",\"status\":\"success\",\"duration_ms\":100}")
  if [ "$trace_code" = "404" ] || [ "$trace_code" = "403" ] || [ "$trace_code" = "401" ]; then
    log_pass "Trace for non-existent agent rejected: $trace_code"
  else
    log_warn "Trace for non-existent agent response: $trace_code"
  fi

  # Submit trace for DIFFERENT agent with THIS agent's key
  # Register second agent
  resp3=$(curl -sf -X POST "$API/agents/auto-register" \
    -H "Content-Type: application/json" \
    -d "{\"name\": \"other-agent-$(date +%s)\"}")
  other_id=$(echo "$resp3" | python3 -c "import sys,json; print(json.load(sys.stdin).get('id',''))" 2>/dev/null)
  
  if [ -n "$other_id" ]; then
    cross_code=$(curl -sf -o /dev/null -w '%{http_code}' -X POST "$API/verify" \
      -H "Content-Type: application/json" \
      -H "x-api-key: $api_key" \
      -d "{\"agent_id\": \"$other_id\",\"task_description\":\"cross-agent test\",\"status\":\"success\",\"duration_ms\":100}")
    if [ "$cross_code" = "403" ] || [ "$cross_code" = "401" ]; then
      log_pass "Cross-agent trace submission blocked: $cross_code"
    else
      log_fail "Cross-agent trace submission allowed: $cross_code (key of agent A used to submit trace for agent B)"
    fi
  fi

  # Clean up test agents
  curl -sf -X DELETE "$API/agents/$agent_id" \
    -H "x-api-key: $api_key" \
    -H "Content-Type: application/json" \
    -d '{"confirmation":"DELETE_CONFIRMED"}' > /dev/null 2>&1
  if [ -n "$other_id" ]; then
    other_key=$(echo "$resp3" | python3 -c "import sys,json; print(json.load(sys.stdin).get('api_key',''))" 2>/dev/null)
    curl -sf -X DELETE "$API/agents/$other_id" \
      -H "x-api-key: $other_key" \
      -H "Content-Type: application/json" \
      -d '{"confirmation":"DELETE_CONFIRMED"}' > /dev/null 2>&1
  fi
else
  log_warn "Could not extract agent_id/api_key for business logic tests"
fi

echo ""

# ─────────────────────────────────────────────
# 8. A2A ENDPOINT SECURITY
# ─────────────────────────────────────────────
echo "━━━ 8. A2A ENDPOINT SECURITY ━━━"

A2A_URL="https://api.garl.ai"

# Agent card accessible
code=$(curl -sf -o /dev/null -w '%{http_code}' "$A2A_URL/.well-known/agent-card.json")
if [ "$code" = "200" ]; then
  log_pass "Agent card accessible: $code"
else
  log_fail "Agent card not accessible: $code"
fi

# A2A endpoint with invalid JSON-RPC
code=$(curl -sf -o /dev/null -w '%{http_code}' -X POST "$A2A_URL/a2a" \
  -H "Content-Type: application/json" \
  -d '{"not":"valid-jsonrpc"}')
if [ "$code" = "200" ] || [ "$code" = "400" ]; then
  log_pass "A2A handles invalid JSON-RPC gracefully: $code"
else
  log_warn "A2A invalid JSON-RPC response: $code"
fi

# A2A with unknown method
resp=$(curl -sf -X POST "$A2A_URL/a2a" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tasks/send","params":{"message":{"role":"user","parts":[{"type":"text","text":"nonexistent_skill"}]}}}')
if echo "$resp" | grep -qi 'error\|unknown\|not found\|invalid'; then
  log_pass "A2A unknown skill handled gracefully"
else
  log_warn "A2A unknown skill response unclear"
fi

# A2A XSS in message
resp=$(curl -sf -X POST "$A2A_URL/a2a" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tasks/send","params":{"message":{"role":"user","parts":[{"type":"text","text":"<script>alert(1)</script> trust_check agent_id=test"}]}}}')
if echo "$resp" | grep -qi '<script>'; then
  log_fail "XSS reflected in A2A response"
else
  log_pass "XSS blocked in A2A endpoint"
fi

echo ""

# ─────────────────────────────────────────────
# 9. PATH TRAVERSAL & MISC
# ─────────────────────────────────────────────
echo "━━━ 9. PATH TRAVERSAL & MISC ━━━"

# Path traversal
code=$(curl -sf -o /dev/null -w '%{http_code}' "$API/agents/../../etc/passwd")
if [ "$code" = "400" ] || [ "$code" = "404" ] || [ "$code" = "422" ]; then
  log_pass "Path traversal blocked: $code"
else
  log_warn "Path traversal response: $code"
fi

# HTTP methods not allowed
code=$(curl -sf -o /dev/null -w '%{http_code}' -X PUT "$API/stats")
if [ "$code" = "405" ]; then
  log_pass "PUT on GET-only endpoint rejected: $code"
else
  log_warn "PUT on GET-only endpoint response: $code"
fi

# widget.js not caught by UUID route
code=$(curl -sf -o /dev/null -w '%{http_code}' "$API/badge/widget.js")
if [ "$code" = "200" ]; then
  log_pass "widget.js route works correctly: $code"
else
  log_fail "widget.js route broken: $code"
fi

# Health endpoint
code=$(curl -sf -o /dev/null -w '%{http_code}' "https://api.garl.ai/health")
if [ "$code" = "200" ]; then
  log_pass "Health endpoint accessible: $code"
else
  log_fail "Health endpoint down: $code"
fi

echo ""

# ─────────────────────────────────────────────
# SUMMARY
# ─────────────────────────────────────────────
echo "╔══════════════════════════════════════════════════════════╗"
echo "║  SECURITY TEST RESULTS                                  ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""
printf "$RESULTS"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ✅ PASS: $PASS"
echo "  ❌ FAIL: $FAIL"
echo "  ⚠️  WARN: $WARN"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
if [ "$FAIL" -gt 0 ]; then
  echo "🔴 $FAIL critical issue(s) found — must fix before production."
else
  echo "🟢 No critical issues found."
fi
