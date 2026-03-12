from crewai.tools import BaseTool
from pydantic import BaseModel, Field
import httpx
import os


class TransportCostInput(BaseModel):
    origin_lat: float = Field(description="Latitude of origin point")
    origin_lon: float = Field(description="Longitude of origin point")
    dest_lat: float = Field(description="Latitude of destination point")
    dest_lon: float = Field(description="Longitude of destination point")


class TransportCostTool(BaseTool):
    name: str = "transport_cost"
    description: str = (
        "Calculate transport cost and time between two points. "
        "Uses Google Maps Directions API + Rome2Rio API. "
        "Returns options: metro, bus, taxi, walking - with prices and times."
    )
    args_schema: type[BaseModel] = TransportCostInput

    def _run(
        self,
        origin_lat: float,
        origin_lon: float,
        dest_lat: float,
        dest_lon: float,
    ) -> str:
        # Google Maps Directions
        gmaps_resp = httpx.get(
            "https://maps.googleapis.com/maps/api/directions/json",
            params={
                "origin": f"{origin_lat},{origin_lon}",
                "destination": f"{dest_lat},{dest_lon}",
                "mode": "transit",
                "key": os.environ["GOOGLE_MAPS_API_KEY"],
            },
            timeout=15,
        )
        gmaps_data = gmaps_resp.json()

        # Rome2Rio for cost estimation
        r2r_resp = httpx.get(
            "https://www.rome2rio.com/api/1.5/json/Search",
            params={
                "key": os.environ["ROME2RIO_API_KEY"],
                "oPos": f"{origin_lat},{origin_lon}",
                "dPos": f"{dest_lat},{dest_lon}",
                "currencyCode": "EUR",
            },
            timeout=15,
        )
        r2r_data = r2r_resp.json()

        options = []
        if gmaps_data.get("routes"):
            route = gmaps_data["routes"][0]["legs"][0]
            options.append(
                f"Transit: {route['duration']['text']}, "
                f"distance: {route['distance']['text']}"
            )

        for route in r2r_data.get("routes", [])[:3]:
            name = route.get("name", "Unknown")
            price = route.get("indicativePrices", [{}])
            price_str = (
                f"EUR{price[0].get('priceLow', '?')}-{price[0].get('priceHigh', '?')}"
                if price
                else "price unknown"
            )
            duration = route.get("totalDuration", 0)
            options.append(f"{name}: ~{duration} min, {price_str}")

        return "\n".join(options) if options else "No transport options found"
