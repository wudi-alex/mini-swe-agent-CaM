import subprocess
import textwrap
import sys
import re
import base64


def exec_code(code_string):
    old_stdout = sys.stdout
    sys.stdout = StringIO()

    try:
        exec(code_string)
        output = sys.stdout.getvalue()
        sys.stdout = old_stdout
        print(output)
    except Exception as e:
        sys.stdout = old_stdout
        print(f"Error: {e}")


def exec_bash_cmd(cmd, timeout=None, auto_fix=True, max_retries=2):
    """
    Execute bash command with automatic escaping error fixes.

    Handles complex Python code with nested quotes by using temp files.
    Auto-retries on syntax/escaping errors using progressively safer methods.
    """
    cmd = textwrap.dedent(cmd).strip()

    if auto_fix and _needs_heredoc_fix(cmd):
        cmd = _fix_heredoc_to_tempfile(cmd)

    original_cmd = cmd

    for attempt in range(max_retries + 1):
        try:
            if attempt > 0 and auto_fix:
                cmd = _retry_with_fix(original_cmd, attempt)
                print(f"[AUTO-FIX] Retry {attempt}: Using safer execution method")

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
                encoding = sys.stdout.encoding or 'ascii'
                safe_output = output.encode(encoding, errors='replace').decode(encoding)
                print('bash execution output:\n', safe_output)

            if result.returncode != 0:
                print(f"Command exited with non-zero status: {result.returncode}")
                if auto_fix and attempt < max_retries and _is_syntax_error(output):
                    continue
                return output

            if attempt > 0:
                print(f"[AUTO-FIX] Fixed after {attempt} attempt(s)")

            return output

        except subprocess.TimeoutExpired:
            print(f"Execution timed out after {timeout} seconds")
            return f"Timeout after {timeout}s"

        except Exception as e:
            print(f"Execution failed: {e}")
            if auto_fix and attempt < max_retries:
                continue
            return str(e)

        finally:
            if attempt == 0 or attempt >= max_retries:
                print("Limit your response to exactly one function definition per turn!")
                print("Response with 'submit()' to finish!")

    return "Failed after all retry attempts"


def _needs_heredoc_fix(cmd):
    """Check if command contains HEREDOC with complex quotes."""
    if 'python' not in cmd.lower() or '<<' not in cmd:
        return False

    code = _extract_heredoc(cmd)
    if not code:
        return False

    complex_patterns = [
        r'["\'].*%[sd].*["\']',
        r'["\'].*\\["\'].*["\']',
        r'f["\'].*\{.*\}.*["\']',
    ]
    return any(re.search(p, code) for p in complex_patterns)


def _extract_heredoc(cmd):
    """Extract Python code from HEREDOC format."""
    match = re.search(r'python[3]?\s+(?:-\s+)?<<[\'"]?(\w+)[\'"]?\s*\n(.*?)\n\1',
                      cmd, re.DOTALL)
    return match.group(2) if match else None


def _fix_heredoc_to_tempfile(cmd):
    """Convert HEREDOC to bash tempfile execution (most reliable method)."""
    code = _extract_heredoc(cmd)
    if not code:
        return cmd

    python_cmd = 'python3' if 'python3' in cmd else 'python'

    post_match = re.search(r'<<[\'"]?\w+[\'"]?\s*\n.*?\n\w+\s*\n(.*)', cmd, re.DOTALL)
    post_cmds = post_match.group(1).strip() if post_match else ''

    new_cmd = f'''tmpfile=$(mktemp --suffix=.py)
cat > "$tmpfile" <<'EOF'
{code}
EOF
{python_cmd} "$tmpfile"
ret=$?
rm -f "$tmpfile"
'''

    if post_cmds:
        new_cmd += f"(exit $ret) && {post_cmds}"
    else:
        new_cmd += "exit $ret"

    return new_cmd


def _is_syntax_error(output):
    """Detect syntax/escaping errors in output."""
    error_patterns = [
        'SyntaxError', 'unexpected.*quote', 'unterminated.*string',
        'invalid syntax', 'unexpected token', 'EOL while scanning'
    ]
    return any(re.search(p, output, re.I) for p in error_patterns)


def _retry_with_fix(cmd, attempt):
    """Apply progressively safer fix strategies."""
    if attempt == 1:
        code = _extract_heredoc(cmd) or _extract_python_c(cmd)
        if code:
            return _make_tempfile_cmd(code, cmd)

    if attempt == 2:
        code = _extract_heredoc(cmd) or _extract_python_c(cmd)
        if code:
            return _make_base64_cmd(code, cmd)

    return cmd


def _extract_python_c(cmd):
    """Extract code from python -c 'code' format."""
    match = re.search(r'python3?\s+-c\s+["\'](.+?)["\']', cmd, re.DOTALL)
    return match.group(1) if match else None


def _make_tempfile_cmd(code, original_cmd):
    """Create bash tempfile command."""
    python_cmd = 'python3' if 'python3' in original_cmd else 'python'
    return f'''tmpfile=$(mktemp --suffix=.py)
cat > "$tmpfile" <<'EOF'
{code}
EOF
{python_cmd} "$tmpfile"
ret=$?
rm -f "$tmpfile"
exit $ret
'''


def _make_base64_cmd(code, original_cmd):
    """Create base64-encoded command (ultimate fallback)."""
    python_cmd = 'python3' if 'python3' in original_cmd else 'python'
    encoded = base64.b64encode(code.encode('utf-8')).decode('ascii')
    return f"echo '{encoded}' | base64 -d | {python_cmd}"


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
