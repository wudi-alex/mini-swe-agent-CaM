import ast
import os
import subprocess
import json
import re
import tempfile
import sys


# ===== Compatibility Helper Functions =====
def get_node_end_lineno(node, source_lines):
    """
    Get the end line number of an AST node (compatible with Python 3.6/3.7)

    Args:
        node: AST node
        source_lines: List of source code lines

    Returns:
        End line number (1-based)
    """
    # Python 3.8+ has end_lineno attribute
    if hasattr(node, 'end_lineno') and node.end_lineno is not None:
        return node.end_lineno

    # Python 3.6/3.7 needs manual calculation
    # Search from start line downward until finding correct end position
    start_line = node.lineno - 1  # Convert to 0-based index

    # For simple nodes, might be only one line
    if not hasattr(node, 'body') or not node.body:
        # Try to find where indentation decreases
        if start_line >= len(source_lines):
            return len(source_lines)

        # Get indentation level of node start
        start_indent = len(source_lines[start_line]) - len(source_lines[start_line].lstrip())

        # Search downward until indentation decreases or file ends
        current_line = start_line + 1
        while current_line < len(source_lines):
            line = source_lines[current_line]
            if line.strip():  # Non-empty line
                current_indent = len(line) - len(line.lstrip())
                if current_indent <= start_indent:
                    return current_line + 1  # Convert to 1-based line number
            current_line += 1

        return len(source_lines)

    # For nodes with body (class, function, etc.), find last child node's end position
    last_lineno = node.lineno
    for child in ast.walk(node):
        if hasattr(child, 'lineno') and child.lineno:
            last_lineno = max(last_lineno, child.lineno)

    # Search from last known line number downward for actual end position
    start_indent = len(source_lines[start_line]) - len(source_lines[start_line].lstrip())
    current_line = last_lineno - 1  # Convert to 0-based index

    while current_line < len(source_lines):
        line = source_lines[current_line]
        if line.strip():  # Non-empty line
            current_indent = len(line) - len(line.lstrip())
            if current_indent <= start_indent and current_line > start_line:
                return current_line + 1  # Convert to 1-based line number
        current_line += 1

    return len(source_lines)


def print_definition_file(names, search_path="."):
    for name in names:
        files = set()

        cmd = ['grep', '-rl', '-E', f"^class\\s+{name}\\s*[:(]",
               search_path, '--include=*.py']
        try:
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                errors='replace',
            )
            if result.returncode == 0 and result.stdout.strip():
                files.update(result.stdout.strip().split('\n'))
        except:
            pass

        cmd = ['grep', '-rl', '-E', f"^def\\s+{name}\\s*\\(",
               search_path, '--include=*.py']
        try:
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                errors='replace',
            )
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
    for name, file_path in name_file_list:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
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
            print(f"{file_path} {name}: error reading file - {e}\n")


def _find_definitions(tree, name):
    definitions = []

    for node in ast.walk(tree):
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name == name:
                definitions.append(node)

    return definitions


def _get_docstring_lines(node, source_lines):
    """
    Get all docstring line numbers in the node

    Args:
        node: AST node
        source_lines: List of source code lines

    Returns:
        Set of docstring line numbers (0-based)
    """
    docstring_lines = set()

    if not isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
        return docstring_lines

    if not node.body:
        return docstring_lines

    first_stmt = node.body[0]
    if isinstance(first_stmt, ast.Expr):
        value = first_stmt.value
        is_docstring = False
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            is_docstring = True
        elif hasattr(ast, 'Str') and isinstance(value, ast.Str):
            is_docstring = True

        if is_docstring:
            end_line = get_node_end_lineno(first_stmt, source_lines)
            for line_num in range(first_stmt.lineno - 1, end_line):
                docstring_lines.add(line_num)

    for item in node.body:
        if isinstance(item, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            docstring_lines.update(_get_docstring_lines(item, source_lines))

    return docstring_lines


def _print_code_with_lines(lines, node, show_comments):
    start_line = node.lineno - 1
    end_line = get_node_end_lineno(node, lines)

    docstring_lines = set()
    if not show_comments:
        docstring_lines = _get_docstring_lines(node, lines)

    for i in range(start_line, end_line):
        if i >= len(lines):
            break

        line = lines[i]

        if not show_comments:
            stripped = line.strip()
            if stripped.startswith('#'):
                continue
            if i in docstring_lines:
                continue

        print(f"{i + 1}: {line}")


def remove_comments_with_mapping(code):
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
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            timeout=10,
            errors='replace',
        )

        if result.returncode != 0:
            print("Error: Syntax error in replaced code")
            print(result.stderr)
            return False

        try:
            flake_result = subprocess.run(
                ['pyflakes', tmp_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                timeout=10,
                errors='replace',
            )
            if flake_result.stdout:
                print("Warning: Lint check found issues")
                print(flake_result.stdout)
        except FileNotFoundError:
            pass

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)

        print("Replaced.")
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
    if not os.path.exists(file_path):
        print("Error: File '{}' does not exist".format(file_path))
        return False

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except Exception as e:
        print("Error: Cannot read file - {}".format(e))
        return False

    if line_number < 1:
        print("Error: Line number must be >= 1")
        return False

    if line_number > len(lines) + 1:
        print("Error: Line number {} exceeds file length (max: {})".format(
            line_number, len(lines) + 1))
        return False

    if not new_code.endswith('\n'):
        new_code = new_code + '\n'

    insert_index = line_number - 1
    lines.insert(insert_index, new_code)

    new_content = ''.join(lines)

    tmp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8')
    tmp_file.write(new_content)
    tmp_file.close()
    tmp_path = tmp_file.name

    try:
        result = subprocess.run(
            ['python', '-m', 'py_compile', tmp_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            timeout=10,
            errors='replace',
        )

        if result.returncode != 0:
            print("Error: Syntax error after code insertion")
            print(result.stderr)
            return False

        try:
            flake_result = subprocess.run(
                ['pyflakes', tmp_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                errors='replace',
                timeout=10
            )
            if flake_result.stdout:
                print("Warning: Lint check found issues")
                print(flake_result.stdout)
        except FileNotFoundError:
            pass

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)

        print("Inserted.")
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


def print_code_context(file_path, lines, show_comments=False):
    """
    Display code lines from a file with line numbers.

    Args:
        file_path: Path to the file to display
        lines: List or tuple of [start_line, end_line] (1-indexed, inclusive)
        show_comments: Whether to show comments and docstrings (default: False)

    Returns:
        None
    """
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
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            file_lines = content.splitlines()

        total_lines = len(file_lines)
        if start_line > total_lines:
            print(f"Error: Start line {start_line} exceeds file length ({total_lines} lines)")
            return

        if end_line > total_lines:
            print(f"Warning: End line {end_line} exceeds file length ({total_lines} lines)")
            end_line = total_lines

        docstring_lines = set()
        if not show_comments and file_path.endswith('.py'):
            try:
                tree = ast.parse(content)
                docstring_lines = _get_all_docstring_lines(tree, file_lines)
            except:
                pass

        for i in range(start_line - 1, end_line):
            line_num = i + 1
            line = file_lines[i]

            if not show_comments:
                stripped = line.strip()
                if stripped.startswith('#'):
                    continue
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


def _get_all_docstring_lines(tree, source_lines):
    """
    Get all docstring line numbers in the AST tree (compatible with Python 3.6+)

    Args:
        tree: AST tree
        source_lines: List of source code lines

    Returns:
        Set of docstring line numbers (0-based)
    """
    docstring_lines = set()

    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            if not node.body:
                continue

            first_stmt = node.body[0]
            if isinstance(first_stmt, ast.Expr):
                value = first_stmt.value
                is_docstring = False
                if isinstance(value, ast.Constant) and isinstance(value.value, str):
                    is_docstring = True
                elif hasattr(ast, 'Str') and isinstance(value, ast.Str):
                    is_docstring = True

                if is_docstring:
                    end_line = get_node_end_lineno(first_stmt, source_lines)
                    for line_num in range(first_stmt.lineno - 1, end_line):
                        docstring_lines.add(line_num)

    return docstring_lines


def exec_bash_cmd(cmd, timeout=None):
    """
    Execute a bash command and display the output safely.
    """
    try:
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
            print('bash execution output :\n', safe_output)

        return output

    except Exception as e:
        print(f"Execution failed: {e}")


def save_code_to_file(file_path, code_str):
    """
    Save code string to a specified file path.

    Args:
        code_str: String containing the code to save
        file_path: Path where the file should be saved

    Returns:
        True if successful, False otherwise
    """
    try:
        dir_name = os.path.dirname(file_path)
        if dir_name and not os.path.exists(dir_name):
            os.makedirs(dir_name)

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
