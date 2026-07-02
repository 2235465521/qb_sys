from django.test import TestCase
import datetime
from standards.tasks import extract_dates_from_text

class DateExtractionTestCase(TestCase):
    def test_normal_date_extraction(self):
        """测试正常没有水印干扰的标准封面文本日期提取"""
        text = (
            "Q/CSGD 003-2018\n"
            "陈氏古典牛膝皮肤抑菌液\n"
            "2018-06-18 发布\n"
            "2018-06-20 实施"
        )
        pub_date, impl_date = extract_dates_from_text(text)
        self.assertEqual(pub_date, datetime.date(2018, 6, 18))
        self.assertEqual(impl_date, datetime.date(2018, 6, 20))

    def test_watermark_date_exclusion(self):
        """测试带有平台水印干扰时，能够排除水印日期，正确提取真实日期"""
        text = (
            "Q/CSGD 003-2018\n"
            "企业标准信息公共服务平台\n"
            "公开 2018年07月16日 09点39分\n"
            "陈氏古典牛膝皮肤抑菌液\n"
            "企业标准信息公共服务平台\n"
            "公开 2018年07月16日 09点39分\n"
            "2018-06-18 发布\n"
            "2018-06-20 实施"
        )
        pub_date, impl_date = extract_dates_from_text(text)
        self.assertEqual(pub_date, datetime.date(2018, 6, 18))
        self.assertEqual(impl_date, datetime.date(2018, 6, 20))

    def test_ocr_character_corrections(self):
        """测试 OCR 常见字符误识别修复后的日期提取"""
        # 测试 O -> 0, l -> 1
        text = (
            "2O18-O6-18 发布\n"
            "2018-06-2O 实施"
        )
        pub_date, impl_date = extract_dates_from_text(text)
        self.assertEqual(pub_date, datetime.date(2018, 6, 18))
        self.assertEqual(impl_date, datetime.date(2018, 6, 20))

        text_l = (
            "2018-06-1l 发布\n"
            "2018-06-20 实施"
        )
        pub_date, impl_date = extract_dates_from_text(text_l)
        self.assertEqual(pub_date, datetime.date(2018, 6, 11))
        self.assertEqual(impl_date, datetime.date(2018, 6, 20))

