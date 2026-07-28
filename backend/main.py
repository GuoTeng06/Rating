"""
拼多多评分看板 — FastAPI 后端
端口 8768，CORS 全开，数据来自 data_loader.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from data_loader import load_all_data, get_summary
from collections import defaultdict

app = FastAPI(title="拼多多评分看板 API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'frontend', 'index.html')


@app.get("/", response_class=HTMLResponse)
def serve_frontend():
    with open(FRONTEND_PATH, "r", encoding="utf-8") as f:
        content = f.read()
    resp = HTMLResponse(content=content)
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp


@app.get("/api/summary")
def api_summary():
    data = load_all_data()
    return get_summary(data)


@app.get("/api/stores")
def api_stores():
    data = load_all_data()
    return [{'name': s, 'brand': data['storeBrand'].get(s, '白牌')} for s in data['stores']]


@app.get("/api/dates")
def api_dates():
    data = load_all_data()
    return data['dates']


@app.get("/api/brands")
def api_brands():
    data = load_all_data()
    return [{'name': b, 'store_count': len(data['brandStores'].get(b, []))} for b in data['brands']]


@app.get("/api/products")
def api_products(
    store: str = Query(None),
    brand: str = Query(None),
    date_from: str = Query(None),
    date_to: str = Query(None),
    search: str = Query(None),
    rating_min: float = Query(None),
):
    data = load_all_data()
    products = data['products']

    if store:
        stores_list = [s.strip() for s in store.split(',') if s.strip()]
        products = [p for p in products if p['store'] in stores_list]
    if brand:
        products = [p for p in products if p['brand'] == brand]
    if date_from:
        products = [p for p in products if p['date'] >= date_from]
    if date_to:
        products = [p for p in products if p['date'] <= date_to]
    if search:
        s = search.lower()
        products = [p for p in products if s in p['id'].lower() or s in p['title'].lower()]
    if rating_min is not None:
        products = [p for p in products if p['rating'] >= rating_min]

    # 按评分降序
    products.sort(key=lambda p: p['rating'], reverse=True)

    # 商品ID去重列表
    id_set = sorted(set(p['id'] for p in products))
    id_count = len(id_set)

    # 商品编码列表（从ID匹配合并评分表中的编码）
    # 注：当前 Excel 无编码列，使用ID前6位作为编码
    codes = sorted(set(p['id'][:6] for p in products))

    return {
        'products': products,
        'id_list': id_set,
        'id_count': id_count,
        'codes': codes,
        'total': len(products),
    }


@app.get("/api/store-ratings")
def api_store_ratings(
    store: str = Query(None),
    brand: str = Query(None),
    date_from: str = Query(None),
    date_to: str = Query(None),
    rating_min: float = Query(None),
):
    data = load_all_data()
    ratings = data['storeRatings']

    if store:
        ratings = [r for r in ratings if r['store'] == store]
    if brand:
        ratings = [r for r in ratings if r['brand'] == brand]
    if date_from:
        ratings = [r for r in ratings if r['date'] >= date_from]
    if date_to:
        ratings = [r for r in ratings if r['date'] <= date_to]
    if rating_min is not None:
        ratings = [r for r in ratings if r['rating'] >= rating_min]

    ratings.sort(key=lambda r: r['rating'], reverse=True)
    return {'ratings': ratings, 'total': len(ratings)}


@app.get("/api/star-data")
def api_star_data(
    store: str = Query(None),
    brand: str = Query(None),
    date_from: str = Query(None),
    date_to: str = Query(None),
):
    data = load_all_data()
    star = data['starData']

    if store:
        star = [s for s in star if s['store'] == store]
    if brand:
        star = [s for s in star if s['brand'] == brand]
    if date_from:
        star = [s for s in star if s['date'] >= date_from]
    if date_to:
        star = [s for s in star if s['date'] <= date_to]

    return {'star_data': star, 'total': len(star)}


@app.get("/api/star/averages")
def api_star_averages(
    brand: str = Query(None),
    date_from: str = Query(None),
    date_to: str = Query(None),
    store: str = Query(None),
):
    """综合体验星级 5 个维度的全店均值"""
    data = load_all_data()
    star = data['starData']

    if store:
        stores = [s.strip() for s in store.split(',') if s.strip()]
        star = [s for s in star if s['store'] in stores]
    if brand:
        star = [s for s in star if s['brand'] == brand]
    if date_from:
        star = [s for s in star if s['date'] >= date_from]
    if date_to:
        star = [s for s in star if s['date'] <= date_to]

    # 5 个指标: 指标名 → 店铺-日期权重
    TARGETS = ['近30天平台求助率', '近90天用户评价得分排名', '近30天严重劣质率',
               '近30天物流综合违规处理率', '近30天店铺活跃度']
    # 每店每日取各指标值（同一日期同一店铺算一次）
    by_store_date = {}
    for s in star:
        key = (s['store'], s['date'])
        if key not in by_store_date:
            by_store_date[key] = {}
        for it in s.get('items', []):
            ind = it.get('indicator', '')
            perf = it.get('performance', '')
            if ind not in TARGETS:
                continue
            try:
                v = float(perf)
            except:
                v = None
            by_store_date[key][ind] = v

    # 每个指标计算有效值的均值
    result = {}
    for t in TARGETS:
        vals = [by_store_date[k][t] for k in by_store_date if t in by_store_date[k] and by_store_date[k][t] is not None]
        avg = round(sum(vals) / len(vals), 4) if vals else None
        result[t] = avg

    return {'averages': result, 'metrics': TARGETS, 'count': len(by_store_date)}


@app.get("/api/trends/product")
def api_product_trends(
    store: str = Query(None),
    date_from: str = Query(None),
    date_to: str = Query(None),
):
    """商品评分趋势：每天该店铺所有商品的平均评分和总评价数"""
    data = load_all_data()
    products = data['products']

    if store:
        products = [p for p in products if p['store'] == store]
    if date_from:
        products = [p for p in products if p['date'] >= date_from]
    if date_to:
        products = [p for p in products if p['date'] <= date_to]

    by_date = defaultdict(lambda: {'rating_sum': 0, 'rating_count': 0, 'reviews_sum': 0})
    for p in products:
        d = p['date']
        by_date[d]['rating_sum'] += p['rating']
        by_date[d]['rating_count'] += 1
        by_date[d]['reviews_sum'] += p['reviews']

    trends = []
    for d in sorted(by_date.keys()):
        v = by_date[d]
        avg_rating = round(v['rating_sum'] / v['rating_count'], 2) if v['rating_count'] > 0 else 0
        trends.append({
            'date': d,
            'avg_rating': avg_rating,
            'avg_reviews': round(v['reviews_sum'] / v['rating_count'], 1) if v['rating_count'] > 0 else 0,
            'product_count': v['rating_count'],
        })

    return {'trends': trends, 'store': store}


@app.get("/api/trends/store")
def api_store_trends(
    store: str = Query(None),
    date_from: str = Query(None),
    date_to: str = Query(None),
):
    """店铺近90天评分趋势"""
    data = load_all_data()
    ratings = data['storeRatings']

    if store:
        ratings = [r for r in ratings if r['store'] == store]
    if date_from:
        ratings = [r for r in ratings if r['date'] >= date_from]
    if date_to:
        ratings = [r for r in ratings if r['date'] <= date_to]

    by_date_store = defaultdict(lambda: defaultdict(list))
    for r in ratings:
        by_date_store[r['date']][r['store']].append(r['rating'])

    store_names = sorted(set(r['store'] for r in ratings))

    trends = {}
    for sn in store_names:
        series = []
        for d in sorted(by_date_store.keys()):
            vals = by_date_store[d].get(sn, [])
            if vals:
                series.append({'date': d, 'rating': round(sum(vals) / len(vals), 2)})
        trends[sn] = series

    return {'trends': trends, 'stores': store_names}


@app.get("/api/trends/store-products")
def api_store_product_trends(
    store: str = Query(None),
    date_from: str = Query(None),
    date_to: str = Query(None),
):
    """多店铺商品评分+评价数趋势（逗号分隔或单个）"""
    data = load_all_data()
    products = data['products']

    stores = [s.strip() for s in store.split(',') if s.strip()] if store else []

    if stores:
        products = [p for p in products if p['store'] in stores]
    if date_from:
        products = [p for p in products if p['date'] >= date_from]
    if date_to:
        products = [p for p in products if p['date'] <= date_to]

    # 按店铺→日期聚合
    by_store_date = defaultdict(lambda: defaultdict(lambda: {'rating_sum': 0, 'rating_cnt': 0, 'reviews_sum': 0}))
    for p in products:
        d = p['date']
        s = p['store']
        by_store_date[s][d]['rating_sum'] += p['rating']
        by_store_date[s][d]['rating_cnt'] += 1
        by_store_date[s][d]['reviews_sum'] += p['reviews']

    ratings = {}
    reviews = {}
    for s, date_map in by_store_date.items():
        r_series, v_series = [], []
        for d in sorted(date_map.keys()):
            v = date_map[d]
            r_series.append({'date': d, 'value': round(v['rating_sum'] / v['rating_cnt'], 2)})
            v_series.append({'date': d, 'value': v['reviews_sum']})
        ratings[s] = r_series
        reviews[s] = v_series

    return {'ratings': ratings, 'reviews': reviews, 'stores': stores}


@app.get("/api/low-rating")
def api_low_rating(threshold: float = Query(40.0)):
    """低于阈值的店铺预警"""
    data = load_all_data()
    ratings = data['storeRatings']

    # 取每个店铺最新日期
    if not data['dates']:
        return {'stores': [], 'threshold': threshold}

    latest_date = data['dates'][-1]
    latest = [r for r in ratings if r['date'] == latest_date and r['rating'] < threshold]
    latest.sort(key=lambda r: r['rating'])

    return {
        'threshold': threshold,
        'latest_date': latest_date,
        'stores': latest,
    }


@app.get("/api/dsr")
def api_dsr(
    store: str = Query(None),
    date_from: str = Query(None),
    date_to: str = Query(None),
):
    """DSR 数据"""
    data = load_all_data()
    dsr = data['dsrData']

    if store:
        dsr = [d for d in dsr if d.get('店铺名称', '') == store]
    if date_from:
        dsr = [d for d in dsr if str(d.get('日期', '')) >= date_from]
    if date_to:
        dsr = [d for d in dsr if str(d.get('日期', '')) <= date_to]

    return {'dsr_data': dsr, 'total': len(dsr)}


@app.get("/api/dsr/averages")
def api_dsr_averages(
    brand: str = Query(None),
    date: str = Query(None),
):
    """DSR KPI 卡片：6 个维度的全店铺加权均值"""
    data = load_all_data()
    dsr = data['dsrData']
    if not dsr:
        return {'data': [], 'metrics': []}

    # 品牌过滤
    if brand:
        brand_stores = set(data['brandStores'].get(brand, []))
        dsr = [d for d in dsr if d.get('店铺名称', '') in brand_stores]
    # 日期过滤
    if date:
        dsr = [d for d in dsr if str(d.get('日期', '')) == date]

    # 6 个维度
    metrics = ['消费者服务体验分', '服务态度体验分', '基础服务体验分', '商品服务体验分', '发货服务体验分', '物流服务体验分']

    def parse_score(val):
        if val is None:
            return None
        try:
            return float(str(val).replace('分', '').replace('%', '').strip())
        except:
            return None

    # 按日期分组求均值
    by_date = defaultdict(lambda: {m: [] for m in metrics})
    for d in dsr:
        dt = str(d.get('日期', ''))
        for m in metrics:
            v = parse_score(d.get(m))
            if v is not None:
                by_date[dt][m].append(v)

    result = []
    for dt in sorted(by_date.keys()):
        row = {'date': dt}
        for m in metrics:
            vals = by_date[dt][m]
            row[m] = round(sum(vals) / len(vals), 2) if vals else 0
        result.append(row)

    return {'data': result, 'metrics': metrics}


@app.get("/api/home/rating-overview")
def api_home_rating_overview(
    date_from: str = Query(None),
    date_to: str = Query(None),
    brand: str = Query(None),
):
    """首页：近90天评分总览（加权平均，权重=各店铺当日商品数）"""
    data = load_all_data()
    ratings = data['storeRatings']
    products = data['products']

    if brand:
        brand_stores = set(data['brandStores'].get(brand, []))
        ratings = [r for r in ratings if r['store'] in brand_stores]
        products = [p for p in products if p['store'] in brand_stores]
    if date_from:
        ratings = [r for r in ratings if r['date'] >= date_from]
        products = [p for p in products if p['date'] >= date_from]
    if date_to:
        ratings = [r for r in ratings if r['date'] <= date_to]
        products = [p for p in products if p['date'] <= date_to]

    store_weight = defaultdict(lambda: defaultdict(int))
    for p in products:
        store_weight[p['date']][p['store']] += 1

    by_date = defaultdict(lambda: {'wsum': 0.0, 'weight': 0, 'stores': set()})
    for r in ratings:
        d = r['date']
        w = max(store_weight[d].get(r['store'], 1), 1)
        by_date[d]['wsum'] += r['rating'] * w
        by_date[d]['weight'] += w
        by_date[d]['stores'].add(r['store'])

    result = []
    for d in sorted(by_date.keys()):
        v = by_date[d]
        wavg = round(v['wsum'] / v['weight'], 2) if v['weight'] > 0 else 0
        result.append({'date': d, 'weighted_avg': wavg, 'store_count': len(v['stores'])})
    return {'data': result}


@app.get("/api/home/product-overview")
def api_home_product_overview(
    date_from: str = Query(None),
    date_to: str = Query(None),
    brand: str = Query(None),
):
    """首页：商品评分与评价数趋势（加权平均，权重=评价数）"""
    data = load_all_data()
    products = data['products']

    if brand:
        brand_stores = set(data['brandStores'].get(brand, []))
        products = [p for p in products if p['store'] in brand_stores]
    if date_from:
        products = [p for p in products if p['date'] >= date_from]
    if date_to:
        products = [p for p in products if p['date'] <= date_to]

    by_date = defaultdict(lambda: {'r_wsum': 0.0, 'v_wsum': 0.0, 'weight': 0, 'count': 0})
    for p in products:
        d = p['date']
        w = max(p['reviews'], 1)
        by_date[d]['r_wsum'] += p['rating'] * w
        by_date[d]['v_wsum'] += p['reviews'] * w
        by_date[d]['weight'] += w
        by_date[d]['count'] += 1

    result = []
    for d in sorted(by_date.keys()):
        v = by_date[d]
        wavg_r = round(v['r_wsum'] / v['weight'], 2) if v['weight'] > 0 else 0
        wavg_v = round(v['v_wsum'] / v['weight'], 2) if v['weight'] > 0 else 0
        result.append({'date': d, 'weighted_avg_rating': wavg_r, 'weighted_avg_reviews': wavg_v, 'product_count': v['count']})
    return {'data': result}


if __name__ == '__main__':
    import uvicorn
    print("Starting 拼多多评分看板 API on http://127.0.0.1:8768")
    uvicorn.run(app, host="0.0.0.0", port=8768)
