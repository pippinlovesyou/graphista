#!/usr/bin/env python
import os
import sys
import subprocess
import logging

# Configure logging to output DEBUG-level messages to stdout.
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stdout,
)

def get_test_files():
    """
    Scans the 'tests' directory and returns a sorted list of test file names
    that start with 'test_' and end with '.py'.
    """
    test_files = []
    tests_dir = "tests"
    if not os.path.isdir(tests_dir):
        logging.error("Tests directory 'tests' not found!")
        return test_files
    for file in os.listdir(tests_dir):
        if file.startswith("test_") and file.endswith(".py"):
            test_files.append(file)
    logging.debug(f"Found test files: {test_files}")
    return sorted(test_files)

def display_menu():
    """
    Displays an interactive menu for running individual tests, all tests, or exiting.
    """
    test_files = get_test_files()
    print("\nTest Runner Menu:")
    for i, test in enumerate(test_files, 1):
        print(f"{i}. Run {test}")
    print(f"{len(test_files) + 1}. Run all tests")
    print(f"{len(test_files) + 2}. Exit")

    choice = input("\nSelect an option: ")
    try:
        choice = int(choice)
        if 1 <= choice <= len(test_files):
            test_file = test_files[choice - 1]
            logging.debug(f"User selected to run test file: tests/{test_file}")
            # The '-s' flag disables output capturing so prints appear in real time.
            subprocess.run([sys.executable, '-m', 'pytest', f'tests/{test_file}', '-v', '-s'])
        elif choice == len(test_files) + 1:
            logging.debug("User selected to run all tests in the 'tests' directory.")
            subprocess.run([sys.executable, '-m', 'pytest', 'tests', '-v', '-s'])
        elif choice == len(test_files) + 2:
            print("Exiting...")
            sys.exit(0)
        else:
            print("Invalid choice")
    except ValueError:
        print("Please enter a valid number")

if __name__ == "__main__":
    while True:
        display_menu()
