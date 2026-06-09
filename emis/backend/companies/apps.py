from django.apps import AppConfig


class CompaniesConfig(AppConfig):
    name = 'companies'

    def ready(self):
        """
        Django 启动完成后触发省市区字典缓存预热。
        使用延迟线程执行，避免在 AppConfig.ready() 阶段直接查询数据库
        触发 Django 6.x 的 RuntimeWarning。
        """
        import os
        is_server = (
            os.environ.get('SERVER_GATEWAY_INTERFACE') is not None
            or os.environ.get('RUN_MAIN') == 'true'
        )
        if not is_server:
            return

        import threading

        def _delayed_warmup():
            try:
                from companies.warmup import warm_area_dict
                warm_area_dict()
            except Exception:
                pass

        # 延迟 3 秒执行，确保 Django 完全初始化、数据库连接就绪后再查询
        t = threading.Timer(3.0, _delayed_warmup)
        t.daemon = True  # 主进程退出时自动销毁
        t.start()
