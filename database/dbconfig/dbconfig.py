import os
import psycopg
from dotenv import load_dotenv

ENV = os.environ.get("ENV", "dev")

if ENV == "dev":
    load_dotenv(".env.dev")
else:
    load_dotenv(".env.prod")

# load_dotenv()

# connection_creds = "dbname=" + os.getenv("DB_NAME") + \
#                    " user=" + os.getenv("DB_USER") + \
#                    " password=" + os.getenv("DB_PASSWORD") + \
#                    " host=" + os.getenv("DB_HOST") + \
#                    " port=" + os.getenv("DB_PORT")

connection_creds = os.getenv("DB_URL")

async def get_db_connection():
    try:
        conn = await psycopg.AsyncConnection.connect(connection_creds)
        return conn
    except Exception as e:
        print("Error connecting to the database:", e)
        return None