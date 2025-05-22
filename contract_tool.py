import sys
import os
import json
from datetime import datetime
from PySide6.QtWidgets import (QApplication, QMainWindow, QTabWidget, QWidget, QVBoxLayout,
                               QHBoxLayout, QTextEdit, QPushButton, QLabel, QFileDialog,
                               QProgressBar, QMessageBox, QSplitter, QListWidget, QGroupBox,
                               QFormLayout, QLineEdit, QSpinBox, QTextBrowser, QDoubleSpinBox,
                               )
from PySide6.QtCore import Qt, QThread, Signal, QSettings
from PySide6.QtGui import QIcon, QFont, QPixmap
import requests
from markdown import markdown
from pdfplumber import open as pdfplumber_open
from docx import Document

# 配置API信息
class APIConfig:
    def __init__(self):
        self.api_base_url = "https://api.deepseek.com/v1"
        self.api_key = ""
        self.model_name = "deepseek-chat"
        self.temperature = 0.2
        self.max_tokens = 8000


# 智能体基类
class Agent:
    def __init__(self, api_config):
        self.api_config = api_config
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_config.api_key}"
        }

    def call_api(self, prompt, system_prompt=""):
        try:
            data = {
                "model": self.api_config.model_name,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                "temperature": self.api_config.temperature,
                "max_tokens": self.api_config.max_tokens
            }

            response = requests.post(
                f"{self.api_config.api_base_url}/chat/completions",
                headers=self.headers,
                data=json.dumps(data)
            )

            if response.status_code == 200:
                return response.json()["choices"][0]["message"]["content"]
            else:
                error_msg = f"API调用失败: HTTP {response.status_code}, {response.text}"
                return error_msg

        except Exception as e:
            return f"API调用异常: {str(e)}"


# 合同条款提取智能体
class ClauseExtractionAgent(Agent):
    def analyze(self, contract_text):
        system_prompt = """
        你是一个专业的合同条款分析专家。你的任务是从合同文本中提取关键条款信息。
        请识别并提取以下类型的条款：
        1. 合同双方信息
        2. 合同标的
        3. 价格与支付条款
        4. 交付条款
        5. 违约责任
        6. 争议解决方式
        7. 保密条款
        8. 合同有效期
        9. 终止条款

        请以JSON格式返回结果，包含条款类型和对应的条款内容。
        如果某个条款类型在合同中未找到，请在JSON中包含该条款类型并将其值设为"未找到"。
        """

        prompt = f"请分析以下合同文本并提取关键条款信息：\n\n{contract_text}"

        response = self.call_api(prompt, system_prompt)

        # 尝试解析JSON结果
        try:
            response = response.strip().replace('```json', '').replace('```', '')
            clause_data = json.loads(response)
            return clause_data
        except:
            # 如果无法解析为JSON，返回原始文本
            return {
                "解析错误": f"无法将响应解析为JSON格式。原始响应: {response}"
            }


# 风险量化分析智能体
class RiskAnalysisAgent(Agent):
    def analyze(self, clause_data):
        system_prompt = """
        你是一位经验丰富的合同风险评估专家。基于提取的合同关键条款信息，
        请对合同进行风险量化分析。评估每个条款的风险等级（低、中、高），
        计算总体风险得分（0-100分），并提供详细的风险分析报告。

        请以JSON格式返回结果，包含以下内容：
        1. 各条款风险评估（风险等级和理由）
        2. 总体风险得分
        3. 主要风险点摘要
        4. 风险等级（基于总体得分：0-30低风险，31-60中等风险，61-100高风险）
        """

        clause_json = json.dumps(clause_data, ensure_ascii=False, indent=2)
        prompt = f"请对以下合同条款进行风险量化分析：\n\n{clause_json}"

        response = self.call_api(prompt, system_prompt)

        try:
            response = response.strip().replace('```json', '').replace('```', '')
            risk_data = json.loads(response)
            return risk_data
        except:
            return {
                "解析错误": f"无法将响应解析为JSON格式。原始响应: {response}"
            }


# 合规性分析智能体
class ComplianceAnalysisAgent(Agent):
    def analyze(self, clause_data, compliance_rules=None):
        if compliance_rules is None:
            compliance_rules = """
            1. 合同必须明确双方当事人的名称、地址和联系方式。
            2. 合同标的必须明确、具体，具有可操作性。
            3. 价格条款必须明确金额、支付方式和支付时间。
            4. 交付条款必须明确交付时间、地点和方式。
            5. 违约责任条款必须明确双方的责任和赔偿方式。
            6. 争议解决条款必须符合法律规定，明确解决方式。
            7. 保密条款必须明确保密信息范围和保密期限。
            8. 合同有效期必须明确起始和终止日期。
            9. 终止条款必须明确终止条件和程序。
            """

        system_prompt = f"""
        你是一位资深的合同合规性审查专家。请根据以下合规性规则，
        对提供的合同条款进行合规性分析：

        {compliance_rules}

        请以JSON格式返回结果，包含：
        1. 各条款合规性评估（合规、不合规、部分合规）
        2. 不合规条款的详细说明和建议
        3. 总体合规性评级（合规、基本合规、不合规）
        4. 合规性得分（0-100分）
        """

        clause_json = json.dumps(clause_data, ensure_ascii=False, indent=2)
        prompt = f"请对以下合同条款进行合规性分析：\n\n{clause_json}"

        response = self.call_api(prompt, system_prompt)

        try:
            response = response.strip().replace('```json', '').replace('```', '')
            compliance_data = json.loads(response)
            return compliance_data
        except:
            return {
                "解析错误": f"无法将响应解析为JSON格式。原始响应: {response}"
            }


# 报告生成智能体
class ReportGenerationAgent(Agent):
    def generate(self, clause_data, risk_data, compliance_data):
        system_prompt = """
        你是一位专业的合同审查报告撰写专家。请根据提供的合同条款信息、
        风险分析数据和合规性分析数据，生成一份全面的合同审查报告。

        报告应包括以下部分：
        1. 报告概述（包括合同基本信息和审查日期）
        2. 关键条款摘要
        3. 风险评估结果
        4. 合规性分析结果
        5. 综合评估与建议
        6. 整改建议清单

        请以清晰、专业的语言撰写报告，确保内容准确、有逻辑性且易于理解。
        """

        combined_data = {
            "条款信息": clause_data,
            "风险分析": risk_data,
            "合规性分析": compliance_data
        }

        combined_json = json.dumps(combined_data, ensure_ascii=False, indent=2)
        prompt = f"请根据以下数据生成合同审查报告：\n\n{combined_json}"

        return self.call_api(prompt, system_prompt)


# 准确性检查智能体
class AccuracyCheckAgent(Agent):
    def check(self, original_contract, generated_report):
        system_prompt = """
        你是一位严谨的合同审查质量保证专家。请检查生成的合同审查报告
        是否准确反映了原始合同的内容。重点检查以下方面：

        1. 关键条款提取的准确性
        2. 风险评估的合理性
        3. 合规性分析的准确性
        4. 报告中是否存在事实性错误
        5. 建议的相关性和可行性

        请提供一份准确性检查报告，指出任何不准确或需要改进的地方，
        并给出改进建议。
        """

        prompt = f"""
        原始合同文本：
        {original_contract}

        生成的审查报告：
        {generated_report}

        请对上述审查报告进行准确性检查。
        """

        return self.call_api(prompt, system_prompt)


# 合同处理工作线程
class ContractProcessingThread(QThread):
    progress_updated = Signal(int, str)
    processing_complete = Signal(object)
    processing_error = Signal(str)

    def __init__(self, api_config, contract_text):
        super().__init__()
        self.api_config = api_config
        self.contract_text = contract_text
        self.results = {}

    def run(self):
        try:
            # 初始化智能体
            self.progress_updated.emit(10, "初始化智能体...")

            clause_agent = ClauseExtractionAgent(self.api_config)
            risk_agent = RiskAnalysisAgent(self.api_config)
            compliance_agent = ComplianceAnalysisAgent(self.api_config)
            report_agent = ReportGenerationAgent(self.api_config)
            accuracy_agent = AccuracyCheckAgent(self.api_config)

            # 1. 条款提取
            self.progress_updated.emit(20, "正在提取合同关键条款...")
            clause_data = clause_agent.analyze(self.contract_text)
            self.results["条款提取"] = clause_data
            self.progress_updated.emit(35, "合同关键条款提取完成")

            # 2. 风险分析
            self.progress_updated.emit(40, "正在进行风险量化分析...")
            risk_data = risk_agent.analyze(clause_data)
            self.results["风险分析"] = risk_data
            self.progress_updated.emit(55, "风险量化分析完成")

            # 3. 合规性分析
            self.progress_updated.emit(60, "正在进行合规性分析...")
            compliance_data = compliance_agent.analyze(clause_data)
            self.results["合规性分析"] = compliance_data
            self.progress_updated.emit(75, "合规性分析完成")

            # 4. 报告生成
            self.progress_updated.emit(80, "正在生成审查报告...")
            report = report_agent.generate(clause_data, risk_data, compliance_data)
            self.results["审查报告"] = report
            self.progress_updated.emit(90, "审查报告生成完成")

            # 5. 准确性检查
            self.progress_updated.emit(91, "正在检查报告准确性...")
            accuracy_check = accuracy_agent.check(self.contract_text, report)
            self.results["准确性检查"] = accuracy_check
            self.progress_updated.emit(100, "报告准确性检查完成")

            self.processing_complete.emit(self.results)

        except Exception as e:
            self.processing_error.emit(f"处理过程中发生错误: {str(e)}")


# 合同审核应用主窗口
class ContractReviewApp(QMainWindow):
    def __init__(self):
        super().__init__()

        self.api_config = APIConfig()
        self.contract_text = ""
        self.processing_thread = None
        self.process_button = None  # 新增：保存处理按钮的引用
        self.setWindowIcon(QIcon('logo.png'))
        self.init_ui()
        self.load_settings()

    def init_ui(self):
        self.setWindowTitle("番石榴企业合同审核系统")
        self.setGeometry(100, 100, 1200, 800)

        # 创建中央部件和布局
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # 在界面最上方显示软件logo以及文字
        logo_layout = QHBoxLayout()
        # 请将 'logo.png' 替换为实际的logo图片文件名
        logo = QPixmap('logo.png').scaled(50, 50, Qt.KeepAspectRatio)
        logo_label = QLabel()
        logo_label.setPixmap(logo)
        logo_layout.addWidget(logo_label, alignment=Qt.AlignLeft)  # 将Logo添加到最左侧

        title_label = QLabel("番石榴企业合同审核系统")
        title_font = QFont()
        title_font.setPointSize(20)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignCenter)  # 标题居中显示
        logo_layout.addWidget(title_label, stretch=1)  # 让标题占据剩余空间

        main_layout.addLayout(logo_layout)

        # 创建顶部菜单
        self.create_menu_bar()

        # 创建标签页
        self.tabs = QTabWidget()

        # 合同上传标签页
        self.upload_tab = QWidget()
        self.init_upload_tab()
        self.tabs.addTab(self.upload_tab, "合同上传")

        # 条款提取标签页
        self.clause_tab = QWidget()
        self.init_clause_tab()
        self.tabs.addTab(self.clause_tab, "条款提取")

        # 风险分析标签页
        self.risk_tab = QWidget()
        self.init_risk_tab()
        self.tabs.addTab(self.risk_tab, "风险分析")

        # 合规性分析标签页
        self.compliance_tab = QWidget()
        self.init_compliance_tab()
        self.tabs.addTab(self.compliance_tab, "合规性分析")

        # 审查报告标签页
        self.report_tab = QWidget()
        self.init_report_tab()
        self.tabs.addTab(self.report_tab, "审查报告")

        # 准确性检查标签页
        self.accuracy_tab = QWidget()
        self.init_accuracy_tab()
        self.tabs.addTab(self.accuracy_tab, "准确性检查")

        # 添加标签页到主布局
        main_layout.addWidget(self.tabs)

        # 状态栏
        self.statusBar().showMessage("就绪")

    def create_menu_bar(self):
        menubar = self.menuBar()

        # 文件菜单
        file_menu = menubar.addMenu("文件")

        # 打开合同动作
        open_action = file_menu.addAction("打开合同")
        open_action.triggered.connect(lambda checked: self.browse_file())

        # 保存报告动作
        save_action = file_menu.addAction("保存报告")
        save_action.triggered.connect(self.save_report)
        save_action.setEnabled(False)
        self.save_action = save_action

        # 退出动作
        exit_action = file_menu.addAction("退出")
        exit_action.triggered.connect(self.close)

        # 设置菜单
        settings_menu = menubar.addMenu("设置")

        # API设置动作
        api_action = settings_menu.addAction("API设置")
        api_action.triggered.connect(self.show_api_settings)

        # 关于菜单
        about_menu = menubar.addMenu("关于")
        usage_agreement_action = about_menu.addAction("使用协议")
        usage_agreement_action.triggered.connect(self.show_usage_agreement)

        # 帮助菜单
        help_menu = menubar.addMenu("帮助")
        usage_info_action = help_menu.addAction("使用信息")
        usage_info_action.triggered.connect(self.show_usage_info)

    def init_upload_tab(self):
        layout = QVBoxLayout(self.upload_tab)

        # 文件选择区域
        file_group = QGroupBox("合同文件")
        file_layout = QVBoxLayout(file_group)

        file_info_layout = QHBoxLayout()
        self.file_path_label = QLabel("未选择文件")
        file_info_layout.addWidget(self.file_path_label)

        browse_button = QPushButton("浏览...")
        browse_button.clicked.connect(self.browse_file)
        file_info_layout.addWidget(browse_button)

        file_layout.addLayout(file_info_layout)

        # 合同文本区域
        text_group = QGroupBox("合同文本")
        text_layout = QVBoxLayout(text_group)

        self.contract_text_edit = QTextEdit()
        self.contract_text_edit.setReadOnly(True)
        text_layout.addWidget(self.contract_text_edit)

        # 处理按钮
        self.process_button = QPushButton("开始审核")  # 新增：保存处理按钮的引用
        self.process_button.setIcon(QIcon.fromTheme("system-run"))
        self.process_button.clicked.connect(self.process_contract)

        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)

        # 添加所有组件到主布局
        layout.addWidget(file_group)
        layout.addWidget(text_group)
        layout.addWidget(self.process_button)
        layout.addWidget(self.progress_bar)

    def init_clause_tab(self):
        layout = QVBoxLayout(self.clause_tab)

        # 创建分割器
        splitter = QSplitter(Qt.Horizontal)

        # 左侧条款列表
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)

        clause_label = QLabel("条款类型")
        left_layout.addWidget(clause_label)

        self.clause_list = QListWidget()
        self.clause_list.itemClicked.connect(self.show_clause_content)
        left_layout.addWidget(self.clause_list)

        splitter.addWidget(left_widget)

        # 右侧条款内容
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)

        content_label = QLabel("条款内容")
        right_layout.addWidget(content_label)

        self.clause_content = QTextEdit()
        self.clause_content.setReadOnly(True)
        right_layout.addWidget(self.clause_content)

        splitter.addWidget(right_widget)

        # 设置分割器比例
        splitter.setSizes([200, 600])

        layout.addWidget(splitter)

    def init_risk_tab(self):
        layout = QVBoxLayout(self.risk_tab)

        self.risk_text = QTextBrowser()
        layout.addWidget(self.risk_text)

    def init_compliance_tab(self):
        layout = QVBoxLayout(self.compliance_tab)

        self.compliance_text = QTextBrowser()
        layout.addWidget(self.compliance_text)

    def init_report_tab(self):
        layout = QVBoxLayout(self.report_tab)

        self.report_text = QTextBrowser()
        layout.addWidget(self.report_text)

    def init_accuracy_tab(self):
        layout = QVBoxLayout(self.accuracy_tab)

        self.accuracy_text = QTextBrowser()
        layout.addWidget(self.accuracy_text)

    def browse_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择合同文件", "", "文本文件 (*.txt);;Word文档 (*.docx);;PDF文件 (*.pdf)"
        )

        if file_path:
            self.file_path_label.setText(file_path)
            self.load_contract(file_path)

    def load_contract(self, file_path):
        try:
            file_ext = os.path.splitext(file_path)[1].lower()

            if file_ext == '.txt':
                with open(file_path, 'r', encoding='utf-8') as file:
                    self.contract_text = file.read()
            elif file_ext == '.docx':
                doc = Document(file_path)
                self.contract_text = "\n".join([para.text for para in doc.paragraphs])
            elif file_ext == '.pdf':
                with pdfplumber_open(file_path) as pdf:
                    pages = []
                    for page in pdf.pages:
                        pages.append(page.extract_text())
                    self.contract_text = "\n".join(pages)
            else:
                QMessageBox.warning(self, "文件类型错误", "不支持的文件类型")
                return

            self.contract_text_edit.setText(self.contract_text)
            self.statusBar().showMessage(f"已加载合同: {os.path.basename(file_path)}")

        except Exception as e:
            QMessageBox.critical(self, "错误", f"加载文件时出错: {str(e)}")
            self.statusBar().showMessage("加载文件失败")

    def show_api_settings(self):
        # 创建API设置对话框
        dialog = QWidget(self, Qt.Dialog)
        dialog.setWindowTitle("API设置")
        dialog.setGeometry(400, 300, 400, 300)

        layout = QVBoxLayout(dialog)

        form_layout = QFormLayout()

        # API密钥
        api_key_edit = QLineEdit()
        api_key_edit.setText(self.api_config.api_key)
        form_layout.addRow("API密钥:", api_key_edit)

        # API基础URL
        api_url_edit = QLineEdit()
        api_url_edit.setText(self.api_config.api_base_url)
        form_layout.addRow("API基础URL:", api_url_edit)

        # 模型名称
        model_edit = QLineEdit()
        model_edit.setText(self.api_config.model_name)
        form_layout.addRow("模型名称:", model_edit)

        # 温度
        temp_spin = QDoubleSpinBox()
        temp_spin.setRange(0.0, 1.0)
        temp_spin.setSingleStep(0.1)
        temp_spin.setValue(self.api_config.temperature)
        form_layout.addRow("温度:", temp_spin)

        # 最大token数
        max_tokens_spin = QSpinBox()
        max_tokens_spin.setRange(100, 10000)
        max_tokens_spin.setSingleStep(100)
        max_tokens_spin.setValue(self.api_config.max_tokens)
        form_layout.addRow("最大token数:", max_tokens_spin)

        layout.addLayout(form_layout)

        # 按钮
        button_layout = QHBoxLayout()

        save_button = QPushButton("保存")
        save_button.clicked.connect(lambda: self.save_api_settings(
            dialog, api_key_edit.text(), api_url_edit.text(),
            model_edit.text(), temp_spin.value(), max_tokens_spin.value()
        ))
        button_layout.addWidget(save_button)

        cancel_button = QPushButton("取消")
        cancel_button.clicked.connect(dialog.close)
        button_layout.addWidget(cancel_button)

        layout.addLayout(button_layout)

        dialog.show()

    def save_api_settings(self, dialog, api_key, api_base_url, model_name, temperature, max_tokens):
        self.api_config.api_key = api_key
        self.api_config.api_base_url = api_base_url
        self.api_config.model_name = model_name
        self.api_config.temperature = temperature
        self.api_config.max_tokens = max_tokens

        self.save_settings()

        dialog.close()
        QMessageBox.information(self, "设置保存", "API设置已保存")

    def process_contract(self):
        if not self.contract_text:
            QMessageBox.warning(self, "合同为空", "请先加载合同文件")
            return

        if not self.api_config.api_key:
            QMessageBox.warning(self, "API密钥未设置", "请先设置API密钥")
            self.show_api_settings()
            return

        # 禁用处理按钮
        self.process_button.setEnabled(False)

        # 重置进度条
        self.progress_bar.setValue(0)

        # 创建并启动处理线程
        self.processing_thread = ContractProcessingThread(self.api_config, self.contract_text)
        self.processing_thread.progress_updated.connect(self.update_progress)
        self.processing_thread.processing_complete.connect(self.processing_finished)
        self.processing_thread.processing_error.connect(self.processing_error)
        self.processing_thread.start()

    def update_progress(self, value, message):
        self.progress_bar.setValue(value)
        self.statusBar().showMessage(message)

    def processing_finished(self, results):
        self.results = results

        # 更新各个标签页的内容
        self.update_clause_tab()
        self.update_risk_tab()
        self.update_compliance_tab()
        self.update_report_tab()
        self.update_accuracy_tab()

        # 启用保存报告按钮
        self.save_action.setEnabled(True)

        # 恢复处理按钮状态
        self.process_button.setEnabled(True)

        self.statusBar().showMessage("合同审核完成")

        # 显示完成消息
        QMessageBox.information(self, "处理完成", "合同审核已完成，请查看各标签页结果")

    def processing_error(self, error_msg):
        QMessageBox.critical(self, "处理错误", error_msg)

        # 恢复处理按钮状态
        self.process_button.setEnabled(True)

        self.statusBar().showMessage("处理过程中发生错误")

    def update_clause_tab(self):
        clause_data = self.results.get("条款提取", {})

        # 清空现有列表
        self.clause_list.clear()

        # 添加条款类型到列表
        for clause_type in clause_data.keys():
            self.clause_list.addItem(clause_type)

        # 如果有条款，显示第一个
        if self.clause_list.count() > 0:
            self.clause_list.setCurrentRow(0)
            self.show_clause_content(self.clause_list.item(0))

    def show_clause_content(self, item):
        clause_type = item.text()
        clause_data = self.results.get("条款提取", {})
        content = clause_data.get(clause_type, "")

        # 如果内容是字典，转换为JSON格式
        if isinstance(content, dict) or isinstance(content, list):
            content = json.dumps(content, ensure_ascii=False, indent=2)

        self.clause_content.setText(content)

    def update_risk_tab(self):
        risk_data = self.results.get("风险分析", {})

        # 如果内容是字典，转换为JSON格式
        if isinstance(risk_data, dict) or isinstance(risk_data, list):
            content = json.dumps(risk_data, ensure_ascii=False, indent=2)
        else:
            content = risk_data

        self.risk_text.setText(content)

    def update_compliance_tab(self):
        compliance_data = self.results.get("合规性分析", {})

        # 如果内容是字典，转换为JSON格式
        if isinstance(compliance_data, dict) or isinstance(compliance_data, list):
            content = json.dumps(compliance_data, ensure_ascii=False, indent=2)
        else:
            content = compliance_data

        self.compliance_text.setText(content)

    def update_report_tab(self):
        report = self.results.get("审查报告", "")
        self.report_text.setText(report)

    def update_accuracy_tab(self):
        accuracy_check = self.results.get("准确性检查", "")
        self.accuracy_text.setText(accuracy_check)

    def save_report(self):
        if not hasattr(self, 'results'):
            QMessageBox.warning(self, "没有报告", "请先处理合同生成报告")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "保存报告", f"合同审查报告_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            "文本文件 (*.txt);;Markdown文件 (*.md);;HTML文件 (*.html)"
        )

        if file_path:
            try:
                file_ext = os.path.splitext(file_path)[1].lower()
                report_content = self.generate_combined_report()

                if file_ext == '.html':
                    # 转换为HTML
                    html_content = markdown.markdown(report_content)
                    with open(file_path, 'w', encoding='utf-8') as file:
                        file.write(html_content)
                else:
                    # 保存为文本或Markdown
                    with open(file_path, 'w', encoding='utf-8') as file:
                        file.write(report_content)

                self.statusBar().showMessage(f"报告已保存到: {file_path}")
                QMessageBox.information(self, "保存成功", f"报告已成功保存到: {file_path}")
            except Exception as e:
                QMessageBox.critical(self, "保存失败", f"保存报告时出错: {str(e)}")
                self.statusBar().showMessage("保存报告失败")

    def generate_combined_report(self):
        # 生成包含所有分析结果的组合报告
        report = "# 合同审查综合报告\n\n"

        # 添加审查日期
        report += f"**审查日期:** {datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')}\n\n"

        # 添加条款提取结果
        report += "## 一、关键条款提取结果\n\n"
        clause_data = self.results.get("条款提取", {})
        if isinstance(clause_data, dict):
            for clause_type, content in clause_data.items():
                report += f"### {clause_type}\n"
                if isinstance(content, dict) or isinstance(content, list):
                    report += f"```json\n{json.dumps(content, ensure_ascii=False, indent=2)}\n```\n\n"
                else:
                    report += f"{content}\n\n"
        else:
            report += f"{clause_data}\n\n"

        # 添加风险分析结果
        report += "## 二、风险量化分析结果\n\n"
        risk_data = self.results.get("风险分析", {})
        if isinstance(risk_data, dict):
            for key, value in risk_data.items():
                report += f"### {key}\n"
                if isinstance(value, dict) or isinstance(value, list):
                    report += f"```json\n{json.dumps(value, ensure_ascii=False, indent=2)}\n```\n\n"
                else:
                    report += f"{value}\n\n"
        else:
            report += f"{risk_data}\n\n"

        # 添加合规性分析结果
        report += "## 三、合规性分析结果\n\n"
        compliance_data = self.results.get("合规性分析", {})
        if isinstance(compliance_data, dict):
            for key, value in compliance_data.items():
                report += f"### {key}\n"
                if isinstance(value, dict) or isinstance(value, list):
                    report += f"```json\n{json.dumps(value, ensure_ascii=False, indent=2)}\n```\n\n"
                else:
                    report += f"{value}\n\n"
        else:
            report += f"{compliance_data}\n\n"

        # 添加主报告
        report += "## 四、详细审查报告\n\n"
        report += self.results.get("审查报告", "")

        # 添加准确性检查
        report += "\n\n## 五、准确性检查结果\n\n"
        report += self.results.get("准确性检查", "")

        return report

    def save_settings(self):
        settings = QSettings("DoubaoSoft", "ContractReview")
        settings.setValue("api_key", self.api_config.api_key)
        settings.setValue("api_base_url", self.api_config.api_base_url)
        settings.setValue("model_name", self.api_config.model_name)
        settings.setValue("temperature", self.api_config.temperature)
        settings.setValue("max_tokens", self.api_config.max_tokens)

    def load_settings(self):
        settings = QSettings("DoubaoSoft", "ContractReview")
        self.api_config.api_key = settings.value("api_key", "")
        self.api_config.api_base_url = settings.value("api_base_url", "https://api.deepseek.com/v1")
        self.api_config.model_name = settings.value("model_name", "deepseek-chat")
        self.api_config.temperature = float(settings.value("temperature", 0.2))
        self.api_config.max_tokens = int(settings.value("max_tokens", 4000))

    def show_usage_agreement(self):
        QMessageBox.information(self, "使用协议", "番石榴企业合同审核系统\n"
                                              "版本: 1.0.0\n\n"
                                              "联系我QQ: 2229029156\n"
                                              "用于企业合同审核。\n\n"
                                              "版权声明：本软件版本为番石榴AI工作室所有，保留所有权利。未经许可，不得复制、传播、修改或分发本软件的任何部分。\n"
                                              "使用本软件即表示您同意遵守相关的使用条款和隐私政策。")

    def show_usage_info(self):
        QMessageBox.information(self, "使用信息", "支持txt、docx以及pdf格式文件的合同审核\n")


if __name__ == "__main__":
    app = QApplication(sys.argv)

    # 设置应用样式
    app.setStyle("Fusion")

    # 创建并显示窗口
    window = ContractReviewApp()
    window.show()

    # 运行应用
    sys.exit(app.exec())
