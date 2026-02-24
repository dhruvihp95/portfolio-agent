"""Helper functions for dataset configuration and file management."""
import os
import json
from typing import Dict, Any, Tuple, Optional, List
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware


def load_datasets_config(config_file: str = "datasets.json") -> Dict[str, Any]:
    """Load datasets configuration from JSON file.
    
    Args:
        config_file: Path to datasets.json configuration file
        
    Returns:
        Dictionary with 'datasets' and 'active_version' keys
        
    Raises:
        FileNotFoundError: If datasets.json does not exist
        json.JSONDecodeError: If datasets.json is not valid JSON
    """
    if not os.path.exists(config_file):
        raise FileNotFoundError(
            f"Configuration file not found: {config_file}. "
            f"Expected structure: {{'datasets': {{'v1': {{...}}, 'v2': {{...}}}}, 'active_version': 'v1'}}"
        )
    
    try:
        with open(config_file, "r", encoding="utf-8") as f:
            config = json.load(f)
    except json.JSONDecodeError as e:
        raise json.JSONDecodeError(
            f"Invalid JSON in {config_file}: {str(e)}",
            e.doc,
            e.pos
        )
    
    return config


def save_datasets_config(config: Dict[str, Any], config_file: str = "datasets.json") -> None:
    """Save datasets configuration to JSON file.
    
    Args:
        config: Dictionary with 'datasets' and 'active_version' keys
        config_file: Path to datasets.json configuration file
        
    Raises:
        IOError: If unable to write to file
    """
    try:
        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
    except IOError as e:
        raise IOError(f"Failed to write configuration to {config_file}: {str(e)}")


def get_active_paths(config_file: str = "datasets.json") -> Tuple[str, str]:
    """Get file paths for active dataset version with validation.
    
    Args:
        config_file: Path to datasets.json configuration file
        
    Returns:
        Tuple of (holdings_path, correlations_path)
        
    Raises:
        FileNotFoundError: If active version not found, files missing, or config file missing
        ValueError: If active_version not set in configuration
    """
    config = load_datasets_config(config_file)
    
    active_version = config.get("active_version")
    if not active_version:
        raise ValueError(
            "No active version set in configuration. "
            f"Available versions: {list(config.get('datasets', {}).keys())}"
        )
    
    datasets = config.get("datasets", {})
    if active_version not in datasets:
        raise FileNotFoundError(
            f"Active version '{active_version}' not found in configuration. "
            f"Available versions: {list(datasets.keys())}"
        )
    
    # Build expected paths
    base_path = os.path.join("data", active_version)
    holdings_path = os.path.join(base_path, "holdings.csv")
    correlations_path = os.path.join(base_path, "correlations.csv")
    
    # Validate both files exist
    missing_files = []
    if not os.path.exists(holdings_path):
        missing_files.append(f"holdings.csv (expected at: {holdings_path})")
    if not os.path.exists(correlations_path):
        missing_files.append(f"correlations.csv (expected at: {correlations_path})")
    
    if missing_files:
        raise FileNotFoundError(
            f"Data files missing for active version '{active_version}'. "
            f"Missing: {', '.join(missing_files)}"
        )
    
    return holdings_path, correlations_path


# Global graph state
GRAPH_STATE: Dict[str, Any] = {
    "active_dataset": None,
    "min_corr": None,
    "built_at": None,
    "nodes": None,
    "edges": None,
    "client_details": None,
    "meta": None,
    "error": None,
}


def rebuild_graph(min_corr: Optional[float] = None) -> None:
    """Rebuild graph from active dataset and store results in GRAPH_STATE.
    
    Reads active dataset paths from datasets.json, calls build_graph(),
    and updates GRAPH_STATE with results or error message.
    
    Args:
        min_corr: Minimum correlation threshold; if None, uses 0.25
        
    Updates GRAPH_STATE with:
        - active_dataset: version name
        - min_corr: threshold used
        - built_at: ISO timestamp
        - nodes, edges, client_details, meta: results from build_graph()
        - error: None if successful, error string if failed
    """
    min_corr = min_corr or 0.25
    
    try:
        # Reset error state
        GRAPH_STATE["error"] = None
        
        # Get active dataset paths
        config = load_datasets_config()
        active_version = config.get("active_version")
        holdings_path, corr_path = get_active_paths()
        
        # Import build_graph here to avoid circular imports
        from portfolio_agent import build_graph
        
        # Build graph
        nodes, edges, client_details, meta = build_graph(
            holdings_path=holdings_path,
            corr_path=corr_path,
            min_corr=min_corr,
        )
        
        # Update state
        GRAPH_STATE["active_dataset"] = active_version
        GRAPH_STATE["min_corr"] = min_corr
        GRAPH_STATE["built_at"] = datetime.utcnow().isoformat() + "Z"
        GRAPH_STATE["nodes"] = nodes
        GRAPH_STATE["edges"] = edges
        GRAPH_STATE["client_details"] = client_details
        GRAPH_STATE["meta"] = meta
        
    except Exception as e:
        error_msg = f"{type(e).__name__}: {str(e)}"
        GRAPH_STATE["error"] = error_msg


# Create FastAPI app
app = FastAPI(
    title="Portfolio Agent",
    description="Graph-based portfolio analysis with holdings and correlations",
    version="1.0.0",
)

# Enable CORS for hackathon (permissive)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods
    allow_headers=["*"],  # Allow all headers
)


# ============================================================================
# REST Endpoints
# ============================================================================

@app.get("/health")
def health_check() -> Dict[str, Any]:
    """Health check endpoint. Returns status, build timestamp, active dataset, and any errors."""
    response = {
        "status": "ok",
        "built_at": GRAPH_STATE.get("built_at"),
        "active_dataset": GRAPH_STATE.get("active_dataset"),
    }
    if GRAPH_STATE.get("error"):
        response["error"] = GRAPH_STATE["error"]
    return response


@app.get("/datasets")
def list_datasets() -> Dict[str, Any]:
    """List available datasets and return active dataset ID."""
    try:
        config = load_datasets_config()
        datasets = config.get("datasets", {})
        active = config.get("active_version")
        return {
            "active_dataset": active,
            "available_datasets": list(datasets.keys()),
            "datasets": datasets,
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to load datasets: {str(e)}"
        )


@app.post("/dataset/select")
def select_dataset(body: Dict[str, str]) -> Dict[str, Any]:
    """Select and switch to a dataset version. Rebuilds graph automatically."""
    dataset = body.get("dataset")
    if not dataset:
        raise HTTPException(status_code=400, detail="Missing 'dataset' key in body")
    
    try:
        config = load_datasets_config()
        if dataset not in config.get("datasets", {}):
            raise ValueError(f"Dataset '{dataset}' not found")
        
        # Update config and save
        config["active_version"] = dataset
        save_datasets_config(config)
        
        # Rebuild graph with current min_corr (default 0.25 if not set)
        current_min_corr = GRAPH_STATE.get("min_corr") or 0.25
        rebuild_graph(min_corr=current_min_corr)
        
        if GRAPH_STATE.get("error"):
            raise HTTPException(
                status_code=500,
                detail=f"Failed to rebuild graph: {GRAPH_STATE['error']}"
            )
        
        return {
            "message": f"Switched to dataset '{dataset}'",
            "active_dataset": GRAPH_STATE.get("active_dataset"),
            "meta": GRAPH_STATE.get("meta"),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error selecting dataset: {str(e)}")


@app.post("/graph/rebuild")
def rebuild_graph_endpoint(body: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
    """Rebuild the graph with optional min_corr threshold."""
    min_corr = None
    if body and "min_corr" in body:
        min_corr = float(body["min_corr"])
    
    try:
        rebuild_graph(min_corr=min_corr)
        
        if GRAPH_STATE.get("error"):
            raise HTTPException(
                status_code=500,
                detail=f"Failed to rebuild graph: {GRAPH_STATE['error']}"
            )
        
        return {
            "message": "Graph rebuilt successfully",
            "active_dataset": GRAPH_STATE.get("active_dataset"),
            "min_corr": GRAPH_STATE.get("min_corr"),
            "built_at": GRAPH_STATE.get("built_at"),
            "meta": GRAPH_STATE.get("meta"),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error rebuilding graph: {str(e)}")


@app.get("/graph")
def get_graph(min_corr: Optional[float] = None) -> Dict[str, Any]:
    """Get the graph. If min_corr differs from cached value, rebuild on the fly."""
    try:
        # Determine if we need to rebuild
        cached_min_corr = GRAPH_STATE.get("min_corr")
        should_rebuild = min_corr is not None and min_corr != cached_min_corr
        
        if should_rebuild:
            rebuild_graph(min_corr=min_corr)
            if GRAPH_STATE.get("error"):
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to build graph: {GRAPH_STATE['error']}"
                )
        elif GRAPH_STATE.get("error"):
            # No cached graph and no rebuild attempted
            raise HTTPException(
                status_code=500,
                detail=f"Graph not available: {GRAPH_STATE['error']}"
            )
        
        return {
            "nodes": GRAPH_STATE.get("nodes", []),
            "edges": GRAPH_STATE.get("edges", []),
            "meta": GRAPH_STATE.get("meta", {}),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting graph: {str(e)}")


@app.get("/client/{client_id}")
def get_client(client_id: str) -> Dict[str, Any]:
    """Get detailed information for a specific client/counterparty."""
    try:
        client_details = GRAPH_STATE.get("client_details", {})
        
        if client_id not in client_details:
            # Return helpful error with available clients
            available = list(client_details.keys())
            raise HTTPException(
                status_code=404,
                detail=f"Client '{client_id}' not found. Available clients: {', '.join(available[:5])}{'...' if len(available) > 5 else ''}"
            )
        
        return client_details[client_id]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching client: {str(e)}")


if __name__ == "__main__":
    # Example usage demonstrating error handling
    try:
        config = load_datasets_config()
        print("Configuration loaded successfully:")
        print(f"  Active version: {config.get('active_version')}")
        print(f"  Available versions: {list(config.get('datasets', {}).keys())}")
        
        holdings, corr = get_active_paths()
        print(f"\nFile paths for active version:")
        print(f"  Holdings: {holdings}")
        print(f"  Correlations: {corr}")
    except (FileNotFoundError, ValueError, IOError) as e:
        print(f"Error: {e}")


# Initialize graph at import time with default min_corr=0.25
# If it fails, error is stored but server continues running
try:
    rebuild_graph(min_corr=0.25)
    if GRAPH_STATE.get("error"):
        print(f"⚠️  Graph initialization failed: {GRAPH_STATE['error']}")
    else:
        print(f"✓ Graph initialized: {GRAPH_STATE['meta']['num_clients']} clients, "
              f"{GRAPH_STATE['meta']['num_edges']} edges")
except Exception as e:
    # Catch any unexpected errors and store them
    error_msg = f"Startup error: {type(e).__name__}: {str(e)}"
    GRAPH_STATE["error"] = error_msg
    print(f"⚠️  {error_msg}")

