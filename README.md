# myVW

Async Python klient pre [myvolkswagen.net](https://www.myvolkswagen.net) — prihlásenie
a extrakcia dát vozidiel (tachometer, servisné intervaly, jazdy, kontrolky) priamym HTTP
prístupom, bez Playwright alebo iného headless prehliadača.

## Ako funguje prihlásenie

Portál používa štandardný OIDC Authorization Code Flow:

1. `GET /app/authproxy/login` → presmerovanie na `identity.vwgroup.io`
2. Odoslanie prihlasovacieho formulára (email + heslo) na `identity.vwgroup.io`
3. Presmerovanie späť na portál → nastavenie `SESSION` a `csrf_token` cookies
4. Volania `/app/authproxy/*` endpointov s hlavičkami `X-Csrf-Token` a `user-id`

Celý flow beží cez zdieľanú `httpx.AsyncClient` cookie jar — netreba spúšťať prehliadač.

## Inštalácia

```bash
pip install -e .
# alebo bez packagingu:
pip install -r requirements.txt
```

## Použitie ako knižnica

```python
import asyncio
from myvw import MyVWClient

async def main():
    async with MyVWClient("email@example.com", "heslo") as client:
        for v in await client.get_vehicles():
            print(v.vin, v.model_name, v.mileage_km, "km")

asyncio.run(main())
```

Voliteľný SOCKS/HTTP proxy:

```python
async with MyVWClient(username, password, proxy="socks5://localhost:8080") as client:
    ...
```

### Návratové dáta

`client.get_vehicles()` vráti zoznam `Vehicle` objektov:

| Pole | Popis |
|---|---|
| `vin`, `nickname`, `license_plate`, `role` | Identifikácia vozidla |
| `model_name`, `engine` | Model a motor |
| `mileage_km`, `data_timestamp` | Aktuálny stav tachometra a čas záznamu |
| `warning_lights` | Zoznam aktívnych kontroliek |
| `maintenance` | `Maintenance` — dni/km do STK a výmeny oleja |
| `short_trip`, `long_trip`, `cyclic_trip` | `Trip` — posledné zaznamenané jazdy |

Zlyhané prihlásenie vyvolá `myvw.LoginError`.

## CLI

```bash
cp .env.example .env   # vyplň VW_USERNAME a VW_PASSWORD
myvw
# alebo:
python -m myvw
python -m myvw --proxy socks5://localhost:8080
```

Vypíše čitateľný prehľad všetkých vozidiel na účte.

## Poznámky

- Neoficiálny klient — portál nemá verejné API, endpointy sa môžu kedykoľvek zmeniť.
- `verify=False` v HTTP klientovi obchádza TLS verifikáciu kvôli známym problémom
  s certifikátmi na strane portálu pri niektorých sieťach — over si to vo svojom prostredí.
