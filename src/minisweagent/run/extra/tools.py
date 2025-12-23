import ast
import os
import subprocess
import json
import re


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


def code_replace(file_path, old_code_lines, new_code):
    """
    Replace lines of code in a file with new code and validate syntax.

    Args:
        file_path: Path to the file to modify
        old_code_lines: Tuple or list of [start_line, end_line] (1-indexed, inclusive)
        new_code: String containing the new code to replace the old lines

    Returns:
        True if replacement successful, False otherwise

    Raises:
        Exception: If syntax error is found after replacement

    Note:
        - If no backup file exists, creates a backup file with '_temp' suffix
        - If backup exists, always replaces based on backup content and saves to original file
        - This allows multiple replacement attempts based on the original content
    """
    # Validate inputs
    if not os.path.exists(file_path):
        print(f"Error: File not found: {file_path}")
        return

    if len(old_code_lines) != 2:
        print("Error: old_code_lines must be [start_line, end_line]")
        return

    start_line, end_line = old_code_lines

    if start_line < 1 or end_line < start_line:
        print(f"Error: Invalid line range [{start_line}, {end_line}]")
        return

    try:
        # Generate backup file path
        dir_name = os.path.dirname(file_path)
        base_name = os.path.basename(file_path)
        name_parts = os.path.splitext(base_name)
        backup_file = os.path.join(dir_name, name_parts[0] + '_temp' + name_parts[1])

        # Check if backup file exists
        if not os.path.exists(backup_file):
            # Create backup file
            with open(file_path, 'r', encoding='utf-8') as f:
                original_content = f.read()
            with open(backup_file, 'w', encoding='utf-8') as f:
                f.write(original_content)
            source_file = file_path
        else:
            # Use backup file as source
            source_file = backup_file

        # Read from source file (either original or backup)
        with open(source_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        # Validate line numbers
        if start_line > len(lines) or end_line > len(lines):
            print(f"Error: Line range [{start_line}, {end_line}] exceeds file length ({len(lines)} lines)")
            return False

        # Convert to 0-indexed
        start_idx = start_line - 1
        end_idx = end_line  # end_line is inclusive, so this is correct for slicing

        # Prepare new code lines
        if not new_code.endswith('\n'):
            new_code += '\n'
        new_code_lines = new_code.splitlines(keepends=True)

        # Replace the lines
        new_lines = lines[:start_idx] + new_code_lines + lines[end_idx:]
        new_content = ''.join(new_lines)

        # Validate syntax using AST
        try:
            ast.parse(new_content, filename=file_path)
        except SyntaxError as e:
            print(f"Syntax Error:")
            print(f"  Line: {e.lineno}")
            print(f"  Message: {e.msg}")
            return

        # If syntax is valid, write the new content
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
            print('Replaced.')
        return

    except Exception as e:
        print(f"Error during code replacement: {e}")
        return


def recover_original_file(file_path):
    """
    Restore the original file content from the backup file.

    Args:
        file_path: Path to the file to restore

    Returns:
        True if restoration successful, False otherwise

    Note:
        - The backup file (_temp suffix) is retained after restoration
        - Only restores if backup file exists
    """
    if not os.path.exists(file_path):
        print(f"Error: File not found: {file_path}")
        return

    # Generate backup file path
    dir_name = os.path.dirname(file_path)
    base_name = os.path.basename(file_path)
    name_parts = os.path.splitext(base_name)
    backup_file = os.path.join(dir_name, name_parts[0] + '_temp' + name_parts[1])

    # Check if backup file exists
    if not os.path.exists(backup_file):
        print(f"Error: Backup file not found: {backup_file}")
        print("No restoration needed - file may not have been modified yet.")
        return

    try:
        # Read backup file content
        with open(backup_file, 'r', encoding='utf-8') as f:
            backup_content = f.read()

        # Restore original file
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(backup_content)
            print('Recovered.')
        return

    except Exception as e:
        print(f"Error during file restoration: {e}")
        return


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

    print(json.dumps({
        'returncode': result.returncode,
        'output': result.stdout,
    }))


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


def exec_code_file(file_path):
    """
    Execute a Python code file.

    Args:
        file_path: Path to the Python file to execute

    Returns:
        Dictionary containing execution results on success

    Raises:
        FileNotFoundError: If the file does not exist
        subprocess.CalledProcessError: If the Python script exits with non-zero code
        Exception: For other execution errors

    Note:
        This function is designed to be called by a subprocess with error handling.
        Errors are raised directly instead of being caught internally.
    """
    # Check if file exists
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Python file not found: {file_path}")

    # Check if file is a Python file
    if not file_path.endswith('.py'):
        raise ValueError(f"File must be a Python file (.py): {file_path}")

    # Execute the Python file
    result = subprocess.run(
        ['python', file_path],
        capture_output=True,
        text=True,
        check=True  # This will raise CalledProcessError if return code != 0
    )

    # Return execution results
    print(json.dumps({
        'returncode': result.returncode,
        'output': result.stdout,
    }))


def submit_patch():
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

    print(json.dumps({
        'returncode': result.returncode,
        'output': result.stdout,
    }))


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
