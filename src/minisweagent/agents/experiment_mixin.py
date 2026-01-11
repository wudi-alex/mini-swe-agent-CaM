"""Mixin for adding project folder structure rendering and advanced model consultation to agents."""

import os
import time
import signal
from pathlib import Path
from minisweagent.models import get_model


class TimeoutError(Exception):
    """Raised when operation times out."""
    pass


def timeout_handler(signum, frame):
    raise TimeoutError("Operation timed out")


class ExperimentMixin:
    """Mixin that adds project folder structure rendering and advanced model consultation capability."""

    def __init__(self, *args,
                 max_folder_depth: int = 5,
                 ignored_dirs: set[str] = None,
                 advanced_model_name: str = None,
                 consultation_strategy: str = "ASK_BY_AGENT",
                 routine_ask_interval: int = 5,
                 initial_analysis: bool = False,
                 advanced_model_timeout: int = 120,
                 **kwargs):
        """
        Initialize the mixin.

        Args:
            max_folder_depth: Maximum depth for folder structure
            ignored_dirs: Set of directories to ignore
            advanced_model_name: Name of advanced model to consult (e.g., 'gpt-5', 'openai/gpt-5', 'claude-opus-4')
            consultation_strategy: Strategy for consultation - "ASK_BY_AGENT" or "ROUTINE_ASK"
            routine_ask_interval: Interval for routine consultation (only used if strategy is ROUTINE_ASK)
            initial_analysis: Whether to include advanced model's initial analysis in system prompt
            advanced_model_timeout: Timeout in seconds for advanced model calls (default: 120)
        """
        # 保存自定义参数
        self.max_folder_depth = max_folder_depth
        self.ignored_dirs = ignored_dirs or {
            '.git', '__pycache__', '.pytest_cache',
            'node_modules', '.venv', 'venv', '.idea',
            '.vscode', 'dist', 'build', '.tox', 'eggs',
            '.eggs', '__pypackages__', '.mypy_cache',
            '.pytest_cache', '.hypothesis', '.coverage'
        }
        self.advanced_model_name = advanced_model_name
        self.advanced_model = None
        self.consultation_strategy = consultation_strategy
        self.routine_ask_interval = routine_ask_interval
        self.initial_analysis = initial_analysis
        self.consultation_count = 0  # 用于追踪咨询次数
        self.advanced_model_timeout = advanced_model_timeout

        # 如果指定了高级模型，初始化它
        if self.advanced_model_name:
            try:
                print(f"[ExperimentMixin] Initializing advanced model: {self.advanced_model_name}")
                # 使用正确的参数名 input_model_name
                self.advanced_model = get_model(
                    input_model_name=self.advanced_model_name,
                    config={}
                )
                print(f"[ExperimentMixin] Advanced model initialized successfully")
                print(f"[ExperimentMixin] Model class: {type(self.advanced_model).__name__}")
            except Exception as e:
                print(f"[ExperimentMixin] Warning: Failed to initialize advanced model {self.advanced_model_name}")
                print(f"[ExperimentMixin] Error: {e}")
                import traceback
                traceback.print_exc()
                self.advanced_model = None

        # 调用父类初始化（支持多重继承）
        super().__init__(*args, **kwargs)

    def get_folder_structure_from_env(self, root_path: str = "/testbed") -> str:
        """
        从环境中获取文件夹结构（在容器内执行命令）

        Args:
            root_path: 根目录路径（通常是 /testbed）

        Returns:
            格式化的文件夹结构字符串
        """
        print(f"[ExperimentMixin] Getting folder structure from: {root_path}")

        # 构建 bash 脚本来获取目录结构
        bash_script = f"""
#!/bin/bash

# 函数：生成树形结构
print_tree() {{
    local prefix="$1"
    local dir="$2"
    local depth="$3"
    local max_depth={self.max_folder_depth}
    
    # 如果达到最大深度，返回
    if [ "$depth" -ge "$max_depth" ]; then
        return
    fi
    
    # 获取所有子目录（排序，排除忽略的目录）
    local subdirs=()
    while IFS= read -r -d '' subdir; do
        local basename=$(basename "$subdir")
        # 检查是否在忽略列表中
        local should_ignore=0
        for ignored in {' '.join(self.ignored_dirs)}; do
            if [ "$basename" = "$ignored" ]; then
                should_ignore=1
                break
            fi
        done
        if [ "$should_ignore" -eq 0 ]; then
            subdirs+=("$subdir")
        fi
    done < <(find "$dir" -mindepth 1 -maxdepth 1 -type d -print0 2>/dev/null | sort -z)
    
    local count=${{#subdirs[@]}}
    local index=0
    
    for subdir in "${{subdirs[@]}}"; do
        local basename=$(basename "$subdir")
        index=$((index + 1))
        
        if [ "$index" -eq "$count" ]; then
            echo "${{prefix}}└── $basename/"
            print_tree "${{prefix}}    " "$subdir" $((depth + 1))
        else
            echo "${{prefix}}├── $basename/"
            print_tree "${{prefix}}│   " "$subdir" $((depth + 1))
        fi
    done
}}

# 检查目录是否存在
if [ ! -d "{root_path}" ]; then
    echo "Path does not exist: {root_path}"
    exit 1
fi

# 打印根目录
echo "$(basename {root_path})/"

# 打印树形结构
print_tree "" "{root_path}" 0
"""

        try:
            # 在环境中执行命令获取文件夹结构
            result = self.env.execute(bash_script)

            if result.get("returncode", 1) == 0:
                output = result.get("output", "")
                if output:
                    print(f"[ExperimentMixin] Folder structure retrieved: {len(output)} characters")
                    return output.strip()
                else:
                    print("[ExperimentMixin] Warning: Empty output from folder structure command")
                    return f"Empty output from folder structure command"
            else:
                print("[ExperimentMixin] Folder structure script failed, trying simple find command")
                # 如果脚本失败，使用简单的 find 命令作为备用
                simple_cmd = f"find {root_path} -type d -not -path '*/.git/*' -not -path '*/__pycache__/*' -not -path '*/node_modules/*' | head -200 | sort"
                result = self.env.execute(simple_cmd)
                if result.get("returncode", 1) == 0:
                    return f"Simplified folder list:\n{result.get('output', '').strip()}"
                else:
                    return f"Failed to get folder structure: {result.get('output', 'unknown error')}"
        except Exception as e:
            print(f"[ExperimentMixin] Error getting folder structure: {e}")
            import traceback
            traceback.print_exc()
            return f"Error getting folder structure: {str(e)}"

    def call_advanced_model_with_timeout(self, messages: list[dict], timeout: int = None) -> dict:
        """
        调用高级模型，带超时机制

        Args:
            messages: 消息列表
            timeout: 超时时间（秒），如果为 None 则使用默认值

        Returns:
            响应字典
        """
        if timeout is None:
            timeout = self.advanced_model_timeout

        print(f"[ExperimentMixin] Calling advanced model with {timeout}s timeout...")
        print(f"[ExperimentMixin] Messages count: {len(messages)}")

        # 计算总字符数
        total_chars = sum(len(str(m.get('content', ''))) for m in messages)
        print(f"[ExperimentMixin] Total message content: {total_chars} characters")

        result = {'response': None, 'error': None}

        def query_model():
            try:
                print(f"[ExperimentMixin] Starting query to {self.advanced_model_name}...")
                print(messages)
                result['response'] = self.advanced_model.query(messages)
                print(f"[ExperimentMixin] Query completed successfully")
            except Exception as e:
                print(f"[ExperimentMixin] Query failed with error: {e}")
                result['error'] = e

        import threading
        thread = threading.Thread(target=query_model)
        thread.daemon = True
        thread.start()

        # 等待线程完成或超时
        thread.join(timeout=timeout)

        if thread.is_alive():
            # 超时了
            print(f"[ExperimentMixin] WARNING: Advanced model call timed out after {timeout}s")
            print(f"[ExperimentMixin] This usually indicates network issues or API problems")
            raise TimeoutError(f"Advanced model call timed out after {timeout} seconds")

        if result['error']:
            raise result['error']

        if result['response'] is None:
            raise Exception("No response received from advanced model")

        return result['response']

    def get_initial_analysis(self, task: str, folder_structure: str) -> str:
        """
        获取高级模型对任务的初始分析和步骤指导

        Args:
            task: 任务描述
            folder_structure: 项目文件夹结构

        Returns:
            高级模型的初始分析
        """
        if not self.advanced_model:
            print("[ExperimentMixin] No advanced model available for initial analysis")
            return ""

        print("[ExperimentMixin] Requesting initial analysis from advanced model...")
        print(f"[ExperimentMixin] Task length: {len(task)} characters")
        print(f"[ExperimentMixin] Folder structure length: {len(folder_structure)} characters")

        try:
            initial_prompt = f"""# Initial Task Analysis Request

You are an expert software engineer. Please analyze the following task and provide detailed guidance.

## Task Description:
{task}

## Project Folder Structure:
{folder_structure}

## Your Task:
Please provide:
1. **Problem Analysis**: What is the core issue that needs to be fixed?
2. **Key Files**: Which files are likely to need modification?
3. **Approach**: What is the recommended approach to solve this issue?
4. **Step-by-Step Plan**: Provide a high-level plan with 3-5 concrete steps
5. **Potential Pitfalls**: What are common mistakes to avoid?

Please be specific and actionable in your guidance."""

            consultation_messages = [
                {
                    "role": "system",
                    "content": "You are an expert software engineer providing initial guidance for a coding task.",
                    "timestamp": time.time()
                },
                {
                    "role": "user",
                    "content": initial_prompt,
                    "timestamp": time.time()
                }
            ]

            print(f"[ExperimentMixin] Prepared {len(consultation_messages)} messages for advanced model")
            start_time = time.time()

            # 记录调用前的 cost
            cost_before = self.advanced_model.cost if hasattr(self.advanced_model, 'cost') else 0
            print(f"[ExperimentMixin] Cost before call: ${cost_before:.4f}")

            # 使用带超时的调用
            try:
                response = self.call_advanced_model_with_timeout(consultation_messages)
            except TimeoutError as e:
                print(f"[ExperimentMixin] Initial analysis timed out: {e}")
                return f"Initial analysis request timed out. Please check your network connection and API access."

            elapsed = time.time() - start_time
            print(f"[ExperimentMixin] Advanced model responded in {elapsed:.2f}s")

            # 记录调用后的 cost 并累加到主模型
            cost_after = self.advanced_model.cost if hasattr(self.advanced_model, 'cost') else 0
            advanced_cost = cost_after - cost_before
            print(f"[ExperimentMixin] Cost after call: ${cost_after:.4f}")

            # 将高级模型的 cost 累加到主模型
            if hasattr(self.model, 'cost'):
                self.model.cost += advanced_cost
                print(f"[ExperimentMixin] Advanced model cost for initial analysis: ${advanced_cost:.4f}")
                print(f"[ExperimentMixin] Total cost so far: ${self.model.cost:.4f}")

            content = response.get("content", "")
            print(f"[ExperimentMixin] Initial analysis received: {len(content)} characters")
            return content

        except Exception as e:
            print(f"[ExperimentMixin] Error getting initial analysis: {e}")
            import traceback
            traceback.print_exc()
            return f"Error getting initial analysis: {str(e)}"

    def consult_advanced_model(self, consultation_type: str = "on_demand") -> str:
        """
        咨询高级模型以获取建议

        Args:
            consultation_type: 咨询类型 - "on_demand" 或 "routine"

        Returns:
            高级模型的回复
        """
        if not self.advanced_model:
            return "Advanced model is not configured. Please specify 'advanced_model_name' parameter."

        print(f"[ExperimentMixin] Consulting advanced model (type: {consultation_type})...")

        try:
            # 构建发送给高级模型的上下文
            consultation_prompt = self._build_consultation_context(consultation_type)

            # 创建临时消息列表用于咨询
            consultation_messages = [
                {
                    "role": "system",
                    "content": "You are an expert software engineer consultant. Another AI agent is working on a coding task and has requested your help. Review the conversation history and provide specific, actionable advice."
                },
                {
                    "role": "user",
                    "content": consultation_prompt
                }
            ]

            print(f"[ExperimentMixin] Prepared {len(consultation_messages)} messages for advanced model")
            start_time = time.time()

            # 记录调用前的 cost
            cost_before = self.advanced_model.cost if hasattr(self.advanced_model, 'cost') else 0

            # 使用带超时的调用
            try:
                response = self.call_advanced_model_with_timeout(consultation_messages)
            except TimeoutError as e:
                print(f"[ExperimentMixin] Consultation timed out: {e}")
                return f"Consultation request timed out. Please check your network connection and API access."

            elapsed = time.time() - start_time
            print(f"[ExperimentMixin] Advanced model responded in {elapsed:.2f}s")

            # 记录调用后的 cost 并累加到主模型
            cost_after = self.advanced_model.cost if hasattr(self.advanced_model, 'cost') else 0
            advanced_cost = cost_after - cost_before

            # 将高级模型的 cost 累加到主模型
            if hasattr(self.model, 'cost'):
                self.model.cost += advanced_cost
                print(f"[ExperimentMixin] Advanced model consultation cost: ${advanced_cost:.4f}")
                print(f"[ExperimentMixin] Total accumulated cost: ${self.model.cost:.4f}")

            self.consultation_count += 1
            content = response.get("content", "No response from advanced model")
            print(f"[ExperimentMixin] Consultation response received: {len(content)} characters")
            return content

        except Exception as e:
            print(f"[ExperimentMixin] Error consulting advanced model: {e}")
            import traceback
            traceback.print_exc()
            return f"Error consulting advanced model: {str(e)}"

    def _build_consultation_context(self, consultation_type: str) -> str:
        """
        构建发送给高级模型的上下文

        Args:
            consultation_type: 咨询类型

        Returns:
            格式化的上下文字符串
        """
        context_parts = []

        if consultation_type == "routine":
            context_parts.append("# Routine Progress Check\n")
            context_parts.append(f"This is routine consultation #{self.consultation_count + 1}. ")
            context_parts.append("The agent has been working for a while and we're checking progress.\n")
        else:
            context_parts.append("# Agent Consultation Request\n")
            context_parts.append("The AI agent has explicitly requested help.\n")

        context_parts.append("\n## Conversation History:\n")

        # 包含最近的对话历史（过滤掉系统消息以减少 token 使用）
        for msg in self.messages[-20:]:  # 只包含最近 20 条消息
            role = msg.get("role", "unknown")
            content = msg.get("content", "")

            # 截断过长的内容
            if len(content) > 2000:
                content = content[:1000] + "\n... [truncated] ...\n" + content[-1000:]

            context_parts.append(f"\n### {role.upper()}:\n{content}\n")

        context_parts.append("\n## Your Task:\n")
        if consultation_type == "routine":
            context_parts.append("Please provide:\n")
            context_parts.append("1. Assessment of current progress\n")
            context_parts.append("2. Evaluation of the agent's approach so far\n")
            context_parts.append("3. Suggestions for improvement or course correction if needed\n")
            context_parts.append("4. Encouragement if on the right track, or redirection if stuck\n")
        else:
            context_parts.append("Please provide:\n")
            context_parts.append("1. Analysis of what the agent has tried so far\n")
            context_parts.append("2. Identification of any mistakes or issues\n")
            context_parts.append("3. Specific suggestions for the next steps\n")
            context_parts.append("4. Any insights about the problem that might help\n")

        return "".join(context_parts)

    def check_advanced_model_request(self, output: dict[str, str]) -> bool:
        """
        检查输出是否包含高级模型咨询请求

        Args:
            output: 命令执行的输出

        Returns:
            是否请求高级模型咨询
        """
        lines = output.get("output", "").lstrip().splitlines()
        if lines and lines[0].strip() == "ASK_ADVANCED_MODEL_FOR_HELP":
            return True
        return False

    def should_routine_consult(self) -> bool:
        """
        检查是否应该进行周期性咨询

        Returns:
            是否应该咨询
        """
        if self.consultation_strategy != "ROUTINE_ASK":
            return False

        if not self.advanced_model:
            return False

        # 检查是否到达咨询间隔
        if self.model.n_calls > 0 and self.model.n_calls % self.routine_ask_interval == 0:
            return True

        return False

    def execute_action(self, action: dict) -> dict:
        """重写 execute_action 以检查高级模型咨询请求"""
        # 调用父类的 execute_action
        output = super().execute_action(action)

        # 策略1: ASK_BY_AGENT - 检查 agent 主动请求
        if self.consultation_strategy == "ASK_BY_AGENT":
            if self.check_advanced_model_request(output):
                print("="*80)
                print("[ExperimentMixin] Advanced Model Consultation (On-Demand)")
                print("="*80)

                # 咨询高级模型
                advice = self.consult_advanced_model(consultation_type="on_demand")

                # 构建咨询响应消息
                consultation_response = f"""
<advanced_model_consultation type="on_demand">
You requested help from an advanced model. Here is the response:

{advice}

Please carefully consider this advice and proceed with your next action.
</advanced_model_consultation>
"""
                # 将高级模型的建议作为 user 消息添加到对话中
                self.add_message("user", consultation_response)

                # 记录咨询事件
                print(f"[ExperimentMixin] Consultation #{self.consultation_count} completed")
                print(f"[ExperimentMixin] Advice preview: {advice[:200]}...")
                print("="*80)

        return output

    def step(self) -> dict:
        """重写 step 以支持周期性咨询"""
        # 策略2: ROUTINE_ASK - 周期性咨询
        if self.should_routine_consult():
            print("="*80)
            print(f"[ExperimentMixin] Advanced Model Consultation (Routine #{self.consultation_count + 1})")
            print(f"[ExperimentMixin] Step: {self.model.n_calls}")
            print("="*80)

            # 咨询高级模型
            advice = self.consult_advanced_model(consultation_type="routine")

            # 构建咨询响应消息
            consultation_response = f"""
<advanced_model_consultation type="routine" step="{self.model.n_calls}">
Regular progress check from advanced model (every {self.routine_ask_interval} steps):

{advice}

Continue with your work, taking this feedback into account.
</advanced_model_consultation>
"""
            # 将高级模型的建议作为 user 消息添加到对话中
            self.add_message("user", consultation_response)

            # 记录咨询事件
            print(f"[ExperimentMixin] Routine consultation #{self.consultation_count} completed")
            print(f"[ExperimentMixin] Advice preview: {advice[:200]}...")
            print("="*80)

        # 调用父类的 step
        return super().step()

    def run(self, task: str, **kwargs) -> tuple[str, str]:
        """重写 run 方法，在执行前添加项目结构和可选的初始分析"""

        print("="*80)
        print("[ExperimentMixin] Starting run with ExperimentMixin")
        print("="*80)

        # 获取工作目录（Docker 容器中通常是 /testbed）
        working_dir = getattr(self.env, 'cwd', '/testbed')
        print(f"[ExperimentMixin] Working directory: {working_dir}")

        # 从环境（容器内）获取文件夹结构
        folder_structure = self.get_folder_structure_from_env(working_dir)

        # 添加到 extra_template_vars
        self.extra_template_vars['project_folders'] = folder_structure
        print(f"[ExperimentMixin] Folder structure added to template vars")

        # 如果启用了初始分析，获取高级模型的分析
        if self.initial_analysis and self.advanced_model:
            print("="*80)
            print("[ExperimentMixin] Getting Initial Analysis from Advanced Model")
            print("="*80)

            try:
                initial_analysis = self.get_initial_analysis(task, folder_structure)
                self.extra_template_vars['initial_analysis'] = initial_analysis

                print(f"[ExperimentMixin] Initial analysis received and added to template vars")
                print("="*80)
            except Exception as e:
                print(f"[ExperimentMixin] Failed to get initial analysis: {e}")
                import traceback
                traceback.print_exc()
                self.extra_template_vars['initial_analysis'] = ""
                print("[ExperimentMixin] Continuing without initial analysis...")
        else:
            self.extra_template_vars['initial_analysis'] = ""
            if self.initial_analysis:
                print("[ExperimentMixin] Initial analysis requested but no advanced model available")

        print("[ExperimentMixin] Starting parent run method...")
        # 调用父类的 run 方法
        return super().run(task, **kwargs)