"""Delete expired session uploads.

    python -m seed.cleanup_sessions

Nothing else ever removes an uploaded document, so without this the chunks
table grows without bound: every visitor's PDF stays forever. The demo corpus
(session_id IS NULL) is never touched.

Run on a schedule -- see render.yaml for the cron job.
"""

from dotenv import load_dotenv

load_dotenv()

import logging

from app.config import SESSION_TTL_DAYS
from app.services.storage import close_pool, delete_expired_sessions

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("rag.cleanup")


def main() -> int:
    try:
        removed = delete_expired_sessions(SESSION_TTL_DAYS)
        log.info(
            "Removed %d session chunk(s) older than %d day(s).", removed, SESSION_TTL_DAYS
        )
        return removed
    finally:
        close_pool()


if __name__ == "__main__":
    main()
