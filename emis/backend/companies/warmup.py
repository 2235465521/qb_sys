"""
companies/warmup.py — 省市区字典缓存预热
系统启动时由 AppConfig.ready() 调用，将全量省市区数据写入 Redis/文件缓存，
供批量导入任务和行政区划筛选直接读缓存，不再每次查库。
"""

CACHE_KEY_PROVINCES = 'dict:provinces'
CACHE_KEY_CITIES    = 'dict:cities'
CACHE_KEY_DISTRICTS = 'dict:districts'
CACHE_TTL = 86400  # 24 小时


def warm_area_dict():
    """
    预热全量省市区字典到缓存（Redis 或文件缓存均支持）。
    数据结构：
      'dict:provinces' → [{id, name, latitude, longitude}, ...]
      'dict:cities'    → [{id, name, province_id, latitude, longitude}, ...]
      'dict:districts' → [{id, name, city_id, latitude, longitude}, ...]
    """
    try:
        from django.core.cache import cache
        from companies.models import Province, City, District

        provinces = list(Province.objects.values('id', 'name', 'latitude', 'longitude'))
        cities    = list(City.objects.values('id', 'name', 'province_id', 'latitude', 'longitude'))
        districts = list(District.objects.values('id', 'name', 'city_id', 'latitude', 'longitude'))

        cache.set(CACHE_KEY_PROVINCES, provinces, timeout=CACHE_TTL)
        cache.set(CACHE_KEY_CITIES,    cities,    timeout=CACHE_TTL)
        cache.set(CACHE_KEY_DISTRICTS, districts, timeout=CACHE_TTL)

        import logging
        logger = logging.getLogger('companies.warmup')
        logger.info(
            f'[warmup] 省市区字典预热完成：省 {len(provinces)} 条，市 {len(cities)} 条，区 {len(districts)} 条'
        )
    except Exception as e:
        import logging
        logging.getLogger('companies.warmup').warning(f'[warmup] 省市区预热失败（非致命）: {e}')


def get_area_data_from_cache():
    """
    从缓存读取省市区数据。缓存 miss 时回退查库并重新写入缓存（自愈机制）。
    返回 (provinces, cities, districts)，均为 list[dict]
    """
    from django.core.cache import cache

    provinces = cache.get(CACHE_KEY_PROVINCES)
    cities    = cache.get(CACHE_KEY_CITIES)
    districts = cache.get(CACHE_KEY_DISTRICTS)

    if provinces is None or cities is None or districts is None:
        # 缓存 miss（系统刚重启、缓存过期等情况），重新预热
        warm_area_dict()
        provinces = cache.get(CACHE_KEY_PROVINCES) or []
        cities    = cache.get(CACHE_KEY_CITIES)    or []
        districts = cache.get(CACHE_KEY_DISTRICTS) or []

    return provinces, cities, districts
