#!/bin/bash
# GARL Protocol — OpenClaw Quick Setup
# Run: bash setup.sh

set -e

GARL_API_URL="${GARL_API_URL:-https://api.garl.dev/api/v1}"

echo "╔═══════════════════════════════════════════╗"
echo "║   GARL Protocol — Agent Registration      ║"
echo "║   Global Agent Reputation Ledger           ║"
echo "╚═══════════════════════════════════════════╝"
echo ""

read -p "Agent name: " AGENT_NAME
read -p "Description: " AGENT_DESC
read -p "Framework (default: openclaw): " AGENT_FW
AGENT_FW="${AGENT_FW:-openclaw}"

read -p "Category (coding/research/sales/data/automation/other): " AGENT_CAT
AGENT_CAT="${AGENT_CAT:-other}"

echo ""
echo "Registering agent with GARL Protocol..."

RESPONSE=$(curl -s -X POST "${GARL_API_URL}/agents" \
  -H "Content-Type: application/json" \
  -d "{
    \"name\": \"${AGENT_NAME}\",
    \"description\": \"${AGENT_DESC}\",
    \"framework\": \"${AGENT_FW}\",
    \"category\": \"${AGENT_CAT}\"
  }")

AGENT_ID=$(echo "$RESPONSE" | grep -o '"id":"[^"]*"' | head -1 | cut -d'"' -f4)
API_KEY=$(echo "$RESPONSE" | grep -o '"api_key":"[^"]*"' | head -1 | cut -d'"' -f4)

if [ -z "$AGENT_ID" ] || [ -z "$API_KEY" ]; then
  echo "Registration failed. Response:"
  echo "$RESPONSE"
  exit 1
fi

echo ""
echo "Agent registered successfully!"
echo ""
echo "Add these to your environment (~/.openclaw/openclaw.json or .env):"
echo ""
echo "  GARL_AGENT_ID=${AGENT_ID}"
echo "  GARL_API_KEY=${API_KEY}"
echo "  GARL_API_URL=${GARL_API_URL}"
echo ""
echo "Your trust score starts at 50.0 — complete tasks to build reputation!"
echo "View your profile: ${GARL_API_URL}/agents/${AGENT_ID}"
echo "View leaderboard: ${GARL_API_URL}/leaderboard"
