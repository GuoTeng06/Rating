"""
拼多多评分看板 — MySQL 数据加载器
"""
import os
import re
import time
from collections import defaultdict
import pymysql

DB_CONFIG = {
    'host': os.environ['MYSQL_HOST'],
    'port': int(os.environ.get('MYSQL_PORT', '3306')),
    'user': os.environ['MYSQL_USER'],
    'password': os.environ['MYSQL_PASSWORD'],
    'database': os.environ['MYSQL_DATABASE'],
    'charset': 'utf8mb4',
    'connect_timeout': 5,
}

BRAND_KEYWORDS = {'威王': '威王', '浪奇': '浪奇', '舒蕾': '舒蕾'}

def _brand(store):
    for kw, b in BRAND_KEYWORDS.items():
        if kw in store:
            return b
    return '白牌'

def _clean_brand(value, store):
    """Clean malformed brand values and infer a brand from the store name."""
    brand = str(value or '').strip()
    if (
        not brand
        or brand.lower() in {'none', 'null', 'nan'}
        or re.fullmatch(r'\d{4}[-/.]\d{1,2}[-/.]\d{1,2}', brand)
        or re.fullmatch(r'\d+(?:\.0+)?', brand)
    ):
        return _brand(store)
    return brand

def _pct(val):
    if val is None: return 0
    s = str(val).strip()
    m = re.search(r'([\d.]+)\s*%', s)
    if m:
        return float(m.group(1))
    s = s.rstrip('%')
    try: return float(s)
    except: return 0

_cache = None
_cache_time = 0
CACHE_TTL = 300

def _get_conn():
    return pymysql.connect(**DB_CONFIG)


def load_all_data(force=False):
    global _cache, _cache_time
    now = time.time()
    if not force and _cache is not None and (now - _cache_time) < CACHE_TTL:
        return _cache

    conn = _get_conn()
    cur = conn.cursor()

    # 1. 合并评分表
    cur.execute("SELECT * FROM `合并评分表`")
    cols = {d[0]: i for i, d in enumerate(cur.description)}
    products = []
    stores_set, dates_set, brands_set = set(), set(), set()
    seen = set()
    for row in cur.fetchall():
        item_id = str(row[cols['ID']] or '').strip()
        title = str(row[cols['标题']] or '').strip()
        reviews_raw = str(row[cols['评价总数']] or '').strip()
        rating_raw = str(row[cols['商品评分']] or '').strip()
        store = str(row[cols['店铺名称']] or '').strip()
        brand_raw = str(row[cols['品牌']] or '').strip()
        date = str(row[cols['日期']] or '').strip()
        product_name = str(row[cols.get('商品名称', cols.get('product_name', ''))] or '').strip()
        product_code = str(row[cols.get('商品编码', cols.get('product_code', ''))] or '').strip()
        if not item_id or not store or not date: continue
        if '已下架' in title: continue
        r = _pct(rating_raw)
        if r == 0: continue
        key = (item_id, date)
        if key in seen: continue
        seen.add(key)
        try: rev = int(float(reviews_raw))
        except: rev = 0
        brand = _clean_brand(brand_raw, store)
        products.append({'id': item_id, 'title': title, 'rating': r, 'reviews': rev, 'store': store, 'brand': brand, 'date': date, 'product_name': product_name, 'product_code': product_code})
        stores_set.add(store); dates_set.add(date); brands_set.add(brand)

    # 2. 店铺评分表
    cur.execute("SELECT * FROM `店铺评分表`")
    cols2 = {d[0]: i for i, d in enumerate(cur.description)}
    rating_col = next((
        name for name in ('店铺评价分排名', '近90天评分总览', '近90天评价总览')
        if name in cols2
    ), None)
    if rating_col is None:
        raise KeyError(f"店铺评分表缺少评分字段，实际字段：{list(cols2.keys())}")

    store_ratings = []
    for row in cur.fetchall():
        rating_raw = str(row[cols2[rating_col]] or '').strip()
        store = str(row[cols2['店铺名称']] or '').strip()
        brand_raw = str(row[cols2['品牌']] or '').strip()
        date = str(row[cols2['日期']] or '').strip()
        if not store or not date: continue
        r = _pct(rating_raw)
        if r == 0: continue
        brand = _clean_brand(brand_raw, store)
        store_ratings.append({'store': store, 'date': date, 'rating': r, 'brand': brand})
        stores_set.add(store); dates_set.add(date)

    # 3. 综合体验星级
    cur.execute("SELECT * FROM `综合体验星级`")
    cols3 = {d[0]: i for i, d in enumerate(cur.description)}
    star_data = []
    current = None
    for row in cur.fetchall():
        store = row[cols3['店铺名称']]
        date = row[cols3['日期']]
        star = row[cols3['当前星级']]
        brand = row[cols3['品牌']]
        dim = str(row[cols3['体验维度']] or '').strip()
        ind = str(row[cols3['考核指标']] or '').strip()
        perf = row[cols3['店铺表现']]
        std = str(row[cols3['下一星级标准']] or '').strip()

        s_store = str(store or '').strip()
        s_date = str(date or '').strip()

        # 仅当店铺或日期变化时才创建新分组
        if not current or current['store'] != s_store or current['date'] != s_date:
            s_star = float(star) if star else 0
            s_brand = str(brand or '').strip()
            current = {
                'store': s_store,
                'date': s_date,
                'star': s_star,
                'brand': _clean_brand(s_brand, s_store),
                'items': []
            }
            star_data.append(current)
        if current and dim:
            current['items'].append({'dimension': dim, 'indicator': ind, 'performance': perf, 'standard': std})

    # 4. DSR 表
    try:
        cur.execute("SELECT * FROM `dsr合并`")
        cols4 = {d[0]: i for i, d in enumerate(cur.description)}
        print(f"[MySQL] DSR columns: {list(cols4.keys())}")
        dsr_data = []
        for row in cur.fetchall():
            item = {}
            for k, i in cols4.items():
                item[k] = row[i]
            dsr_data.append(item)
    except Exception as e:
        print(f"[MySQL] DSR query failed: {e}")
        dsr_data = []

    conn.close()
    all_stores = sorted(stores_set)
    all_dates = sorted(dates_set)
    all_brands = sorted(brands_set)

    store_brand = {}
    brand_stores = defaultdict(list)
    for sr in store_ratings:
        store_brand[sr['store']] = sr['brand']
        if sr['store'] not in brand_stores[sr['brand']]:
            brand_stores[sr['brand']].append(sr['store'])
    for p in products:
        if p['store'] not in store_brand:
            store_brand[p['store']] = p['brand']
            if p['store'] not in brand_stores[p['brand']]:
                brand_stores[p['brand']].append(p['store'])

    result = {
        'stores': all_stores, 'dates': all_dates, 'brands': all_brands,
        'brandStores': {k: sorted(v) for k, v in brand_stores.items()},
        'storeBrand': store_brand, 'storeRatings': store_ratings,
        'products': products, 'starData': star_data, 'dsrData': dsr_data,
    }

    _cache = result; _cache_time = now
    print(f"[MySQL] products={len(products)}, storeRatings={len(store_ratings)}, stores={len(all_stores)}, dates={len(all_dates)}, starData={len(star_data)}")
    return result


def get_summary(data=None):
    if data is None: data = load_all_data()
    return {
        'total_products': len(data['products']), 'total_stores': len(data['stores']),
        'total_dates': len(data['dates']), 'total_store_ratings': len(data['storeRatings']),
        'date_range': [data['dates'][0], data['dates'][-1]] if data['dates'] else ['', ''],
        'update_time': time.strftime('%Y-%m-%d %H:%M:%S'),
    }
