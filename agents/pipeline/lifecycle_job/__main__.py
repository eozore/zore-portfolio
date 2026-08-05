"""
lifecycle_job/__main__.py
=========================
Entry point para Cloud Run Job.
Lê a variável de ambiente LIFECYCLE_DRY_RUN (default "false").
Se LIFECYCLE_DRY_RUN=true, apenas lista projetos expirados sem arquivar.
"""

import logging
import os
import sys

logging.basicConfig(
    level=logging.INFO,
    stream=sys.stdout,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger("lifecycle_job.__main__")


def main() -> None:
    dry_run_env = os.environ.get("LIFECYCLE_DRY_RUN", "false").lower()
    dry_run = dry_run_env in ("1", "true", "yes")

    archive_bucket = os.environ.get(
        "GCS_ARCHIVE_BUCKET", "vazfy-417019-pipeline-archive"
    )
    media_bucket = os.environ.get(
        "GCS_MEDIA_BUCKET", "vazfy-417019-pipeline-media"
    )
    retention_days = int(os.environ.get("LIFECYCLE_RETENTION_DAYS", "60"))

    logger.info(
        "Starting lifecycle_job | dry_run=%s retention_days=%d "
        "media_bucket=%s archive_bucket=%s",
        dry_run, retention_days, media_bucket, archive_bucket,
    )

    from job import LifecycleJob

    job = LifecycleJob(
        media_bucket=media_bucket,
        archive_bucket=archive_bucket,
        retention_days=retention_days,
        dry_run=dry_run,
    )

    results = job.run()

    logger.info("lifecycle_job completed | %s", results)

    total = results.get("total_expired", 0)
    archived = results.get("archived", 0)
    failed = results.get("failed", 0)

    if failed > 0:
        logger.warning("%d project(s) failed to archive.", failed)
        sys.exit(1)

    logger.info("Done. %d/%d project(s) archived.", archived, total)


if __name__ == "__main__":
    main()
