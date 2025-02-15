import os
import datetime
from typing import List, Set

def find_files(directory: str, excluded_extensions: Set[str] = {'.pyc', '.pyo', '__pycache__'}, exclude_init: bool = True) -> List[str]:
    """Recursively find all files in a directory.

    Args:
        directory: Directory to search.
        excluded_extensions: Set of filename endings to ignore.
        exclude_init: If True, ignore files named exactly '__init__.py'.

    Returns:
        A sorted list of file paths.
    """
    files = []
    for root, _, filenames in os.walk(directory):
        for filename in filenames:
            if exclude_init and filename == "__init__.py":
                continue
            if not any(filename.endswith(ext) for ext in excluded_extensions):
                files.append(os.path.join(root, filename))
    return sorted(files)

def combine_code(root_files: List[str], base_dirs: List[str], include_tests: bool = False, include_docs: bool = False) -> str:
    """Combine code from specified root files and directories.

    Args:
        root_files: A list of filenames in the root to include.
        base_dirs: A list of directory names (e.g. ['graphrouter', 'ingestion_engine', 'llm_engine']).
        include_tests: If True, include files from the 'tests' directory.
        include_docs: If True, include files from the 'docs' directory.

    Returns:
        A single string with the concatenated file contents.
    """
    all_files = []

    # Add specified root files (if they exist)
    for file_name in root_files:
        if os.path.exists(file_name) and os.path.isfile(file_name):
            all_files.append(file_name)

    # Add files from the base directories
    for dir_path in base_dirs:
        if os.path.exists(dir_path):
            all_files.extend(find_files(dir_path))

    # Optionally add tests
    if include_tests and os.path.exists('tests'):
        all_files.extend(find_files('tests'))

    # Optionally add docs
    if include_docs and os.path.exists('docs'):
        all_files.extend(find_files('docs'))

    # Combine content from all files
    combined = []
    separator = "=" * 80

    for file_path in all_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                combined.append(f"\n{separator}")
                combined.append(f"FILE: {file_path}")
                combined.append(separator)
                combined.append(content)
                combined.append(f"{separator}\n")
        except Exception as e:
            combined.append(f"\nError reading {file_path}: {str(e)}\n")

    return "\n".join(combined)

def main():
    # Create output directory if it doesn't exist
    output_dir = "full_code"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Generate timestamp for the output filename
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = os.path.join(output_dir, f"combined_code_{timestamp}.txt")

    # Specify root files to include (only memory.py and README.md in root)
    root_files = ["memory.py", "README.md"]

    # Specify the base directories to combine
    base_dirs = ['graphrouter', 'ingestion_engine', 'llm_engine']

    # Set flags to include tests and docs if desired
    include_tests = True   # Change to False to exclude the tests folder.
    include_docs = True    # Change to False to exclude the docs folder.

    combined_code = combine_code(root_files, base_dirs, include_tests, include_docs)

    # Write the combined code into a text file in the full_code directory
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(combined_code)

    print(f"Combined code written to: {output_file}")

if __name__ == "__main__":
    main()
