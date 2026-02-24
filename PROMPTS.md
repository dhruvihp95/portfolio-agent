# Development Prompts & Iterations

This file documents all user requests and implementation steps that built the Portfolio Agent backend.

---

## 1. Initial Project Overview (Prompt #1)

**User Request:**
> Build a Python FastAPI backend called "portfolio agent" that reads two CSVs (holdings + correlation matrix) and builds a client graph (nodes=counterparties, edges=correlation weights). It must support two dataset versions (v1 and v2) stored in data/v1 and data/v2, allow switching active dataset, and allow rebuilding the graph. Use in-memory cache (no DB). Provide REST endpoints for datasets, switching, rebuild, graph, and client detail. Use pandas for CSV parsing.
>
> Most files are in place alongwith relevant datafiles. Can you help review and generate/clean up code to match the require,ments?

**Status**: ✅ Complete
**Outcome**: Reviewed existing code, identified issues (duplicate code, wrong filenames), created complete implementation plan

---

## 2. Code Generation Focus (Prompt #2)

**User Request:**
> Focus on generating code. Don't need python setup

**Status**: ✅ Noted
**Outcome**: Skipped Python environment configuration, focused purely on code generation

---

## 3. App Helper Functions (Prompt #3)

**User Request:**
> In app.py, implement helper functions:
> - load_datasets_config() reads datasets.json
> - save_datasets_config(cfg) writes it back
> - get_active_paths() returns active holdings_path and corr_path
>
> Validate that the active dataset exists and files exist; if missing, raise a clear error message.

**Status**: ✅ Complete
**Details**:
- Created [app.py](app.py) with 3 helper functions
- Full validation with clear error messages
- Handles missing files, missing versions, missing config
- Returns tuple (holdings_path, correlations_path)

---

## 4. Advanced Build Graph Function (Prompt #4)

**User Request:**
> In portfolio_agent.py, implement build_graph(holdings_path, corr_path, min_corr=0.25) returning (nodes, edges, client_details, meta).
>
> Requirements:
> - Holdings CSV required columns: counterparty, ticker_or_contract, product_type, quantity, price_demo, notional_usd_est. If missing, raise ValueError with list of missing columns.
> - Build client_details dict keyed by client_id (slug of counterparty name). Each entry contains:
>   - name, id
>   - positions: list of rows (original fields)
>   - aggregates: gross_notional, net_notional, positions_count, product_mix
> - Correlation CSV is a matrix. Parse it into numeric. Build undirected edges for i<j where corr>=min_corr. Edge object: {source, target, weight, corr_pct}.
> - Node object: {id, label, gross_notional, net_notional, positions_count, product_mix}
> - meta: dataset stats (num_clients, num_edges, corr_min_kept, corr_max_kept, min_corr_used)
> - Add a slugify(name) helper that makes lowercase, replaces non-alphanumerics with hyphens, and strips repeats.

**Status**: ✅ Complete
**Details**:
- Added `slugify()` function for URL-friendly names
- Implemented full `build_graph()` returning 4-tuple
- Node structure with all required fields
- Edge structure with normalized weights + original percentages
- Client details with positions and aggregates
- Complete metadata tracking
- Column validation with helpful error messages

---

## 5. Validation Checkpoint (Prompt #5)

**User Request:**
> Confirm all requested changes so far are properly implemented.

**Status**: ✅ Complete
**Details**:
- Verified all 3 helper functions in app.py
- Confirmed build_graph() with all requirements
- Checked slugify() implementation
- Validated requirements.txt with pinned versions
- Confirmed FastAPI app setup with 6 REST endpoints

---

## 6. Global State & Auto-Initialization (Prompt #6)

**User Request:**
> In app.py, add a global GRAPH_STATE dict with keys: active_dataset, min_corr, built_at, nodes, edges, client_details, meta.
>
> Implement rebuild_graph(min_corr=None) that reads active dataset paths from datasets.json, calls build_graph, and stores results in GRAPH_STATE.
>
> On app startup (at import time), try to rebuild graph with default min_corr=0.25; if it fails, store the error in GRAPH_STATE under error but keep server running.

**Status**: ✅ Complete
**Details**:
- Global GRAPH_STATE dict with 8 keys
- `rebuild_graph()` function that reads config and calls build_graph
- Automatic initialization at import time
- Graceful error handling (stores error, keeps server running)
- Status messages on startup

---

## 7. REST API Endpoints (Prompt #7)

**User Request:**
> Implement these FastAPI endpoints in app.py:
> - GET /health → {status:"ok", built_at, active_dataset, error?}
> - GET /datasets → active dataset and available dataset IDs
> - POST /dataset/select {dataset} → set active, rebuild, return meta
> - POST /graph/rebuild {min_corr?} → rebuild and return meta
> - GET /graph ?min_corr → rebuild if differs, return {nodes, edges, meta}
> - GET /client/{client_id} → return client details or 404
>
> Ensure CORS is enabled permissively for hackathon (allow all origins).

**Status**: ✅ Complete
**Details**:
- All 6 endpoints implemented with full error handling
- CORS middleware with permissive settings (all origins/methods/headers)
- Dynamic graph rebuilding based on query parameters
- Helpful 404 messages with available clients listed
- Proper HTTP status codes and error messages
- Request body validation for POST endpoints

---

## 8. Data Agnosticism (Prompt #8)

**User Request:**
> Make the agent data-agnostic:
> - If correlation matrix contains names not found in holdings, keep them only if you want, but by default filter to intersection and report dropped names in meta.
> - If holdings contains counterparties missing in corr matrix, include nodes but with no edges; report them in meta.
> - Add these lists to meta: dropped_from_corr, missing_corr_for_holdings.
> - Do not crash; only raise if core columns missing or files not readable.

**Status**: ✅ Complete
**Details**:
- Refactored build_graph() to be data-agnostic
- Handles counterparties in corr but not holdings (drops with reporting)
- Handles counterparties in holdings but not corr (nodes without edges)
- Tracks both as lists in metadata
- Never crashes on data mismatches
- Only raises on missing core columns or unreadable files
- Improved gross_notional calculation to sum all positions

---

## 9. Debug Script (Prompt #9)

**User Request:**
> Add a script scripts/print_summary.py that loads active dataset and prints:
> - clients, # edges
> - top 3 clients by gross_notional
>
> This is just for debugging locally.

**Status**: ✅ Complete
**Details**:
- Created [scripts/print_summary.py](scripts/print_summary.py) (109 lines)
- Prints formatted summary with ASCII separators
- Shows dataset info, client count, edge count
- Lists top 3 clients with full details
- Reports dropped/missing counterparties
- Graceful error handling with clear messages

---

## 10. Testing Guide & curl Examples (Prompt #10)

**User Request:**
> After implementing, show me exactly how to test using curl:
> - GET /health
> - GET /datasets
> - POST /graph/rebuild
> - GET /graph
> - GET /client/{some_id} (provide example id)
>
> Also print any errors if dataset files are missing.

**Status**: ✅ Complete
**Details**:
- Created comprehensive [TESTING.md](TESTING.md) with:
  - Real client IDs from v1 data (bridgewater-associates, man-group, d-e-shaw-co, etc.)
  - Full curl commands for all 6 endpoints
  - Expected responses (success & error cases)
  - Error scenario examples (missing files, invalid clients)
  - Bash testing script template
  - Postman collection JSON
  - Pretty-printing with jq

---

## 11. How to Run (Prompt #11)

**User Request:**
> How can we run this?

**Status**: ✅ Complete
**Details**:
- Provided quick start (3 steps)
- Full walkthrough with verification
- Server startup command with expected output
- Testing in separate PowerShell window
- Alternative approaches (run.py script)
- Debug script usage
- Troubleshooting common issues
- API documentation URLs

---

## 12. Documentation (Prompt #12)

**User Request:**
> Build a readme file describing all changes. Also create another file listing all prompts used

**Status**: ✅ Complete
**Details**:
- Created [README.md](README.md) with:
  - Project overview and key features
  - Architecture documentation
  - Module descriptions with line counts
  - API response examples
  - Running instructions
  - File manifest
  - Future enhancements
  - Technical details (data agnosticism, caching, error handling)
- Created [PROMPTS.md](PROMPTS.md) (this file) documenting all 12 development iterations

---

## Summary of Implementation

**Total Code Generated**:
- portfolio_agent.py: 395 lines
- app.py: 377 lines
- scripts/print_summary.py: 109 lines
- TESTING.md: 400+ lines documentation
- README.md: 300+ lines documentation
- requirements.txt: 4 lines

**Key Achievements**:
✅ FastAPI backend with 6 REST endpoints
✅ Graph-based portfolio analysis
✅ Multi-dataset support with switching
✅ In-memory caching
✅ Data-agnostic with graceful error handling
✅ Comprehensive API documentation
✅ Testing guide with real examples
✅ Debug utilities for local development
✅ CORS enabled for hackathon
✅ Automatic graph initialization on startup

**Technology Stack**:
- Python 3.8+
- FastAPI 0.104.1
- Uvicorn 0.24.0
- pandas 2.1.3
- Pydantic 2.5.0

---

## Timeline

| Iteration | Focus | Files Modified |
|-----------|-------|-----------------|
| 1 | Project overview & cleanup | portfolio_agent.py |
| 2 | Code generation focus | (acknowledged) |
| 3 | Helper functions | app.py |
| 4 | Advanced build_graph | portfolio_agent.py |
| 5 | Validation checkpoint | (confirmed) |
| 6 | Global state & initialization | app.py |
| 7 | REST API endpoints | app.py |
| 8 | Data agnosticism | portfolio_agent.py, app.py |
| 9 | Debug script | scripts/print_summary.py |
| 10 | Testing guide | TESTING.md |
| 11 | Runtime instructions | (console output) |
| 12 | Final documentation | README.md, PROMPTS.md |

---

## Notes for Future Development

1. **Database Integration**: Consider SQLAlchemy + PostgreSQL for persistence
2. **Real-time Updates**: WebSocket support for dynamic graph updates
3. **Advanced Filtering**: Percentile-based correlation filtering, dynamic thresholds
4. **Risk Analysis**: Position-level and portfolio-level risk metrics
5. **Visualization**: React/Vue frontend with D3.js graph visualization
6. **Authentication**: JWT-based API security
7. **Batch Operations**: Bulk dataset import/export
8. **Performance**: Consider caching layer (Redis) for high-frequency queries

---

Generated: February 23, 2026
Last Updated: Portfolio Agent Backend - Complete Implementation
