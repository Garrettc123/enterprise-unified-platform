#!/usr/bin/env python3
"""Master orchestration runner for full autonomous sync system."""

import asyncio
import logging
import sys
from typing import Optional
from enum import Enum
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(name)s | %(levelname)-8s | %(message)s',
    handlers=[
        logging.FileHandler(f"sync_orchestration_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

from service_integration import ServiceIntegrationOrchestrator


class SyncMode(Enum):
    """Modes for running orchestration."""
    FULL = "full"  # Run all sync operations
    CLOUD_ONLY = "cloud-only"  # Cloud deployment sync only
    DATABASE_ONLY = "database-only"  # Database sync only
    MONITOR = "monitor"  # Monitor only, no sync


class OrchestrationRunner:
    """Runner for the full autonomous sync orchestration."""

    def __init__(self, mode: SyncMode = SyncMode.FULL):
        self.mode = mode
        self.orchestrator = ServiceIntegrationOrchestrator()
        self.start_time: Optional[datetime] = None
        self.sync_count = 0

    def print_banner(self):
        """Print startup banner."""
        banner = f"""
╔════════════════════════════════════════════════════════════════════════════╗
║                                                                            ║
║                   AUTONOMOUS SYNC ORCHESTRATION ENGINE                     ║
║                                                                            ║
║                          Enterprise Unified Platform                       ║
║                                                                            ║
║  Mode: {self.mode.value.upper():<55}               ║
║  Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S'):<46}               ║
║                                                                            ║
╚════════════════════════════════════════════════════════════════════════════╝
        """
        logger.info(banner)

    def print_configuration(self):
        """Print system configuration."""
        logger.info("\n" + "="*80)
        logger.info("SYSTEM CONFIGURATION")
        logger.info("="*80)
        logger.info(f"Mode: {self.mode.value}")

        if self.mode in [SyncMode.FULL, SyncMode.CLOUD_ONLY]:
            logger.info(f"Cloud Providers: {len(self.orchestrator.sync_engine.providers)}")
            for name in self.orchestrator.sync_engine.providers:
                logger.info(f"  - {name}")

        if self.mode in [SyncMode.FULL, SyncMode.DATABASE_ONLY]:
            logger.info(f"Databases: {len(self.orchestrator.db_sync_manager.connectors)}")
            for name in self.orchestrator.db_sync_manager.connectors:
                logger.info(f"  - {name}")
            logger.info(f"Sync Pairs: {len(self.orchestrator.db_sync_manager.sync_pairs)}")
            for i, (source, target, direction) in enumerate(self.orchestrator.db_sync_manager.sync_pairs, 1):
                logger.info(f"  {i}. {source} <-> {target} ({direction.value})")

        logger.info("="*80 + "\n")

    async def run(self):
        """Run the orchestration based on selected mode."""
        self.start_time = datetime.now()
        self.print_banner()

        try:
            if self.mode == SyncMode.FULL:
                self._configure_all()
                self.print_configuration()
                await self.orchestrator.run_full_autonomous_sync()

            elif self.mode == SyncMode.CLOUD_ONLY:
                self.orchestrator.configure_cloud_sync()
                logger.info("\n" + "="*80)
                logger.info("CLOUD SYNC MODE - ACTIVE")
                logger.info("="*80 + "\n")
                await self.orchestrator.sync_engine.run_continuous_sync(check_interval=60)

            elif self.mode == SyncMode.DATABASE_ONLY:
                self.orchestrator.configure_database_sync()
                logger.info("\n" + "="*80)
                logger.info("DATABASE SYNC MODE - ACTIVE")
                logger.info("="*80 + "\n")
                await self.orchestrator.db_sync_manager.run_continuous_sync(check_interval=30)

            elif self.mode == SyncMode.MONITOR:
                self._configure_all()
                logger.info("\n" + "="*80)
                logger.info("MONITOR MODE - ACTIVE (NO SYNC)")
                logger.info("="*80 + "\n")
                while True:
                    status = self.orchestrator.get_full_status()
                    logger.info(f"Status Update: {status}")
                    await asyncio.sleep(30)

        except KeyboardInterrupt:
            logger.info("\n\n" + "="*80)
            logger.info("ORCHESTRATION STOPPED BY USER")
            logger.info("="*80)
            self._print_summary()

        except Exception as e:
            logger.error(f"\n\nFATAL ERROR: {str(e)}", exc_info=True)
            sys.exit(1)

    def _configure_all(self):
        """Configure all components."""
        self.orchestrator.configure_cloud_sync()
        self.orchestrator.configure_database_sync()

    def _print_summary(self):
        """Print execution summary."""
        if self.start_time:
            duration = datetime.now() - self.start_time
            logger.info(f"\nExecution Time: {duration}")
            logger.info(f"Total Syncs: {self.sync_count}")
            status = self.orchestrator.get_full_status()
            logger.info(f"\nFinal Status:")
            logger.info(f"  Cloud Sync: {status['cloud_sync'].get('running', False)}")
            logger.info(f"  Database Sync: {status['database_sync'].get('running', False)}")


def print_usage():
    """Print usage information."""
    usage = """
Usage: python run_orchestration.py [MODE]

Modes:
  full            Run complete autonomous sync (cloud + database)
  cloud-only      Run cloud provider sync only
  database-only   Run database sync only
  monitor         Monitor without syncing

Examples:
  python run_orchestration.py full
  python run_orchestration.py cloud-only
  python run_orchestration.py database-only
  python run_orchestration.py monitor

Control:
  Press Ctrl+C to stop
    """
    print(usage)


async def main():
    """Main entry point."""
    mode = SyncMode.FULL  # Default mode

    if len(sys.argv) > 1:
        mode_str = sys.argv[1].lower()
        try:
            mode = SyncMode(mode_str)
        except ValueError:
            logger.error(f"Invalid mode: {mode_str}")
            print_usage()
            sys.exit(1)

    runner = OrchestrationRunner(mode)
    await runner.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}", exc_info=True)
        sys.exit(1)
