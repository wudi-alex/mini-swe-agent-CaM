import time
from typing import List, Dict, Any


def reasoning_effort_cost_comparison():
    """Test cost comparison across different reasoning_effort levels for GPT-5-mini."""
    print("\n" + "=" * 80)
    print("  GPT-5-MINI REASONING EFFORT COST COMPARISON")
    print("=" * 80)

    try:
        from minisweagent.models import get_model
        print("\n✓ Imported get_model")
    except ImportError as e:
        print(f"\n✗ Import failed: {e}")
        return False

    model_name = "openai/gpt-5-mini"

    print(f"\n{'=' * 80}")
    print(f"  Model: {model_name}")
    print(f"  Testing reasoning_effort levels: minimal, low, medium, high")
    print(f"  Note: Using Chat Completions API format")
    print(f"{'=' * 80}")

    # 测试任务：需要推理的逻辑问题
    test_problem = """Solve this logic puzzle:

There are 5 houses in 5 different colors in a row. In each house lives a person with a different nationality. The 5 owners drink a certain type of beverage, smoke a certain brand of cigar, and keep a certain pet. No owners have the same pet, smoke the same brand of cigar, or drink the same beverage.

Hints:
1. The Brit lives in the red house.
2. The Swede keeps dogs as pets.
3. The Dane drinks tea.
4. The green house is on the immediate left of the white house.
5. The green house's owner drinks coffee.
6. The owner who smokes Pall Mall rears birds.
7. The owner of the yellow house smokes Dunhill.
8. The owner living in the center house drinks milk.
9. The Norwegian lives in the first house.
10. The owner who smokes Blends lives next to the one who keeps cats.
11. The owner who keeps the horse lives next to the one who smokes Dunhill.
12. The owner who smokes Bluemasters drinks beer.
13. The German smokes Prince.
14. The Norwegian lives next to the blue house.
15. The owner who smokes Blends lives next to the one who drinks water.

Question: Who owns the fish?"""

    # 定义要测试的推理强度级别
    reasoning_levels = [
        {
            'effort': 'minimal',
            'description': 'Fastest, cheapest - minimal thinking',
            'use_case': 'Simple tasks, quick responses'
        },
        {
            'effort': 'low',
            'description': 'Quick - basic reasoning',
            'use_case': 'Straightforward problems'
        },
        {
            'effort': 'medium',
            'description': 'Balanced - default level',
            'use_case': 'Most tasks (default)'
        },
        {
            'effort': 'high',
            'description': 'Thorough - deep reasoning',
            'use_case': 'Complex problems, critical tasks'
        }
    ]

    print(f"\n  Test Problem: Einstein's Riddle (Who owns the fish?)")
    print(f"  This requires multi-step logical reasoning.\n")

    results = []

    for level_config in reasoning_levels:
        effort = level_config['effort']

        print(f"\n{'─' * 80}")
        print(f"  Testing: reasoning_effort = '{effort}'")
        print(f"  Description: {level_config['description']}")
        print(f"  Use case: {level_config['use_case']}")
        print(f"{'─' * 80}")

        try:
            # 初始化模型（每次重新初始化以重置 cost）
            model = get_model(input_model_name=model_name, config={})

            # 构建消息
            messages = [
                {
                    'role': 'user',
                    'content': test_problem
                }
            ]

            cost_before = model.cost if hasattr(model, 'cost') else 0.0
            start_time = time.time()

            # ✅ 正确方式：对于 Chat Completions API，使用顶层参数 reasoning_effort
            # litellm 会将额外的 kwargs 传递给底层 API
            response = model.query(messages, reasoning_effort=effort)

            elapsed = time.time() - start_time
            cost_after = model.cost if hasattr(model, 'cost') else 0.0
            query_cost = cost_after - cost_before

            # 提取响应内容
            content = response.get("content", "")

            # 提取 token 信息
            extra = response.get("extra", {})
            response_data = extra.get("response", {})

            def safe_get(obj, *keys, default=0):
                for key in keys:
                    if obj is None:
                        return default
                    if isinstance(obj, dict):
                        obj = obj.get(key)
                    else:
                        obj = getattr(obj, key, None)
                return obj if obj is not None else default

            usage = safe_get(response_data, 'usage')

            if usage:
                prompt_tokens = safe_get(usage, 'prompt_tokens', default=0)
                completion_tokens = safe_get(usage, 'completion_tokens', default=0)
                total_tokens = safe_get(usage, 'total_tokens', default=0)

                # 提取 reasoning tokens（在 completion_tokens_details 中）
                completion_details = safe_get(usage, 'completion_tokens_details')
                reasoning_tokens = safe_get(completion_details, 'reasoning_tokens', default=0)
                # 如果有 text_tokens 字段
                text_tokens = safe_get(completion_details, 'text_tokens', default=0)
                # 如果没有 text_tokens，计算：text = completion - reasoning
                if text_tokens == 0 and reasoning_tokens > 0:
                    text_tokens = completion_tokens - reasoning_tokens

                # 缓存信息
                prompt_details = safe_get(usage, 'prompt_tokens_details')
                cached_tokens = safe_get(prompt_details, 'cached_tokens', default=0)
            else:
                prompt_tokens = completion_tokens = total_tokens = 0
                reasoning_tokens = text_tokens = cached_tokens = 0

            result = {
                'effort': effort,
                'description': level_config['description'],
                'elapsed_time': elapsed,
                'cost': query_cost,
                'prompt_tokens': prompt_tokens,
                'completion_tokens': completion_tokens,
                'reasoning_tokens': reasoning_tokens,
                'text_tokens': text_tokens,
                'total_tokens': total_tokens,
                'cached_tokens': cached_tokens,
                'response_length': len(content),
                'answer': content[:300]
            }
            results.append(result)

            # 打印结果
            print(f"\n  ✓ Completed in {elapsed:.2f}s")
            print(f"  💰 Cost: ${query_cost:.6f}")

            print(f"\n  📊 Token Breakdown:")
            print(f"     - Prompt tokens: {prompt_tokens:,}")
            if cached_tokens > 0:
                print(f"     - Cached tokens: {cached_tokens:,}")
            print(f"     - Completion tokens: {completion_tokens:,}")
            if reasoning_tokens > 0:
                print(f"       ├─ Reasoning tokens: {reasoning_tokens:,} 🧠")
                print(f"       └─ Text tokens: {text_tokens:,}")
            print(f"     - Total tokens: {total_tokens:,}")

            # 计算推理 token 占比
            if completion_tokens > 0 and reasoning_tokens > 0:
                reasoning_pct = (reasoning_tokens / completion_tokens * 100)
                print(f"\n  🧠 Reasoning Analysis:")
                print(f"     - Reasoning tokens: {reasoning_tokens:,} ({reasoning_pct:.1f}% of completion)")
                print(f"     - Text tokens: {text_tokens:,} ({100 - reasoning_pct:.1f}% of completion)")

            print(f"\n  📝 Answer Preview:")
            preview = content[:200].replace('\n', ' ')
            print(f"     {preview}...")

            # 延迟避免速率限制
            time.sleep(2)

        except Exception as e:
            print(f"\n  ✗ Test failed: {e}")
            import traceback
            traceback.print_exc()

            # 如果是因为不支持 reasoning_effort，尝试不带参数
            if "reasoning_effort" in str(e) or "Unknown parameter" in str(e):
                print(f"\n  ⚠️  Model may not support reasoning_effort parameter")
                print(
                    f"  ℹ️  Note: GPT-5-mini requires Chat Completions API with 'reasoning_effort' as top-level param")
            continue

    # 汇总分析
    print(f"\n\n{'=' * 80}")
    print("  SUMMARY - REASONING EFFORT COST ANALYSIS")
    print(f"{'=' * 80}\n")

    if not results:
        print("  ✗ No successful queries to analyze")
        print("\n  💡 Troubleshooting:")
        print("     1. Ensure you're using a GPT-5 model (gpt-5, gpt-5-mini, gpt-5-nano)")
        print("     2. Check that your OpenAI SDK supports reasoning_effort")
        print("     3. Verify litellm is updated: pip install --upgrade litellm")
        return False

    # 表格标题
    print(f"  {'Effort':<10} {'Cost ($)':<12} {'Time(s)':<9} {'Total':<10} {'Reasoning':<12} {'Text':<10}")
    print(f"  {'Level':<10} {'':>12} {'':>9} {'Tokens':<10} {'Tokens':<12} {'Tokens':<10}")
    print(f"  {'-' * 79}")

    # 打印每行
    for r in results:
        reasoning_display = f"{r['reasoning_tokens']:,}" if r['reasoning_tokens'] > 0 else "N/A"
        text_display = f"{r['text_tokens']:,}" if r['text_tokens'] > 0 else "N/A"

        print(f"  {r['effort']:<10} ${r['cost']:<11.6f} {r['elapsed_time']:<9.2f} "
              f"{r['total_tokens']:<10,} {reasoning_display:<12} {text_display:<10}")

    # 成本对比分析
    if len(results) > 1:
        print(f"\n  {'─' * 79}")
        print(f"  💰 Cost Comparison (relative to 'minimal'):")

        minimal_cost = next((r['cost'] for r in results if r['effort'] == 'minimal'), None)
        if minimal_cost and minimal_cost > 0:
            for r in results:
                if r['effort'] != 'minimal':
                    cost_ratio = r['cost'] / minimal_cost
                    extra_cost = r['cost'] - minimal_cost
                    print(f"     - {r['effort']:<10}: {cost_ratio:.2f}x cost (+${extra_cost:.6f})")

        # 推理 token 对比
        has_reasoning = any(r['reasoning_tokens'] > 0 for r in results)
        if has_reasoning:
            print(f"\n  🧠 Reasoning Tokens Comparison:")
            for r in results:
                if r['reasoning_tokens'] > 0:
                    reasoning_pct = (r['reasoning_tokens'] / r['completion_tokens'] * 100)
                    print(
                        f"     - {r['effort']:<10}: {r['reasoning_tokens']:,} tokens ({reasoning_pct:.1f}% of completion)")

        # 时间对比
        print(f"\n  ⏱️  Latency Comparison:")
        minimal_time = next((r['elapsed_time'] for r in results if r['effort'] == 'minimal'), None)
        if minimal_time and minimal_time > 0:
            for r in results:
                if r['effort'] != 'minimal':
                    time_ratio = r['elapsed_time'] / minimal_time
                    extra_time = r['elapsed_time'] - minimal_time
                    print(f"     - {r['effort']:<10}: {time_ratio:.2f}x time (+{extra_time:.2f}s)")

        # 质量对比（基于答案长度）
        print(f"\n  📏 Response Length (proxy for detail):")
        for r in results:
            print(f"     - {r['effort']:<10}: {r['response_length']:,} characters")

    # 推荐
    print(f"\n{'=' * 80}")
    print("  💡 RECOMMENDATIONS")
    print(f"{'=' * 80}")
    print(f"  When to use each level:")
    print(f"  - minimal: Fast responses, simple tasks, UI interactions")
    print(f"  - low:     Quick decisions, straightforward problems")
    print(f"  - medium:  Default choice, balanced performance (recommended)")
    print(f"  - high:    Complex logic, critical decisions, accuracy-first")
    print(f"\n  Trade-offs:")
    print(f"  - Cost increases with reasoning effort (more reasoning tokens)")
    print(f"  - Latency increases with reasoning effort (more processing time)")
    print(f"  - Quality generally improves with higher effort (better reasoning)")
    print(f"\n  API Usage Note:")
    print(f"  - Chat Completions API: Use reasoning_effort='medium' (top-level param)")
    print(f"  - Responses API: Use reasoning={{'effort': 'medium'}} (nested object)")
    print(f"{'=' * 80}\n")

    return True


if __name__ == "__main__":
    success = reasoning_effort_cost_comparison()
    exit(0 if success else 1)