import time
import logging
import argparse
from storage import StorageManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("downsampler")

def run_downsampler_loop(db_dir: str, interval_sec: int = 300):
    """
    Periodically computes hourly aggregate rollups from raw high-rate readings.
    """
    storage = StorageManager(db_dir=db_dir)
    logger.info(f"Starting downsampler background worker (interval: {interval_sec}s)...")

    while True:
        try:
            start_t = time.time()
            rows_processed = storage.compute_hourly_rollups()
            elapsed = time.time() - start_t
            stats = storage.get_db_stats()
            
            logger.info(
                f"Hourly rollups updated in {elapsed:.2f}s | "
                f"Total Raw Rows: {stats['total_raw_rows']} | "
                f"Total Hourly Summaries: {stats['total_hourly_rows']} | "
                f"DB Size: {stats['file_size_mb']} MB"
            )
        except Exception as e:
            logger.error(f"Error during downsampling rollup: {e}", exc_info=True)

        time.sleep(interval_sec)

def main():
    parser = argparse.ArgumentParser(description="WT901C Hourly Downsampler Background Service")
    parser.add_argument("--db-dir", type=str, default="data", help="Directory storing SQLite database")
    parser.add_argument("--interval", type=int, default=300, help="Downsampling interval in seconds (default: 300s / 5 min)")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    args = parser.parse_args()

    storage = StorageManager(db_dir=args.db_dir)
    if args.once:
        logger.info("Running single downsample aggregation pass...")
        storage.compute_hourly_rollups()
        stats = storage.get_db_stats()
        logger.info(f"Done! DB Stats: {stats}")
    else:
        run_downsampler_loop(db_dir=args.db_dir, interval_sec=args.interval)

if __name__ == "__main__":
    main()
