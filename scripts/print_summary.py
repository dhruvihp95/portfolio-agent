#!/usr/bin/env python3
"""
Debug script to print summary of loaded portfolio graph.

Usage:
    python scripts/print_summary.py
"""
import sys
import os

# Add parent directory to path to import app module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import GRAPH_STATE


def main():
    """Print portfolio graph summary."""
    
    # Check if graph was loaded successfully
    if GRAPH_STATE.get("error"):
        print(f"❌ Error loading graph: {GRAPH_STATE['error']}")
        return
    
    if not GRAPH_STATE.get("nodes"):
        print("❌ No graph data available")
        return
    
    print("=" * 70)
    print("Portfolio Graph Summary")
    print("=" * 70)
    
    # Basic stats
    num_clients = GRAPH_STATE.get("meta", {}).get("num_clients", 0)
    num_edges = GRAPH_STATE.get("meta", {}).get("num_edges", 0)
    active_dataset = GRAPH_STATE.get("active_dataset", "N/A")
    built_at = GRAPH_STATE.get("built_at", "N/A")
    min_corr = GRAPH_STATE.get("min_corr", "N/A")
    
    print(f"\nActive Dataset: {active_dataset}")
    print(f"Built At: {built_at}")
    print(f"Min Correlation Threshold: {min_corr}")
    print(f"\nClients: {num_clients}")
    print(f"Edges: {num_edges}")
    
    # Top 3 clients by gross_notional
    client_details = GRAPH_STATE.get("client_details", {})
    if client_details:
        print("\n" + "-" * 70)
        print("Top 3 Clients by Gross Notional")
        print("-" * 70)
        
        # Sort by gross_notional (descending)
        sorted_clients = sorted(
            client_details.items(),
            key=lambda x: x[1].get("aggregates", {}).get("gross_notional", 0),
            reverse=True
        )
        
        for rank, (client_id, details) in enumerate(sorted_clients[:3], 1):
            name = details.get("name", "Unknown")
            gross = details.get("aggregates", {}).get("gross_notional", 0)
            net = details.get("aggregates", {}).get("net_notional", 0)
            positions = details.get("aggregates", {}).get("positions_count", 0)
            product_mix = details.get("aggregates", {}).get("product_mix", {})
            
            print(f"\n{rank}. {name} ({client_id})")
            print(f"   Gross Notional: ${gross:,.2f}")
            print(f"   Net Notional: ${net:,.2f}")
            print(f"   Positions: {positions}")
            print(f"   Product Mix: {', '.join(f'{k}: {v:.1%}' for k, v in product_mix.items())}")
    
    # Additional metadata
    meta = GRAPH_STATE.get("meta", {})
    dropped = meta.get("dropped_from_corr", [])
    missing_corr = meta.get("missing_corr_for_holdings", [])
    
    if dropped:
        print("\n" + "-" * 70)
        print(f"Dropped from Correlation Matrix ({len(dropped)})")
        print("-" * 70)
        for name in dropped[:5]:
            print(f"  • {name}")
        if len(dropped) > 5:
            print(f"  ... and {len(dropped) - 5} more")
    
    if missing_corr:
        print("\n" + "-" * 70)
        print(f"Missing from Correlation Matrix ({len(missing_corr)})")
        print("-" * 70)
        for name in missing_corr[:5]:
            print(f"  • {name}")
        if len(missing_corr) > 5:
            print(f"  ... and {len(missing_corr) - 5} more")
    
    print("\n" + "=" * 70)


if __name__ == "__main__":
    main()
