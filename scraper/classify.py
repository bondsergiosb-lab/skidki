"""Раскладывает товары по категориям и определяет, для кого товар (женщины / девочки).

Магазины называют одно и то же по-разному, поэтому ищем корни слов на украинском,
русском и английском в названии товара и в пути раздела магазина.
"""
import re

# (категория, подкатегория, корни слов). Порядок важен: первая подходящая строка выигрывает,
# поэтому «специфичные» вещи (купальник, пижама) стоят выше общих (костюм, топ).
RULES = [
    ("shoes", "sneakers", "кросівк кроссовк кеди кеды сліпон слипон sneaker trainer"),
    ("shoes", "boots", "черевик ботинк чобіт чоботи сапог ботильйон ботильон ботфорт угг дутик челсі челси boot"),
    ("shoes", "slippers", "тапоч тапк шльопанц шлепанц сланц крокс в'єтнамк вьетнамк slipper"),
    ("shoes", "shoes", "туфл балетк лофер мокасин босоніжк босоножк сандал мюлі мюли еспадрил эспадрил"),
    ("bags", "bags", "сумк сумочк рюкзак клатч шопер бананк гаманець гаманц кошел портмоне косметичк bag backpack"),
    ("clothes", "underwear", "піжам пижам білизн белье бюстгальт бралет трус халат шкарпет носк колгот термобіл термобел sock"),
    ("clothes", "swim", "купальн плавк swim"),
    ("clothes", "outerwear", "куртк пальт пуховик жилет парк тренч шуб дублянк бомбер анорак вітрівк ветровк jacket coat"),
    ("clothes", "dresses", "сукн плаття платт плать спідниц юбк сарафан dress skirt"),
    ("clothes", "knit", "светр свитер кардиган кофт джемпер худі худи світшот свитшот толстовк фліс флис реглан пуловер "
                        "гольф водолазк hoodie sweatshirt crew"),
    ("clothes", "bottoms", "штани штаны брюк джинс легінс легинс лосин шорт джогер кюлот палацо trouser pant jean legging"),
    ("clothes", "tops", "футболк топ блуз сорочк рубаш лонгслів лонгслив майк боді поло туніка t-shirt"),
    ("clothes", "suits", "костюм комбінезон комбинезон жакет піджак пиджак suit"),
    ("accessories", "accessories",
     "шапк шарф снуд рукавич перчат кепк панам бейсболк ремін ремень пояс окуляр очки прикрас украш "
     "сережк серьг браслет намист колье кольє резинк заколк обруч пов'язк повязк хустк платок годинник часы парасол зонт"),
]
_RULES = [(c, s, re.compile("|".join(re.escape(w) for w in words.split()), re.I)) for c, s, words in RULES]

# Не одежда/обувь — такие товары не показываем вовсе
SKIP = re.compile(r"тарілк|тарелк|чашк|подушк|ковдр|одеял|постіль|постел|свічк|свеч|іграшк|игрушк|"
                  r"кружк|рушник|полотенц|декор|ялинк|елочн|посуд|для тварин|для собак|для кішок|"
                  r"парфум|туалетна вода|блиск для губ|помад|крем |гель для|шампун", re.I)

WOMEN = re.compile(r"жіноч|женск|для жінок|для женщин|жінкам|\bwomen|\bwoman|\bwmns|\bw\b", re.I)
GIRLS = re.compile(r"дівчат|дівчинк|девоч|для дівч|\bgirl|дитяч.*дівч|teen girl|preteen", re.I)
MEN = re.compile(r"чоловіч|мужск|для чоловіків|для мужчин|\bmen'?s?\b|\bman\b", re.I)
BOYS = re.compile(r"хлопчик|мальчик|\bboys?\b", re.I)
BABY = re.compile(r"немовл|новонарод|0-2|0-24|\bbaby\b|малюк", re.I)
KIDS = re.compile(r"дитяч|детск|\bkids?\b|junior|\bjr\b", re.I)

# Для детских товаров без указания пола (Sinsay так отдаёт всю детскую распродажу) — подсказки в названии
GIRLISH = re.compile(r"сукн|плат|спідниц|юбк|легінс|лосин|рюш|оборк|мережив|бант|паєтк|блискіт|квітк|квітков|рожев|"
                     r"пудров|лаванд|єдиноріг|unicorn|принцес|barbie|hello kitty|minnie|frozen|kuromi|my melody|"
                     r"cinnamoroll|pusheen|\blol\b|gabby|superkitties|care bears|demon hunters|wednesday|топ|блуз|"
                     r"бікіні|купальник|сердеч|метелик|леопард", re.I)
BOYISH = re.compile(r"star wars|marvel|spider|людина-павук|batman|avengers|месники|hot wheels|brawl stars|sonic|"
                    r"динозавр|\bdino|машинк|трактор|футбольн|камуфляж|jurassic|transformers|ninjago|lego city", re.I)


_MONTHS = re.compile(r"\d\s*(м|міс|мес|m)\b", re.I)
_HEIGHT = re.compile(r"^\s*(\d{2,3})\b")


def baby_only(sizes: list[str]) -> bool:
    """Все размеры младенческие: в месяцах («74 (6-9 м)») или рост до 92 см."""
    if not sizes:
        return False
    for s in sizes:
        m = _HEIGHT.match(s)
        if not (_MONTHS.search(s) or (m and 50 <= int(m.group(1)) <= 92)):
            return False
    return True


def categorize(title: str, path: str) -> tuple[str, str] | None:
    if SKIP.search(title):
        return None
    # раздел/тип товара от магазина надёжнее названия (у спортивных брендов названия — это модели)
    for source in (path, title):
        for cat, sub, rx in _RULES:
            if rx.search(source):
                return cat, sub
    return None


def audience(hint: str, title: str, path: str) -> str | None:
    """women | girls | kids (детское без пола) | unisex,
    либо None если товар не для наших девочек (мужское, мальчики, младенцы)."""
    text = f"{title} | {path}"
    if hint in ("men", "boys") or BABY.search(text):
        return None
    if hint == "girls" or GIRLS.search(text):
        return "girls"
    if hint == "women" or WOMEN.search(text):
        return "women"
    if MEN.search(text) or BOYS.search(text):
        return None
    if hint == "kids" or KIDS.search(text):  # магазин без детского раздела, но в названии «дитячі … Kids»
        if GIRLISH.search(title):
            return "girls"
        if BOYISH.search(text):
            return None
        return "kids"
    return "unisex"
