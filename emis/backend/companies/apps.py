from django.apps import AppConfig


class CompaniesConfig(AppConfig):
    name = 'companies'

    def ready(self):
        """
        Django 启动完成后立即触发省市区字典缓存预热。
        仅在实际 Web 服务器进程（Gunicorn / runserver）中执行，
        管理命令（migrate, shell 等）中跳过，避免在数据库未就绪时报错。
        """
        import os
        # RUN_MAIN=true 表示 runserver 的主工作进程
        # SERVER_GATEWAY_INTERFACE 由 Gunicorn/uWSGI 注入
        is_server = (
            os.environ.get('RUN_MAIN') == 'true'
            or os.environ.get('SERVER_GATEWAY_INTERFACE') is not None
            or os.environ.get('GUNICORN_WORKER') is not None
        )
        if not is_server:
            return

        try:
            from companies.warmup import warm_area_dict
            warm_area_dict()
        except Exception:
            # 预热失败不应阻断服务启动
            pass
