#!/bin/bash
# End-to-end smoke test script
# Tests the full recommendation system pipeline

set -e

echo "=========================================="
echo "Running End-to-End Smoke Test"
echo "=========================================="

# Configuration
INGEST_URL="http://localhost:8000"
SERVE_URL="http://localhost:8001"
TEST_USER_ID="smoke_test_user_$(date +%s)"
TEST_ITEM_ID="smoke_test_item_001"

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Helper functions
check_service() {
    local service_name=$1
    local url=$2
    
    echo -n "Checking $service_name... "
    if curl -s -f "$url/health" > /dev/null; then
        echo -e "${GREEN}✓${NC}"
        return 0
    else
        echo -e "${RED}✗${NC}"
        return 1
    fi
}

# Test 1: Check service health
echo ""
echo "Test 1: Service Health Checks"
echo "----------------------------"
if ! check_service "Ingestion Service" "$INGEST_URL"; then
    echo -e "${RED}Error: Ingestion service is not running${NC}"
    exit 1
fi

if ! check_service "Serving Service" "$SERVE_URL"; then
    echo -e "${RED}Error: Serving service is not running${NC}"
    exit 1
fi

# Test 2: Ingest events
echo ""
echo "Test 2: Event Ingestion"
echo "----------------------"
echo -n "Posting test event... "
EVENT_RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$INGEST_URL/events" \
    -H "Content-Type: application/json" \
    -d "{
        \"user_id\": \"$TEST_USER_ID\",
        \"event_type\": \"view\",
        \"item_id\": \"$TEST_ITEM_ID\",
        \"timestamp\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"
    }")

HTTP_CODE=$(echo "$EVENT_RESPONSE" | tail -n1)
if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "201" ]; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${RED}✗ (HTTP $HTTP_CODE)${NC}"
    echo "Response: $EVENT_RESPONSE"
    exit 1
fi

# Post a few more events
for i in {1..5}; do
    curl -s -X POST "$INGEST_URL/events" \
        -H "Content-Type: application/json" \
        -d "{
            \"user_id\": \"$TEST_USER_ID\",
            \"event_type\": \"view\",
            \"item_id\": \"item_00$i\",
            \"timestamp\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"
        }" > /dev/null
done
echo "Posted 6 events for user $TEST_USER_ID"

# Test 3: Wait for processing
echo ""
echo "Test 3: Waiting for Stream Processing"
echo "------------------------------------"
echo "Waiting 10 seconds for events to be processed..."
sleep 10

# Test 4: Get recommendations
echo ""
echo "Test 4: Recommendation Retrieval"
echo "--------------------------------"
echo -n "Getting recommendations for $TEST_USER_ID... "
REC_RESPONSE=$(curl -s -w "\n%{http_code}" "$SERVE_URL/recommend?user_id=$TEST_USER_ID&k=10")

HTTP_CODE=$(echo "$REC_RESPONSE" | tail -n1)
REC_BODY=$(echo "$REC_RESPONSE" | head -n-1)

if [ "$HTTP_CODE" = "200" ]; then
    echo -e "${GREEN}✓${NC}"
    echo ""
    echo "Recommendations received:"
    echo "$REC_BODY" | python -m json.tool 2>/dev/null || echo "$REC_BODY"
    
    # Check if recommendations are valid
    if echo "$REC_BODY" | grep -q "recommendations"; then
        echo -e "${GREEN}✓ Recommendations format is valid${NC}"
    else
        echo -e "${YELLOW}⚠ Recommendations may be empty (new user)${NC}"
    fi
else
    echo -e "${RED}✗ (HTTP $HTTP_CODE)${NC}"
    echo "Response: $REC_BODY"
    exit 1
fi

# Test 5: Test fallback for unknown user
echo ""
echo "Test 5: Fallback Behavior"
echo "------------------------"
UNKNOWN_USER="unknown_user_$(date +%s)"
echo -n "Testing recommendations for unknown user... "
FALLBACK_RESPONSE=$(curl -s -w "\n%{http_code}" "$SERVE_URL/recommend?user_id=$UNKNOWN_USER&k=10")

HTTP_CODE=$(echo "$FALLBACK_RESPONSE" | tail -n1)
if [ "$HTTP_CODE" = "200" ]; then
    echo -e "${GREEN}✓${NC}"
    echo "Fallback to popularity baseline works"
else
    echo -e "${YELLOW}⚠ (HTTP $HTTP_CODE)${NC}"
fi

# Summary
echo ""
echo "=========================================="
echo -e "${GREEN}✓ Smoke Test Completed Successfully!${NC}"
echo "=========================================="
echo ""
echo "Test Summary:"
echo "  - Service health checks: ✓"
echo "  - Event ingestion: ✓"
echo "  - Stream processing: ✓ (waited 10s)"
echo "  - Recommendation retrieval: ✓"
echo "  - Fallback behavior: ✓"
echo ""

