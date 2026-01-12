"""Run on a single SWE-Bench instance."""

import traceback
from pathlib import Path

import typer
import yaml
from datasets import load_dataset

from minisweagent import global_config_dir
from minisweagent.agents.default import FormatError
from minisweagent.agents.interactive import InteractiveAgent
from minisweagent.config import builtin_config_dir, get_config_path
from minisweagent.models import get_model
from minisweagent.run.extra.swebench import (
    DATASET_MAPPING,
    get_sb_environment,
)
from minisweagent.run.utils.save import save_traj
from minisweagent.utils.log import logger

app = typer.Typer(add_completion=False)

DEFAULT_OUTPUT = global_config_dir / "astropy-13398-mini.traj.json"


class InteractiveAgentCam(InteractiveAgent):
    def parse_action(self, response: dict) -> dict:
        """Parse the action from the message and construct python -c command."""
        import re

        # 提取 agent 返回的函数代码
        function_code = response["content"].strip()

        # 读取本地 tools.py 文件内容
        # 获取当前脚本所在目录
        current_dir = Path(__file__).parent

        # 构建 tools.py 路径
        tools_path = current_dir / 'tools.py'
        try:
            with open(tools_path, 'r', encoding='utf-8') as f:
                tools_code = f.read()
        except FileNotFoundError:
            raise FileNotFoundError("tools.py file not found in current directory")

        # 提取所有函数名（从 def function_name(): 中提取）
        func_name_matches = re.findall(r'def\s+(\w+)\s*\(', function_code)

        # 特殊处理 submit() 情况
        if function_code == 'submit()':
            full_code = f"{tools_code}\n\n{function_code}"
        elif not func_name_matches:
            raise FormatError(
                f"Could not extract function name from response. "
                f"Expected format: def action(): ..."
            )
        else:
            # 拼接完整代码：tools定义 + agent函数定义 + 依次调用所有函数
            function_calls = '\n'.join([f"{func_name}()" for func_name in func_name_matches])
            full_code = f"{tools_code}\n\n{function_code}\n\n{function_calls}"

        # 转义代码中的特殊字符用于shell命令
        # 将单引号替换为 '\'' (结束单引号、转义单引号、开始新单引号)
        escaped_code = full_code.replace("'", "'\"'\"'")

        # 构造 bash 命令：使用单引号包裹代码避免大部分转义问题
        action = f"python -c '{escaped_code}'"

        return {"action": action, **response}


# fmt: off
@app.command()
def main(
        subset: str = typer.Option("verified", "--subset", help="SWEBench subset to use or path to a dataset",
                                   rich_help_panel="Data selection"),
        split: str = typer.Option("dev", "--split", help="Dataset split", rich_help_panel="Data selection"),
        instance_spec: str = typer.Option(0, "-i", "--instance", help="SWE-Bench instance ID or index",
                                          rich_help_panel="Data selection"),
        model_name: str | None = typer.Option(None, "-m", "--model", help="Model to use", rich_help_panel="Basic"),
        model_class: str | None = typer.Option(None, "-c", "--model-class",
                                               help="Model class to use (e.g., 'anthropic' or 'minisweagent.models.anthropic.AnthropicModel')",
                                               rich_help_panel="Advanced"),
        config_path: Path = typer.Option(builtin_config_dir / "extra" / "swebench_cam.yaml", "-c", "--config",
                                         help="Path to a config file", rich_help_panel="Basic"),
        environment_class: str | None = typer.Option(None, "--environment-class", rich_help_panel="Advanced"),
        exit_immediately: bool = typer.Option(False, "--exit-immediately",
                                              help="Exit immediately when the agent wants to finish instead of prompting.",
                                              rich_help_panel="Basic"),
        output: Path = typer.Option(DEFAULT_OUTPUT, "-o", "--output", help="Output trajectory file",
                                    rich_help_panel="Basic"),
) -> None:
    # fmt: on
    """Run on a single SWE-Bench instance."""
    dataset_path = DATASET_MAPPING.get(subset, subset)
    logger.info(f"Loading dataset from {dataset_path}, split {split}...")
    instances = {
        inst["instance_id"]: inst  # type: ignore
        for inst in load_dataset(dataset_path, split=split)
    }
    if instance_spec.isnumeric():
        instance_spec = sorted(instances.keys())[int(instance_spec)]
    instance: dict = instances[instance_spec]  # type: ignore

    config_path = get_config_path(config_path)
    logger.info(f"Loading agent config from '{config_path}'")
    config = yaml.safe_load(config_path.read_text())
    if environment_class is not None:
        config.setdefault("environment", {})["environment_class"] = environment_class
    if model_class is not None:
        config.setdefault("model", {})["model_class"] = model_class
    if exit_immediately:
        config.setdefault("agent", {})["confirm_exit"] = False
    env = get_sb_environment(config, instance)
    agent = InteractiveAgentCam(
        get_model(model_name, config.get("model", {})),
        env,
        **({"mode": "yolo"} | config.get("agent", {})),
    )

    exit_status, result, extra_info = None, None, None
    try:
        exit_status, result = agent.run(instance["problem_statement"])  # type: ignore[arg-type]
    except Exception as e:
        logger.error(f"Error processing instance {instance_spec}: {e}", exc_info=True)
        exit_status, result = type(e).__name__, str(e)
        extra_info = {"traceback": traceback.format_exc()}
    finally:
        save_traj(agent, output, exit_status=exit_status, result=result,
                  extra_info=extra_info)  # type: ignore[arg-type]


if __name__ == "__main__":
    app()
