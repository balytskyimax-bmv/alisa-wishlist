import urllib.request
import urllib.parse
import ssl
import json
import os
import sys

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
}

BASE_DIR = "/Users/mac/.gemini/antigravity/scratch/baby-wishlist"
IMG_DIR = os.path.join(BASE_DIR, "public", "images")
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(IMG_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)

ITEMS = [
    {
        "id": "vezha-pomichnicya",
        "title": "Вежа-помічниця Монтессорі Goodevas (Айворі)",
        "category": "Меблі та розвиток",
        "price": "3 959 грн",
        "url": "https://antoshka.ua/uk/vezha-pomichnicja-montessori-goodevas-ajvori-e693.html",
        "note": "Корисна для безпечної участі дитини у побуті та на кухні",
        "images": [
            "https://antoshka.ua/media/catalog/product/cache/eade3e7b24aa4f9558cee11e8cfd62bd/6/1/6128688.webp",
            "https://antoshka.ua/media/catalog/product/cache/b673f3b949f63d36a1bdaae583849e0d/6/1/6128688_01.webp"
        ],
        "reserved": False,
        "reservedBy": "",
        "reservedAt": None,
        "wishes": ""
    },
    {
        "id": "dytyachyj-vigvam",
        "title": "Дитячий вігвам “Неймовірний кавовий”",
        "category": "Кімната та затишок",
        "price": "2 850 грн",
        "url": "https://zhuzhyk.com.ua/product/dytyachyj-vigvam-nejmovirnyj-kavovyj/",
        "note": "Затишний куточок для ігор, читання та відпочинку",
        "images": [
            "https://zhuzhyk.com.ua/wp-content/uploads/2025/08/PSX_20250803_121142-1_copy-1072x1536.webp",
            "https://zhuzhyk.com.ua/wp-content/uploads/2025/08/IMG_7362_copy-729x1024.webp"
        ],
        "reserved": False,
        "reservedBy": "",
        "reservedAt": None,
        "wishes": ""
    },
    {
        "id": "igrovyj-kompleks-4v1",
        "title": "4в1 Дитячий ігровий комплекс (Піклер, дуга, гірка, подушка)",
        "category": "Спорт та активність",
        "price": "5 150 грн",
        "url": "https://goodevas.ua/products/montessori-4in1-climbing-set-pikler-triangle-arch-slide-board-and-cushion-for-toddlers-1-3-years?variant=51211157406003",
        "note": "Розвиває координацію, баланс та впевненість рухів малечі",
        "images": [
            "https://cdn.shopify.com/s/files/1/0931/0863/3907/files/montessori-4in1-climbing-set-pikler-triangle-arch-slide-board-and-cushion-for-toddlers-13-years-786854.jpg?v=1742983375",
            "https://cdn.shopify.com/s/files/1/0931/0863/3907/files/Frame_2121453990.png?v=1757929581"
        ],
        "reserved": False,
        "reservedBy": "",
        "reservedAt": None,
        "wishes": ""
    },
    {
        "id": "futbolka-zirochka",
        "title": "Футболка «Зірочка» від Hey Musya",
        "category": "Одяг",
        "price": "750 грн",
        "url": "https://heymusya.com/products/futbolka-zirochka",
        "note": "Потрібний розмір: 76–86 см",
        "images": [
            "https://heymusya.com/uploads/6a634e14-2aac-4f56-becb-9668c19f072a.webp",
            "https://heymusya.com/uploads/69bbd558-c505-42bb-98dc-84a7ed61751d.webp"
        ],
        "reserved": False,
        "reservedBy": "",
        "reservedAt": None,
        "wishes": ""
    },
    {
        "id": "baby-born-rozi",
        "title": "Інтерактивна лялька Baby Born Розі 30 см",
        "category": "Ляльки та пупси",
        "price": "1 699 грн",
        "url": "https://antoshka.ua/uk/interaktivna-ljal-ka-baby-born-rozi-30-sm-840481.html",
        "note": "М'яконабивна, підходить для обіймів малечі від 1 року",
        "images": [
            "https://antoshka.ua/media/catalog/product/cache/eade3e7b24aa4f9558cee11e8cfd62bd/6/1/6132338.webp",
            "https://antoshka.ua/media/catalog/product/cache/b673f3b949f63d36a1bdaae583849e0d/6/1/6132338_01.webp"
        ],
        "reserved": False,
        "reservedBy": "",
        "reservedAt": None,
        "wishes": ""
    },
    {
        "id": "lyalka-vendela",
        "title": "Лялька Vendela 30 см (Bukowski Design)",
        "category": "Ляльки та пупси",
        "price": "1 250 грн",
        "url": "https://teddybears.com.ua/lialka-vendela-30-sm-bukowski-design-24033a/",
        "note": "Ніжна авторська шведська текстильна лялька",
        "images": [
            "https://images.prom.ua/6500092104_w640_h640_kukla-vendela-30.jpg",
            "https://images.prom.ua/6500177595_w640_h640_kukly-vendela-and-.jpg"
        ],
        "reserved": False,
        "reservedBy": "",
        "reservedAt": None,
        "wishes": ""
    },
    {
        "id": "lyalka-bella",
        "title": "Лялька Bella Creamy Stripe",
        "category": "Ляльки та пупси",
        "price": "1 450 грн",
        "url": "https://piepiekids.com/toys/baby-toys/bella-baby-doll-creamy-stripe-2907640590169",
        "note": "Стильна органічна лялечка у смугастому вбранні",
        "images": [
            "https://piepiekids.com/image/cache/catalog/torgsoft/59016_1-1000x1000.jpg",
            "https://piepiekids.com/image/cache/catalog/torgsoft/59016_2-1000x1000.jpg"
        ],
        "reserved": False,
        "reservedBy": "",
        "reservedAt": None,
        "wishes": ""
    },
    {
        "id": "pups-klein-coralie",
        "title": "М'який пупс Klein Baby Coralie з аксесуарами",
        "category": "Ляльки та пупси",
        "price": "1 199 грн",
        "url": "https://bi.ua/ukr/product/myagkiy-pups-klein-baby-coralie-s-aksessuarami-1723-bc.html",
        "note": "М'якенький пупс з тарілочкою та ложкою для гри",
        "images": [
            "https://bi.ua/uploaded-images/products/604682_1.jpg",
            "https://toybox.com.cy/cdn/shop/files/klein-1723-princess-coralie-cuddle-toybox-1.jpg"
        ],
        "reserved": False,
        "reservedBy": "",
        "reservedAt": None,
        "wishes": ""
    },
    {
        "id": "kilymok-ortek",
        "title": "Килимок масажний ортопедичний Ortek Пазли Мікс (10 ел)",
        "category": "Здоров'я та масаж",
        "price": "1 290 грн",
        "url": "https://antoshka.ua/uk/kilimok-masazhnij-ortek-pazli-miks-10-el-12808.html",
        "note": "Масажні модульні пазли для правильного формування стопи",
        "images": [
            "https://antoshka.ua/media/catalog/product/cache/eade3e7b24aa4f9558cee11e8cfd62bd/6/1/6129753.webp",
            "https://antoshka.ua/media/catalog/product/cache/b673f3b949f63d36a1bdaae583849e0d/6/1/6129753_01.webp"
        ],
        "reserved": False,
        "reservedBy": "",
        "reservedAt": None,
        "wishes": ""
    },
    {
        "id": "konyk-terrio-dizy",
        "title": "Коник-гойдалка 2в1 Terrio “Dizy”",
        "category": "Транспорт та гойдалки",
        "price": "2 190 грн",
        "url": "https://bomki.com.ua/konyk-hoidalka-2v1-terrio-dizy/",
        "note": "Трансформується: гойдалка та каталка на колесах",
        "images": [
            "https://images.prom.ua/6721789238_w640_h640_loshadka-2v1-terrio.jpg",
            "https://images.prom.ua/7563553955_w640_h640_loshadka-2v1-terrio.jpg"
        ],
        "reserved": True,
        "reservedBy": "Зарезервовано гостем",
        "reservedAt": "2026-10-17 21:00",
        "wishes": "З любов'ю для Алісоньки!"
    },
    {
        "id": "elektromobil-bmw",
        "title": "Дитячий електромобіль BMW M",
        "category": "Транспорт та гойдалки",
        "price": "6 499 грн",
        "url": "https://prom.ua/ua/m9059728233957577580-detskij-elektromobil-bmw.html?p=3124296964",
        "note": "Справжній перший автомобіль із пультом керування для батьків",
        "images": [
            "https://images.prom.ua/7559400250_w640_h640_detskij-elektromobil-bmw.jpg",
            "https://images.prom.ua/7564416424_w640_h640_detskij-elektromobil-bmw.jpg"
        ],
        "reserved": False,
        "reservedBy": "",
        "reservedAt": None,
        "wishes": ""
    },
    {
        "id": "piramidka-done-by-deer",
        "title": "Пірамідка-жирафа Done by Deer Raffi Мікс кольорів (4833179)",
        "category": "Розвиваючі іграшки",
        "price": "1 150 грн",
        "url": "https://zabavka.ua/piramidka-done-by-deer-raffi-miks-koloriv-4833179",
        "note": "Сенсорна дерев'яна пірамідка-неваляйка з різними текстурами",
        "images": [
            "https://donebydeer.com/cdn/shop/products/Stacking-tower-Raffi-Colour-mix-Front-PS.jpg?v=1751974752&width=600",
            "https://donebydeer.com/cdn/shop/products/Stacking-tower-Raffi-Colour-mix-Function-4-PS.jpg?v=1751974752&width=700"
        ],
        "reserved": False,
        "reservedBy": "",
        "reservedAt": None,
        "wishes": ""
    },
    {
        "id": "katalka-pelikan",
        "title": "Іграшка-каталка Kiddi Smart «Пелікан-Витівник»",
        "category": "Розвиваючі іграшки",
        "price": "1 099 грн",
        "url": "https://baby.bi.ua/ukr/product/igrushka-katalka-kiddi-smart-pelikan-zateynik-064642.html",
        "note": "Озвучена українською мовою, викидає кульки під час руху",
        "images": [
            "https://bi.ua/uploaded-images/products/599346_1.jpg",
            "https://images.prom.ua/7792115970_w640_h640_katalka-kiddi-smart.jpg"
        ],
        "reserved": False,
        "reservedBy": "",
        "reservedAt": None,
        "wishes": ""
    },
    {
        "id": "rybalka-lilliputiens",
        "title": "Магнітна рибалка Lilliputiens Каченя Гаспард (83675)",
        "category": "Розвиваючі іграшки",
        "price": "1 190 грн",
        "url": "https://zabavka.ua/mahnitna-rybalka-lilliputiens-kachenia-haspard-83675",
        "note": "Розвиваюча магнітна водна гра з качечками для купання",
        "images": [
            "https://images.prom.ua/7627239186_w640_h640_magnitnaya-rybalka-lilliputiens.jpg",
            "https://images.prom.ua/7564662757_w640_h640_magnitnaya-rybalka-utyonok.jpg"
        ],
        "reserved": False,
        "reservedBy": "",
        "reservedAt": None,
        "wishes": ""
    }
]

def download_file(url, path):
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, context=ctx, timeout=10) as r:
            data = r.read()
            if len(data) > 2000:
                with open(path, "wb") as f:
                    f.write(data)
                return True
    except Exception as e:
        print(f"Error downloading {url}: {e}")
    return False

# Download all local copies and update paths
final_items = []
for item in ITEMS:
    local_images = []
    for idx, img_url in enumerate(item["images"]):
        ext = ".jpg"
        if ".webp" in img_url.lower(): ext = ".webp"
        elif ".png" in img_url.lower(): ext = ".png"
        
        fname = f"{item['id']}_{idx+1}{ext}"
        fpath = os.path.join(IMG_DIR, fname)
        
        # Download if not already downloaded or if size is too small
        if not os.path.exists(fpath) or os.path.getsize(fpath) < 3000:
            print(f"Downloading {fname} from {img_url[:60]}...")
            if download_file(img_url, fpath):
                local_images.append(f"/images/{fname}")
            else:
                # fallback to remote URL
                local_images.append(img_url)
        else:
            local_images.append(f"/images/{fname}")

    item_copy = dict(item)
    # Provide local images, and keep remoteUrls for reference/backup
    item_copy["images"] = local_images
    item_copy["remoteImages"] = item["images"]
    final_items.append(item_copy)

out_file = os.path.join(DATA_DIR, "gifts.json")
with open(out_file, "w", encoding="utf-8") as f:
    json.dump(final_items, f, ensure_ascii=False, indent=2)

print(f"\nAll done! 14 items saved to {out_file}")
