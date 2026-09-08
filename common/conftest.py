import datetime
import os

import pytest
import pytest_html
from py.xml import html, raw


def pytest_configure(config):
    """自动为 pytest-html 报告添加时间戳，避免每次运行覆盖同一文件。"""
    htmlpath = config.option.htmlpath
    if htmlpath:
        now = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        reports_dir = os.path.join(project_root, "reports")
        os.makedirs(reports_dir, exist_ok=True)

        base_name = os.path.splitext(os.path.basename(htmlpath))[0]
        new_name = f"{base_name}_{now}.html"
        config.option.htmlpath = os.path.join(reports_dir, new_name)


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """把 device_info 附加到测试报告 extras。"""
    pytest_html = item.config.pluginmanager.getplugin("html")
    outcome = yield
    report = outcome.get_result()
    if report.when == "call" and pytest_html:
        instance = getattr(item, "instance", None)
        device_info = getattr(instance, "device_info", None)
        if device_info:
            content = "<br>".join(device_info)
            report.extras.append(pytest_html.extras.html(
                f"<b>CAN 设备信息（SN / device_index）</b><br>{content}"
            ))


def pytest_html_results_table_header(cells):
    """在 pytest-html 表格中添加一列。"""
    cells.insert(2, html.th("CAN 设备"))


def pytest_html_results_table_row(report, cells):
    """在每行中显示 device_info。"""
    device_html = ""
    for extra in getattr(report, "extras", []):
        if extra.get("format_type") == pytest_html.extras.FORMAT_HTML and "CAN 设备信息" in extra.get("content", ""):
            device_html = extra["content"]
            break
    cells.insert(2, html.td(raw(device_html) if device_html else "-"))


def pytest_sessionfinish(session, exitstatus):
    """测试结束后，从 allure-results 生成美观的 HTML 报告。"""
    allure_dir = session.config.option.allure_report_dir
    if allure_dir and os.path.isdir(allure_dir):
        from common.reports import Reports

        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        target_dir = os.path.join(project_root, "reports")
        report_path = Reports().generate_report_html(allure_dir, target_dir)
        print(f"\n[Allure-style HTML report] {report_path}")
