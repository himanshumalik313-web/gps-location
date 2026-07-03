import reverse_geocoder as rg

_cache = {}

def reverse_geocode(lat: float, lon: float) -> dict:
    """Turns (lat, lon) into a city/state/country name. Cached so it's fast."""
    key = (round(lat, 4), round(lon, 4))
    if key in _cache:
        return _cache[key]
    result = rg.search([(lat, lon)])[0]
    place = {
        "city": result.get("name", ""),
        "state": result.get("admin1", ""),
        "country": result.get("cc", ""),
    }
    _cache[key] = place
    return place