import ast
import os
import subprocess
import json
import re
import tempfile


def find_definition_file(names, search_path="."):
    """
    查找类或函数定义并打印结果

    参数:
        names: 要查找的类名或函数名列表
        search_path: 搜索路径，默认为当前目录

    输出格式: file_path name
    """
    for name in names:
        files = set()

        # 搜索类定义
        cmd = ['grep', '-rl', '-E', f"^class\\s+{name}\\s*[:(]",
               search_path, '--include=*.py']
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0 and result.stdout.strip():
                files.update(result.stdout.strip().split('\n'))
        except:
            pass

        cmd = ['grep', '-rl', '-E', f"^def\\s+{name}\\s*\\(",
               search_path, '--include=*.py']
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0 and result.stdout.strip():
                files.update(result.stdout.strip().split('\n'))
        except:
            pass

        if files:
            for file_path in sorted(files):
                if file_path:
                    print(f"{file_path} {name}")
        else:
            print(f"{name} not found.")


def print_definition(name_file_list, show_comments=False):
    """
    打印类或函数的定义代码

    参数:
        name_file_list: [(name, file_path), ...] 列表
        show_comments: 是否显示注释，默认False

    输出格式:
        file_path name:
        line_num: code
    """
    for name, file_path in name_file_list:
        try:
            with open(file_path, 'r') as f:
                content = f.read()
                lines = content.splitlines()

            tree = ast.parse(content)
            definitions = _find_definitions(tree, name)

            if not definitions:
                print(f"{file_path} {name}: not found\n")
                continue

            for node in definitions:
                print(f"{file_path} {name}:")
                _print_code_with_lines(lines, node, show_comments)
                print()

        except Exception as e:
            print(f"{file_path} {name}: error reading file\n")


def _find_definitions(tree, name):
    """使用ast查找类或函数定义"""
    definitions = []

    for node in ast.walk(tree):
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name == name:
                definitions.append(node)

    return definitions


def _get_docstring_lines(node):
    """获取docstring所在的行号集合（递归处理嵌套的函数和类）"""
    docstring_lines = set()

    if not isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
        return docstring_lines

    if not node.body:
        return docstring_lines

    # 检查第一个语句是否是docstring
    first_stmt = node.body[0]
    if isinstance(first_stmt, ast.Expr):
        value = first_stmt.value
        # Python 3.8+ 使用 Constant，旧版本使用 Str
        is_docstring = False
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            is_docstring = True
        elif hasattr(ast, 'Str') and isinstance(value, ast.Str):
            is_docstring = True

        if is_docstring:
            # 添加docstring的所有行
            for line_num in range(first_stmt.lineno - 1, first_stmt.end_lineno):
                docstring_lines.add(line_num)

    # 递归处理body中的所有嵌套函数和类
    for item in node.body:
        if isinstance(item, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            docstring_lines.update(_get_docstring_lines(item))

    return docstring_lines


def _print_code_with_lines(lines, node, show_comments):
    """打印带行号的代码"""
    start_line = node.lineno - 1
    end_line = node.end_lineno

    # 获取docstring的行范围
    docstring_lines = set()
    if not show_comments:
        docstring_lines = _get_docstring_lines(node)

    for i in range(start_line, end_line):
        if i >= len(lines):
            break

        line = lines[i]

        # 过滤注释和docstring
        if not show_comments:
            stripped = line.strip()
            # 跳过#注释
            if stripped.startswith('#'):
                continue
            # 跳过docstring行
            if i in docstring_lines:
                continue

        print(f"{i + 1}: {line}")


def remove_comments_with_mapping(code):
    """
    Remove comments from Python code and create line mapping

    Args:
        code: Python code string

    Returns:
        Tuple of (code_no_comments, line_mapping)
        line_mapping[i] = original line number for comment-free line i
    """
    lines = code.split('\n')
    result_lines = []
    line_mapping = []
    in_multiline = False
    multiline_char = None

    for orig_idx, line in enumerate(lines):
        if in_multiline:
            if multiline_char * 3 in line:
                in_multiline = False
                idx = line.find(multiline_char * 3)
                remaining = line[idx + 3:].strip()
                if remaining:
                    result_lines.append(remaining)
                    line_mapping.append(orig_idx)
            continue

        stripped = line.strip()
        if stripped.startswith('"""') or stripped.startswith("'''"):
            quote_char = stripped[0]
            if stripped.count(quote_char * 3) >= 2:
                continue
            else:
                in_multiline = True
                multiline_char = quote_char
                continue

        processed_line = line
        if '#' in line:
            in_string = False
            string_char = None
            for i, char in enumerate(line):
                if char in ('"', "'") and (i == 0 or line[i - 1] != '\\'):
                    if not in_string:
                        in_string = True
                        string_char = char
                    elif char == string_char:
                        in_string = False
                elif char == '#' and not in_string:
                    processed_line = line[:i].rstrip()
                    break
        else:
            processed_line = line.rstrip()

        result_lines.append(processed_line)
        line_mapping.append(orig_idx)

    return '\n'.join(result_lines), line_mapping


def normalize(text):
    """Normalize text, handle newlines and extra spaces"""
    lines = text.splitlines()
    normalized_lines = [line.rstrip() for line in lines]
    return '\n'.join(normalized_lines)


def find_code_block_lines(file_content, old_code):
    """
    Find the line range where old_code exists in file_content
    Comparison is done without comments

    Args:
        file_content: File content as string
        old_code: Code block to find

    Returns:
        Tuple of (start_line, end_line) in original file line numbers (0-based),
        or (None, None) if not found
    """
    old_code_normalized = normalize(old_code)
    old_code_no_comments, _ = remove_comments_with_mapping(old_code_normalized)
    old_lines = [line.strip() for line in old_code_no_comments.split('\n') if line.strip()]

    if not old_lines:
        return None, None

    file_content_no_comments, line_mapping = remove_comments_with_mapping(file_content)
    file_lines_no_comments = [line.strip() for line in file_content_no_comments.split('\n')]

    num_old = len(old_lines)
    num_file = len(file_lines_no_comments)

    for i in range(num_file):
        match_count = 0
        old_idx = 0
        file_idx = i
        first_match_idx = None
        last_match_idx = None

        while old_idx < num_old and file_idx < num_file:
            if file_lines_no_comments[file_idx] == old_lines[old_idx]:
                if first_match_idx is None:
                    first_match_idx = file_idx
                last_match_idx = file_idx
                match_count += 1
                old_idx += 1
                file_idx += 1
            elif not file_lines_no_comments[file_idx]:
                file_idx += 1
            else:
                break

        if match_count == num_old:
            orig_start = line_mapping[first_match_idx]
            orig_end = line_mapping[last_match_idx]
            return orig_start, orig_end

    return None, None


def code_replace(file_path, old_code, new_code):
    """
    Replace code in Python file and perform lint check
    Ignores comments when matching old code
    Replaces by line range (including comment lines)

    Args:
        file_path: Path to Python file
        old_code: Code to be replaced (comments are ignored during matching)
        new_code: New code

    Returns:
        bool: Whether replacement was successful
    """
    if not os.path.exists(file_path):
        print("Error: File '{}' does not exist".format(file_path))
        return False

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            original_content = f.read()
    except Exception as e:
        print("Error: Cannot read file {}".format(e))
        return False

    start_line, end_line = find_code_block_lines(original_content, old_code)

    if start_line is None:
        print("Error: Code to replace not found in file")
        print("Looking for:\n{}".format(old_code))
        return False

    file_lines = original_content.split('\n')
    new_code_normalized = normalize(new_code)
    new_code_lines = new_code_normalized.split('\n')

    new_file_lines = (
            file_lines[:start_line] +
            new_code_lines +
            file_lines[end_line + 1:]
    )

    new_content = '\n'.join(new_file_lines)

    tmp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8')
    tmp_file.write(new_content)
    tmp_file.close()
    tmp_path = tmp_file.name

    try:
        result = subprocess.run(
            ['python', '-m', 'py_compile', tmp_path],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode != 0:
            print("Error: Syntax error in replaced code")
            print(result.stderr)
            return False

        try:
            flake_result = subprocess.run(
                ['pyflakes', tmp_path],
                capture_output=True,
                text=True,
                timeout=10
            )
            if flake_result.stdout:
                print("Warning: Lint check found issues")
                print(flake_result.stdout)
        except FileNotFoundError:
            pass

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)

        print("Replaced")
        return True

    except subprocess.TimeoutExpired:
        print("Error: Lint check timeout")
        return False
    except Exception as e:
        print("Error: {}".format(e))
        return False
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def code_insert(file_path, new_code, line_number):
    """
    Insert code at specified line number in Python file and perform lint check

    Args:
        file_path: Path to Python file
        new_code: Code to insert
        line_number: Line number to insert at (1-based indexing)

    Returns:
        bool: Whether insertion was successful
    """
    # Check if file exists
    if not os.path.exists(file_path):
        print("Error: File '{}' does not exist".format(file_path))
        return False

    # Read file content
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except Exception as e:
        print("Error: Cannot read file - {}".format(e))
        return False

    # Validate line number (1-based indexing)
    if line_number < 1:
        print("Error: Line number must be >= 1")
        return False

    if line_number > len(lines) + 1:
        print("Error: Line number {} exceeds file length (max: {})".format(
            line_number, len(lines) + 1))
        return False

    # Prepare new code with proper newline
    if not new_code.endswith('\n'):
        new_code = new_code + '\n'

    # Insert new code at specified line (convert to 0-based index)
    insert_index = line_number - 1
    lines.insert(insert_index, new_code)

    # Join all lines to create new content
    new_content = ''.join(lines)

    # Test new code in temporary file first
    tmp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8')
    tmp_file.write(new_content)
    tmp_file.close()
    tmp_path = tmp_file.name

    try:
        # Use py_compile for syntax check
        result = subprocess.run(
            ['python', '-m', 'py_compile', tmp_path],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode != 0:
            print("Error: Syntax error after code insertion")
            print(result.stderr)
            return False

        # Optional: Use pyflakes for deeper check
        try:
            flake_result = subprocess.run(
                ['pyflakes', tmp_path],
                capture_output=True,
                text=True,
                timeout=10
            )
            if flake_result.stdout:
                print("Warning: Lint check found issues")
                print(flake_result.stdout)
        except FileNotFoundError:
            # pyflakes not installed, skip
            pass

        # Write new content to original file
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)

        print("Inserted")
        return True

    except subprocess.TimeoutExpired:
        print("Error: Lint check timeout")
        return False
    except Exception as e:
        print("Error: {}".format(e))
        return False
    finally:
        # Clean up temporary file
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def show_code_context(file_path, lines, show_comments=False):
    """
    Display code lines from a file with line numbers.

    Args:
        file_path: Path to the file to display
        lines: List or tuple of [start_line, end_line] (1-indexed, inclusive)
        show_comments: Whether to show comments and docstrings (default: False)

    Returns:
        None
    """
    # Validate inputs
    if not os.path.exists(file_path):
        print(f"Error: File not found: {file_path}")
        return

    if len(lines) != 2:
        print("Error: lines must be [start_line, end_line]")
        return

    start_line, end_line = lines

    if start_line < 1 or end_line < start_line:
        print(f"Error: Invalid line range [{start_line}, {end_line}]")
        return

    try:
        # Read the file
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            file_lines = content.splitlines()

        # Validate line numbers
        total_lines = len(file_lines)
        if start_line > total_lines:
            print(f"Error: Start line {start_line} exceeds file length ({total_lines} lines)")
            return

        # Adjust end_line if it exceeds file length
        if end_line > total_lines:
            print(f"Warning: End line {end_line} exceeds file length ({total_lines} lines)")
            end_line = total_lines

        # Get docstring lines if filtering comments
        docstring_lines = set()
        if not show_comments and file_path.endswith('.py'):
            try:
                tree = ast.parse(content)
                docstring_lines = _get_all_docstring_lines(tree)
            except:
                pass  # If parsing fails, just skip docstring filtering

        # Display lines
        for i in range(start_line - 1, end_line):  # Convert to 0-indexed
            line_num = i + 1
            line = file_lines[i]

            # Filter comments and docstrings
            if not show_comments:
                stripped = line.strip()
                # Skip # comments
                if stripped.startswith('#'):
                    continue
                # Skip docstring lines
                if i in docstring_lines:
                    continue

            print(f"{line_num:4d} {line}")

        return

    except UnicodeDecodeError:
        print(f"Error: Unable to decode file {file_path} (not a text file?)")
        return
    except Exception as e:
        print(f"Error reading file: {e}")
        return


def _get_all_docstring_lines(tree):
    """Get all docstring line numbers in the AST tree"""
    docstring_lines = set()

    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            if not node.body:
                continue

            # Check if first statement is a docstring
            first_stmt = node.body[0]
            if isinstance(first_stmt, ast.Expr):
                value = first_stmt.value
                is_docstring = False
                if isinstance(value, ast.Constant) and isinstance(value.value, str):
                    is_docstring = True
                elif hasattr(ast, 'Str') and isinstance(value, ast.Str):
                    is_docstring = True

                if is_docstring:
                    for line_num in range(first_stmt.lineno - 1, first_stmt.end_lineno):
                        docstring_lines.add(line_num)

    return docstring_lines


def exec_bash_cmd(cmd):
    """
    Execute a bash command and display the output.

    Args:
        cmd: String containing the bash command to execute

    Returns:
        Dictionary containing:
            - 'returncode': Exit code of the command (0 for success)
            - 'stdout': Standard output as string
            - 'stderr': Standard error as string
            - 'success': Boolean indicating if command succeeded
    """
    result = subprocess.run(
        cmd,
        shell=True,
        capture_output=True,
        text=True,
        executable='/bin/bash'
    )

    print('bash execution output:\n', result.stdout)


def save_code_to_file(code_str, file_path):
    """
    Save code string to a specified file path.

    Args:
        code_str: String containing the code to save
        file_path: Path where the file should be saved

    Returns:
        True if successful, False otherwise
    """
    try:
        # Create directory if it doesn't exist
        dir_name = os.path.dirname(file_path)
        if dir_name and not os.path.exists(dir_name):
            os.makedirs(dir_name)

        # Write code to file
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(code_str)

        return

    except PermissionError:
        print(f"Error: Permission denied to write to {file_path}")
        return
    except Exception as e:
        print(f"Error saving file: {e}")
        return


def submit():
    """
    执行提交命令并返回 git diff 的 patch 内容

    Args:
        cwd: 工作目录路径，默认为当前目录
        timeout: 命令超时时间（秒），默认 30 秒

    Returns:
        dict: 包含 returncode, output, stderr 的字典
    """
    command = "echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT && git add -A && git diff --cached"

    result = subprocess.run(
        command,
        shell=True,  # 需要 shell=True 来执行 && 连接的命令
        capture_output=True,  # 捕获 stdout 和 stderr
        text=True,  # 以文本模式返回（而不是字节）
        encoding='utf-8',
        errors='replace'  # 处理编码错误
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
