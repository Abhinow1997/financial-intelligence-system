"""One place that opens a Snowpark session for every demo script.
"""

from pathlib import Path

from snowflake.snowpark import Session
from snowflake.snowpark.context import get_active_session
from snowflake.snowpark.exceptions import SnowparkSessionException

CONNECTIONS_FILE = Path(__file__).resolve().parent / ".snowflake" / "connections.toml"
CONNECTION_NAME = "demo"


def get_session() -> Session:
    """Reuse the Snowsight notebook session if there is one, else open our own."""
    try:
        return get_active_session()
    except SnowparkSessionException:
        pass  # running locally: no notebook session, so connect with connections.toml
    return Session.builder.configs(
        {"connection_name": CONNECTION_NAME, "connections_file_path": CONNECTIONS_FILE}
    ).create()
