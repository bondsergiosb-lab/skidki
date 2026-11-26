"""Список подключённых магазинов: id → (название, сайт, функция сбора).

Чтобы добавить магазин: напишите модуль с функцией scrape(http), которая отдаёт Item, и впишите его сюда.
"""
from . import gepur, kasta, lcw, lpp, megasport, prom, puma, rozetka, vovk

STORES = {
    "megasport": (megasport.NAME, megasport.SITE, megasport.scrape),
    "sinsay": ("Sinsay", "https://www.sinsay.com/ua/uk/", lpp.SINSAY),
    "lcw": (lcw.NAME, lcw.SITE, lcw.scrape),
    "reserved": ("Reserved", "https://www.reserved.com/ua/uk/", lpp.RESERVED),
    "cropp": ("Cropp", "https://www.cropp.com/ua/uk/", lpp.CROPP),
    "house": ("House", "https://www.housebrand.com/ua/uk/", lpp.HOUSE),
    "mohito": ("Mohito", "https://www.mohito.com/ua/uk/", lpp.MOHITO),
    "kasta": (kasta.NAME, kasta.SITE, kasta.scrape),
    "rozetka": (rozetka.NAME, rozetka.SITE, rozetka.scrape),
    "prom": (prom.NAME, prom.SITE, prom.scrape),
    "gepur": (gepur.NAME, gepur.SITE, gepur.scrape),
    "vovk": (vovk.NAME, vovk.SITE, vovk.scrape),
    "puma": (puma.NAME, puma.SITE, puma.scrape),
}
