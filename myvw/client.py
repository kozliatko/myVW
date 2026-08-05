"""
myvolkswagen.net klient — priamy HTTP prístup bez Playwright.

Prihlásenie prebieha cez štandardný OIDC Authorization Code Flow:
  1. GET /app/authproxy/login → presmerovanie na identity.vwgroup.io
  2. Odoslanie prihlasovacieho formulára na identity.vwgroup.io
  3. Presmerovanie späť na portál → nastavenie session cookies
  4. Volania /app/authproxy/* endpointov s X-Csrf-Token + user-id hlavičkami

Príklad:
    import asyncio
    from myvw import MyVWClient

    async def main():
        async with MyVWClient("email@example.com", "heslo") as c:
            for v in await c.get_vehicles():
                print(v.vin, v.model_name, v.mileage_km)

    asyncio.run(main())
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin

import httpx

# ---------------------------------------------------------------------------
# Konštanty
# ---------------------------------------------------------------------------

_PORTAL = "https://www.myvolkswagen.net"
_AP = "/app/authproxy"

# URL inicializujúca OAuth2 flow – naviguje na identity.vwgroup.io
_LOGIN_URL = (
    f"{_PORTAL}{_AP}/login"
    "?fag=vw-phs,vwag-weconnect"
    "&scope-vw-phs=profile,cars,vin"
    "&scope-vwag-weconnect=openid,mbb"
    "&prompt-vwag-weconnect=none"
    f"&redirectUrl={_PORTAL}%2Fsk%2Fsk%2Fmyvolkswagen.html"
    "&sessionTimeout=1800"
)

# Hlavičky napodobňujúce bežný prehliadač
_BROWSER_HDR: dict[str, str] = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "sk-SK,sk;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
}

# Hlavičky pre API volania na authproxy
# user-id '__userId__' je placeholder; authproxy ho zamení za skutočné ID zo session.
_API_HDR: dict[str, str] = {
    "Content-Type": "application/json;charset=UTF-8",
    "Accept-Language": "sk-SK",
    "user-id": "__userId__",
    "Referer": f"{_PORTAL}/sk/sk/myvolkswagen.html",
}

_ENDPOINTS: dict[str, str] = {
    "data":     f"{_AP}/vw-phs/proxy/vehicles/{{vin}}/data/sk-SK?resourceHost=cwat-group-vehicle-file-service-prod",
    "details":  f"{_AP}/vw-phs/proxy/vehicles/{{vin}}/details/sk-SK?resourceHost=cwat-group-vehicle-file-service-prod",
    "warnings": f"{_AP}/vwag-weconnect/proxy/vehicles/{{vin}}/warninglights/last?gdc=myvw-mbb-prod&resourceHost=myvw-vcf-prod",
    "maint":    f"{_AP}/vw-phs/proxy/vehicles/{{vin}}/maintenance/status?gdc=myvw-mbb-prod&resourceHost=myvw-vcf-prod",
    "trip_st":  f"{_AP}/vw-phs/proxy/vehicles/{{vin}}/tripdata/shortterm/last?gdc=myvw-mbb-prod&resourceHost=myvw-vcf-prod",
    "trip_lt":  f"{_AP}/vw-phs/proxy/vehicles/{{vin}}/tripdata/longterm/last?gdc=myvw-mbb-prod&resourceHost=myvw-vcf-prod",
    "trip_cy":  f"{_AP}/vw-phs/proxy/vehicles/{{vin}}/tripdata/cyclic/last?gdc=myvw-mbb-prod&resourceHost=myvw-vcf-prod",
}

# ---------------------------------------------------------------------------
# Parsovanie HTML formulára
# ---------------------------------------------------------------------------

class _FormParser(HTMLParser):
    """Extrahuje prvý HTML formulár — action URL a všetky input polia."""

    def __init__(self) -> None:
        super().__init__()
        self._form: dict[str, Any] | None = None
        self.result: dict[str, Any] | None = None

    def handle_starttag(self, tag: str, attrs_list: list) -> None:
        attrs = dict(attrs_list)
        if tag == "form" and self._form is None:
            self._form = {"action": attrs.get("action", ""), "fields": {}}
        elif tag == "input" and self._form is not None:
            name = attrs.get("name")
            if name:
                self._form["fields"][name] = attrs.get("value", "")

    def handle_endtag(self, tag: str) -> None:
        if tag == "form" and self._form and self.result is None:
            self.result = self._form


def _parse_form(html: str, base_url: str = "") -> tuple[str, dict[str, str]]:
    """Vráti (action_url, {field_name: value}) z prvého formulára v HTML."""
    p = _FormParser()
    p.feed(html)
    if not p.result:
        raise LoginError("Prihlasovací formulár sa nenašiel v odpovedi identity servera")
    action = p.result["action"] or base_url
    if action and not action.startswith("http"):
        action = urljoin(base_url, action)
    return action, p.result["fields"]


# ---------------------------------------------------------------------------
# Dátové triedy
# ---------------------------------------------------------------------------

@dataclass
class Maintenance:
    """Servisné intervaly vozidla."""
    inspection_due_days: int | None = None
    inspection_due_km: int | None = None
    oil_due_days: int | None = None
    oil_due_km: int | None = None


@dataclass
class Trip:
    """Zaznamenaná jazda."""
    trip_type: str = ""
    distance_km: int | None = None
    avg_fuel_l100: float | None = None
    travel_time_min: int | None = None
    avg_speed_kmh: int | None = None
    end_timestamp: str = ""


@dataclass
class Vehicle:
    """Kompletný stav jedného vozidla."""
    vin: str
    nickname: str = ""
    license_plate: str = ""
    role: str = ""
    model_name: str = ""
    engine: str = ""
    mileage_km: int | None = None
    data_timestamp: str = ""
    warning_lights: list = field(default_factory=list)
    maintenance: Maintenance = field(default_factory=Maintenance)
    short_trip: Trip | None = None
    long_trip: Trip | None = None
    cyclic_trip: Trip | None = None


# ---------------------------------------------------------------------------
# Výnimky
# ---------------------------------------------------------------------------

class LoginError(RuntimeError):
    """Prihlásenie zlyhalo."""


# ---------------------------------------------------------------------------
# Klient
# ---------------------------------------------------------------------------

class MyVWClient:
    """
    Async klient pre myvolkswagen.net.

    Používa httpx.AsyncClient so zdieľanou cookie jar — session cookies
    získané počas prihlásenia sa automaticky posielajú pri každom ďalšom requeste.

    Podporuje async with aj manuálne volanie start()/close().
    """

    def __init__(
        self,
        username: str,
        password: str,
        *,
        proxy: str | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._username = username
        self._password = password
        self._proxy = proxy
        self._transport = transport
        self._http: httpx.AsyncClient | None = None

    # -- Lifecycle -----------------------------------------------------------

    async def start(self) -> None:
        """Vytvorí HTTP session."""
        kwargs: dict[str, Any] = {
            "follow_redirects": True,
            "verify": False,
            "headers": _BROWSER_HDR,
            "timeout": 30.0,
        }
        if self._proxy:
            kwargs["proxy"] = self._proxy
        if self._transport is not None:
            kwargs["transport"] = self._transport
        self._http = httpx.AsyncClient(**kwargs)

    async def close(self) -> None:
        """Zatvorí HTTP session."""
        if self._http:
            await self._http.aclose()
            self._http = None

    async def __aenter__(self) -> "MyVWClient":
        await self.start()
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.close()

    # -- Prihlásenie ---------------------------------------------------------

    async def login(self) -> None:
        """
        Prihlási sa do myvolkswagen.net cez OIDC flow na identity.vwgroup.io.

        Po úspešnom prihlásení sú SESSION a csrf_token cookies uložené
        v internej cookie jar a automaticky posielané pri každom ďalšom requeste.

        Vyvolá LoginError ak prihlásenie zlyhá.
        """
        http = self._http

        # Krok 1: GET login URL → sleduj presmerovaniami až na identity.vwgroup.io
        r = await http.get(_LOGIN_URL)
        if "identity.vwgroup.io" not in str(r.url):
            raise LoginError(
                f"Neočakávaná URL po login redirecte: {r.url}"
            )

        # Krok 2: Parsuj prihlasovací formulár
        login_page_url = str(r.url)
        action, fields = _parse_form(r.text, login_page_url)

        # Krok 3: Doplň prihlasovacie údaje a odošli formulár
        fields["username"] = self._username
        fields["password"] = self._password

        r = await http.post(
            action or login_page_url,
            data=fields,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        # Overenie: sme späť na portáli?
        if _PORTAL not in str(r.url):
            raise LoginError(
                f"Prihlásenie zlyhalo — finálna URL: {r.url}\n"
                f"Odpoveď (prvých 300 znakov): {r.text[:300]}"
            )

        # Verifikácia session cookie
        if not self._http.cookies.get("SESSION"):
            raise LoginError("SESSION cookie sa nenastavila — prihlasovacie údaje nesprávne?")

    # -- Hlavná metóda -------------------------------------------------------

    async def get_vehicles(self) -> list[Vehicle]:
        """
        Prihlási sa a vráti zoznam Vehicle objektov so všetkými dostupnými dátami.
        """
        await self.login()

        relations = await self._get_relations()
        return [await self._fetch_vehicle(rel) for rel in relations]

    # -- Pomocné metódy ------------------------------------------------------

    def _api_headers(self) -> dict[str, str]:
        csrf = self._http.cookies.get("csrf_token", "")
        return {**_API_HDR, "X-Csrf-Token": csrf, "traceId": str(uuid.uuid4())}

    async def _api(self, path: str) -> dict | list | None:
        """GET na authproxy endpoint, vráti JSON alebo None pri chybe."""
        r = await self._http.get(
            f"{_PORTAL}{path}",
            headers=self._api_headers(),
        )
        if r.status_code == 200:
            return r.json()
        return None

    async def _get_relations(self) -> list[dict]:
        """Vráti zoznam vehicle relations (obsahuje VINy, prezývky, EČV)."""
        data = await self._api(
            f"{_AP}/vw-phs/proxy/v2/users/me/relations?resourceHost=myvw-vum-prod"
        )
        if not data or "relations" not in data:
            raise RuntimeError("Nepodarilo sa získať zoznam vozidiel z portálu")
        return data["relations"]

    async def _fetch_vehicle(self, rel: dict) -> Vehicle:
        vin = rel.get("vehicle", {}).get("vin", "")
        v = Vehicle(
            vin=vin,
            nickname=rel.get("vehicleNickname", ""),
            license_plate=rel.get("licensePlate", ""),
            role=rel.get("role", ""),
        )
        ep = {k: tpl.format(vin=vin) for k, tpl in _ENDPOINTS.items()}

        data = await self._api(ep["data"])
        if data:
            v.model_name = data.get("modelName", "")

        details = await self._api(ep["details"])
        if details:
            v.engine = details.get("engine", "")

        warnings = await self._api(ep["warnings"])
        if warnings and "data" in warnings:
            d = warnings["data"]
            v.mileage_km = d.get("mileage_km")
            v.warning_lights = d.get("warningLights", [])
            v.data_timestamp = d.get("carCapturedTimestamp", "")[:19].replace("T", " ")

        maint = await self._api(ep["maint"])
        if maint and "data" in maint:
            d = maint["data"]
            v.maintenance = Maintenance(
                inspection_due_days=d.get("inspectionDue_days"),
                inspection_due_km=d.get("inspectionDue_km"),
                oil_due_days=d.get("oilServiceDue_days"),
                oil_due_km=d.get("oilServiceDue_km"),
            )

        for key, attr in [
            ("trip_st", "short_trip"),
            ("trip_lt", "long_trip"),
            ("trip_cy", "cyclic_trip"),
        ]:
            td = await self._api(ep[key])
            if td and "data" in td:
                d = td["data"]
                setattr(v, attr, Trip(
                    trip_type=d.get("tripType", ""),
                    distance_km=d.get("mileage_km"),
                    avg_fuel_l100=d.get("averageFuelConsumption"),
                    travel_time_min=d.get("travelTime"),
                    avg_speed_kmh=d.get("averageSpeed_kmph"),
                    end_timestamp=d.get("tripEndTimestamp", "")[:19].replace("T", " "),
                ))

        return v
