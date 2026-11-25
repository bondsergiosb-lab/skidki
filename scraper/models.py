from dataclasses import dataclass, field


@dataclass
class Item:
    """Один товар в том виде, как его отдал магазин (до проверки скидки)."""

    store: str
    sku: str
    title: str
    url: str
    image: str
    price: float                      # текущая цена
    old_price: float | None = None    # «старая» цена, которую показывает магазин
    brand: str = ""
    path: str = ""                    # категория/раздел магазина, текстом — для классификатора
    audience: str = ""                # подсказка магазина: women | girls | kids | unisex | men | boys
    sizes: list[str] = field(default_factory=list)  # размеры в наличии (если магазин их отдаёт)
    lowest_30d: float | None = None   # «найнижча ціна за 30 днів», если магазин её публикует
    hints: str = ""                   # доп. текст (SEO-описание) — только для определения «для кого»

    @property
    def id(self) -> str:
        return f"{self.store}:{self.sku}"
