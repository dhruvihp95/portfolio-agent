# Portfolio Agent - Complete Implementation

A FastAPI-based backend for analyzing investment portfolios using graph-based correlation analysis. Reads holdings and correlation matrices, builds a client interaction graph, and provides REST endpoints for querying portfolio data.

## Project Overview

**Purpose**: Build a Python FastAPI backend that processes investment holdings and correlation data to construct a client graph where nodes represent counterparties and edges represent correlation weights.

**Key Features**:
- ✅ Reads two CSVs: holdings (positions) + correlation matrix
- ✅ Builds in-memory graph with nodes (counterparties) and edges (correlations)
- ✅ Supports two dataset versions (v1 and v2) with easy switching
- ✅ Data-agnostic: gracefully handles mismatches between datasets
- ✅ REST API with 6 endpoints + CORS enabled
- ✅ Automatic graph rebuild with configurable correlation threshold
- ✅ Comprehensive error handling and reporting

---

## Architecture

### Core Modules

#### `portfolio_agent.py` (395 lines)
**Main graph builder with FastAPI integration**

**Key Functions**:
- `slugify(name: str)`: Converts counterparty names to URL-friendly slugs
  - Example: "D. E. Shaw & Co." → "d-e-shaw-co"
  
- `build_graph(holdings_path, corr_path, min_corr=0.25)`: 
  - Returns: `(nodes, edges, client_details, meta)` tuple
  - **Nodes**: `{id, label, gross_notional, net_notional, positions_count, product_mix}`
  - **Edges**: `{source, target, weight (normalized 0-1), corr_pct (original %)}`
  - **Client Details**: Full position data with aggregates per counterparty
  - **Meta**: Statistics including dropped/missing names, correlation ranges
  - **Data-agnostic**: Handles mismatches gracefully, reports discrepancies

**Validation**:
- Requires holdings columns: counterparty, ticker_or_contract, product_type, quantity, price_demo, notional_usd_est
- Only raises on missing core columns or unreadable files
- Never crashes on data mismatches

#### `app.py` (377 lines)
**Configuration, state management, and REST API endpoints**

**Global State**:
```python
GRAPH_STATE = {
    "active_dataset": str,
    "min_corr": float,
    "built_at": ISO timestamp,
    "nodes": List,
    "edges": List,
    "client_details": Dict,
    "meta": Dict,
    "error": Optional[str],
}
```

**Helper Functions**:
- `load_datasets_config()`: Reads datasets.json with validation
- `save_datasets_config(cfg)`: Persists config back to file
- `get_active_paths()`: Returns (holdings_path, correlations_path) with full validation
- `rebuild_graph(min_corr=None)`: Rebuilds graph and updates GRAPH_STATE

**Initialization**: On import, automatically tries to rebuild graph with default min_corr=0.25. If it fails, stores error but keeps server running.

**REST Endpoints** (6 total):
1. `GET /health` → Status, build timestamp, active dataset, errors
2. `GET /datasets` → Available versions, active version, dataset metadata
3. `POST /dataset/select {dataset}` → Switch version, auto-rebuild
4. `POST /graph/rebuild {min_corr?}` → Force rebuild with optional threshold
5. `GET /graph ?min_corr` → Get full graph (rebuilds if min_corr differs)
6. `GET /client/{client_id}` → Get client details with all positions and aggregates

**CORS**: Fully permissive (all origins, methods, headers) for hackathon use.

#### `scripts/print_summary.py` (109 lines)
**Local debugging script**

Prints to console:
- Active dataset and build timestamp
- Total clients and edges
- Top 3 clients by gross notional with details
- Dropped and missing counterparties (if any)

**Usage**: `python scripts/print_summary.py`

---

## Data Files

### Structure
```
data/
├── v1/
│   ├── holdings.csv          (225 positions, 20 counterparties)
│   └── correlations.csv      (20x20 correlation matrix)
└── v2/
    ├── holdings.csv
    └── correlations.csv

datasets.json                 (Registry of available versions & active)
```

### CSV Formats

**holdings.csv** (Required columns):
- counterparty: Investment firm name
- ticker_or_contract: Security identifier
- product_type: OPTION, EQUITY, RATES_FUTURE, etc.
- quantity: Position size (signed)
- price_demo: Demo price
- notional_usd_est: Estimated notional value in USD
- (+ other columns ignored)

**correlations.csv** (Matrix format):
- Row/column labels: Counterparty names (must match holdings)
- Values: Correlation percentages (0-100 or 0-1)
- Automatically normalized to [0,1] range

### Sample Data

**v1 Dataset**:
- 20 counterparties (Bridgewater Associates, Man Group, Elliott, Citadel, etc.)
- ~225 position records
- 20×20 correlation matrix

**v2 Dataset**:
- Same structure, may have different correlations or positions

---

## API Response Examples

### GET /health
```json
{
  "status": "ok",
  "built_at": "2026-02-23T12:34:56.789Z",
  "active_dataset": "v1"
}
```

### GET /graph
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
        "EQUITY": 0.395
      }
    }
  ],
  "edges": [
    {
      "source": "bridgewater-associates",
      "target": "man-group",
      "weight": 0.491,
      "corr_pct": 49.1
    }
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

### GET /client/bridgewater-associates
```json
{
  "name": "Bridgewater Associates",
  "id": "bridgewater-associates",
  "positions": [
    {
      "counterparty": "Bridgewater Associates",
      "ticker_or_contract": "QQQ_20261026_P_498p94",
      "product_type": "OPTION",
      "quantity": 3396,
      "notional_usd_est": 205593.84,
      ...
    }
  ],
  "aggregates": {
    "gross_notional": 5234567.89,
    "net_notional": 2345678.90,
    "positions_count": 15,
    "product_mix": {...}
  }
}
```

---

## Running the Application

### Prerequisites
```powershell
# Install dependencies
pip install -r requirements.txt
```

**Requirements.txt**:
- fastapi==0.104.1
- uvicorn[standard]==0.24.0
- pandas==2.1.3
- pydantic==2.5.0

### Start Server
```powershell
# From project root
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

### Test Endpoints
```powershell
# Health check
curl http://localhost:8000/health

# Get graph
curl http://localhost:8000/graph

# Get client
curl http://localhost:8000/client/bridgewater-associates

# Rebuild with custom threshold
curl -X POST http://localhost:8000/graph/rebuild `
  -H "Content-Type: application/json" `
  -d '{"min_corr": 0.5}'
```

### Debug Script
```powershell
python scripts/print_summary.py
```

### API Documentation
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

---

## Key Implementation Details

### Data Agnosticism
The system gracefully handles mismatches:
- **Counterparties in correlation but not holdings**: Dropped from edges, listed in `meta.dropped_from_corr`
- **Counterparties in holdings but not correlation**: Included as nodes with no edges, listed in `meta.missing_corr_for_holdings`
- **No crashes**: Only raises on missing core columns or unreadable files

### Correlation Normalization
- Automatically detects if correlations are in percentage (0-100) or decimal (0-1) format
- Converts to normalized [0, 1] range for consistent edge weights

### Aggregation Logic
- **Gross Notional**: Sum of absolute notional values
- **Net Notional**: Sum of signed notional (quantity-weighted direction)
- **Product Mix**: Share of each product type by notional percentage

### Caching Strategy
- Per-version graph cache in `GRAPH_STATE`
- Cache invalidated on dataset switch
- Dynamic cache invalidation when query `min_corr` differs

### Error Handling
- **File errors**: Clear messages with expected paths
- **Column validation**: Lists missing required columns
- **Data mismatches**: Reported in metadata, never crashes
- **Startup resilience**: Server starts even if graph initialization fails

---

## Testing

See [TESTING.md](TESTING.md) for:
- Complete curl examples for all endpoints
- Real client IDs from v1 dataset
- Error scenario testing
- Bash test script
- Postman collection

---

## File Manifest

| File | Lines | Purpose |
|------|-------|---------|
| portfolio_agent.py | 395 | Core graph builder + FastAPI app |
| app.py | 377 | Config, state, REST endpoints |
| scripts/print_summary.py | 109 | Debug script for local testing |
| requirements.txt | 4 | Python dependencies |
| datasets.json | 15 | Dataset registry |
| TESTING.md | 400+ | Test guide with curl examples |
| README.md | This file | Project documentation |

---

## Future Enhancements

- [ ] Database persistence (SQLAlchemy + PostgreSQL)
- [ ] WebSocket support for real-time graph updates
- [ ] GraphQL API alternative to REST
- [ ] Advanced correlation filtering (percentile-based, dynamic thresholds)
- [ ] Position-level risk analysis
- [ ] Visualization dashboard (React frontend)
- [ ] Batch import for new datasets
- [ ] Authentication & authorization

---

## Credits

Built for hackathon with FastAPI, pandas, and Python 3.8+.

Last Updated: February 23, 2026
