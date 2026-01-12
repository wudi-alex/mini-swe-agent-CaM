import subprocess
import textwrap
import sys
import re


def exec_bash_cmd(cmd, timeout=None, auto_fix=True, max_retries=2):
    cmd = textwrap.dedent(cmd).strip()

    original_cmd = cmd
    retry_count = 0

    while retry_count <= max_retries:
        try:
            if retry_count > 0 and auto_fix:
                cmd = _auto_fix_bash_escaping(original_cmd, retry_count)

            result = subprocess.run(
                cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                encoding='utf-8',
                errors='replace',
                executable='/bin/bash',
                timeout=timeout
            )

            output = result.stdout

            try:
                print('bash execution output:\n', output)
            except UnicodeEncodeError:
                terminal_encoding = sys.stdout.encoding or 'ascii'
                safe_output = output.encode(terminal_encoding, errors='replace').decode(terminal_encoding)
                print('bash execution output:\n', safe_output)

            if result.returncode != 0:
                print(f"Command exited with non-zero status: {result.returncode}")

                if auto_fix and retry_count < max_retries and _is_escaping_error(output):
                    retry_count += 1
                    continue

                return output
            # if retry_count > 0:
            #     print(f"[AUTO-FIX] Successfully fixed after {retry_count} attempt(s)")
            return output

        except subprocess.TimeoutExpired:
            print(f"Execution timed out after {timeout} seconds")
            return f"Timeout after {timeout}s"

        except Exception as e:
            print(f"Execution failed: {e}")

            if auto_fix and retry_count < max_retries and _is_escaping_error(str(e)):
                retry_count += 1
                continue

            return str(e)

        finally:
            print("""Directly response 'submit()' to finish, no other tokens.""")

    return "Failed after all retry attempts"


def _is_escaping_error(error_msg):
    """检测是否是转义相关的错误"""
    escaping_patterns = [
        r"unexpected.*quote",
        r"unterminated.*string",
        r"unmatched.*quote",
        r"syntax error.*quote",
        r"invalid syntax.*quote",
        r"EOL while scanning",
        r"unexpected token",
        r"bad substitution",
        r"command not found.*['\"]",
    ]

    error_lower = error_msg.lower()
    return any(re.search(pattern, error_lower, re.IGNORECASE) for pattern in escaping_patterns)


def _auto_fix_bash_escaping(cmd, attempt):
    """
    自动修复常见的 bash 转义问题

    策略：
    1. 第一次重试：如果检测到 python 代码，使用 HEREDOC
    2. 第二次重试：使用 base64 编码避免所有转义问题
    """
    if attempt == 1:
        # 策略 1: 检测是否包含 Python 代码，使用 HEREDOC
        if _contains_python_code(cmd):
            return _convert_to_heredoc(cmd)
        else:
            # 对于非 Python 命令，转义特殊字符
            return _escape_special_chars(cmd)

    elif attempt == 2:
        # 策略 2: 使用 base64 编码（终极方案）
        return _encode_with_base64(cmd)

    return cmd


def _contains_python_code(cmd):
    """检测命令是否包含 Python 代码"""
    python_indicators = [
        'python', 'python3',
        'import ', 'from ',
        'def ', 'class ',
        'print(', 'if __name__',
    ]
    return any(indicator in cmd for indicator in python_indicators)


def _convert_to_heredoc(cmd):
    """将 Python 代码转换为 HEREDOC 格式"""
    # 提取 python 命令和代码
    if 'python' in cmd and ('-c' in cmd or '<<' not in cmd):
        # 尝试提取 python -c 'code' 格式
        match = re.search(r'python3?\s+-c\s+["\'](.+)["\']', cmd, re.DOTALL)
        if match:
            python_code = match.group(1)
            # 去除转义字符
            python_code = python_code.replace(r'\"', '"').replace(r"\'", "'").replace(r'\\', '\\')

            return f'''python3 <<'PYTHON_EOF'
{python_code}
PYTHON_EOF'''

    return cmd


def _escape_special_chars(cmd):
    """转义 bash 特殊字符（保守策略）"""
    # 对于包含引号的字符串，尝试使用单引号包裹
    # 这是一个简化版本，实际情况可能需要更复杂的逻辑

    # 如果命令包含双引号但不包含单引号，用单引号包裹
    if '"' in cmd and "'" not in cmd:
        # 找到 -c 参数后的内容
        match = re.search(r'(-c\s+)(.+)', cmd, re.DOTALL)
        if match:
            prefix = match.group(1)
            code = match.group(2).strip()
            # 移除原有的引号
            code = code.strip('"').strip("'")
            return cmd[:match.start(1)] + prefix + f"'{code}'"

    return cmd


def _encode_with_base64(cmd):
    """使用 base64 编码避免所有转义问题（终极方案）"""
    import base64

    # 提取实际要执行的 Python 代码
    if 'python' in cmd:
        match = re.search(r'python3?\s+(?:-c\s+)?["\']?(.+?)["\']?$', cmd, re.DOTALL)
        if match:
            python_code = match.group(1).strip().strip('"').strip("'")

            # Base64 编码
            encoded = base64.b64encode(python_code.encode('utf-8')).decode('ascii')

            return f"echo '{encoded}' | base64 -d | python3"

    return cmd

def submit():
    """
    Submit final output by adding all changes to git and showing diff
    """
    command = "echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT && git add -A && git diff --cached"

    result = subprocess.run(
        command,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
        errors='replace'
    )

    print(result.stdout)


from functools import wraps


def bug_reproduction(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        # TODO: Implement logic to trigger the bug reproduction workflow
        return func(*args, **kwargs)

    return wrapper


def bug_localization(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        # TODO: Implement logic to identify suspicious lines or functions
        return func(*args, **kwargs)

    return wrapper


def test_generation(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        # TODO: Implement logic for test case generation
        return func(*args, **kwargs)

    return wrapper


def patch_generation(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        # TODO: Implement logic to synthesize patches
        return func(*args, **kwargs)

    return wrapper


def patch_verification(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        # TODO: Implement logic to validate the candidate patch
        return func(*args, **kwargs)

    return wrapper


def debug(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        # TODO: Implement general debugging utilities
        return func(*args, **kwargs)

    return wrapper
