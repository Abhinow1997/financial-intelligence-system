"""Talk to the Snowflake MCP server like Claude Desktop would: list tools, call one.

    ../.venv/Scripts/python.exe mcp_client_test.py
"""

import asyncio
import json
import tomllib
from pathlib import Path

from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport

conn = tomllib.loads((Path(__file__).parent / ".snowflake" / "connections.toml").read_text())["demo"]
HOST = f"{conn['account'].lower()}.snowflakecomputing.com"
URL = f"https://{HOST}/api/v2/databases/DEMO_DB/schemas/MARKET/mcp-servers/STOCKS_MCP"

QUERY = """
SELECT ticker, ROUND(value, 2) AS close
FROM SNOWFLAKE_CURATED_DATA_FREE.PUBLIC_DATA_FREE.STOCK_PRICE_TIMESERIES
WHERE variable = 'post-market_close_adjusted'
  AND ticker IN ('AAPL', 'MSFT', 'NVDA')
  AND date = '2026-08-06'
ORDER BY ticker
"""


async def main() -> None:
    transport = StreamableHttpTransport(URL, headers={"Authorization": f"Bearer {conn['password']}"})
    async with Client(transport) as client:
        print(f"Connected to {URL}\n")

        for tool in await client.list_tools():
            print(f"tool: {tool.name}\n  {tool.title}\n  input: {json.dumps(tool.input_schema)}\n")

        result = await client.call_tool("stock_sql", {"sql": QUERY})
        print("call stock_sql (a SELECT):")
        print(result.content[0].text, "\n")

        # The tool is configured read_only: true, so Snowflake should refuse writes.
        result = await client.call_tool(
            "stock_sql", {"sql": "CREATE TABLE DEMO_DB.MARKET.SHOULD_FAIL (x INT)"}, raise_on_error=False
        )
        print(f"call stock_sql (a CREATE TABLE): is_error={result.is_error}")
        print(result.content[0].text, "\n")

        # Tool 2: why did NVDA jump on 2023-05-24? Search that month's earnings call.
        args = {"ticker": "NVDA", "keywords": "data center", "from_date": "2023-05-01", "to_date": "2023-05-31"}
        result = await client.call_tool("earnings_call_search", args)
        passages = json.loads(result.content[0].text)
        print(f"call earnings_call_search {args}: {len(passages)} passages")
        for p in passages:
            print(f"  {p['event_date']} | {p['speaker']} ({p['role']}) | {' '.join(p['text'].split()[:15])} ...")


asyncio.run(main())
