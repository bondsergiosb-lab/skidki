"""Магазины, которые описываются настройками общего парсера карточек (cards.Shop)."""
from .cards import Shop

UAH = r"([\d\s&#;nbsp.,]+)"

MARATHON = Shop(
    store="marathon", name="Marathon", site="https://marathon.ua",
    sections=[("/uk/sale/", "")],
    card=r'<div class="product_box flex"',
    title=r'data-name="([^"]+)"', url=r'<a href="(https://marathon\.ua/uk/[^"]+\.html)"',
    price=r'<span class="price">\s*' + UAH, old=r'class="old_price">([^<]+)<',
    # data-category у части товаров ошибочный (ботинки в «Спортивні шорти») — категорию берём из названия
    image=r'data-src="([^"]+)"', brand=r'data-brand="([^"]+)"', sku=r'data-model="([^"]+)"',
    sizes=r'<span>([^<]+)</span>(?=[^<]*(?:<span>[^<]*</span>\s*)*</div>)',
    gender=[(r'marathon\.ua/uk/women/', "women"), (r'marathon\.ua/uk/men/', "men"),
            (r'marathon\.ua/uk/(?:kids|deti|children)', "kids")],
    pages=12,  # robots.txt просит 5 секунд между запросами
)

NEW_BALANCE = Shop(
    store="newbalance", name="New Balance", site="https://newbalance.ua",
    sections=[("/store/sale/women", "women"), ("/store/sale/man", "men"), ("/store/sale/children", "kids")],
    card=r'<li class="products__item"',
    title=r'data-name="([^"]+)"', url=r'<a href="([^"]+)" class="products__link"',
    price=r'prices__price_discount">([^<]+)<', old=r'prices__price_old">([^<]+)<',
    image=r'(https://newbalance\.ua/resize/photos/auto/400/400/[^"\s]+)', brand=r'data-brand="([^"]+)"',
    sku=r'data-product-id="([^"]+)"', path=r'data-category="([^"]+)"',
    gender=[(r'data-gender_age="unisex"', "unisex")],
    pages=8,
)

ALL_STARS = Shop(
    store="allstars", name="All Stars", site="https://allstars.ua",
    sections=[("/store/aktsiyi/", "")],
    card=r"<div class='catItem",
    title=r'class="catItemTitle">([^<]+)<', url=r'href="(https://allstars\.ua/product/[^"]+)" class="catItemTitle"',
    price=r'<span class="price">([^<]+)<', old=r'class="priceOld">([^<]+)<',
    image=r'<img src="(/storage/product/[^"]+)"',
    brand=r'catItemTitle">\s*[^A-Z<]*?([A-Z][A-Z0-9&\']+)',  # «Чоловічі кросівки NIKE V5 …»
    gender=[(r'gender">Для чоловіків, Для жінок', "unisex"), (r'gender">[^<]*жінок', "women"),
            (r'gender">[^<]*чоловіків', "men"), (r'gender">[^<]*(?:дітей|дівч|хлопч)', "kids")],
    pages=15,
)

SYMBOL = Shop(
    store="symbol", name="Symbol", site="https://symbol.ua",
    sections=[("/uk/store/sale/women", "women"), ("/uk/store/sale/man", "men"), ("/uk/store/sale/children", "kids")],
    card=r'<(?:div|li|article)[^>]*class="catalog__item[\s"]',
    title=r'class="product_item_title">([^<]+)<', url=r'<a href="(https://symbol\.ua/uk/store/[^"]+)" class="catalog__item-name',
    price=r'item-new-price">([^<]+)<', old=r'item-old-price">([^<]+)<',
    image=r'<img[^>]+src="(https://media\d*\.symbol\.ua/[^"]+)"', brand=r'class="catalog__item-name[^"]*">([^<]+)<',
    sizes=r'catalog__item-size-item[^"]*"[^>]*>\s*([^<]+?)\s*<',
    page="page={n}&per-page=48", pages=6,
)

MODOZA = Shop(
    store="modoza", name="Modoza", site="https://modoza.com",
    sections=[("/rasprodazha/", "")],
    card=r'<div class="md-prod-panel js_product_item"',
    title=r'class="js_name">([^<]+)<', url=r'<a href="(/[^"]+-\d+/)"',
    price=r'js_price">([^<]+)<', old=r'class="old-price">\s*<span class="numb">([^<]+)<',
    image=r'<img src="(https://cdn\.modoza\.com/[^"]+)"', brand=r'js_brand">([^<]+)<',
    sku=r'data-id="(\d+)"', sizes_in=r'<div class="sizes">(.*?)</div>', sizes=r'<span>([^<(]+)</span>',
    gender=[(r'js_g_category">[^<]*zhensk', "women"), (r'js_g_category">[^<]*muzhsk', "men"),
            (r'js_g_category">[^<]*(?:detsk|devoch)', "kids")],
    page="p={n}", pages=20,
)

PREGO = Shop(
    store="prego", name="Prego", site="https://prego.ua",
    sections=[("/uk/akciya/akcii-obyv", "women"), ("/uk/akciya/akcii-obyv-muzskaya", "men"), ("/uk/akciya/akcii-sumki", "women")],
    card=r'<article class="product"',
    title=r'class="product__name">\s*([^<]+)', url=r'<a href="(/uk/[^"]+)" class="product__link"',
    price=r'product__new-price[^"]*">\s*<span>([^<]+)<', old=r'product__old-price">\s*<span>([^<]+)<',
    image=r'<img src="(https://static\.prego\.ua/[^"]+)"', fixed_brand="Prego",
    pages=10,
)

MIRATON = Shop(
    store="miraton", name="Miraton", site="https://www.miraton.ua",
    sections=[("/ua/catalog/outlet/", "")],
    card=r'<div class="product-item[\s"]',
    title=r'product-name">\s*<a[^>]*>([^<]+)<', url=r'product-name">\s*<a[^>]*href="([^"]+)"',
    price=r'price-current">([^<]+)<', old=r'price-old"><span>([^<]+)<',
    image=r'<img src="(/upload/[^"]+)"', brand=r'product-brand"><span>([^<]+)<',
    sku=r'data-id="(\d+)"', sizes_in=r'product-size-list">(.*?)</div>', sizes=r'>\s*([^<>]+?)\s*</a>',
    page="PAGEN_1={n}", pages=15,
)

WELFARE = Shop(
    store="welfare", name="Welfare", site="https://welfare.ua",
    sections=[("/sale/zhinkam/", "women"), ("/sale/mygchinam/", "men")],
    card=r'<div class="product" data-ga4',
    title=r'class="name">([^<]+)<', url=r'<a href="(https://welfare\.ua/[^"]+)"',
    price=r'current-price">([^<]+)<', old=r'<s>([^<]+)</s>',
    image=r'<img src="(https://welfare\.ua/image/[^"]+)"', brand=r'item_brand&quot;:&quot;([^&]+)&',
    sku=r'class="sku">([^<]+)<', path=r'item_category2&quot;:&quot;([^&]+)&',
    pages=8,
)

COLINS = Shop(
    store="colins", name="Colin's", site="https://www.colins.ua",
    sections=[("/c/womens-products-outlet-880", "women"), ("/c/mens-products-outlet-891", "men")],
    card=r'<div class="productCartMain"',
    title=r'class="product-name track-link" title="([^"]+)"', url=r'class="product-name track-link"[^>]*href="(/p/[^"]+)"',
    price=r'product-new-price">([^<]+)<', old=r'product-old-price">([^<]+)<',
    image=r"src='(https://img-colinsua[^']+)'", fixed_brand="Colin's", sku=r'data-id="(\d+)"',
    pages=10,
)

ULTRA = Shop(
    store="ultra", name="Ultra Shop", site="https://ultra-shop.com",
    sections=[("/store/sale/women", "women"), ("/store/sale/men", "men"), ("/store/sale/kids", "kids")],
    card=r'<li class="product-list__item',
    title=r'data-name="([^"]+)"', url=r'<a href="([^"]+)" class="product-link',
    price=r'data-price="([^"]+)"', old=r'class="old-price">([^<]+)<',
    image=r'data-srcset="(https://media\.ultra-shop\.com/[^"\s]+)', brand=r'data-brand="([^"]+)"',
    sku=r'data-product-id="(\d+)"', path=r'data-category="([^"]+)"',
    sizes_in=r'product-sizes__items">(.*?)</span>\s*</span>', sizes=r'<span>([^<]+)</span>',
    pages=8,
)

SOLMAR = Shop(
    store="solmar", name="Solmar", site="https://solmar.com.ua",
    sections=[("/catalog/sale/", "women")],
    card=r'<div class="s-catalog__item"',
    title=r'class="gtag-data"[^>]*data-name="([^"]+)"', url=r'class="s-product__title" href="([^"]+)"',
    price=r's-product__new-price">([^<]+)<', old=r's-product__old-price">([^<]+)<',
    image=r'<img class="hiden_img[^>]*src="([^"]+)"', fixed_brand="Solmar", sku=r'data-gtag-id="(\d+)"',
    page="/page-{n}/", pages=15,
)

ANABEL_ARTO = Shop(
    store="anabel", name="Anabel Arto", site="https://anabel-arto.com",
    sections=[("/catalog/odyag/c37/filter/sale=1", "women"), ("/catalog/bilizna-6/c78/filter/sale=1", "women"),
              ("/catalog/kupalniki/c56/filter/sale=1", "women"), ("/catalog/dlya-cholovikiv-2/c50/filter/sale=1", "men"),
              ("/catalog/dlya-ditey-ta-pidlitkiv/c30/filter/sale=1", "kids")],
    card=r'<article class="card js-import',
    title=r'class="card__link" href="[^"]+">\s*([^<]+)', url=r'class="card__link" href="([^"]+)"',
    price=r'product-cost__last">([^<]+)<', old=r'product-cost__old">([^<]+)<',
    image=r'<img [^>]*src="(https://anabel-arto\.com/storage/products/[^"]+)"', fixed_brand="Anabel Arto",
    pages=6,
)

ADIDAS = Shop(
    store="adidas", name="adidas", site="https://www.adidas.ua",
    sections=[("/sale", "")],
    card=r'<div class="product [^"]*list__item',
    title=r'class="product__title"[^>]*>([^<]+)<', url=r'<a href="(/[^"]+)" class="product__info"',
    price=r'class="price__sale"[^>]*>([^<]+)<', old=r'class="old price__first"[^>]*>([^<]+)<',
    image=r'(https://assetmanagerpim-res\.cloudinary\.com/images/w_390/[^&"]+)', fixed_brand="adidas",
    pages=25,
)

SHOPS = [MARATHON, NEW_BALANCE, ALL_STARS, SYMBOL, MODOZA, PREGO, MIRATON, WELFARE, COLINS, ULTRA, SOLMAR,
         ANABEL_ARTO, ADIDAS]
