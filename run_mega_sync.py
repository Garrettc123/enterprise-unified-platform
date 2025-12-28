#!/usr/bin/env python3
"""Master deployment script for mega orchestrator.

Usage:
    python run_mega_sync.py                  # Run full mega sync
    python run_mega_sync.py --mode cloud    # Cloud sync only
    python run_mega_sync.py --mode database # Database sync only
    python run_mega_sync.py --mode check    # Health check only
"""

import asyncio
import argparse
import logging
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(name)s | %(levelname)-8s | %(message)s'
)
logger = logging.getLogger(__name__)

from mega_orchestrator import MegaOrchestrator


async def run_full_sync():
    """Run full mega orchestrator."""
    orchestrator = MegaOrchestrator()
    orchestrator.configure_all_systems()
    orchestrator.print_configuration_summary()
    await orchestrator.run_mega_sync()


async def run_mode(mode: str):
    """Run specific sync mode."""
    orchestrator = MegaOrchestrator()
    orchestrator.configure_all_systems()
    
    if mode == "cloud":
        logger.info("Running CLOUD SYNC ONLY")
        await orchestrator.cloud_sync.run_continuous_sync()
    elif mode == "database":
        logger.info("Running DATABASE SYNC ONLY")
        await orchestrator.db_sync.run_continuous_sync()
    elif mode == "storage":
        logger.info("Running STORAGE SYNC ONLY")
        await orchestrator.storage_sync.run_continuous_sync()
    elif mode == "cache":
        logger.info("Running CACHE SYNC ONLY")
        await orchestrator.cache_sync.run_continuous_sync()
    elif mode == "messages":
        logger.info("Running MESSAGE QUEUE SYNC ONLY")
        await orchestrator.message_sync.run_continuous_sync()
    elif mode == "search":
        logger.info("Running SEARCH INDEX SYNC ONLY")
        await orchestrator.search_sync.run_continuous_sync()
    elif mode == "ml":
        logger.info("Running ML PIPELINE SYNC ONLY")
        await orchestrator.ml_sync.run_continuous_sync()
    elif mode == "graphql":
        logger.info("Running GRAPHQL SYNC ONLY")
        await orchestrator.graphql_sync.run_continuous_sync()
    elif mode == "check":
        logger.info("Running HEALTH CHECK")
        orchestrator.print_configuration_summary()
        status = orchestrator.get_full_status()
        logger.info(f"\nStatus: {status}")
        return
    else:
        logger.error(f"Unknown mode: {mode}")
        sys.exit(1)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Mega Autonomous Sync Orchestrator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_mega_sync.py                    # Full mega sync
  python run_mega_sync.py --mode cloud       # Cloud deployments only
  python run_mega_sync.py --mode database    # Database replication only
  python run_mega_sync.py --mode check       # Health check
        """
    )
    
    parser.add_argument(
        "--mode",
        choices=["cloud", "database", "storage", "cache", "messages", "search", "ml", "graphql", "check"],
        default=None,
        help="Run specific sync mode (default: full mega sync)"
    )
    
    parser.add_argument(
        "--check-interval",
        type=int,
        default=30,
        help="Check interval in seconds (default: 30)"
    )
    
    args = parser.parse_args()
    
    logger.info("""
╔════════════════════════════════════════════════════════════════════════════╗
║         MEGA AUTONOMOUS SYNC ORCHESTRATOR - FULL PRODUCTION SETUP          ║
║                                                                            ║
║  Synchronizes 25+ infrastructure components across cloud, databases,       ║
║  storage, cache, queues, search, ML, and GraphQL systems                   ║
╚════════════════════════════════════════════════════════════════════════════╝
    """)
    
    try:
        if args.mode:
            asyncio.run(run_mode(args.mode))
        else:
            asyncio.run(run_full_sync())
    except KeyboardInterrupt:
        logger.info("\n\nShutdown complete.")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
