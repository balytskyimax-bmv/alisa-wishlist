import urllib.request
import urllib.parse
import ssl
import re
import json
import os
import sys

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
    'Accept-Language': 'uk-UA,uk;q=0.9,en-US;q=0.8,en;q=0.7',
    'Sec-Ch-Ua': '"Chromium";v="122", "Not(A:Brand";v="24", "Google Chrome";v="122"',
    'Sec-Ch-Ua-Mobile': '?0',
    'Sec-Ch-Ua-Platform': '"macOS"',
}

PRODUCTS_CONFIG = [
    {
        "id": "vezha-pomichnicya",
        "category": "Меблі та розвиток",
        "default_title": "Вежа-помічниця Монтессорі Goodevas айворі",
        "url": "https://antoshka.ua/uk/vezha-pomichnicja-montessori-goodevas-ajvori-e693.html"
    },
    {
        "id": "dytyachyj-vigvam",
        "category": "Кімната та затишок",
        "default_title": "Дитячий вігвам “Неймовірний кавовий”",
        "url": "https://zhuzhyk.com.ua/product/dytyachyj-vigvam-nejmovirnyj-kavovyj/"
    },
    {
        "id": "igrovyj-kompleks-4v1",
        "category": "Спорт та активність",
        "default_title": "4в1 Дитячий ігровий комплекс для малюків (трикутник Піклер, гірка, дуга)",
        "url": "https://goodevas.ua/products/montessori-4in1-climbing-set-pikler-triangle-arch-slide-board-and-cushion-for-toddlers-1-3-years?variant=51211157406003"
    },
    {
        "id": "futbolka-zirochka",
        "category": "Одяг та аксесуари",
        "default_title": "Футболка «Зірочка» Hey Musya",
        "url": "https://heymusya.com/products/futbolka-zirochka"
    },
    {
        "id": "baby-born-rozi",
        "category": "Ляльки та пупси",
        "default_title": "Інтерактивна лялька Baby Born Розі 30 см",
        "url": "https://antoshka.ua/uk/interaktivna-ljal-ka-baby-born-rozi-30-sm-840481.html"
    },
    {
        "id": "lyalka-vendela",
        "category": "Ляльки та пупси",
        "default_title": "Лялька Vendela 30 см Bukowski Design",
        "url": "https://teddybears.com.ua/lialka-vendela-30-sm-bukowski-design-24033a/"
    },
    {
        "id": "lyalka-bella",
        "category": "Ляльки та пупси",
        "default_title": "Лялька Bella Creamy Stripe",
        "url": "https://piepiekids.com/toys/baby-toys/bella-baby-doll-creamy-stripe-2907640590169"
    },
    {
        "id": "pups-klein-coralie",
        "category": "Ляльки та пупси",
        "default_title": "М'який пупс Klein Baby Coralie з аксесуарами",
        "url": "https://bi.ua/ukr/product/myagkiy-pups-klein-baby-coralie-s-aksessuarami-1723-bc.html"
    },
    {
        "id": "kilymok-ortek",
        "category": "Здоров'я та масаж",
        "default_title": "Килимок масажний Ortek Пазли Мікс 10 ел",
        "url": "https://antoshka.ua/uk/kilimok-masazhnij-ortek-pazli-miks-10-el-12808.html"
    },
    {
        "id": "konyk-terrio-dizy",
        "category": "Транспорт та гойдалки",
        "default_title": "Коник-гойдалка 2в1 Terrio “Dizy”",
        "url": "https://bomki.com.ua/konyk-hoidalka-2v1-terrio-dizy/"
    },
    {
        "id": "elektromobil-bmw",
        "category": "Транспорт та гойдалки",
        "default_title": "Дитячий електромобіль BMW M",
        "url": "https://prom.ua/ua/m9059728233957577580-detskij-elektromobil-bmw.html?p=3124296964"
    },
    {
        "id": "piramidka-done-by-deer",
        "category": "Розвиваючі іграшки",
        "default_title": "Пірамідка Done by Deer Raffi Мікс кольорів",
        "url": "https://zabavka.ua/piramidka-done-by-deer-raffi-miks-koloriv-4833179"
    },
    {
        "id": "katalka-pelikan",
        "category": "Розвиваючі іграшки",
        "default_title": "Іграшка-каталка Kiddi Smart Пелікан-Витівник",
        "url": "https://baby.bi.ua/ukr/product/igrushka-katalka-kiddi-smart-pelikan-zateynik-064642.html"
    },
    {
        "id": "rybalka-lilliputiens",
        "category": "Розвиваючі іграшки",
        "default_title": "Магнітна рибалка Lilliputiens Каченя Гаспард",
        "url": "https://zabavka.ua/mahnitna-rybalka-lilliputiens-kachenia-haspard-83675"
    }
]

IMG_DIR = "/Users/mac/.gemini/antigravity/scratch/baby-wishlist/public/images"
DATA_DIR = "/Users/mac/.gemini/antigravity/scratch/baby-wishlist/data"
os.makedirs(IMG_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)

def fetch_url(url):
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, context=ctx, timeout=15) as res:
            content_type = res.headers.get_content_type()
            if 'image' in content_type:
                return res.read()
            charset = res.headers.get_content_charset() or 'utf-8'
            return res.read().decode(charset, errors='replace')
    except Exception as e:
        print(f"Error fetching {url}: {e}", file=sys.stderr)
        return None

def download_image(url, target_path):
    try:
        data = fetch_url(url)
        if isinstance(data, bytes) and len(data) > 3000:
            with open(target_path, 'wb') as f:
                f.write(data)
            return True
    except Exception as e:
        print(f"Download failed for {url}: {e}")
    return False

def clean_text(t):
    return re.sub(r'\s+', ' ', t).strip()

results = []
for p in PRODUCTS_CONFIG:
    print(f"\n--- Scraping {p['default_title']} ---")
    html = fetch_url(p["url"])
    title = p["default_title"]
    price = ""
    description = ""
    candidate_images = []

    if html and isinstance(html, str):
        # Title
        t_match = re.search(r'<meta\s+property=["\']og:title["\']\s+content=["\'](.*?)["\']', html, re.I)
        if not t_match:
            t_match = re.search(r'<title>(.*?)</title>', html, re.I)
        if t_match:
            cand = clean_text(t_match.group(1))
            cand = cand.split('|')[0].split(' - ')[0].replace('купити за ціною', '').strip()
            if len(cand) > 5:
                title = cand

        # Description
        d_match = re.search(r'<meta\s+property=["\']og:description["\']\s+content=["\'](.*?)["\']', html, re.I)
        if d_match:
            description = clean_text(d_match.group(1))

        # Price detection
        price_patterns = [
            r'["\']price["\']\s*:\s*["\']?([0-9\s.,]+)["\']?',
            r'class=["\'][^"\']*(?:price|cost)[^"\']*["\'][^>]*>([0-9\s.,]+)\s*грн',
            r'([0-9]{1,3}(?:[ \u00a0][0-9]{3})*)\s*грн'
        ]
        for pat in price_patterns:
            m = re.search(pat, html, re.I)
            if m:
                val = m.group(1).replace('\u00a0', ' ').replace(' ', '').replace(',', '.')
                try:
                    num = float(val)
                    if 50 < num < 50000:
                        price = f"{int(num):,} грн".replace(',', ' ')
                        break
                except:
                    pass

        # Image collection
        # og:image
        for m in re.finditer(r'<meta\s+property=["\']og:image["\']\s+content=["\'](.*?)["\']', html, re.I):
            u = m.group(1).strip()
            if u not in candidate_images:
                candidate_images.append(u)
        for m in re.finditer(r'<meta\s+content=["\'](.*?)["\']\s+property=["\']og:image["\']', html, re.I):
            u = m.group(1).strip()
            if u not in candidate_images:
                candidate_images.append(u)

        # Look for gallery or data-zoom / data-src
        for m in re.finditer(r'(?:data-zoom-image|data-large|data-full|data-src|src)=["\'](https?://[^"\']+\.(?:jpg|jpeg|png|webp)[^"\']*)["\']', html, re.I):
            u = m.group(1).strip()
            low = u.lower()
            if any(skip in low for skip in ['logo', 'icon', 'banner', 'avatar', 'payment', 'facebook', 'instagram', 'star', 'loader', 'sprite', 'pixel', 'badge', 'cart']):
                continue
            if u not in candidate_images:
                candidate_images.append(u)

    print(f"Found {len(candidate_images)} candidate images for {p['id']}")
    saved_images = []
    
    for idx, img_url in enumerate(candidate_images):
        if len(saved_images) >= 2:
            break
        ext = ".jpg"
        if ".png" in img_url.lower(): ext = ".png"
        elif ".webp" in img_url.lower(): ext = ".webp"
        
        filename = f"{p['id']}_{len(saved_images)+1}{ext}"
        filepath = os.path.join(IMG_DIR, filename)
        print(f"Downloading #{len(saved_images)+1}: {img_url}")
        if download_image(img_url, filepath):
            saved_images.append(f"/images/{filename}")

    # Fallback if less than 2
    for i in range(len(saved_images), 2):
        saved_images.append(f"https://images.unsplash.com/photo-1515488042361-ee00e0ddd4e4?w=600&auto=format&fit=crop&q=80")

    results.append({
        "id": p["id"],
        "title": title,
        "category": p["category"],
        "price": price if price else "Дивіться на сайті",
        "description": description[:180] + "..." if len(description) > 180 else description,
        "url": p["url"],
        "images": saved_images,
        "reserved": False,
        "reservedBy": "",
        "reservedAt": None,
        "wishes": ""
    })

out_file = os.path.join(DATA_DIR, "gifts.json")
with open(out_file, "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

print(f"\nAll done! Saved {len(results)} items to {out_file}")
