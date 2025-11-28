from urllib.parse import urlencode

from fastapi import HTTPException

from utils.browser import PlaywrightManager


async def get_inserate_klaz(
    browser_manager: PlaywrightManager,
    query: str = None,
    location: str = None,
    radius: int = None,
    min_price: int = None,
    max_price: int = None,
    page_count: int = 1
):
    base_url = "https://www.kleinanzeigen.de"

    # Price-Filter im Pfad
    price_path = ""
    if min_price is not None or max_price is not None:
        min_price_str = str(min_price) if min_price is not None else ""
        max_price_str = str(max_price) if max_price is not None else ""
        price_path = f"/preis:{min_price_str}:{max_price_str}"

    # Query-Parameter wie bisher
    params = {}
    if query:
        params["keywords"] = query
    if location:
        # location wird zusätzlich im Pfad genutzt
        params["locationStr"] = location
    if radius:
        params["radius"] = radius

    # Suchpfad nach Kleinanzeigen-Schema:
    # /s-{PLZ}{price_path}/seite:{page}
    # z.B. /s-35390/preis:100:500/seite:2
    if location:
        search_path = f"/s-{location}{price_path}/seite:{{page}}"
    else:
        # Fallback ohne PLZ (allgemeine Suche)
        search_path = f"/s{price_path}/seite:{{page}}"

    # Basis-URL (page wird später mit .format ersetzt)
    search_url = base_url + search_path + ("?" + urlencode(params) if params else "")

    page = await browser_manager.new_context_page()
    try:
        # Erste Seite laden
        first_url = search_url.format(page=1)
        vawait page.goto(first_url, timeout=120000)
await page.wait_for_selector(".ad-listitem", timeout=60000)

        results = []

        for i in range(page_count):
            # Seite i (0-basiert) → page = i + 1
            page_results = await get_ads(page)
            results.extend(page_results)

            # Nächste Seite laden, falls gewünscht
            if i < page_count - 1:
                next_page_number = i + 2  # 2, 3, 4, ...
                next_url = search_url.format(page=next_page_number)
                try:
                    await page.goto(next_url, timeout=120000)
await page.wait_for_selector(".ad-listitem", timeout=60000)
                except Exception as e:
                    print(f"Failed to load page {next_page_number}: {str(e)}")
                    break

        return results

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await browser_manager.close_page(page)


async def get_ads(page):
    try:
        items = await page.query_selector_all(
            ".ad-listitem:not(.is-topad):not(.badge-hint-pro-small-srp)"
        )
        results = []
        for item in items:
            article = await item.query_selector("article")
            if not article:
                continue

            data_adid = await article.get_attribute("data-adid")
            data_href = await article.get_attribute("data-href")

            # Titel holen
            title_element = await article.query_selector("h2.text-module-begin a.ellipsis")
            title_text = await title_element.inner_text() if title_element else ""

            # Preis holen
            price_el = await article.query_selector(
                "p.aditem-main--middle--price-shipping--price"
            )
            price_text = await price_el.inner_text() if price_el else ""
            price_text = (
                price_text.replace("€", "")
                .replace("VB", "")
                .replace(".", "")
                .strip()
            )

            # Beschreibung holen
            description_el = await article.query_selector(
                "p.aditem-main--middle--description"
            )
            description_text = await description_el.inner_text() if description_el else ""

            if data_adid and data_href:
                data_href_full = f"https://www.kleinanzeigen.de{data_href}"
                results.append(
                    {
                        "adid": data_adid,
                        "url": data_href_full,
                        "title": title_text,
                        "price": price_text,
                        "description": description_text,
                    }
                )

        return results

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
