"""Portfolio agent: builds client graph from holdings + correlation CSVs.

This module provides a FastAPI backend that:
  - Reads two CSVs (holdings + correlation matrix)
  - Builds a client graph (nodes=counterparties, edges=correlation weights)
  - Supports two dataset versions (v1 and v2) stored in data/v1 and data/v2
  - Allows switching active dataset and rebuilding the graph
  - Uses in-memory cache (no DB)
  - Provides REST endpoints for datasets, switching, rebuild, graph, and client detail

Usage:
  uvicorn portfolio_agent:app --reload
"""
from typing import Dict, Any, Optional, List, Tuple
import os
import json
import re
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse


def slugify(name: str) -> str:
    """Convert name to slug: lowercase, replace non-alphanumerics with hyphens, strip repeats.
    
    Examples:
        "Bridgewater Associates" -> "bridgewater-associates"
        "D. E. Shaw & Co." -> "d-e-shaw-co"
    """
    # Convert to lowercase
    slug = name.lower()
    # Replace non-alphanumeric characters with hyphens
    slug = re.sub(r'[^a-z0-9]+', '-', slug)
    # Strip leading/trailing hyphens
    slug = slug.strip('-')
    # Collapse multiple consecutive hyphens
    slug = re.sub(r'-+', '-', slug)
    return slug


def build_graph(
    holdings_path: str,
    corr_path: str,
    min_corr: float = 0.25
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Dict[str, Any]], Dict[str, Any]]:
    """Build portfolio graph from holdings and correlation CSVs.
    
    Data-agnostic: handles mismatches between holdings and correlation matrix gracefully.
    - Counterparties in correlation but not in holdings are dropped (reported in meta)
    - Counterparties in holdings but not in correlation get nodes but no edges (reported in meta)
    - Only crashes if core columns are missing or files unreadable
    
    Args:
        holdings_path: Path to holdings.csv
        corr_path: Path to correlations.csv (correlation matrix)
        min_corr: Minimum correlation threshold (0.0-1.0) to include edges
        
    Returns:
        Tuple of (nodes, edges, client_details, meta)
        
    Raises:
        FileNotFoundError: If CSV files don't exist
        ValueError: If required columns are missing
    """
    # Load holdings CSV
    if not os.path.exists(holdings_path):
        raise FileNotFoundError(f"Holdings file not found: {holdings_path}")
    if not os.path.exists(corr_path):
        raise FileNotFoundError(f"Correlations file not found: {corr_path}")
    
    holdings_df = pd.read_csv(holdings_path)
    
    # Validate required columns in holdings
    required_cols = {
        "counterparty",
        "ticker_or_contract",
        "product_type",
        "quantity",
        "price_demo",
        "notional_usd_est",
    }
    missing_cols = required_cols - set(holdings_df.columns)
    if missing_cols:
        raise ValueError(
            f"Holdings CSV missing required columns: {sorted(missing_cols)}. "
            f"Found columns: {sorted(holdings_df.columns)}"
        )
    
    # Load correlation matrix
    corr_df = pd.read_csv(corr_path, index_col=0)
    
    # Track data mismatches for meta reporting
    holdings_counterparties = set(holdings_df["counterparty"].unique())
    corr_counterparties = set(corr_df.index.astype(str))
    
    dropped_from_corr = list(corr_counterparties - holdings_counterparties)
    missing_corr_for_holdings = list(holdings_counterparties - corr_counterparties)
    
    # Build client_details: keyed by slug of counterparty name (from holdings only)
    client_details: Dict[str, Dict[str, Any]] = {}
    
    for counterparty in holdings_df["counterparty"].unique():
        client_id = slugify(counterparty)
        positions = holdings_df[holdings_df["counterparty"] == counterparty].to_dict("records")
        
        # Compute aggregates
        gross_notional = sum(abs(p.get("notional_usd_est", 0) or 0) for p in positions)
        net_notional = 0.0
        for pos in positions:
            qty = pos.get("quantity", 0) or 0
            notional = pos.get("notional_usd_est", 0) or 0
            net_notional += notional if qty >= 0 else -notional
        
        # Product mix: share of gross notional by product type
        product_mix = {}
        total_notional = sum(abs(p.get("notional_usd_est", 0) or 0) for p in positions)
        for pos in positions:
            prod_type = pos.get("product_type", "unknown")
            notional = abs(pos.get("notional_usd_est", 0) or 0)
            if prod_type not in product_mix:
                product_mix[prod_type] = 0.0
            product_mix[prod_type] += notional / total_notional if total_notional > 0 else 0.0
        
        client_details[client_id] = {
            "name": counterparty,
            "id": client_id,
            "positions": positions,
            "aggregates": {
                "gross_notional": gross_notional,
                "net_notional": net_notional,
                "positions_count": len(positions),
                "product_mix": product_mix,
            },
        }
    
    # Build nodes: from client_details (only holdings counterparties)
    nodes: List[Dict[str, Any]] = []
    for client_id, details in client_details.items():
        agg = details["aggregates"]
        nodes.append({
            "id": client_id,
            "label": details["name"],
            "gross_notional": agg["gross_notional"],
            "net_notional": agg["net_notional"],
            "positions_count": agg["positions_count"],
            "product_mix": agg["product_mix"],
        })
    
    # Build edges from correlation matrix (upper triangle, min_corr filter)
    # Only include edges between counterparties that are in holdings
    edges: List[Dict[str, Any]] = []
    corr_values = []
    corr_df_index = corr_df.index.astype(str).tolist()
    corr_df_columns = corr_df.columns.astype(str).tolist()
    
    for i, u_orig in enumerate(corr_df_index):
        for j, v_orig in enumerate(corr_df_columns):
            if i >= j:  # Upper triangle only
                continue
            try:
                # Skip if either party is not in holdings
                if u_orig not in holdings_counterparties or v_orig not in holdings_counterparties:
                    continue
                
                w_pct = float(corr_df.iloc[i, j])
                # Normalize: if in percentage form (>1), convert to [0, 1]
                w = w_pct / 100.0 if w_pct > 1 else w_pct
                corr_values.append(w)
                
                # Create slugified IDs for node matching
                u_slug = slugify(u_orig)
                v_slug = slugify(v_orig)
                
                # Only include if meets threshold
                if w >= min_corr:
                    edges.append({
                        "source": u_slug,
                        "target": v_slug,
                        "weight": w,
                        "corr_pct": w_pct,
                    })
            except (ValueError, TypeError):
                continue
    
    # Build metadata
    corr_values_filtered = [e["weight"] for e in edges] if edges else []
    meta = {
        "num_clients": len(client_details),
        "num_edges": len(edges),
        "corr_min_kept": min(corr_values_filtered) if corr_values_filtered else None,
        "corr_max_kept": max(corr_values_filtered) if corr_values_filtered else None,
        "min_corr_used": min_corr,
        "dropped_from_corr": dropped_from_corr,
        "missing_corr_for_holdings": missing_corr_for_holdings,
    }
    
    return nodes, edges, client_details, meta


class PortfolioAgent:
    """In-memory portfolio graph builder using pandas."""
    
    def __init__(self, datasets_file: str = "datasets.json"):
        self.datasets_file = datasets_file
        self.registry = self._load_registry()
        self.active_version = self.registry.get("active_version") or self._pick_first_version()
        self._graph_cache: Dict[str, Optional[Dict[str, Any]]] = {}  # cache per version

    def _load_registry(self) -> Dict[str, Any]:
        """Load datasets.json or return default registry."""
        if not os.path.exists(self.datasets_file):
            return {"datasets": {}, "active_version": None}
        with open(self.datasets_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def _save_registry(self) -> None:
        """Persist registry to datasets.json."""
        with open(self.datasets_file, "w", encoding="utf-8") as f:
            json.dump(self.registry, f, indent=2)

    def _pick_first_version(self) -> Optional[str]:
        """Pick the first available version from registry."""
        ds = self.registry.get("datasets", {})
        return next(iter(ds.keys()), None) if ds else None

    def get_datasets(self) -> Dict[str, Any]:
        """Return the full registry."""
        return self.registry

    def switch_version(self, version: str) -> None:
        """Switch active version and clear cache."""
        if version not in self.registry.get("datasets", {}):
            raise ValueError(f"version {version} not found in registry")
        self.registry["active_version"] = version
        self.active_version = version
        self._graph_cache = {}  # clear all caches on switch
        self._save_registry()

    def _get_paths_for_version(self, version: Optional[str] = None) -> Dict[str, str]:
        """Get file paths for a specific version."""
        version = version or self.active_version
        base = os.path.join("data", version)
        return {
            "holdings": os.path.join(base, "holdings.csv"),
            "correlations": os.path.join(base, "correlations.csv"),
        }

    def build_graph(self, version: Optional[str] = None, force: bool = False) -> Dict[str, Any]:
        """Build the graph from CSVs. Cache per version unless force=True."""
        version = version or self.active_version
        if not force and version in self._graph_cache:
            return self._graph_cache[version]

        paths = self._get_paths_for_version(version)

        # Verify files exist
        for key, path in paths.items():
            if not os.path.exists(path):
                raise FileNotFoundError(f"{key}.csv missing: {path}")

        # Load holdings: counterparty -> notional weight
        holdings_df = pd.read_csv(paths["holdings"])
        # Group by counterparty and sum notional_usd_est
        if "counterparty" in holdings_df.columns and "notional_usd_est" in holdings_df.columns:
            holdings = holdings_df.groupby("counterparty")["notional_usd_est"].sum().to_dict()
        else:
            # Fallback: try first two columns
            holdings_df.columns = ["counterparty", "weight"] + list(holdings_df.columns[2:])
            holdings = {
                str(r["counterparty"]): float(r.get("weight", 0.0)) 
                for _, r in holdings_df.iterrows()
            }

        # Load correlation matrix (counterparties x counterparties)
        corr_df = pd.read_csv(paths["correlations"], index_col=0)

        # Build nodes from unique counterparties
        counterparties = sorted(set(list(corr_df.index.astype(str)) + list(holdings.keys())))
        nodes = [
            {"id": cp, "weight": holdings.get(cp, 0.0)}
            for cp in counterparties
        ]

        # Build edges from correlation matrix (upper triangle only to avoid duplicates)
        edges = []
        corr_df_index = corr_df.index.astype(str).tolist()
        corr_df_columns = corr_df.columns.astype(str).tolist()
        
        for i, u in enumerate(corr_df_index):
            for j, v in enumerate(corr_df_columns):
                if i >= j:
                    continue
                try:
                    # Convert from percentage to [0, 1] if needed
                    w = float(corr_df.iloc[i, j])
                    if w > 1:  # Likely in percentage form (0-100)
                        w = w / 100.0
                    edges.append({"u": u, "v": v, "weight": w})
                except (ValueError, TypeError):
                    continue

        graph = {"version": version, "nodes": nodes, "edges": edges}
        self._graph_cache[version] = graph
        return graph

    def get_graph(self, version: Optional[str] = None) -> Dict[str, Any]:
        """Get cached graph or build it."""
        version = version or self.active_version
        if version not in self._graph_cache:
            return self.build_graph(version)
        return self._graph_cache[version]

    def get_client(self, client_id: str, version: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Get client details with neighbors."""
        version = version or self.active_version
        g = self.get_graph(version)
        nodes = {n["id"]: n for n in g.get("nodes", [])}
        
        if client_id not in nodes:
            return None
        
        neighbors = []
        for e in g.get("edges", []):
            if e["u"] == client_id:
                neighbors.append({"id": e["v"], "weight": e["weight"]})
            elif e["v"] == client_id:
                neighbors.append({"id": e["u"], "weight": e["weight"]})
        
        return {
            "id": client_id,
            "weight": nodes[client_id].get("weight"),
            "neighbor_count": len(neighbors),
            "neighbors": sorted(neighbors, key=lambda x: x["weight"], reverse=True),
        }


# FastAPI application
app = FastAPI(
    title="Portfolio Agent",
    description="Graph-based portfolio analysis with holdings and correlations",
    version="1.0.0",
)

# Global agent instance
agent = PortfolioAgent()


# REST Endpoints
@app.get("/datasets")
def list_datasets() -> Dict[str, Any]:
    """List available datasets and active version."""
    return agent.get_datasets()


@app.post("/switch/{version}")
def switch_dataset(version: str) -> Dict[str, str]:
    """Switch to a different dataset version."""
    try:
        agent.switch_version(version)
        return {"message": f"Switched to version {version}", "active_version": agent.active_version}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/rebuild/{version}")
def rebuild_graph(version: str, force: bool = True) -> Dict[str, Any]:
    """Force rebuild the graph for a specific version."""
    try:
        return agent.build_graph(version=version, force=force)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error building graph: {str(e)}")


@app.get("/graph")
def get_graph(version: Optional[str] = None) -> Dict[str, Any]:
    """Get the graph for active or specified version."""
    try:
        if version is None:
            version = agent.active_version
        return agent.get_graph(version)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting graph: {str(e)}")


@app.get("/client/{client_id}")
def get_client_details(client_id: str, version: Optional[str] = None) -> Dict[str, Any]:
    """Get details for a specific client/counterparty."""
    try:
        if version is None:
            version = agent.active_version
        result = agent.get_client(client_id, version)
        if result is None:
            raise HTTPException(status_code=404, detail=f"Client {client_id} not found")
        return result
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting client: {str(e)}")


@app.get("/health")
def health_check() -> Dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok", "active_version": agent.active_version}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
