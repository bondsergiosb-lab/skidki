"""Список подключённых магазинов: id → (название, сайт, функция сбора).

Чтобы добавить магазин: напишите модуль с функцией scrape(http), которая отдаёт Item, и впишите его сюда.
"""
from . import lcw, lpp, megasport

STORES = {
    "megasport": (megasport.NAME, megasport.SITE, megasport.scrape),
    "sinsay": ("Sinsay", "https://www.sinsay.com/ua/uk/", lpp.SINSAY),
    "lcw": (lcw.NAME, lcw.SITE, lcw.scrape),
}
