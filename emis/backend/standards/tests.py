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

    def test_watermark_without_timestamp_and_separated_lines(self):
        """测试水印没有时间戳或被分成多行时的正确提取"""
        text = (
            "Q/PMS 001-2024\n"
            "企业标准信息公共服务平台\n"
            "公开 2024年06月07日 16点37分\n"
            "住宿业pms和入住机自助入住设备技术要求\n"
            "公开 2024年06月07日\n"
            "2024-04-20发布        2024-04-20实施\n"
            "青岛易修物联科技有限公司发布"
        )
        pub_date, impl_date = extract_dates_from_text(text)
        self.assertEqual(pub_date, datetime.date(2024, 4, 20))
        self.assertEqual(impl_date, datetime.date(2024, 4, 20))

    def test_watermark_ocr_misrecognition(self):
        """测试水印公开被误识别为公布时的排除能力"""
        text = (
            "公布 2024年06月07日 16点37分\n"
            "2024-04-20发布        2024-04-20实施"
        )
        pub_date, impl_date = extract_dates_from_text(text)
        self.assertEqual(pub_date, datetime.date(2024, 4, 20))
        self.assertEqual(impl_date, datetime.date(2024, 4, 20))

    def test_only_publish_date_fallback_implement_date(self):
        """测试仅有发布日期没有实施日期时，实施日期自动对齐为发布日期"""
        text = (
            "Q/PMS 001-2024\n"
            "住宿业pms和入住机自助入住设备技术要求\n"
            "2024-04-20发布"
        )
        pub_date, impl_date = extract_dates_from_text(text)
        self.assertEqual(pub_date, datetime.date(2024, 4, 20))
        self.assertEqual(impl_date, datetime.date(2024, 4, 20))

    def test_implement_date_earlier_than_publish_date_correction(self):
        """测试实施日期早于发布日期异常时，修正实施日期为发布日期"""
        text = (
            "2024-04-20发布        2024-04-10实施"
        )
        pub_date, impl_date = extract_dates_from_text(text)
        self.assertEqual(pub_date, datetime.date(2024, 4, 20))
        self.assertEqual(impl_date, datetime.date(2024, 4, 20))



