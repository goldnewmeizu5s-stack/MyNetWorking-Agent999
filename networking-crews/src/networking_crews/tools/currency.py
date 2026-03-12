from crewai.tools import BaseTool
from pydantic import BaseModel, Field
import httpx


class CurrencyInput(BaseModel):
    amount: float = Field(description="Amount to convert")
    from_currency: str = Field(
        description="Source currency (EUR, USD, GBP, etc.)"
    )
    to_currency: str = Field(description="Target currency")


class CurrencyTool(BaseTool):
    name: str = "currency"
    description: str = (
        "Currency conversion. Use for events in different countries."
    )
    args_schema: type[BaseModel] = CurrencyInput

    def _run(
        self, amount: float, from_currency: str, to_currency: str
    ) -> str:
        if from_currency.upper() == to_currency.upper():
            return f"{amount} {from_currency}"

        resp = httpx.get(
            f"https://api.exchangerate-api.com/v4/latest/{from_currency.upper()}",
            timeout=10,
        )
        data = resp.json()
        rate = data["rates"].get(to_currency.upper())
        if not rate:
            return f"ERROR: Unknown currency {to_currency}"

        converted = round(amount * rate, 2)
        return f"{amount} {from_currency} = {converted} {to_currency} (rate: {rate})"
