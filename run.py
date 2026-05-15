import logging

from dashboard.app import app
from ingestion.scheduler import start_scheduler


if __name__ == "__main__":
    logging.getLogger("werkzeug").setLevel(logging.ERROR)
    start_scheduler()
    app.run(debug=False, port=8050)
