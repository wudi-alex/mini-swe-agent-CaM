#!/usr/bin/env python3

"""Run on a single SWE-Bench instance with InteractiveExperimentAgent."""

import traceback
from pathlib import Path

import typer
import yaml
from datasets import load_dataset

from minisweagent import global_config_dir
from minisweagent.agents.experiment_agent import InteractiveExperimentAgent
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


# fmt: off
@app.command()
def main(
        subset: str = typer.Option("verified", "--subset", help="SWEBench subset to use or path to a dataset",
                                   rich_help_panel="Data selection"),
        split: str = typer.Option("dev", "--split", help="Dataset split", rich_help_panel="Data selection"),
        instance_spec: str = typer.Option("sphinx-doc__sphinx-10435", "-i", "--instance", help="SWE-Bench instance ID or index",
                                          rich_help_panel="Data selection"),
        model_name: str | None = typer.Option(None, "-m", "--model", help="Model to use", rich_help_panel="Basic"),
        model_class: str | None = typer.Option(None, "-c", "--model-class",
                                               help="Model class to use (e.g., 'anthropic' or 'minisweagent.models.anthropic.AnthropicModel')",
                                               rich_help_panel="Advanced"),
        config_path: Path = typer.Option(builtin_config_dir / "extra" / "swebench_exp.yaml", "-c", "--config",
                                         help="Path to a config file", rich_help_panel="Basic"),
        environment_class: str | None = typer.Option(None, "--environment-class", rich_help_panel="Advanced"),
        exit_immediately: bool = typer.Option(False, "--exit-immediately",
                                              help="Exit immediately when the agent wants to finish instead of prompting.",
                                              rich_help_panel="Basic"),
        output: Path = typer.Option(DEFAULT_OUTPUT, "-o", "--output", help="Output trajectory file",
                                    rich_help_panel="Basic"),
        max_folder_depth: int = typer.Option(1, "--max-folder-depth", help="Maximum depth for folder structure tree",
                                             rich_help_panel="ExperimentAgent"),
        ignore_dirs: str = typer.Option(
            ".git,__pycache__,.pytest_cache,node_modules,.venv,venv,.idea,.vscode,dist,build", "--ignore-dirs",
            help="Comma-separated list of directories to ignore", rich_help_panel="ExperimentAgent"),
        advanced_model: str | None = typer.Option('openai/gpt-5', "--advanced-model",
                                                  help="Advanced model to consult when agent requests help (e.g., 'gpt-5', 'claude-opus-4')",
                                                  rich_help_panel="ExperimentAgent"),
        consultation_strategy: str = typer.Option("ASK_BY_AGENT", "--consultation-strategy",
                                                  help="Consultation strategy: 'ASK_BY_AGENT' (agent decides) or 'ROUTINE_ASK' (periodic)",
                                                  rich_help_panel="ExperimentAgent"),
        routine_ask_interval: int = typer.Option(5, "--routine-ask-interval",
                                                 help="Interval for routine consultation (only used with ROUTINE_ASK strategy)",
                                                 rich_help_panel="ExperimentAgent"),
        initial_analysis: bool = typer.Option(True, "--initial-analysis",
                                              help="Include advanced model's initial analysis in system prompt",
                                              rich_help_panel="ExperimentAgent"),
) -> None:
    # fmt: on
    """Run on a single SWE-Bench instance with InteractiveExperimentAgent."""
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

    # Parse ignored directories
    ignored_dirs_set = set(d.strip() for d in ignore_dirs.split(",") if d.strip())
    logger.info(f"Using InteractiveExperimentAgent with folder structure rendering")
    logger.info(f"  Max folder depth: {max_folder_depth}")
    logger.info(f"  Ignoring directories: {ignored_dirs_set}")
    if advanced_model:
        logger.info(f"  Advanced model: {advanced_model}")
        logger.info(f"  Consultation strategy: {consultation_strategy}")
        if consultation_strategy == "ROUTINE_ASK":
            logger.info(f"  Routine ask interval: every {routine_ask_interval} steps")
        logger.info(f"  Initial analysis: {'enabled' if initial_analysis else 'disabled'}")

    env = get_sb_environment(config, instance)
    agent = InteractiveExperimentAgent(
        get_model(model_name, config.get("model", {})),
        env,
        max_folder_depth=max_folder_depth,
        ignored_dirs=ignored_dirs_set,
        advanced_model_name=advanced_model,
        consultation_strategy=consultation_strategy,
        routine_ask_interval=routine_ask_interval,
        initial_analysis=initial_analysis,
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
        logger.info(f"Trajectory saved to {output}")


if __name__ == "__main__":
    app()