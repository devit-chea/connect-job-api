import os
import shutil
import subprocess


def get_base_directory():
    """
    Get the root directory of the git repository dynamically.
    """
    try:
        # Run git command to get the root of the repository
        base_dir = (
            subprocess.check_output(["git", "rev-parse", "--show-toplevel"])
            .strip()
            .decode()
        )
        return base_dir
    except subprocess.CalledProcessError:
        print(
            "Failed to determine the base directory. Ensure you are in a git repository."
        )
        return None


def copy_items(base_dir, target_dir):
    """
    Automatically copy relevant files and directories to the target directory.
    """
    # Directories to copy
    directories_to_copy = ["apps", "configs", "requirements", "storages"]

    for directory in directories_to_copy:
        # Ensure the directory name does not start with a leading slash
        directory = directory.lstrip(os.sep)
        source_path = os.path.join(base_dir, directory)
        target_path = os.path.join(target_dir, directory)

        if os.path.exists(source_path):
            try:
                # Copy the directory tree to the target location
                shutil.copytree(source_path, target_path, dirs_exist_ok=True)
                print(f"Copied directory: {source_path} to {target_path}")
            except Exception as e:
                print(f"An error occurred while copying {source_path}: {e}")
        else:
            print(f"Source directory does not exist: {source_path}")


def main():
    """
    Set up a new project using the WDG Micro Skeleton.
    """
    print("WDG Micro Skeleton Template Initialized!")

    # Get the base directory dynamically using Git
    base_dir = get_base_directory()
    if base_dir is None:
        print("Error: Could not determine the base directory.")
        return

    # Verify the base directory
    print(f"Base directory: {base_dir}")

    # Target directory (current working directory)
    target_dir = os.getcwd()

    # Automatically copy all relevant files and directories
    copy_items(base_dir, target_dir)

    print(f"Project setup complete in {target_dir}!")
    print("Next steps:")
    print("1. Rename the `configs` folder to match your project name (if needed).")
    print("2. Install your own dependencies: `pip install -r requirements.txt`")
    print("3. Update `.env` with your environment variables.")
    print("4. Run `python manage.py migrate` to initialize the database.")
    print("You're ready to start!")


if __name__ == "__main__":
    main()
