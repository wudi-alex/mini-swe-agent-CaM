import time
from typing import List, Dict, Any


def test_prompt_caching_cost_fixed():
    """Test prompt caching cost savings - FIXED VERSION with correct cache extraction."""
    print("\n" + "=" * 80)
    print("  PROMPT CACHING COST TEST (FIXED) - GPT-4O-MINI")
    print("=" * 80)

    try:
        from minisweagent.models import get_model
        print("\n✓ Imported get_model")
    except ImportError as e:
        print(f"\n✗ Import failed: {e}")
        return False

    # 使用支持 caching 的模型
    model_name = "openai/gpt-5-mini"  # ✅ 已知支持 caching
    # model_name = "openai/gpt-5-mini"  # ❌ 当前有 bug

    print(f"\n{'=' * 80}")
    print(f"  Initializing model: {model_name}")
    print(f"  Note: GPT-5-mini has known caching issues, using gpt-4o-mini instead")
    print(f"{'=' * 80}")

    try:
        model = get_model(input_model_name=model_name, config={})
        print(f"✓ Model initialized: {type(model).__name__}")
    except Exception as e:
        print(f"✗ Model initialization failed: {e}")
        return False

    # 准备足够大的静态上下文（>1024 tokens）
    static_system_prompt = """You are an expert software engineer with extensive experience in:

**Python Programming:**
- Advanced Python features (decorators, metaclasses, context managers, generators)
- Async/await patterns and concurrent programming
- Type hints and static type checking with mypy
- Performance optimization and profiling
- Memory management and garbage collection
- Python internals and CPython implementation

**Software Architecture:**
- Microservices architecture and design patterns (SOLID, DRY, KISS)
- Domain-Driven Design (DDD) and hexagonal architecture
- Event-driven architecture and message queues
- RESTful API design and GraphQL
- Database design (SQL and NoSQL)
- Caching strategies (Redis, Memcached)
- Service mesh and API gateways

**Testing & Quality:**
- Test-Driven Development (TDD) and Behavior-Driven Development (BDD)
- Unit testing with pytest, unittest, and nose
- Integration testing and end-to-end testing
- Mocking and test doubles
- Property-based testing with Hypothesis
- Code coverage analysis
- Static analysis and linting (pylint, flake8, black, isort)

**DevOps & Infrastructure:**
- Containerization with Docker and Kubernetes
- CI/CD pipelines (GitHub Actions, GitLab CI, Jenkins)
- Infrastructure as Code (Terraform, CloudFormation)
- Cloud platforms (AWS, Azure, GCP)
- Monitoring and observability (Prometheus, Grafana, ELK stack)
- Logging best practices and distributed tracing

**Documentation Tools:**
- Sphinx documentation system
- reStructuredText and Markdown
- API documentation with Swagger/OpenAPI
- DocBook and LaTeX for PDF generation
- Documentation as Code principles
- Automated documentation generation

**Security:**
- OWASP Top 10 vulnerabilities
- Authentication and authorization (OAuth2, JWT, SAML)
- Encryption and cryptography
- Secure coding practices
- Dependency vulnerability scanning
- Security testing and penetration testing

**Performance:**
- Algorithm complexity analysis (Big O notation)
- Database query optimization
- Caching strategies and CDN usage
- Load balancing and horizontal scaling
- Profiling and benchmarking tools
- Memory leak detection and resolution

You provide clear, actionable, and well-structured guidance.
Always consider edge cases, error handling, maintainability, and scalability.
Your responses are detailed, technically accurate, and include code examples when appropriate."""

    static_context = """# Sphinx Project - Detailed Context

## Project Overview
Sphinx is a powerful documentation generator that converts reStructuredText files into various output formats (HTML, LaTeX, PDF, ePub, man pages, etc.). It's widely used in the Python community for creating technical documentation.

## Architecture Overview

### Core Components:

1. **Application Layer** (`sphinx/application.py`)
   - Main Sphinx class that coordinates all components
   - Manages configuration, extensions, and build process
   - Event system for hooks and callbacks

2. **Builders** (`sphinx/builders/`)
   - HTML Builder: Generates HTML documentation
   - LaTeX Builder: Creates LaTeX source for PDF generation
   - Text Builder: Plain text output
   - Custom builders can be added via extensions

3. **Writers** (`sphinx/writers/`)
   - LaTeXWriter: Converts doctree to LaTeX
   - HTMLWriter: Converts doctree to HTML
   - ManualPageWriter: Man page generation
   - Each writer handles format-specific rendering

4. **Directives & Roles** (`sphinx/directives/`, `sphinx/roles/`)
   - Code blocks: syntax highlighting for code examples
   - Admonitions: notes, warnings, important boxes
   - Cross-references: automatic linking between documents
   - Custom roles: inline markup (e.g., :code:, :math:)

5. **Domains** (`sphinx/domains/`)
   - Python domain: autodoc, function signatures, class documentation
   - JavaScript domain: JS API documentation
   - C/C++ domains: C/C++ API documentation
   - Each domain provides specialized directives and roles

## Key Technologies

### Pygments Integration
- Provides syntax highlighting for 500+ languages
- Generates tokens for each code element
- LaTeX output uses \\PYG{type}{content} macros
- HTML output uses <span class="..."> tags

### LaTeX Processing Chain
1. reStructuredText → Docutils doctree
2. Doctree → LaTeX source (via LaTeXWriter)
3. LaTeX source → PDF (via pdflatex/xelatex/lualatex)

### Recent Enhancement - PR #10251
**Feature**: Inline code syntax highlighting for :code: role
- Before: ``:python:`code``` → plain monospace text
- After: ``:python:`code``` → syntax-highlighted inline code

**Implementation Details**:
- Modified `sphinx/roles.py` to handle code role
- Updated `sphinx/writers/latex.py` for LaTeX output
- Added Pygments tokenization for inline code
- Wraps tokens in \\sphinxcode{\\sphinxupquote{...}}

**Problem Identified**:
- Extra whitespace added at start and end of inline code in PDF
- Caused by newlines in LaTeX macro expansion
- TeX treats newlines as spaces in certain contexts

## File Structure (Relevant to Bug)
````
sphinx/
├── writers/
│   └── latex.py          ← LaTeX output generation (PRIMARY FIX LOCATION)
├── roles.py              ← Role definitions including :code:
├── highlighting.py       ← Pygments integration
└── util/
    └── texescape.py      ← LaTeX escaping utilities

tests/
└── test_build_latex.py   ← LaTeX output tests
````

## Technical Background

### LaTeX Whitespace Handling
- TeX ignores spaces after control sequences
- Newlines are treated as spaces
- Percent signs (%) comment out newlines
- \\sphinxcode{\\sphinxupquote{CONTENT}} structure

### Current Bug Behavior
````latex
% Current (incorrect):
\\sphinxcode{\\sphinxupquote{
\\PYG{k}{def} ... \\PYG{k}{pass}
}}

% Desired (correct):
\\sphinxcode{\\sphinxupquote{%
\\PYG{k}{def} ... \\PYG{k}{pass}%
}}
````

The newlines after opening brace and before closing brace create unwanted spaces in PDF output.

## Testing Environment
- Python 3.9+
- Sphinx 5.x
- LaTeX distribution (TeX Live, MiKTeX)
- Pygments 2.x

## Build Process
````bash
# Create test documentation
sphinx-quickstart
# Edit index.rst with inline code examples
# Build LaTeX
make latex
# Generate PDF
cd _build/latex && make
```"""

    test_queries = [
        "What is the core issue?",
        "Which file to modify?",
        "What's the fix approach?",
        "How to test the fix?",
        "Any side effects?",
    ]

    # 估算 token 数
    estimated_tokens = (len(static_system_prompt) + len(static_context)) / 4
    print(f"\n  Estimated static context: ~{estimated_tokens:.0f} tokens")
    print(f"  Minimum required for caching: 1024 tokens")
    print(f"  Cache eligible: {'✅ YES' if estimated_tokens >= 1024 else '❌ NO'}\n")

    print(f"{'=' * 80}")
    print("  Test Plan:")
    print(f"{'=' * 80}")
    print(f"  Number of queries: {len(test_queries)}")
    print(f"  Expected behavior:")
    print(f"    - Query 1: Full processing (cache WRITE)")
    print(f"    - Query 2-5: Cache READ (90% cost reduction on cached portion)")
    print(f"{'=' * 80}\n")

    results = []

    for i, query in enumerate(test_queries, 1):
        print(f"\n{'─' * 80}")
        print(f"  Query {i}/{len(test_queries)}")
        print(f"{'─' * 80}")
        print(f"  Question: {query}")

        # 构建消息（移除 timestamp 以保持一致性）
        messages = [
            {
                'role': 'system',
                'content': static_system_prompt
            },
            {
                'role': 'user',
                'content': static_context + f"\n\n## Your Task:\n{query}\n\nProvide a brief answer (2-3 sentences)."
            }
        ]

        cost_before = model.cost if hasattr(model, 'cost') else 0.0

        try:
            start_time = time.time()
            response = model.query(messages)
            elapsed = time.time() - start_time

            cost_after = model.cost if hasattr(model, 'cost') else 0.0
            query_cost = cost_after - cost_before

            content = response.get("content", "")

            # ✅ 修正：按照实际响应格式提取 token 信息
            extra = response.get("extra", {})
            response_data = extra.get("response", {})

            # 支持字典和对象两种访问方式
            def safe_get(obj, *keys, default=0):
                """安全地从嵌套字典/对象中获取值"""
                for key in keys:
                    if obj is None:
                        return default
                    if isinstance(obj, dict):
                        obj = obj.get(key)
                    else:
                        obj = getattr(obj, key, None)
                return obj if obj is not None else default

            # 提取 usage 信息
            usage = safe_get(response_data, 'usage')

            if usage:
                prompt_tokens = safe_get(usage, 'prompt_tokens', default=0)
                completion_tokens = safe_get(usage, 'completion_tokens', default=0)
                total_tokens = safe_get(usage, 'total_tokens', default=0)

                # ✅ 正确路径：usage.prompt_tokens_details.cached_tokens
                prompt_tokens_details = safe_get(usage, 'prompt_tokens_details')
                cached_tokens = safe_get(prompt_tokens_details, 'cached_tokens', default=0)

                # 额外信息（如果有）
                completion_tokens_details = safe_get(usage, 'completion_tokens_details')
                reasoning_tokens = safe_get(completion_tokens_details, 'reasoning_tokens', default=0)
            else:
                prompt_tokens = completion_tokens = total_tokens = cached_tokens = reasoning_tokens = 0

            # 打印调试信息（第一次查询时）
            if i == 1:
                print(f"\n  🔍 Debug - Response Structure:")
                print(f"     - response_data type: {type(response_data)}")
                print(f"     - usage type: {type(usage)}")
                if usage:
                    print(f"     - usage keys: {list(usage.keys()) if isinstance(usage, dict) else dir(usage)}")

            result = {
                'query_num': i,
                'query': query,
                'elapsed_time': elapsed,
                'query_cost': query_cost,
                'total_cost': cost_after,
                'prompt_tokens': prompt_tokens,
                'completion_tokens': completion_tokens,
                'total_tokens': total_tokens,
                'cached_tokens': cached_tokens,
                'reasoning_tokens': reasoning_tokens,
                'response_length': len(content)
            }
            results.append(result)

            # 打印结果
            print(f"\n  ✓ Query completed in {elapsed:.2f}s")
            print(f"  💰 Cost Breakdown:")
            print(f"     - This query: ${query_cost:.6f}")
            print(f"     - Total cost: ${cost_after:.6f}")

            if prompt_tokens > 0:
                cache_pct = (cached_tokens / prompt_tokens * 100) if prompt_tokens > 0 else 0
                new_tokens = prompt_tokens - cached_tokens

                print(f"\n  📊 Token Usage:")
                print(f"     - Total prompt tokens: {prompt_tokens:,}")
                print(f"     - Cached tokens: {cached_tokens:,} ({cache_pct:.1f}%)")
                print(f"     - New tokens: {new_tokens:,}")
                print(f"     - Completion tokens: {completion_tokens:,}")
                if reasoning_tokens > 0:
                    print(f"     - Reasoning tokens: {reasoning_tokens:,}")
                print(f"     - Total tokens: {total_tokens:,}")

            print(f"\n  📝 Response preview:")
            preview = content[:200].replace('\n', ' ')
            print(f"     {preview}...")

            # 缓存命中提示
            if i == 1:
                if cached_tokens > 0:
                    print(f"\n  ⚠️  Unexpected: First query had {cached_tokens} cached tokens!")
                else:
                    print(f"\n  ✅ First query: No cache (expected)")
            elif cached_tokens > 0:
                print(f"\n  ✅ CACHE HIT!")
                print(f"     - Reused from previous query: {cached_tokens:,} tokens")
            else:
                print(f"\n  ❌ CACHE MISS (unexpected for query {i})")

            # 费用对比
            if i > 1:
                first_cost = results[0]['query_cost']
                savings = first_cost - query_cost
                savings_pct = (savings / first_cost * 100) if first_cost > 0 else 0
                print(f"\n  💡 Cost Comparison:")
                print(f"     - First query cost: ${first_cost:.6f}")
                print(f"     - This query cost: ${query_cost:.6f}")
                print(f"     - Savings: ${savings:.6f} ({savings_pct:.1f}%)")

        except Exception as e:
            print(f"\n  ✗ Query failed: {e}")
            import traceback
            traceback.print_exc()
            continue

        # 延迟但保持在缓存时间内
        if i < len(test_queries):
            time.sleep(1)

    # 汇总报告
    print(f"\n\n{'=' * 80}")
    print("  SUMMARY - CACHE EFFECTIVENESS ANALYSIS")
    print(f"{'=' * 80}\n")

    if not results:
        print("  ✗ No successful queries to analyze")
        return False

    print(f"  {'#':<4} {'Cost ($)':<13} {'Prompt':<10} {'Cached':<10} {'Cache %':<10} {'Status':<20}")
    print(f"  {'-' * 79}")

    for r in results:
        cache_pct = (r['cached_tokens'] / r['prompt_tokens'] * 100) if r['prompt_tokens'] > 0 else 0
        if r['query_num'] == 1:
            status = "🔵 FIRST (cache write)" if r['cached_tokens'] == 0 else "⚠️  UNEXPECTED CACHE"
        elif r['cached_tokens'] > 0:
            status = "✅ CACHE HIT"
        else:
            status = "❌ CACHE MISS"

        print(f"  {r['query_num']:<4} ${r['query_cost']:<12.6f} {r['prompt_tokens']:<10,} "
              f"{r['cached_tokens']:<10,} {cache_pct:<9.1f}% {status:<20}")

    # 统计分析
    if len(results) > 1:
        total_cached = sum(r['cached_tokens'] for r in results[1:])
        total_prompt = sum(r['prompt_tokens'] for r in results[1:])
        cache_hits = sum(1 for r in results[1:] if r['cached_tokens'] > 0)
        overall_cache_rate = (total_cached / total_prompt * 100) if total_prompt > 0 else 0

        first_query_cost = results[0]['query_cost']
        actual_total = sum(r['query_cost'] for r in results)
        cost_without_cache = first_query_cost * len(results)
        total_savings = cost_without_cache - actual_total
        savings_pct = (total_savings / cost_without_cache * 100) if cost_without_cache > 0 else 0

        print(f"\n  {'─' * 79}")
        print(f"  💰 Financial Summary:")
        print(f"     - Total actual cost: ${actual_total:.6f}")
        print(f"     - Cost without caching: ${cost_without_cache:.6f}")
        print(f"     - Total savings: ${total_savings:.6f} ({savings_pct:.1f}%)")

        print(f"\n  📊 Cache Performance:")
        print(f"     - Queries with cache hits: {cache_hits}/{len(results) - 1}")
        print(f"     - Overall cache rate: {overall_cache_rate:.1f}%")
        print(f"     - Total cached tokens: {total_cached:,}")
        print(f"     - Average cached per hit: {total_cached / cache_hits:,.0f} tokens" if cache_hits > 0 else "")

        if total_cached == 0:
            print(f"\n  ⚠️  WARNING: No cache hits detected!")
            print(f"     Possible reasons:")
            print(f"     1. Model doesn't support caching (GPT-5-mini/nano have bugs)")
            print(f"     2. Prompt too small (need ≥1024 tokens)")
            print(f"     3. Messages not identical enough")
            print(f"     4. Cache expiry (unlikely with 1s delays)")
            print(f"\n  💡 Recommendation: Try openai/gpt-4o-mini instead")
        else:
            print(f"\n  ✅ Caching is working! {savings_pct:.1f}% cost reduction achieved.")

    print(f"\n{'=' * 80}\n")
    return True


if __name__ == "__main__":
    success = test_prompt_caching_cost_fixed()
    exit(0 if success else 1)

# 原来的结构：
response = {
    "extra": {
        "response": {
            "usage": {
                "prompt_tokens_details": {
                    "cached_tokens": 0  # ← 这里
                }
            }
        }
    }
}


def safe_get(obj, *keys, default=0):
    """支持字典和对象两种访问方式"""
    for key in keys:
        if obj is None:
            return default
        if isinstance(obj, dict):
            obj = obj.get(key)
        else:
            obj = getattr(obj, key, None)
    return obj if obj is not None else default


