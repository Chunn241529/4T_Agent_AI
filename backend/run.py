# run.py

import uvicorn
from app.main import app
from app.utils.logger import logger

if __name__ == "__main__":
    logger.info("Khởi động server tại http://127.0.0.1:8000")
    uvicorn.run(app, host="127.0.0.1", port=8000)
