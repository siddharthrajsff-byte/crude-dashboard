from dashboard.app import app
from ingestion.scheduler import start_scheduler


if __name__ == "__main__":
    start_scheduler()
    app.run(debug=False, port=8050)
