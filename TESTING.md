# Portfolio Agent API Testing Guide

## Start the Server

```bash
# From the project root directory
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

Server will start at: `http://localhost:8000`

---

## Test Endpoints with curl

### 1. Health Check
```bash
curl -X GET http://localhost:8000/health
```

**Expected Response** (Success):
```json
{
  "status": "ok",
  "built_at": "2026-02-23T12:34:56.789Z",
  "active_dataset": "v1"
}
```

**Expected Response** (With Errors):
```json
{
  "status": "ok",
  "built_at": null,
  "active_dataset": null,
  "error": "FileNotFoundError: Data files missing for active version 'v1'..."
}
```

---

### 2. List Available Datasets
```bash
curl -X GET http://localhost:8000/datasets
```

**Expected Response**:
```json
{
  "active_dataset": "v1",
  "available_datasets": ["v1", "v2"],
  "datasets": {
    "v1": {
      "path": "data/v1",
      "description": "Initial dataset"
    },
    "v2": {
      "path": "data/v2",
      "description": "Second version with updates"
    }
  }
}
```

---

### 3. Rebuild Graph
```bash
# Rebuild with default min_corr=0.25
curl -X POST http://localhost:8000/graph/rebuild

# Rebuild with custom correlation threshold
curl -X POST http://localhost:8000/graph/rebuild \
  -H "Content-Type: application/json" \
  -d '{"min_corr": 0.5}'
```

**Expected Response** (Success):
```json
{
  "message": "Graph rebuilt successfully",
  "active_dataset": "v1",
  "min_corr": 0.25,
  "built_at": "2026-02-23T12:34:56.789Z",
  "meta": {
    "num_clients": 20,
    "num_edges": 145,
    "corr_min_kept": 0.25,
    "corr_max_kept": 0.99,
    "min_corr_used": 0.25,
    "dropped_from_corr": [],
    "missing_corr_for_holdings": []
  }
}
```

**Expected Response** (Missing Files Error):
```json
{
  "detail": "Failed to rebuild graph: FileNotFoundError: Data files missing for active version 'v1'. Missing: holdings.csv (expected at: data/v1/holdings.csv), correlations.csv (expected at: data/v1/correlations.csv)"
}
```

---

### 4. Get Full Graph
```bash
# Get cached graph
curl -X GET http://localhost:8000/graph

# Get graph with different min_corr (rebuilds if different)
curl -X GET "http://localhost:8000/graph?min_corr=0.5"
```

**Expected Response**:
```json
{
  "nodes": [
    {
      "id": "bridgewater-associates",
      "label": "Bridgewater Associates",
      "gross_notional": 5234567.89,
      "net_notional": 2345678.90,
      "positions_count": 15,
      "product_mix": {
        "OPTION": 0.605,
        "EQUITY": 0.395,
        "INDEX_FUTURE": 0.0
      }
    },
    {
      "id": "man-group",
      "label": "Man Group",
      "gross_notional": 3456789.12,
      "net_notional": 1234567.89,
      "positions_count": 12,
      "product_mix": {
        "OPTION": 0.75,
        "RATES_FUTURE": 0.25
      }
    }
    // ... more nodes
  ],
  "edges": [
    {
      "source": "bridgewater-associates",
      "target": "man-group",
      "weight": 0.491,
      "corr_pct": 49.1
    },
    // ... more edges (only those >= min_corr)
  ],
  "meta": {
    "num_clients": 20,
    "num_edges": 145,
    "corr_min_kept": 0.25,
    "corr_max_kept": 0.99,
    "min_corr_used": 0.25,
    "dropped_from_corr": [],
    "missing_corr_for_holdings": []
  }
}
```

---

### 5. Get Client Details

Available client IDs from v1 dataset (real examples):
- `bridgewater-associates`
- `man-group`
- `elliott-investment-management`
- `millennium-management`
- `citadel`
- `d-e-shaw-co`
- `two-sigma`
- `goldman-sachs-asset-management`

```bash
# Get Bridgewater Associates details
curl -X GET http://localhost:8000/client/bridgewater-associates

# Get Man Group details
curl -X GET http://localhost:8000/client/man-group

# Get D. E. Shaw & Co. details
curl -X GET http://localhost:8000/client/d-e-shaw-co
```

**Expected Response** (Success):
```json
{
  "name": "Bridgewater Associates",
  "id": "bridgewater-associates",
  "positions": [
    {
      "counterparty": "Bridgewater Associates",
      "ticker_or_contract": "QQQ_20261026_P_498p94",
      "cusip": "",
      "product_type": "OPTION",
      "underlying": "QQQ",
      "quantity": 3396,
      "price_demo": 60.54,
      "notional_usd_est": 205593.84,
      "currency": "USD",
      "trade_date": "2026-02-23",
      "expiry": "2026-10-26",
      "strike": 498.94,
      "option_type": "PUT",
      "exchange": "CBOE/NYSEARCA/CME (synthetic)",
      "notes": "Synthetic demo portfolio; not real positions or prices."
    },
    // ... more positions
  ],
  "aggregates": {
    "gross_notional": 5234567.89,
    "net_notional": 2345678.90,
    "positions_count": 15,
    "product_mix": {
      "OPTION": 0.605,
      "EQUITY": 0.395,
      "INDEX_FUTURE": 0.0
    }
  }
}
```

**Expected Response** (Client Not Found - 404):
```json
{
  "detail": "Client 'invalid-client-id' not found. Available clients: bridgewater-associates, man-group, elliott-investment-management, millennium-management, citadel..."
}
```

---

### 6. Switch Dataset (and Auto-Rebuild)
```bash
# Switch to v2
curl -X POST http://localhost:8000/dataset/select \
  -H "Content-Type: application/json" \
  -d '{"dataset": "v2"}'

# Switch back to v1
curl -X POST http://localhost:8000/dataset/select \
  -H "Content-Type: application/json" \
  -d '{"dataset": "v1"}'
```

**Expected Response** (Success):
```json
{
  "message": "Switched to dataset 'v2'",
  "active_dataset": "v2",
  "meta": {
    "num_clients": 20,
    "num_edges": 142,
    "corr_min_kept": 0.25,
    "corr_max_kept": 0.99,
    "min_corr_used": 0.25,
    "dropped_from_corr": [],
    "missing_corr_for_holdings": []
  }
}
```

**Expected Response** (Invalid Dataset):
```json
{
  "detail": "Dataset 'v3' not found"
}
```

---

## Error Scenarios

### Missing Data Files

If you delete or move the CSV files:

```bash
# This will show errors in /health
curl -X GET http://localhost:8000/health
```

Response:
```json
{
  "status": "ok",
  "built_at": null,
  "active_dataset": null,
  "error": "FileNotFoundError: Data files missing for active version 'v1'. Missing: holdings.csv (expected at: data/v1/holdings.csv), correlations.csv (expected at: data/v1/correlations.csv)"
}
```

### Invalid Configuration

If `datasets.json` is missing or malformed:

```json
{
  "error": "FileNotFoundError: Configuration file not found: datasets.json..."
}
```

---

## Testing Script (Bash)

Save as `test_api.sh`:

```bash
#!/bin/bash

BASE_URL="http://localhost:8000"
INDENT="jq ."

echo "=== Testing Portfolio Agent API ==="
echo

echo "1. Health Check"
curl -s -X GET $BASE_URL/health | $INDENT
echo
echo

echo "2. List Datasets"
curl -s -X GET $BASE_URL/datasets | $INDENT
echo
echo

echo "3. Rebuild Graph with min_corr=0.25"
curl -s -X POST $BASE_URL/graph/rebuild \
  -H "Content-Type: application/json" \
  -d '{"min_corr": 0.25}' | $INDENT
echo
echo

echo "4. Get Graph (high level summary)"
curl -s -X GET $BASE_URL/graph | jq '{num_nodes: (.nodes | length), num_edges: (.edges | length), meta}'
echo
echo

echo "5. Get Bridgewater Associates Details"
curl -s -X GET $BASE_URL/client/bridgewater-associates | jq '{name, id, positions_count: (.positions | length), aggregates}'
echo
echo

echo "6. Get Invalid Client (Expected 404)"
curl -s -X GET $BASE_URL/client/invalid-client | jq .
echo

echo "=== All Tests Complete ==="
```

Run with:
```bash
chmod +x test_api.sh
./test_api.sh
```

---

## Postman Collection Alternative

Use this as a Postman collection (import as JSON):

```json
{
  "info": {
    "name": "Portfolio Agent API",
    "version": "1.0"
  },
  "item": [
    {
      "name": "Health",
      "request": {
        "method": "GET",
        "url": "{{base_url}}/health"
      }
    },
    {
      "name": "Datasets",
      "request": {
        "method": "GET",
        "url": "{{base_url}}/datasets"
      }
    },
    {
      "name": "Rebuild Graph",
      "request": {
        "method": "POST",
        "url": "{{base_url}}/graph/rebuild",
        "body": {
          "mode": "raw",
          "raw": "{\"min_corr\": 0.25}"
        }
      }
    },
    {
      "name": "Get Graph",
      "request": {
        "method": "GET",
        "url": "{{base_url}}/graph"
      }
    },
    {
      "name": "Get Client - Bridgewater",
      "request": {
        "method": "GET",
        "url": "{{base_url}}/client/bridgewater-associates"
      }
    }
  ]
}
```

Set Postman variable: `base_url = http://localhost:8000`
