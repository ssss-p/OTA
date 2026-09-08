import datetime
import json
import os

from common.common import Constants


class Reports:
    def report_excel_load_result_json_files(self, result_dir):
        result_json_list = []
        for filename in os.listdir(result_dir):
            if filename.endswith("result.json"):
                abs_path = os.path.join(result_dir, filename)
                result_json_list.append([abs_path, os.stat(abs_path).st_ctime])

        result_json_list = sorted(result_json_list, key=lambda x: x[1])
        return result_json_list

    def report_excel_parse_result_json_files(self, result_json_list):
        result_list = []
        for item in result_json_list:
            with open(item[0], "r", encoding="utf-8") as f:
                one_case_result_data = json.load(f)

            steps = one_case_result_data.get("steps", [])
            steps_list = []
            for item in steps:
                steps_list.append([item["status"], item["name"]])

            parent_suite = ""
            suite = ""
            for item in one_case_result_data.get("labels", []):
                if item["name"] == "parentSuite":
                    parent_suite = item["value"]
                if item["name"] == "suite":
                    suite = item["value"]
            result_list.append({
                "casename": one_case_result_data.get("name", ""),
                "parent_suite": parent_suite,
                "suite": suite,
                "result": one_case_result_data.get("status", ""),
                "steps": steps_list
            })
        return result_list

    def generate_report_excel(self, report_dir_tmp, target_dir):
        from library.files.excel_driver import ExcelDriver

        result_json_list = self.report_excel_load_result_json_files(report_dir_tmp)
        result_list = self.report_excel_parse_result_json_files(result_json_list)

        now_time = datetime.datetime.now()
        default_excel = os.path.join(Constants.BASE_DIR, "tools", "default_template.xlsx")
        saved_excel = os.path.join(target_dir, f"{now_time.strftime('%Y_%m_%d_%H%M%S')}.xlsx")

        workbook = ExcelDriver.load_workbook(default_excel)
        worksheet_cover = ExcelDriver.load_worksheet(workbook, "Cover")
        ExcelDriver.set_cell_value(worksheet_cover, "E20", now_time.strftime("%Y年%m月%d日"), border=False)

        worksheet = ExcelDriver.load_worksheet(workbook, "Overview")
        worksheet_details = ExcelDriver.load_worksheet(workbook, "Details")

        ExcelDriver.set_cell_value(worksheet, "A1", "Test Report")
        ExcelDriver.set_cell_value(worksheet, "H1", now_time)

        detail_sheet_row = 1
        pass_cnt, fail_cnt, skip_cnt = 0, 0, 0
        start_row = 7
        begin = start_row
        for item in result_list:
            casename, parent_suite, suite, result, steps = item["casename"], item["parent_suite"], item["suite"], item[
                "result"], item["steps"]
            ExcelDriver.set_cell_value(worksheet, f"A{start_row}", parent_suite,
                                       merge_cells_str=f"A{start_row}:D{start_row}")

            # Test ID
            ExcelDriver.set_cell_value(worksheet, f"E{start_row}", suite, horizontal="left")

            # Test Case Name
            ExcelDriver.set_cell_value(worksheet, f"F{start_row}", casename, horizontal="left",
                                       merge_cells_str=f"F{start_row}:J{start_row}")
            if result == "passed":
                ExcelDriver.set_cell_value(worksheet, f"K{start_row}", "PASS", cellcolor="70ad47")
                pass_cnt += 1
            if result == "failed":
                ExcelDriver.set_cell_value(worksheet, f"K{start_row}", "FAIL", cellcolor="ff0000")
                fail_cnt += 1
            if result == "skipped":
                ExcelDriver.set_cell_value(worksheet, f"K{start_row}", "SKIP", cellcolor="a6a6a6")
                skip_cnt += 1
            start_row += 1

            # 添加Details详情页  -s
            ExcelDriver.set_cell_value(worksheet_details, f"A{detail_sheet_row}", casename, horizontal="left",
                                       column_width=24)
            detail_sheet_row += 1
            for step in steps:
                status, step_str = step[0], step[1]
                if status == "failed":
                    ExcelDriver.set_cell_value(worksheet_details, f"A{detail_sheet_row}", status, horizontal="left",
                                               row_height=14, cellcolor="FF0000")
                elif status == "passed":
                    ExcelDriver.set_cell_value(worksheet_details, f"A{detail_sheet_row}", status, horizontal="left",
                                               row_height=14, cellcolor="70ad47")
                else:
                    ExcelDriver.set_cell_value(worksheet_details, f"A{detail_sheet_row}", status, horizontal="left",
                                               row_height=14)
                ExcelDriver.set_cell_value(worksheet_details, f"B{detail_sheet_row}", step_str, horizontal="left",
                                           row_height=14, column_width=160)
                detail_sheet_row += 1
            # 添加Details详情页  -e

        # 测试统计数据
        ExcelDriver.set_cell_value(worksheet, "F3", pass_cnt + fail_cnt + skip_cnt, fontcolor="6eaae1")
        ExcelDriver.set_cell_value(worksheet, "I3", pass_cnt, fontcolor="70ad47")
        ExcelDriver.set_cell_value(worksheet, "I4", fail_cnt, fontcolor="ff0000")
        ExcelDriver.set_cell_value(worksheet, "I5", skip_cnt, fontcolor="a6a6a6")

        ExcelDriver.save(workbook, saved_excel)
        ExcelDriver.close(workbook)

    def generate_report_html(self, result_dir, target_dir):
        """从 allure result.json 生成美观的 HTML 报告。"""
        result_json_list = self.report_excel_load_result_json_files(result_dir)
        result_list = self.report_excel_parse_result_json_files(result_json_list)

        pass_cnt = sum(1 for item in result_list if item["result"] == "passed")
        fail_cnt = sum(1 for item in result_list if item["result"] == "failed")
        skip_cnt = sum(1 for item in result_list if item["result"] == "skipped")
        total_cnt = len(result_list)

        now_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        rows = []
        for idx, item in enumerate(result_list, 1):
            status = item["result"]
            status_class = "status-pass" if status == "passed" else "status-fail" if status == "failed" else "status-skip"
            status_text = status.upper()

            steps_html = ""
            for step_status, step_name in item["steps"]:
                step_class = "status-pass" if step_status == "passed" else "status-fail" if step_status == "failed" else "status-skip"
                steps_html += f'<div class="step"><span class="step-badge {step_class}">{step_status.upper()}</span>{step_name}</div>'

            rows.append(f"""
                <tr>
                    <td>{idx}</td>
                    <td>{item['parent_suite']}</td>
                    <td>{item['suite']}</td>
                    <td>{item['casename']}</td>
                    <td><span class="badge {status_class}">{status_text}</span></td>
                    <td>
                        <details>
                            <summary>查看步骤 ({len(item['steps'])})</summary>
                            <div class="steps">{steps_html}</div>
                        </details>
                    </td>
                </tr>
            """)

        html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>测试报告</title>
    <style>
        * {{ box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; margin: 0; padding: 20px; background: #f5f7fa; color: #333; }}
        .container {{ max-width: 1400px; margin: 0 auto; }}
        h1 {{ margin-bottom: 10px; }}
        .subtitle {{ color: #888; margin-bottom: 30px; }}
        .summary {{ display: flex; gap: 20px; margin-bottom: 30px; }}
        .card {{ flex: 1; background: #fff; border-radius: 8px; padding: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); text-align: center; }}
        .card .number {{ font-size: 32px; font-weight: bold; margin-bottom: 5px; }}
        .card .label {{ color: #666; font-size: 14px; }}
        .card.total .number {{ color: #4a90e2; }}
        .card.pass .number {{ color: #70ad47; }}
        .card.fail .number {{ color: #e74c3c; }}
        .card.skip .number {{ color: #999; }}
        table {{ width: 100%; border-collapse: collapse; background: #fff; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.06); }}
        th, td {{ padding: 14px 16px; text-align: left; border-bottom: 1px solid #eee; }}
        th {{ background: #4a90e2; color: #fff; font-weight: 500; }}
        tr:hover {{ background: #f9fafb; }}
        .badge {{ display: inline-block; padding: 4px 10px; border-radius: 12px; font-size: 12px; font-weight: bold; color: #fff; }}
        .status-pass {{ background: #70ad47; }}
        .status-fail {{ background: #e74c3c; }}
        .status-skip {{ background: #999; }}
        details {{ cursor: pointer; }}
        summary {{ color: #4a90e2; outline: none; }}
        .steps {{ margin-top: 10px; padding-left: 10px; }}
        .step {{ padding: 6px 0; border-bottom: 1px dashed #eee; }}
        .step:last-child {{ border-bottom: none; }}
        .step-badge {{ display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 11px; color: #fff; margin-right: 10px; min-width: 48px; text-align: center; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>测试报告</h1>
        <div class="subtitle">生成时间：{now_time}</div>

        <div class="summary">
            <div class="card total"><div class="number">{total_cnt}</div><div class="label">总用例</div></div>
            <div class="card pass"><div class="number">{pass_cnt}</div><div class="label">通过</div></div>
            <div class="card fail"><div class="number">{fail_cnt}</div><div class="label">失败</div></div>
            <div class="card skip"><div class="number">{skip_cnt}</div><div class="label">跳过</div></div>
        </div>

        <table>
            <thead>
                <tr>
                    <th>序号</th>
                    <th>父套件</th>
                    <th>套件</th>
                    <th>用例名称</th>
                    <th>结果</th>
                    <th>步骤详情</th>
                </tr>
            </thead>
            <tbody>
                {''.join(rows)}
            </tbody>
        </table>
    </div>
</body>
</html>"""

        os.makedirs(target_dir, exist_ok=True)
        now = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = os.path.join(target_dir, f"allure_report_{now}.html")
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(html)
        return report_path