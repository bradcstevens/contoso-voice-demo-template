#!/bin/bash

# Load environment variables
set -a
source .env
set +a

# Configuration
BASE_URL="https://api.digikey.com"
INDEX_DIR="product-index"
RATE_LIMIT_DELAY=1  # Delay between requests in seconds

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Ensure product-index directory exists
mkdir -p "$INDEX_DIR/categories" "$INDEX_DIR/products"

# Clean up existing files
if [ -f "${INDEX_DIR}/categories/categories.json" ]; then
  echo -e "${YELLOW}Removing existing categories file...${NC}"
  rm -f "${INDEX_DIR}/categories/categories.json"
fi

if [ -n "$(ls -A ${INDEX_DIR}/products/*.json 2>/dev/null)" ]; then
  echo -e "${YELLOW}Removing existing product files...${NC}"
  rm -f "${INDEX_DIR}/products/"*.json
fi

echo -e "${YELLOW}Step 1: Authenticating with DigiKey API...${NC}"

# Get access token
AUTH_RESPONSE=$(curl -s -X POST "$ACCESS_TOKEN_URL" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "client_id=${DIGIKEY_CLIENT_ID}&client_secret=${DIGIKEY_CLIENT_SECRET}&grant_type=${GRANT_TYPE}")

ACCESS_TOKEN=$(echo "$AUTH_RESPONSE" | jq -r '.access_token // empty')

if [ -z "$ACCESS_TOKEN" ]; then
  echo -e "${RED}Error: Failed to retrieve access token${NC}"
  echo "Response: $AUTH_RESPONSE"
  exit 1
fi

echo -e "${GREEN}✓ Authentication successful${NC}"

# Function to make API request with retry logic
make_api_request() {
  local url=$1
  local output_file=$2
  local description=$3
  local max_retries=3
  local retry_count=0
  
  while [ $retry_count -lt $max_retries ]; do
    response=$(curl -s -w "\n%{http_code}" -X GET "$url" \
      -H "Authorization: Bearer ${ACCESS_TOKEN}" \
      -H "X-DIGIKEY-Client-Id: ${DIGIKEY_CLIENT_ID}" \
      -H "Accept: application/json")
    
    http_code=$(echo "$response" | tail -n 1)
    body=$(echo "$response" | sed '$d')
    
    if [ "$http_code" -eq 200 ]; then
      echo "$body" | jq '.' > "$output_file"
      echo -e "${GREEN}✓ $description${NC}"
      return 0
    elif [ "$http_code" -eq 429 ]; then
      retry_count=$((retry_count + 1))
      echo -e "${YELLOW}⚠ Rate limit hit. Waiting 10 seconds... (Retry $retry_count/$max_retries)${NC}"
      sleep 10
    else
      echo -e "${RED}✗ Failed: $description (HTTP $http_code)${NC}"
      echo "$body" | jq '.' 2>/dev/null || echo "$body"
      return 1
    fi
  done
  
  echo -e "${RED}✗ Failed after $max_retries retries: $description${NC}"
  return 1
}

echo -e "\n${YELLOW}Step 2: Fetching all product categories...${NC}"

# Fetch all categories
make_api_request \
  "${BASE_URL}/products/v4/search/categories" \
  "${INDEX_DIR}/categories/categories.json" \
  "Retrieved all categories"

if [ $? -ne 0 ]; then
  echo -e "${RED}Failed to fetch categories. Exiting.${NC}"
  exit 1
fi

# Extract category IDs and names
CATEGORIES=$(jq -r '.Categories[] | "\(.CategoryId)|\(.Name)"' "${INDEX_DIR}/categories/categories.json")

TOTAL_CATEGORIES=$(echo "$CATEGORIES" | wc -l | xargs)
echo -e "${GREEN}Found $TOTAL_CATEGORIES categories${NC}"

echo -e "\n${YELLOW}Step 3: Fetching products for each category...${NC}"

CURRENT=0
while IFS='|' read -r category_id category_name; do
  CURRENT=$((CURRENT + 1))
  echo -e "\n[${CURRENT}/${TOTAL_CATEGORIES}] Processing: ${category_name} (ID: ${category_id})"
  
  # Create a safe filename from category name (lowercase alphanumeric with dashes)
  safe_name=$(echo "$category_name" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9]/-/g' | sed 's/--*/-/g' | sed 's/^-//; s/-$//')
  
  # Search for products in this category
  search_request="{
    \"Keywords\": \"\",
    \"Limit\": 50,
    \"Offset\": 0,
    \"FilterOptionsRequest\": {
      \"CategoryFilter\": [
        {
          \"Id\": \"${category_id}\"
        }
      ]
    }
  }"
  
  response=$(curl -s -w "\n%{http_code}" -X POST \
    "${BASE_URL}/products/v4/search/keyword" \
    -H "Authorization: Bearer ${ACCESS_TOKEN}" \
    -H "X-DIGIKEY-Client-Id: ${DIGIKEY_CLIENT_ID}" \
    -H "Content-Type: application/json" \
    -H "Accept: application/json" \
    -d "$search_request")
  
  http_code=$(echo "$response" | tail -n 1)
  body=$(echo "$response" | sed '$d')
  
  if [ "$http_code" -eq 200 ]; then
    product_count=$(echo "$body" | jq -r '.ProductsCount // 0')
    echo "$body" | jq '.' > "${INDEX_DIR}/products/${safe_name}.json"
    echo -e "${GREEN}  ✓ Found ${product_count} products${NC}"
  elif [ "$http_code" -eq 429 ]; then
    echo -e "${YELLOW}  ⚠ Rate limit hit. Waiting 10 seconds...${NC}"
    sleep 10
    # Retry this category
    CURRENT=$((CURRENT - 1))
    continue
  else
    echo -e "${RED}  ✗ Failed (HTTP $http_code)${NC}"
  fi
  
  # Rate limiting delay
  sleep $RATE_LIMIT_DELAY
done <<< "$CATEGORIES"

echo -e "\n${GREEN}========================================${NC}"
echo -e "${GREEN}✓ Product index creation complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo -e "Categories file: ${INDEX_DIR}/categories/categories.json"
echo -e "Product files: ${INDEX_DIR}/products/"
echo -e "Total categories indexed: ${TOTAL_CATEGORIES}"
