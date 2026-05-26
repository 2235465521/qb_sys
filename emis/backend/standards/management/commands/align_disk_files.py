import os
from django.core.management.base import BaseCommand
from django.conf import settings
from standards.models import Standard

class Command(BaseCommand):
    help = "扫描Y盘磁盘阵列并与数据库clean_id对齐"

    def handle(self, *args, **options):
        # 1. 获取settings中配置的根目录
        root_path = getattr(settings, 'SHARED_DISK_ROOT', r"Y:\磁盘阵列\标准文件下载\企标下载")
        target_dir = os.path.join(root_path, "整合")
        
        if not os.path.exists(target_dir):
            self.stdout.write(self.style.ERROR(f"找不到目标磁盘阵列路径: {target_dir}"))
            return

        self.stdout.write(self.style.SUCCESS(f"正在扫描路径: {target_dir} ..."))
        
        # 2. 读取磁盘上所有的 PDF 文件
        try:
            disk_files = [f for f in os.listdir(target_dir) if f.lower().endswith('.pdf')]
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"读取目录失败: {e}"))
            return
            
        self.stdout.write(self.style.WARNING(f"磁盘共发现 {len(disk_files)} 个PDF文件"))

        # 辅助归一化函数：移除所有非字母数字字符，统一转小写
        def normalize(s):
            return "".join(c for c in s if c.isalnum()).lower() if s else ""

        # 3. 构建归一化磁盘文件名与原始文件名的列表
        file_norms = [(f, normalize(f)) for f in disk_files]

        # 4. 从数据库查出所有待对齐的记录
        standards = Standard.objects.all()
        success_count = 0

        # 5. 循环比对更新
        for std in standards:
            if not std.clean_id:
                continue
            
            clean_norm = normalize(std.clean_id)
            if not clean_norm:
                continue
            
            # 在磁盘文件中寻找以前缀匹配的归一化名称
            matched_file = None
            for filename, fnorm in file_norms:
                if fnorm.startswith(clean_norm):
                    matched_file = filename
                    break
            
            if matched_file:
                relative_path = f"整合/{matched_file}"
                if std.disk_filename != relative_path:
                    std.disk_filename = relative_path
                    std.save(update_fields=['disk_filename'])
                success_count += 1
                
        self.stdout.write(self.style.SUCCESS(f"对齐完成！成功匹配并更新了 {success_count} 条标准数据。"))